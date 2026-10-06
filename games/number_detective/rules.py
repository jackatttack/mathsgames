"""
Number Detective rules: pools, question cards, the candidate engine and par.
No UIKit.

Four hidden tiles, A to D, each hold a value from a pool (repeats allowed).
Each turn the player is dealt HAND_SIZE question cards, chooses one and the
tiles it asks about, and sees only the answer. Every answer rules out
hidden combinations; the game keeps every combination still possible.

Questions lose information on purpose: a product does not say which factor
pair, a gap does not say which tile is bigger. A card whose answer could
never vary for a pool (no prime is a square) is never dealt for it.

Par comes from a detective that gets the same hidden tiles and the same
card hands, and always asks the question that leaves the fewest
possibilities on average. A sharp player can beat it.
"""

import functools
import itertools
import random
from collections import Counter
from dataclasses import dataclass


# --- editable rules ----------------------------------------------------------

TILE_COUNT = 4
TILE_NAMES = ("A", "B", "C", "D")
HAND_SIZE = 2              # question cards dealt each turn; 2 keeps par varied
WRONG_GUESS_COST = 1       # added to the score for naming a tile wrongly
MAX_PAR_QUESTIONS = 30     # the par detective gives up after this many


# --- pools -------------------------------------------------------------------

@dataclass(frozen=True)
class Pool:
    name: str
    label: str
    description: str
    values: tuple


POOLS = (
    Pool("small", "Small", "Numbers 1 to 6", tuple(range(1, 7))),
    Pool("classic", "Classic", "Numbers 1 to 12", tuple(range(1, 13))),
    Pool("primes", "Primes", "Primes from 2 to 23", (2, 3, 5, 7, 11, 13, 17, 19, 23)),
)

POOL_NAMES = tuple(pool.name for pool in POOLS)


def find_pool(name):
    for pool in POOLS:
        if pool.name == name:
            return pool
    raise ValueError("Unknown pool %r; choose one of %s" % (name, POOL_NAMES))


# --- question cards ----------------------------------------------------------

def _is_square(number):
    root = int(number ** 0.5 + 0.5)
    return root * root == number


def _compare(values):
    return (values[0] > values[1]) - (values[0] < values[1])


def _compare_phrase(names, answer):
    wording = {1: "%s is bigger than %s", -1: "%s is smaller than %s", 0: "%s equals %s"}
    return wording[answer] % (names[0], names[1])


@dataclass(frozen=True)
class QuestionType:
    """One kind of question card."""

    name: str        # stable id
    title: str       # printed on the card
    arity: int       # tiles the player chooses; 0 means it asks about all four
    weight: int      # how often it is dealt, relative to the others
    answer: object   # function(values tuple) -> hashable answer
    phrase: object   # function(tile names, answer) -> clue text


QUESTION_TYPES = (
    QuestionType("multiply", "Multiply two", 2, 2,
                 lambda values: values[0] * values[1],
                 lambda names, answer: "%s × %s = %d" % (names[0], names[1], answer)),
    QuestionType("add", "Add two", 2, 1,
                 lambda values: values[0] + values[1],
                 lambda names, answer: "%s + %s = %d" % (names[0], names[1], answer)),
    QuestionType("difference", "Gap between two", 2, 3,
                 lambda values: abs(values[0] - values[1]),
                 lambda names, answer: "%s and %s are %d apart" % (names[0], names[1], answer)),
    QuestionType("add_three", "Add three", 3, 1,
                 lambda values: sum(values),
                 lambda names, answer: "%s + %s + %s = %d" % (names[0], names[1], names[2], answer)),
    QuestionType("even", "Odd or even", 1, 3,
                 lambda values: values[0] % 2 == 0,
                 lambda names, answer: "%s is %s" % (names[0], "even" if answer else "odd")),
    QuestionType("square", "Square or not", 1, 3,
                 lambda values: _is_square(values[0]),
                 lambda names, answer: "%s is %sa square" % (names[0], "" if answer else "not ")),
    QuestionType("compare", "Which is bigger", 2, 3,
                 _compare, _compare_phrase),
    QuestionType("largest", "Largest of all", 0, 2,
                 lambda values: max(values),
                 lambda names, answer: "The largest is %d" % answer),
)

