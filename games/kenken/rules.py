"""
KenKen rules: puzzles, cages and checking. No UIKit.

A KenKen puzzle of size n is an n x n grid where every row and every column
holds 1 to n exactly once. The grid is divided into cages. Each cage shows a
target and an operation, and the numbers in the cage must make the target
with that operation. Subtraction and division cages always hold two cells and
are read as larger - smaller and larger / smaller. A one-cell cage simply
states its number.

Numbers may repeat inside a cage, as long as the repeats sit in different
rows and columns.

generate_puzzle() builds a random puzzle for a board size and a set of
allowed operations, and only ever returns puzzles with exactly one solution.
"""

import itertools
import random
from dataclasses import dataclass


# --- editable settings -------------------------------------------------------

BOARD_SIZES = (3, 4, 5, 6)

OPERATIONS = ("add", "subtract", "multiply", "divide")

OPERATION_SYMBOLS = {
    "add": "+",
    "subtract": "\u2212",
    "multiply": "\u00d7",
    "divide": "\u00f7",
}

# How likely each cage size is when a new cage starts growing. A cage can end
# up smaller when it runs out of free neighbours.
CAGE_SIZE_WEIGHTS = {1: 0, 2: 6, 3: 4, 4: 2}

# How likely each operation is when several would fit a cage. Subtraction
# and division only fit some pairs, so they get more weight when they do.
OPERATION_WEIGHTS = {"add": 2, "subtract": 3, "multiply": 2, "divide": 4}

# Fresh random puzzles tried before the generator repairs one into a unique
# puzzle by turning ambiguous cells into one-cell cages.
FRESH_ATTEMPTS = 30


# --- fixed rules -------------------------------------------------------------

# These operations only make sense on exactly two cells.
TWO_CELL_OPERATIONS = ("subtract", "divide")

# Every puzzle needs at least one of these: without them no cage can hold
# three or more cells, and most of the board turns into given numbers.
ANCHOR_OPERATIONS = ("add", "multiply")


def operations_allowed(operations):
    """True when this set of operations can make a proper puzzle."""
    return any(operation in operations for operation in ANCHOR_OPERATIONS)

SMALLEST_SUPPORTED_SIZE = 3
LARGEST_SUPPORTED_SIZE = 9


# --- records -----------------------------------------------------------------

@dataclass(frozen=True)
class Cage:
    """One cage: its cells in reading order, its operation and its target.

    operation is an OPERATIONS name, or None for a one-cell cage.
    """

    cells: tuple
    operation: object
    target: int

    def label(self):
        """The text drawn in the cage's first cell, e.g. '12x' or '3'."""
        if self.operation is None:
            return str(self.target)
        return "%d%s" % (self.target, OPERATION_SYMBOLS[self.operation])

    def label_cell(self):
        """The cell that carries the label: the first in reading order."""
        return self.cells[0]


@dataclass(frozen=True)
class Puzzle:
    """A complete puzzle: its size, its cages and its one solution."""

    size: int
    cages: tuple      # Cage records, ordered by their label cell
    solution: tuple   # rows of ints

    def cage_lookup(self):
        """Return {cell: cage index} for every cell on the board."""
        return {
            cell: index
            for index, cage in enumerate(self.cages)
            for cell in cage.cells
        }


# --- arithmetic --------------------------------------------------------------

def combine(operation, values):
    """Return what these cage values make with operation, or None if nothing.

    None means the operation cannot apply: division that is not exact, or a
    two-cell operation given a different number of values.
    """
    values = tuple(values)
    if operation is None:
        return values[0] if len(values) == 1 else None
    if operation == "add":
        return sum(values)
    if operation == "multiply":
        product = 1
        for value in values:
            product *= value
        return product
    if len(values) != 2:
        return None
    larger, smaller = max(values), min(values)
    if operation == "subtract":
        return larger - smaller
    if operation == "divide":
        return larger // smaller if larger % smaller == 0 else None
    raise ValueError("Unknown operation %r" % operation)


