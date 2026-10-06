"""
A Number Detective case as a headless state machine. No UIKit.

The player asks questions from the current hand of cards and names tiles.
A correct name reveals the tile for free; a wrong one costs
WRONG_GUESS_COST and rules that value out for that tile. The case is
solved when every tile is revealed, and par is worked out then.

Score is questions asked plus wrong-guess costs; lower is better.
"""

import random

from games.number_detective import rules


class DetectiveGame:
    """One case at a time, from a chosen pool."""

    def __init__(self, pool_name="classic", rng=None):
        self.pool = rules.find_pool(pool_name)
        self.rng = rng or random.Random()
        self.new_case()

    def new_case(self):
        values = self.pool.values
        self.hidden = tuple(self.rng.choice(values) for _ in range(rules.TILE_COUNT))
        self.dealer = rules.HandDealer(
            self.rng.random(), rules.available_type_names(self.pool.name))
        self.candidates = rules.all_candidates(values)
        self.clues = []
        self.revealed = [None] * rules.TILE_COUNT
        self.wrong_guesses = 0
        self.par = None

    # --- reading -------------------------------------------------------------

    @property
    def questions_asked(self):
        return len(self.clues)

    @property
    def hand(self):
        """The card names dealt for the next question."""
        return self.dealer.hand(self.questions_asked)

    @property
    def solved(self):
        return all(value is not None for value in self.revealed)

    @property
    def score(self):
        return self.questions_asked + self.wrong_guesses * rules.WRONG_GUESS_COST

    def possible_values(self, tile):
        """Values tile could still hold, given every clue and guess so far."""
        return sorted({candidate[tile] for candidate in self.candidates})

    # --- asking --------------------------------------------------------------

    def ask(self, card_index, tiles=()):
        """Ask card card_index from the hand about tiles. Returns the Clue or None."""
        if self.solved or not 0 <= card_index < len(self.hand):
            return None
        question = rules.QUESTION_BY_NAME[self.hand[card_index]]
        tiles = tuple(tiles)

        if question.arity == 0:
            tiles = ()
        elif (
            len(tiles) != question.arity
            or len(set(tiles)) != question.arity
            or any(not 0 <= tile < rules.TILE_COUNT for tile in tiles)
        ):
            return None

        answer = rules.ask_values(question, self.hidden, tiles)
        self.candidates = rules.filter_candidates(self.candidates, question, tiles, answer)
        clue = rules.Clue(
            question.name, rules.tiles_for(question, tiles), answer,
            rules.clue_text(question, tiles, answer),
        )
        self.clues.append(clue)
        return clue

    # --- naming tiles --------------------------------------------------------

    def guess(self, tile, value):
        """Name tile's value. True if right, False if wrong, None if not allowed."""
        if self.solved or not 0 <= tile < rules.TILE_COUNT:
            return None
        if self.revealed[tile] is not None or value not in self.pool.values:
            return None

        if self.hidden[tile] == value:
            self.revealed[tile] = value
            self.candidates = [c for c in self.candidates if c[tile] == value]
            if self.solved:
                self.par = rules.par_questions(self.hidden, self.pool.values, self.dealer)
            return True

        self.wrong_guesses += 1
        self.candidates = [c for c in self.candidates if c[tile] != value]
        return False