QUESTION_BY_NAME = {question.name: question for question in QUESTION_TYPES}


def tiles_for(question, tiles):
    """The tiles a question reads: all four for arity 0, else those chosen."""
    if question.arity == 0:
        return tuple(range(TILE_COUNT))
    return tuple(tiles)


def ask_values(question, values, tiles):
    """The answer question gives about these tiles of a full set of values."""
    return question.answer(tuple(values[tile] for tile in tiles_for(question, tiles)))


def clue_text(question, tiles, answer):
    names = [TILE_NAMES[tile] for tile in tiles_for(question, tiles)]
    return question.phrase(names, answer)


def selections(question):
    """Every distinct choice of tiles for a question."""
    if question.arity == 0:
        return [()]
    return list(itertools.combinations(range(TILE_COUNT), question.arity))


@functools.lru_cache(maxsize=None)
def available_type_names(pool_name):
    """Card names whose answers can vary for this pool, in QUESTION_TYPES order."""
    values = find_pool(pool_name).values
    names = []
    for question in QUESTION_TYPES:
        count = question.arity or TILE_COUNT
        answers = {question.answer(combo) for combo in itertools.product(values, repeat=count)}
        if len(answers) > 1:
            names.append(question.name)
    return tuple(names)


def deal_hand(rng, names):
    """HAND_SIZE different card names, chosen by weight."""
    remaining = list(names)
    hand = []
    while remaining and len(hand) < HAND_SIZE:
        weights = [QUESTION_BY_NAME[name].weight for name in remaining]
        chosen = rng.choices(remaining, weights=weights)[0]
        hand.append(chosen)
        remaining.remove(chosen)
    return tuple(hand)


class HandDealer:
    """The case's sequence of card hands, the same for the player and for par.

    Hands come from their own seeded generator, so hand n is the same
    whoever asks for it and whenever.
    """

    def __init__(self, seed, names):
        self._rng = random.Random(seed)
        self._names = tuple(names)
        self._hands = []

    def hand(self, turn):
        while len(self._hands) <= turn:
            self._hands.append(deal_hand(self._rng, self._names))
        return self._hands[turn]


# --- the candidate engine ----------------------------------------------------

@dataclass(frozen=True)
class Clue:
    """One question asked and what it revealed."""

    question: str     # QuestionType name
    tiles: tuple      # the tiles it read
    answer: object
    text: str


def all_candidates(values):
    """Every possible hidden set: one value per tile, repeats allowed."""
    return list(itertools.product(values, repeat=TILE_COUNT))


def filter_candidates(candidates, question, tiles, answer):
    return [
        candidate for candidate in candidates
        if ask_values(question, candidate, tiles) == answer
    ]


def best_question(candidates, hand):
    """(name, tiles) from the hand that leaves the fewest possibilities on average.

    Measured as the sum of squared answer-group sizes, which is proportional
    to the expected number of possibilities left. Ties keep the earlier option.
    """
    best = None
    for name in hand:
        question = QUESTION_BY_NAME[name]
        for tiles in selections(question):
            groups = Counter(ask_values(question, candidate, tiles) for candidate in candidates)
            spread = sum(size * size for size in groups.values())
            if best is None or spread < best[0]:
                best = (spread, name, tiles)
    return best[1], best[2]


def par_questions(hidden, values, dealer):
    """How many questions the par detective needs to pin down every tile."""
    candidates = all_candidates(values)
    asked = 0
    while len(candidates) > 1 and asked < MAX_PAR_QUESTIONS:
        name, tiles = best_question(candidates, dealer.hand(asked))
        question = QUESTION_BY_NAME[name]
        answer = ask_values(question, hidden, tiles)
        candidates = filter_candidates(candidates, question, tiles, answer)
        asked += 1
    return asked