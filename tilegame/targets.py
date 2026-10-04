"""Make-a-target play shared by tile games: one round, scoring, a session.

No UIKit lives here.

A round has a target and a starting board. Every committed move is
recorded; the closest value so far is kept, and making the target exactly
solves the round. A session scores each finished round once:
SOLVE_POINTS for a solve, otherwise Countdown-style near-miss points from
the closest value, and keeps a streak of consecutive solves.
"""

from fractions import Fraction

from .board_state import BoardState, any_exact_value, orthogonal_neighbours


# --- editable scoring -------------------------------------------------------

SOLVE_POINTS = 10
NEAR_MISS_POINTS = ((5, 7), (10, 5))   # (within this distance, points)


class TargetRound:
    """One dealt board, its target, and the closest value made so far.

    The board's rules travel with the round, so starting_board() always
    builds a board that plays by them.
    """

    def __init__(self, starting_rows, target, merge_rule=orthogonal_neighbours,
                 result_rule=any_exact_value):
        self.starting_rows = [list(row) for row in starting_rows]
        self.target = target
        self.merge_rule = merge_rule
        self.result_rule = result_rule

        self.best = None
        self.solved = False
        self.scored = False

    def starting_board(self):
        return BoardState(self.starting_rows, self.merge_rule, self.result_rule)

    def distance(self, value):
        return abs(Fraction(value) - self.target)

    def best_distance(self):
        if self.best is None:
            return None
        return self.distance(self.best)

    def record(self, value):
        """Track the closest value made. Returns True when this solves it."""
        if self.solved:
            return False

        value = Fraction(value)

        if self.best is None or self.distance(value) < self.best_distance():
            self.best = value

        if value == self.target:
            self.solved = True
            return True

        return False


def points_for_distance(distance):
    """Points for finishing a round this far from its target."""
    if distance is None:
        return 0

    if distance == 0:
        return SOLVE_POINTS

    for within, points in NEAR_MISS_POINTS:
        if distance <= within:
            return points

    return 0


class TargetSession:
    """Running score and streak across rounds, while the game is open."""

    def __init__(self):
        self.score = 0
        self.streak = 0
        self.best_streak = 0
        self.boards = 0

    def finish(self, round_):
        """Score a finished round once. Returns the points awarded."""
        if round_.scored:
            return 0

        round_.scored = True
        points = points_for_distance(round_.best_distance())

        self.score += points
        self.boards += 1

        if round_.solved:
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
        else:
            self.streak = 0

        return points