def cage_status(cage, grid):
    """'incomplete', 'correct' or 'wrong' for a cage on a grid of rows.

    Empty cells in grid are None.
    """
    values = [grid[row][col] for row, col in cage.cells]
    if any(value is None for value in values):
        return "incomplete"
    return "correct" if combine(cage.operation, values) == cage.target else "wrong"


def is_solved(puzzle, grid):
    """True when grid is full, every row and column is 1..n, and every cage holds."""
    size = puzzle.size
    full_set = set(range(1, size + 1))
    for row in range(size):
        if set(grid[row]) != full_set:
            return False
    for col in range(size):
        if {grid[row][col] for row in range(size)} != full_set:
            return False
    return all(cage_status(cage, grid) == "correct" for cage in puzzle.cages)


# --- board geometry ----------------------------------------------------------

def all_cells(size):
    return [(row, col) for row in range(size) for col in range(size)]


def neighbours(cell, size):
    """Cells up, down, left and right of cell that are on the board."""
    row, col = cell
    for row_step, col_step in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        next_row, next_col = row + row_step, col + col_step
        if 0 <= next_row < size and 0 <= next_col < size:
            yield (next_row, next_col)


def connected_groups(cells):
    """Split cells into orthogonally connected groups, each sorted."""
    remaining = set(cells)
    groups = []
    while remaining:
        start = min(remaining)
        group = [start]
        remaining.discard(start)
        frontier = [start]
        while frontier:
            row, col = frontier.pop()
            for step in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                neighbour = (row + step[0], col + step[1])
                if neighbour in remaining:
                    remaining.discard(neighbour)
                    group.append(neighbour)
                    frontier.append(neighbour)
        groups.append(sorted(group))
    return groups


# --- generation --------------------------------------------------------------

def generate_puzzle(size, operations, rng=None, stats=None):
    """Return a random Puzzle with exactly one solution.

    size is the board width. operations is a collection of OPERATIONS names
    that must include add or multiply (see operations_allowed). Pass a
    seeded random.Random as rng for a repeatable puzzle. Pass a dict as
    stats to learn how many fresh attempts were used and how many cells the
    repair step turned into one-cell cages.
    """
    allowed = tuple(operation for operation in OPERATIONS if operation in operations)
    if not operations_allowed(allowed):
        raise ValueError("Choose add or multiply, with any other operations")
    if not SMALLEST_SUPPORTED_SIZE <= size <= LARGEST_SUPPORTED_SIZE:
        raise ValueError("Board size must be %d to %d" % (
            SMALLEST_SUPPORTED_SIZE, LARGEST_SUPPORTED_SIZE))
    rng = rng or random.Random()
    largest_cage = max(CAGE_SIZE_WEIGHTS)

    for attempt in range(1, FRESH_ATTEMPTS + 1):
        square = latin_square(size, rng)
        groups = partition_cages(size, largest_cage, rng)
        cages = build_cages(groups, square, allowed, rng)
        if len(find_solutions(size, cages, limit=2)) == 1:
            if stats is not None:
                stats.update(attempts=attempt, repaired_cells=0)
            return Puzzle(size, tuple(cages), square)

    cages, repaired = repair_until_unique(size, cages, square, allowed, rng)
    if stats is not None:
        stats.update(attempts=FRESH_ATTEMPTS, repaired_cells=repaired)
    return Puzzle(size, tuple(cages), square)


def latin_square(size, rng):
    """A random Latin square: shuffled rows, columns and symbols of a cycle."""
    row_order = list(range(size))
    col_order = list(range(size))
    symbols = list(range(1, size + 1))
    rng.shuffle(row_order)
    rng.shuffle(col_order)
    rng.shuffle(symbols)
    return tuple(
        tuple(symbols[(row_order[row] + col_order[col]) % size] for col in range(size))
        for row in range(size)
    )


