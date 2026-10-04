"""Headless tile board: values, pluggable rules, moves and undo.

No UIKit lives here. Cells are addressed as (row, col) and an empty cell
holds None. Values are exact Fractions so chains never drift through
floating-point error.

Move:
    choose a source tile, choose an operation, choose a destination tile.
    The source is the left operand. The result replaces the destination and
    the source cell becomes empty. Each move is one undo step.

Two rules are pluggable, so different games share this board:

    merge_rule(source, destination)             which cells may merge
    result_rule(left, operation, right, value)  which results are allowed

The defaults are Multiple Merge's: orthogonal neighbours, any exact value.
Countdown uses any_pair and positive_whole_numbers.
"""

from fractions import Fraction


OPERATIONS = ("+", "-", "×", "/")

OPERATION_SYMBOLS = {
    "+": "+",
    "-": "−",
    "×": "×",
    "/": "÷",
}


def evaluate(left, operation, right):
    """Return left <operation> right exactly, or None when undefined."""
    left = Fraction(left)
    right = Fraction(right)

    if operation == "+":
        return left + right
    if operation == "-":
        return left - right
    if operation == "×":
        return left * right
    if operation == "/":
        if right == 0:
            return None
        return left / right

    raise ValueError("Unknown operation: {}".format(operation))


def format_value(value):
    """Display text for a value: whole numbers plainly, others as a/b."""
    value = Fraction(value)
    if value.denominator == 1:
        return str(value.numerator)
    return "{}/{}".format(value.numerator, value.denominator)


# --- merge rules: which pairs of cells may merge ----------------------------

def orthogonal_neighbours(source, destination):
    """Multiple Merge: up, down, left or right of each other."""
    return abs(source[0] - destination[0]) + abs(source[1] - destination[1]) == 1


def any_pair(source, destination):
    """Countdown: any two different cells."""
    return tuple(source) != tuple(destination)


# --- result rules: which results are allowed --------------------------------

def any_exact_value(left, operation, right, value):
    """Multiple Merge: fractions and negatives are fine."""
    return True


def positive_whole_numbers(left, operation, right, value):
    """Countdown: every result must be a positive whole number."""
    return value > 0 and value.denominator == 1


class MoveResult:
    """A committed move: which cells took part and what it produced."""

    def __init__(self, source, destination, operation, left, right, value):
        self.source = source
        self.destination = destination
        self.operation = operation
        self.left = left
        self.right = right
        self.value = value

    def expression(self):
        return "{} {} {} = {}".format(
            format_value(self.left),
            OPERATION_SYMBOLS[self.operation],
            format_value(self.right),
            format_value(self.value),
        )


class BoardState:
    """The source of truth for tile values on a rectangular board."""

    def __init__(self, rows_of_values, merge_rule=orthogonal_neighbours,
                 result_rule=any_exact_value):
        self.cells = [
            [None if value is None else Fraction(value) for value in row]
            for row in rows_of_values
        ]
        self.rows = len(self.cells)
        self.cols = len(self.cells[0]) if self.cells else 0
        self.merge_rule = merge_rule
        self.result_rule = result_rule
        self._original = self.snapshot()
        self._undo = []

    def copy_with(self, rows_of_values):
        """A new board with these values and the same rules (for searches)."""
        return BoardState(rows_of_values, self.merge_rule, self.result_rule)

    # --- reading -------------------------------------------------------

    def in_bounds(self, cell):
        row, col = cell
        return 0 <= row < self.rows and 0 <= col < self.cols

    def value_at(self, cell):
        row, col = cell
        return self.cells[row][col]

    @staticmethod
    def is_adjacent(a, b):
        """Orthogonal adjacency, kept for callers that ask directly."""
        return orthogonal_neighbours(a, b)

    def can_merge(self, source, destination):
        """True when both cells hold values and the merge rule allows them."""
        return (
            self.in_bounds(source)
            and self.in_bounds(destination)
            and self.value_at(source) is not None
            and self.value_at(destination) is not None
            and self.merge_rule(tuple(source), tuple(destination))
        )

    def result_of(self, source, operation, destination):
        """The value this move would make, or None if not allowed.

        Changes nothing. Raises ValueError for an unknown operation.
        """
        if operation not in OPERATIONS:
            raise ValueError("Unknown operation: {}".format(operation))

        if not self.can_merge(source, destination):
            return None

        left = self.value_at(source)
        right = self.value_at(destination)
        value = evaluate(left, operation, right)

        if value is None or not self.result_rule(left, operation, right, value):
            return None

        return value

    def move_allowed(self, source, operation, destination):
        return self.result_of(source, operation, destination) is not None

    # --- changing ------------------------------------------------------

    def apply_move(self, source, operation, destination):
        """Commit one move and return a MoveResult, or None if not allowed.

        A rejected move changes nothing and records no undo step.
        """
        value = self.result_of(source, operation, destination)

        if value is None:
            return None

        left = self.value_at(source)
        right = self.value_at(destination)

        self._undo.append(self.snapshot())
        self.cells[destination[0]][destination[1]] = value
        self.cells[source[0]][source[1]] = None

        return MoveResult(source, destination, operation, left, right, value)

    # --- history -------------------------------------------------------

    def snapshot(self):
        """Return a copy of the grid. Fractions are immutable, so rows suffice."""
        return [list(row) for row in self.cells]

    def restore(self, snapshot):
        self.cells = [list(row) for row in snapshot]

    def can_undo(self):
        return bool(self._undo)

    def undo(self):
        """Restore the board to before the last move. Returns False if none."""
        if not self._undo:
            return False
        self.restore(self._undo.pop())
        return True

    def reset(self):
        """Return to the starting values and forget move history."""
        self.restore(self._original)
        self._undo = []