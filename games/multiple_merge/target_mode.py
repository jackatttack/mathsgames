"""Target mode: make one target number from the board, board after board.

No UIKit lives here.

Rules:
    Each board has one target that some sequence of moves makes exactly.
    Making it solves the board: SOLVE_POINTS and the streak grows.
    Skipping scores the closest value made so far, Countdown style (see
    NEAR_MISS_POINTS), and resets the streak.

Board styles:
    mixed            four numbers from STARTING_NUMBER_RANGE
    same             four of one number
    three_plus_one   three of one number and one different number

Difficulty comes from the solver. For every value a board can produce,
analyse_routes counts how many move sequences end by making it, and the
fewest moves any of them needs. DIFFICULTY_RULES turns those two numbers
into easy, medium and hard. Same-number boards rank their own targets by
rarity instead (see RELATIVE_DIFFICULTY_STYLES).
"""

import random
import time
from fractions import Fraction

from tilegame.board_state import BoardState, OPERATIONS
from tilegame.targets import (
    NEAR_MISS_POINTS,
    SOLVE_POINTS,
    TargetRound as SharedTargetRound,
    TargetSession,
    points_for_distance,
)
from .classic import BOARD_COLS, BOARD_ROWS, merge_pairs


# --- editable settings ------------------------------------------------------

DIFFICULTIES = ("easy", "medium", "hard")
BOARD_STYLES = ("mixed", "same", "three_plus_one")

DEFAULT_DIFFICULTY = "medium"
DEFAULT_BOARD_STYLE = "mixed"

# For a target: (fewest, most) routes that make it, and (fewest, most) moves
# its shortest route needs. None means no upper limit. A 2x2 board needs
# 3 moves to use every tile.
DIFFICULTY_RULES = {
    "easy":   {"routes": (4, None), "shortest": (1, 2)},
    "medium": {"routes": (2, 6),    "shortest": (2, 3)},
    "hard":   {"routes": (1, 2),    "shortest": (3, 3)},
}

# Four identical tiles reach every value by many mirror-image routes, so
# absolute route counts never look rare. These styles rank the board's own
# targets instead: hard from the rarest third, easy from the commonest.
RELATIVE_DIFFICULTY_STYLES = ("same",)
TARGET_RANGE = (10, 200)          # targets are whole numbers in this range
STARTING_NUMBER_RANGE = (1, 12)   # mixed boards, and the odd one out in 3 + 1
SAME_NUMBER_RANGE = (2, 9)        # the repeated number on same and 3 + 1

# Dealing stops at whichever limit comes first, then falls back to the best
# board seen so the app never hangs.
MAX_DEAL_ATTEMPTS = 300
MAX_DEAL_SECONDS = 1.0

# SOLVE_POINTS and NEAR_MISS_POINTS live in tilegame/targets.py.


# --- route analysis ---------------------------------------------------------

def analyse_routes(board):
    """Return {value: [route_count, shortest]} for every producible value.

    route_count is how many move sequences end with a move that makes the
    value; shortest is the fewest moves any of them uses. Exhaustive
    depth-first search; the board passed in is never changed.
    """
    stats = {}
    position = board.copy_with(board.snapshot())

    def explore(depth):
        for source, destination in merge_pairs(position):
            for operation in OPERATIONS:
                result = position.apply_move(source, operation, destination)

                if result is None:
                    continue

                entry = stats.get(result.value)
                if entry is None:
                    stats[result.value] = [1, depth]
                else:
                    entry[0] += 1
                    entry[1] = min(entry[1], depth)

                explore(depth + 1)
                position.undo()

    explore(1)
    return stats


def _within(number, bounds):
    low, high = bounds
    return number >= low and (high is None or number <= high)


def targets_matching(stats, on_board, rule=None):
    """Whole-number targets in TARGET_RANGE, not on the board, meeting rule."""
    low, high = TARGET_RANGE
    matches = []

    for value, (routes, shortest) in stats.items():
        if value.denominator != 1:
            continue

        whole = value.numerator

        if not low <= whole <= high or whole in on_board:
            continue

        if rule is not None and not (
            _within(routes, rule["routes"])
            and _within(shortest, rule["shortest"])
        ):
            continue

        matches.append(whole)

    return sorted(matches)