def partition_cages(size, largest_cage, rng):
    """Cover the board with connected groups of 1 to largest_cage cells.

    Groups grow from random starting cells. Cells left stranded on their own
    are then merged into a neighbouring group where there is room, since
    every one-cell cage gives a number away.
    """
    sizes = [cage_size for cage_size in CAGE_SIZE_WEIGHTS if cage_size <= largest_cage]
    weights = [CAGE_SIZE_WEIGHTS[cage_size] for cage_size in sizes]

    free = set(all_cells(size))
    starts = all_cells(size)
    rng.shuffle(starts)

    groups = []
    for start in starts:
        if start not in free:
            continue
        wanted = rng.choices(sizes, weights=weights)[0]
        group = [start]
        free.discard(start)
        while len(group) < wanted:
            options = [
                neighbour
                for cell in group
                for neighbour in neighbours(cell, size)
                if neighbour in free
            ]
            if not options:
                break
            chosen = rng.choice(options)
            group.append(chosen)
            free.discard(chosen)
        groups.append(sorted(group))
    return merge_stranded_cells(groups, size, largest_cage)


def merge_stranded_cells(groups, size, largest_cage):
    """Join each one-cell group to its smallest neighbouring group with room.

    A cell stays on its own only when every neighbouring group is full.
    Ties go to the earlier group, so the result is repeatable.
    """
    groups = [list(group) for group in groups]
    owner = {cell: index for index, group in enumerate(groups) for cell in group}

    for index, group in enumerate(groups):
        if len(group) != 1:
            continue
        cell = group[0]
        options = {
            owner[neighbour]
            for neighbour in neighbours(cell, size)
            if owner[neighbour] != index
            and 0 < len(groups[owner[neighbour]]) < largest_cage
        }
        if not options:
            continue
        chosen = min(options, key=lambda other: (len(groups[other]), other))
        groups[chosen].append(cell)
        groups[index] = []
        owner[cell] = chosen

    return [sorted(group) for group in groups if group]


def build_cages(groups, square, allowed, rng):
    """Turn cell groups into cages using the solution square, sorted by label cell."""
    cages = []
    for cells in groups:
        cages.extend(cages_for_group(cells, square, allowed, rng))
    return sorted(cages, key=lambda cage: cage.cells[0])


def cages_for_group(cells, square, allowed, rng):
    """One cage for these cells, or one-cell cages if no allowed operation fits."""
    values = tuple(square[row][col] for row, col in cells)
    if len(cells) == 1:
        return [Cage(tuple(cells), None, values[0])]

    choices = []
    for operation in allowed:
        target = combine(operation, values)
        if target is not None:
            choices.append((operation, target))

    if not choices:
        return [Cage((cell,), None, square[cell[0]][cell[1]]) for cell in cells]

    weights = [OPERATION_WEIGHTS[operation] for operation, _ in choices]
    operation, target = rng.choices(choices, weights=weights)[0]
    return [Cage(tuple(cells), operation, target)]


def repair_until_unique(size, cages, square, allowed, rng):
    """Make cells one-cell cages until the puzzle has one solution.

    Each round finds a second solution, picks a cell where it differs from
    the intended square and splits that cell off as a one-cell cage. Such a
    cell can never differ again, so this always finishes.

    Returns (cages, number of cells split off).
    """
    repaired = 0
    while True:
        solutions = find_solutions(size, cages, limit=2)
        if len(solutions) == 1:
            return cages, repaired
        other = solutions[1] if solutions[0] == square else solutions[0]
        differing = [
            (row, col)
            for row in range(size)
            for col in range(size)
            if other[row][col] != square[row][col]
        ]
        cages = split_off(cages, rng.choice(differing), square, allowed, rng)
        repaired += 1


