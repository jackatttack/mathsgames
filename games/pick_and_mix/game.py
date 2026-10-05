"""
A Pick & Mix match as a headless state machine. No UIKit.

Phases of a round:

    draft    players pick pool tiles in turn; either may merge in their
             own hand at any time
    solving  every pick is made; players keep merging, then lock in
    scored   both have locked in and the round is scored

When a hand is locked in, its tile closest to the target counts. The loser
of a round picks first in the next; after a tie, first pick alternates. The
match ends when a player reaches match_points.

The screen calls these methods from taps and redraws from the state; it
never changes the state itself.
"""

import random
from dataclasses import dataclass

from games.pick_and_mix import rules
from games.pick_and_mix.hand import Hand


DRAFT = "draft"
SOLVING = "solving"
SCORED = "scored"

DEFAULT_MATCH_POINTS = 30
PLAYERS = (0, 1)


@dataclass(frozen=True)
class RoundResult:
    """A scored round, kept for the results panel and match history."""

    round_number: int
    target: int
    values: tuple          # the counted value per player
    score: rules.RoundScore
    best: tuple            # per player: (value, distance, steps) from their picks


class PickAndMixGame:
    """One match between two players on one device."""

    def __init__(self, pool_name="standard", match_points=DEFAULT_MATCH_POINTS, rng=None):
        self.pool_name = pool_name
        self.match_points = match_points
        self.rng = rng or random.Random()
        self.new_match()

    # --- match ---------------------------------------------------------------

    def new_match(self):
        self.scores = [0, 0]
        self.round_number = 0
        self.first_picker = 0
        self.results = []
        self.start_round()

    @property
    def match_winner(self):
        """The player who has reached match_points, or None."""
        for player in PLAYERS:
            if self.scores[player] >= self.match_points:
                return player
        return None

    # --- round ---------------------------------------------------------------

    def start_round(self):
        self.deal = rules.deal(self.pool_name, self.rng)
        self.target = self.deal.target
        self.pool = list(self.deal.numbers)
        self.taken_by = [None] * len(self.pool)
        self.hands = [Hand(), Hand()]
        self.turn = self.first_picker
        self.phase = DRAFT
        self.locked = [False, False]
        self.result = None
        self.round_number += 1

    def next_round(self):
        """Deal the next round once this one is scored and the match goes on."""
        if self.phase != SCORED or self.match_winner is not None:
            return False
        self.start_round()
        return True

    # --- drafting ------------------------------------------------------------

    def picks_made(self, player):
        return len(self.hands[player].picked)

    def can_pick(self, index):
        return (
            self.phase == DRAFT
            and 0 <= index < len(self.pool)
            and self.taken_by[index] is None
        )

    def pick(self, index):
        """The current player takes pool tile index. Returns True if taken."""
        if not self.can_pick(index):
            return False
        player = self.turn
        self.hands[player].add_tile(self.pool[index])
        self.taken_by[index] = player

        if all(self.picks_made(other) >= rules.PICKS_PER_PLAYER for other in PLAYERS):
            self.phase = SOLVING
        else:
            self.turn = 1 - player
        return True

    # --- merging -------------------------------------------------------------

    def can_play(self, player):
        """True while this player may still merge and undo."""
        return self.phase in (DRAFT, SOLVING) and not self.locked[player]

    def merge(self, player, source, destination, operation):
        if not self.can_play(player):
            return None
        return self.hands[player].merge(source, destination, operation)

    def undo(self, player):
        if not self.can_play(player):
            return False
        return self.hands[player].undo()

    # --- locking in and scoring ----------------------------------------------

    def can_lock_in(self, player):
        return self.phase == SOLVING and not self.locked[player]

    def lock_in(self, player):
        """Lock this player's hand. Scores the round when both are locked."""
        if not self.can_lock_in(player):
            return False
        self.locked[player] = True
        if all(self.locked):
            self._score_round()
        return True

    def _score_round(self):
        values = tuple(hand.closest_to(self.target) for hand in self.hands)
        score = rules.score_round(self.target, values)
        for player in PLAYERS:
            self.scores[player] += score.points[player]

        best = tuple(rules.closest(hand.picked, self.target) for hand in self.hands)
        self.result = RoundResult(self.round_number, self.target, values, score, best)
        self.results.append(self.result)

        if score.winner is None:
            self.first_picker = 1 - self.first_picker
        else:
            self.first_picker = 1 - score.winner
        self.phase = SCORED