# --- dealing ----------------------------------------------------------------

def deal_numbers(style, rng):
    """Return starting rows for a board style."""
    low, high = STARTING_NUMBER_RANGE

    if style == "same":
        repeated = rng.randint(*SAME_NUMBER_RANGE)
        values = [repeated] * (BOARD_ROWS * BOARD_COLS)
    elif style == "three_plus_one":
        repeated = rng.randint(*SAME_NUMBER_RANGE)
        others = [n for n in range(low, high + 1) if n != repeated]
        values = [repeated, repeated, repeated, rng.choice(others)]
        rng.shuffle(values)
    elif style == "mixed":
        values = [rng.randint(low, high) for _ in range(BOARD_ROWS * BOARD_COLS)]
    else:
        raise ValueError("Unknown board style: {}".format(style))

    return [
        values[row * BOARD_COLS:(row + 1) * BOARD_COLS]
        for row in range(BOARD_ROWS)
    ]


class TargetRound(SharedTargetRound):
    """A Target-mode board: the shared round plus how it was dealt."""

    def __init__(self, starting_rows, target, routes, shortest, difficulty,
                 style, matched=True, attempts=1):
        super().__init__(starting_rows, target)
        self.routes = routes
        self.shortest = shortest
        self.difficulty = difficulty
        self.style = style
        self.matched = matched      # False when dealing fell back
        self.attempts = attempts


def ranked_target(stats, on_board, difficulty, rng):
    """Pick a target by rarity on this board, or None if it has none.

    Targets are ordered rarest first (fewest routes, then most moves).
    Hard picks from the rarest third, easy from the commonest third,
    medium from the middle.
    """
    targets = targets_matching(stats, on_board)

    if not targets:
        return None

    def rarity(target):
        routes, shortest = stats[Fraction(target)]
        return (routes, -shortest, target)

    ordered = sorted(targets, key=rarity)
    third = max(1, len(ordered) // 3)

    if difficulty == "hard":
        pool = ordered[:third]
    elif difficulty == "easy":
        pool = ordered[-third:]
    else:
        pool = ordered[third:len(ordered) - third] or ordered

    return rng.choice(pool)


def deal_target_round(difficulty=DEFAULT_DIFFICULTY,
                      style=DEFAULT_BOARD_STYLE, rng=None,
                      clock=time.monotonic):
    """Deal a board and a target that matches the difficulty rule.

    If no board within the attempt and time limits has a matching target,
    the first board with any target in TARGET_RANGE is used instead and
    round.matched is False.
    """
    rng = rng or random.Random()
    rule = DIFFICULTY_RULES[difficulty]
    deadline = clock() + MAX_DEAL_SECONDS
    fallback = None
    attempts = 0

    while True:
        attempts += 1
        rows = deal_numbers(style, rng)
        stats = analyse_routes(BoardState(rows))
        on_board = {value for row in rows for value in row}

        if style in RELATIVE_DIFFICULTY_STYLES:
            target = ranked_target(stats, on_board, difficulty, rng)
        else:
            candidates = targets_matching(stats, on_board, rule)
            target = rng.choice(candidates) if candidates else None

        if target is not None:
            routes, shortest = stats[Fraction(target)]
            return TargetRound(rows, target, routes, shortest, difficulty,
                               style, True, attempts)

        if fallback is None:
            loose = targets_matching(stats, on_board)
            if loose:
                fallback = (rows, stats, loose)

        out_of_budget = attempts >= MAX_DEAL_ATTEMPTS or clock() > deadline

        if out_of_budget and fallback is not None:
            break

    rows, stats, loose = fallback
    target = rng.choice(loose)
    routes, shortest = stats[Fraction(target)]
    return TargetRound(rows, target, routes, shortest, difficulty, style,
                       False, attempts)


# --- scoring ----------------------------------------------------------------

# points_for_distance and TargetSession live in tilegame/targets.py and are
# imported above, so every tile game scores the same way.