"""Classic Multiples mode: targets, board dealing and found-target tracking.

No UIKit lives here.

Rules:
    Settings choose a multiple, for example 10. The targets are the first
    TARGET_COUNT multiples: 10, 20, ... 100.

    A target is found when a move produces exactly that value. Found targets
    stay found when the board is reset to its starting numbers, so one board
    can be searched for several targets.

    A board is only dealt if at least MIN_REACHABLE_TARGETS targets can be
    made from it, and no starting number is itself a target.

    The board is complete when every reachable target has been found.
"""

import random
from collections import deque
from fractions import Fraction

from tilegame.board_state import BoardState, OPERATIONS


# --- editable settings ------------------------------------------------------

DEFAULT_MULTIPLE = 10

# The choices offered in the settings panel.
MULTIPLE_CHOICES = (2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 25)

TARGET_COUNT = 10              # targets are multiple × 1 .. TARGET_COUNT
MIN_REACHABLE_TARGETS = 5      # a dealt board must allow at least this many
STARTING_NUMBER_RANGE = (1, 12)
BOARD_ROWS = 2
BOARD_COLS = 2

# Dealing gives up after this many random boards and keeps the best one seen,
# so an awkward multiple can never hang the app.
MAX_DEAL_ATTEMPTS = 200


# --- targets ----------------------------------------------------------------

def targets_for(multiple):
    """Return the target list for a multiple, smallest first."""
    return [multiple * step for step in range(1, TARGET_COUNT + 1)]


# --- searching a board ------------------------------------------------------

NEIGHBOUR_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def merge_pairs(board):
    """Return every (source, destination) pair that could merge right now.

    The board's merge rule decides, so this works for neighbour-only and
    any-pair boards alike.
    """
    cells = [
        (row, col)
        for row in range(board.rows)
        for col in range(board.cols)
        if board.value_at((row, col)) is not None
    ]

    return [
        (source, destination)
        for source in cells
        for destination in cells
        if board.can_merge(source, destination)
    ]


def reachable_values(board):
    """Return every value that some sequence of moves can produce.

    Exhaustive depth-first search over board positions. Positions already
    explored are skipped, which keeps a 2x2 board to a few thousand moves.
    """
    produced = set()
    explored = set()

    def explore(cells):
        key = tuple(tuple(row) for row in cells)

        if key in explored:
            return

        explored.add(key)
        position = board.copy_with(cells)

        for source, destination in merge_pairs(position):
            for operation in OPERATIONS:
                result = position.apply_move(source, operation, destination)

                if result is None:
                    continue

                produced.add(result.value)
                explore(position.snapshot())
                position.undo()

    explore(board.snapshot())
    return produced


def reachable_targets(board, targets):
    """Return the set of targets that some sequence of moves can make."""
    values = reachable_values(board)
    return {target for target in targets if Fraction(target) in values}


def solution_moves(board, target):
    """Return the shortest list of moves whose last move produces target.

    Each move is (source, operation, destination), ready for
    BoardState.apply_move. Returns None when no sequence of moves from the
    current position makes target. The board itself is never changed.

    Breadth-first, so the first route found is a shortest one. Operations
    are tried in OPERATIONS order, so hints prefer + over - over × over ÷
    when routes are equally short.
    """
    target = Fraction(target)
    start = board.snapshot()
    explored = {tuple(tuple(row) for row in start)}
    queue = deque([(start, [])])

    while queue:
        cells, moves = queue.popleft()
        position = board.copy_with(cells)

        for source, destination in merge_pairs(position):
            for operation in OPERATIONS:
                result = position.apply_move(source, operation, destination)

                if result is None:
                    continue

                route = moves + [(source, operation, destination)]
                child = position.snapshot()
                position.undo()

                if result.value == target:
                    return route

                key = tuple(tuple(row) for row in child)
                if key not in explored:
                    explored.add(key)
                    queue.append((child, route))

    return None


# --- one dealt board --------------------------------------------------------

class ClassicRound:
    """One dealt board, its targets, and which of them have been found."""

    def __init__(self, multiple, starting_rows, reachable, attempts=1):
        self.multiple = multiple
        self.targets = targets_for(multiple)
        self.starting_rows = [list(row) for row in starting_rows]
        self.reachable = set(reachable)
        self.attempts = attempts
        self.found = set()

    def starting_board(self):
        """A fresh BoardState holding the dealt numbers."""
        return BoardState(self.starting_rows)

    def record(self, value):
        """Mark value found if it is an unfound target.

        Returns True only when this value newly completes a target.
        """
        value = Fraction(value)

        if value.denominator != 1:
            return False

        whole = value.numerator

        if whole not in self.targets or whole in self.found:
            return False

        self.found.add(whole)
        return True

    def is_complete(self):
        return self.reachable <= self.found


def deal_round(multiple=DEFAULT_MULTIPLE, rng=None):
    """Deal a board for multiple that meets the reachable-target rule.

    If no board within MAX_DEAL_ATTEMPTS meets MIN_REACHABLE_TARGETS, the
    best board seen is returned; its round.reachable shows how many it has.
    """
    rng = rng or random.Random()
    targets = targets_for(multiple)

    low, high = STARTING_NUMBER_RANGE
    allowed = [n for n in range(low, high + 1) if n not in targets]

    if not allowed:
        raise ValueError(
            "No starting numbers left for multiple {}".format(multiple)
        )

    best_rows = None
    best_reachable = set()
    attempts = 0

    for attempts in range(1, MAX_DEAL_ATTEMPTS + 1):
        rows = [
            [rng.choice(allowed) for _ in range(BOARD_COLS)]
            for _ in range(BOARD_ROWS)
        ]
        reachable = reachable_targets(BoardState(rows), targets)

        if best_rows is None or len(reachable) > len(best_reachable):
            best_rows = rows
            best_reachable = reachable

        if len(reachable) >= MIN_REACHABLE_TARGETS:
            break

    return ClassicRound(multiple, best_rows, best_reachable, attempts)