def split_off(cages, cell, square, allowed, rng):
    """Return cages with cell in its own cage; the rest of its cage is rebuilt."""
    owner = next(cage for cage in cages if cell in cage.cells)
    kept = [cage for cage in cages if cage is not owner]
    rest = [other for other in owner.cells if other != cell]
    groups = [[cell]] + connected_groups(rest)
    rebuilt = []
    for group in groups:
        rebuilt.extend(cages_for_group(group, square, allowed, rng))
    return sorted(kept + rebuilt, key=lambda cage: cage.cells[0])


# --- solving -----------------------------------------------------------------

def cage_candidates(cage, size):
    """Every tuple of values that satisfies the cage on its own.

    Values in cells sharing a row or column must differ.
    """
    cells = cage.cells
    count = len(cells)
    clashes = [
        (first, second)
        for first in range(count)
        for second in range(first + 1, count)
        if cells[first][0] == cells[second][0] or cells[first][1] == cells[second][1]
    ]
    candidates = []
    for values in itertools.product(range(1, size + 1), repeat=count):
        if any(values[first] == values[second] for first, second in clashes):
            continue
        if combine(cage.operation, values) == cage.target:
            candidates.append(values)
    return candidates


def find_solutions(size, cages, limit=2):
    """Return up to limit solutions, each a tuple of row tuples.

    Searches cage by cage, always filling the cage with fewest options left.
    limit=2 is the uniqueness test: one result means one solution.
    """
    candidates = [cage_candidates(cage, size) for cage in cages]
    row_used = [0] * size
    col_used = [0] * size
    grid = [[0] * size for _ in range(size)]
    open_cages = set(range(len(cages)))
    found = []

    def fits(cage, values):
        for (row, col), value in zip(cage.cells, values):
            bit = 1 << value
            if row_used[row] & bit or col_used[col] & bit:
                return False
        return True

    def toggle(cage, values):
        # XOR is safe: values within one row or column of a cage differ.
        for (row, col), value in zip(cage.cells, values):
            bit = 1 << value
            row_used[row] ^= bit
            col_used[col] ^= bit
            grid[row][col] = value

    def search():
        if not open_cages:
            found.append(tuple(tuple(row) for row in grid))
            return
        best_index = None
        best_options = None
        for index in open_cages:
            cage = cages[index]
            options = [values for values in candidates[index] if fits(cage, values)]
            if best_options is None or len(options) < len(best_options):
                best_index, best_options = index, options
                if not options:
                    return
        cage = cages[best_index]
        open_cages.discard(best_index)
        for values in best_options:
            toggle(cage, values)
            search()
            toggle(cage, values)
            if len(found) >= limit:
                break
        open_cages.add(best_index)

    search()
    return found


# --- checking ----------------------------------------------------------------

def check_puzzle(puzzle, allowed=None):
    """Return a list of problems with a puzzle; an empty list means valid."""
    problems = []
    owner_of = {}
    for index, cage in enumerate(puzzle.cages):
        for cell in cage.cells:
            if cell in owner_of:
                problems.append("cell %s is in two cages" % (cell,))
            owner_of[cell] = index
        if len(connected_groups(cage.cells)) != 1:
            problems.append("cage %d is not connected" % index)
        if cage.operation is None and len(cage.cells) != 1:
            problems.append("cage %d has no operation but several cells" % index)
        if cage.operation in TWO_CELL_OPERATIONS and len(cage.cells) != 2:
            problems.append("cage %d: %s needs two cells" % (index, cage.operation))
        if allowed is not None and cage.operation is not None and cage.operation not in allowed:
            problems.append("cage %d uses %s, not allowed" % (index, cage.operation))
        values = [puzzle.solution[row][col] for row, col in cage.cells]
        if combine(cage.operation, values) != cage.target:
            problems.append("cage %d target does not match the solution" % index)

    missing = set(all_cells(puzzle.size)) - set(owner_of)
    if missing:
        problems.append("cells in no cage: %s" % sorted(missing))
    if not is_solved(puzzle, puzzle.solution):
        problems.append("the solution breaks the rules")
    return problems