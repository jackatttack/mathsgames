"""
Sudoku rules: grids, puzzles, a uniqueness counter and a human-style grader.
No UIKit.

A Sudoku of size n fills an n x n grid so every row, column and box holds
1 to n once. Boxes are 2 x 2 on 4 x 4, 2 rows x 3 columns on 6 x 6 and
3 x 3 on 9 x 9.

Difficulty is graded by technique, not by counting givens. A puzzle's level
is the hardest technique the grader needs to solve it without guessing:

    1 easy    naked singles: a cell with only one possible value
    2 medium  hidden singles: a value with only one possible cell in a unit
    3 hard    naked pairs, pointing and box-line reduction

generate_puzzle() removes clues from a full grid in symmetric pairs, keeping
each removal only while the grader can still finish using techniques up to
the chosen level. A puzzle the grader finishes without guessing has exactly
one solution, so every puzzle is unique.

Internally grids are flat lists of length n * n, with 0 for an empty cell.
Puzzle records use rows, with None for an empty cell.
"""

import functools
import random
from dataclasses import dataclass


# --- editable settings -------------------------------------------------------

BOARD_SIZES = (4, 6, 9)

# Box shape for each size, as (rows, columns).
BOX_SHAPES = {4: (2, 2), 6: (2, 3), 9: (3, 3)}

DIFFICULTIES = ("easy", "medium", "hard")
DIFFICULTY_LEVELS = {"easy": 1, "medium": 2, "hard": 3}

# Which difficulties each size can really reach. Small boards are solved
# by singles alone, so they never need the harder techniques.
DIFFICULTIES_BY_SIZE = {
    4: ("easy",),
    6: ("easy", "medium"),
    9: ("easy", "medium", "hard"),
}

TECHNIQUE_NAMES = {
    1: "naked singles",
    2: "hidden singles",
    3: "pairs and pointing",
}

# Fresh grids tried to find a puzzle that needs exactly the chosen level.
# After that the hardest puzzle found is used, which may be easier. About
# one 9 x 9 grid in ten can be made Hard, so this keeps fallbacks rare.
ATTEMPTS = 40


# --- records -----------------------------------------------------------------

@dataclass(frozen=True)
class Geometry:
    """Where every cell sits, as flat indices, for one board size."""

    size: int
    box_rows: int
    box_cols: int
    rows: tuple        # each a tuple of flat indices
    cols: tuple
    boxes: tuple
    units: tuple       # rows, then columns, then boxes
    row_of: tuple      # per flat index
    col_of: tuple
    box_of: tuple
    peers: tuple       # per flat index: other indices sharing a unit


@dataclass(frozen=True)
class Puzzle:
    """A Sudoku to play: its givens, its one solution and its graded level."""

    size: int
    givens: tuple      # rows, None for an empty cell
    solution: tuple    # rows of ints
    difficulty: str    # the difficulty asked for
    level: int         # hardest technique the grader needed

    def givens_by_cell(self):
        """{(row, col): value} for every given, ready for FillGrid."""
        return {
            (row, col): value
            for row, row_values in enumerate(self.givens)
            for col, value in enumerate(row_values)
            if value is not None
        }

    def given_count(self):
        return len(self.givens_by_cell())


# --- geometry ----------------------------------------------------------------

@functools.lru_cache(maxsize=None)
def geometry(size):
    """The Geometry for a board size. Cached: built once per size."""
    if size not in BOX_SHAPES:
        raise ValueError("Board size must be one of %s" % (BOARD_SIZES,))
    box_rows, box_cols = BOX_SHAPES[size]
    boxes_across = size // box_cols

    rows = tuple(tuple(row * size + col for col in range(size)) for row in range(size))
    cols = tuple(tuple(row * size + col for row in range(size)) for col in range(size))
    boxes = tuple(
        tuple(
            (band * box_rows + row) * size + stack * box_cols + col
            for row in range(box_rows)
            for col in range(box_cols)
        )
        for band in range(size // box_rows)
        for stack in range(boxes_across)
    )

    count = size * size
    row_of = tuple(index // size for index in range(count))
    col_of = tuple(index % size for index in range(count))
    box_of = tuple(
        (row_of[index] // box_rows) * boxes_across + col_of[index] // box_cols
        for index in range(count)
    )

    peers = []
    for index in range(count):
        shared = (
            set(rows[row_of[index]])
            | set(cols[col_of[index]])
            | set(boxes[box_of[index]])
        )
        shared.discard(index)
        peers.append(tuple(sorted(shared)))

    return Geometry(
        size=size, box_rows=box_rows, box_cols=box_cols,
        rows=rows, cols=cols, boxes=boxes, units=rows + cols + boxes,
        row_of=row_of, col_of=col_of, box_of=box_of, peers=tuple(peers),
    )


def cell_units(size):
    """Every unit as (row, col) cells: the units argument for FillGrid."""
    geo = geometry(size)
    return tuple(
        tuple((geo.row_of[index], geo.col_of[index]) for index in unit)
        for unit in geo.units
    )


def to_rows(cells, size):
    """Flat cells (0 empty) to rows (None empty)."""
    return tuple(
        tuple(cells[row * size + col] or None for col in range(size))
        for row in range(size)
    )


def flatten(rows):
    """Rows (None empty) to flat cells (0 empty)."""
    return [value or 0 for row in rows for value in row]


def full_mask(size):
    """Bits 1..size set: every value possible."""
    return ((1 << size) - 1) << 1


# --- full grids --------------------------------------------------------------

def full_grid(size, rng):
    """A random complete grid, as rows.

    Starts from a standard valid pattern, then shuffles band order, rows
    within each band, stack order, columns within each stack, and symbols.
    Every one of those shuffles keeps the grid valid.
    """
    box_rows, box_cols = BOX_SHAPES[size]

    def pattern(row, col):
        return (box_cols * (row % box_rows) + row // box_rows + col) % size

    bands = list(range(size // box_rows))
    rng.shuffle(bands)
    row_order = [
        band * box_rows + row
        for band in bands
        for row in rng.sample(range(box_rows), box_rows)
    ]

    stacks = list(range(size // box_cols))
    rng.shuffle(stacks)
    col_order = [
        stack * box_cols + col
        for stack in stacks
        for col in rng.sample(range(box_cols), box_cols)
    ]

    symbols = list(range(1, size + 1))
    rng.shuffle(symbols)

    return tuple(
        tuple(symbols[pattern(row_order[row], col_order[col])] for col in range(size))
        for row in range(size)
    )


# --- brute-force counting ----------------------------------------------------

def count_solutions(cells, size, limit=2):
    """Count solutions of flat cells (0 empty), stopping at limit.

    A plain search, always trying the cell with fewest options. Used to
    check puzzles; generation relies on the grader instead.
    """
    geo = geometry(size)
    every_value = full_mask(size)
    values = list(cells)
    row_used = [0] * size
    col_used = [0] * size
    box_used = [0] * size

    for index, value in enumerate(values):
        if value:
            bit = 1 << value
            row, col, box = geo.row_of[index], geo.col_of[index], geo.box_of[index]
            if (row_used[row] | col_used[col] | box_used[box]) & bit:
                return 0
            row_used[row] |= bit
            col_used[col] |= bit
            box_used[box] |= bit

    empties = [index for index, value in enumerate(values) if not value]
    found = 0

    def search():
        nonlocal found
        best = -1
        best_mask = 0
        best_count = size + 1
        for index in empties:
            if values[index]:
                continue
            mask = every_value & ~(
                row_used[geo.row_of[index]]
                | col_used[geo.col_of[index]]
                | box_used[geo.box_of[index]]
            )
            if not mask:
                return
            options = bin(mask).count("1")
            if options < best_count:
                best, best_mask, best_count = index, mask, options
                if options == 1:
                    break
        if best < 0:
            found += 1
            return

        row, col, box = geo.row_of[best], geo.col_of[best], geo.box_of[best]
        mask = best_mask
        while mask:
            bit = mask & -mask
            mask ^= bit
            values[best] = bit.bit_length() - 1
            row_used[row] |= bit
            col_used[col] |= bit
            box_used[box] |= bit
            search()
            values[best] = 0
            row_used[row] &= ~bit
            col_used[col] &= ~bit
            box_used[box] &= ~bit
            if found >= limit:
                return

    search()
    return found


# --- the grader --------------------------------------------------------------

def logic_solve(cells, size, max_level=3):
    """Solve flat cells like a person, using techniques up to max_level.

    Always uses the easiest technique that makes progress. Returns
    (solved flat tuple, hardest level used), or (None, hardest level used)
    when it gets stuck or finds a contradiction.
    """
    geo = geometry(size)
    every_value = full_mask(size)
    values = list(cells)
    candidates = [0] * len(values)
    for index, value in enumerate(values):
        if not value:
            used = 0
            for peer in geo.peers[index]:
                if values[peer]:
                    used |= 1 << values[peer]
            candidates[index] = every_value & ~used

    def place(index, value):
        values[index] = value
        candidates[index] = 0
        bit = 1 << value
        for peer in geo.peers[index]:
            candidates[peer] &= ~bit

    hardest = 0
    while True:
        empties = [index for index, value in enumerate(values) if not value]
        if not empties:
            return tuple(values), hardest
        if any(candidates[index] == 0 for index in empties):
            return None, hardest

        singles = [
            index for index in empties
            if candidates[index] & (candidates[index] - 1) == 0
        ]
        if singles:
            for index in singles:
                if not values[index] and candidates[index]:
                    place(index, candidates[index].bit_length() - 1)
            hardest = max(hardest, 1)
            continue

        if max_level >= 2 and _place_hidden_single(geo, candidates, place):
            hardest = max(hardest, 2)
            continue

        if max_level >= 3 and _eliminate(geo, candidates):
            hardest = max(hardest, 3)
            continue

        return None, hardest


def _place_hidden_single(geo, candidates, place):
    """Place one value that has only one possible cell in some unit."""
    for unit in geo.units:
        seen_once = 0
        seen_twice = 0
        for index in unit:
            seen_twice |= seen_once & candidates[index]
            seen_once |= candidates[index]
        hidden = seen_once & ~seen_twice
        if hidden:
            bit = hidden & -hidden
            for index in unit:
                if candidates[index] & bit:
                    place(index, bit.bit_length() - 1)
                    return True
    return False


def _eliminate(geo, candidates):
    """Level-3 eliminations. Returns True if any candidate was removed."""
    pairs = _naked_pairs(geo, candidates)
    pointing = _pointing(geo, candidates)
    claiming = _box_line_reduction(geo, candidates)
    return pairs or pointing or claiming


def _naked_pairs(geo, candidates):
    """Two cells in a unit with the same two candidates own those values."""
    changed = False
    for unit in geo.units:
        cells_by_pair = {}
        for index in unit:
            mask = candidates[index]
            if mask and bin(mask).count("1") == 2:
                cells_by_pair.setdefault(mask, []).append(index)
        for mask, cells in cells_by_pair.items():
            if len(cells) != 2:
                continue
            for index in unit:
                if index not in cells and candidates[index] & mask:
                    candidates[index] &= ~mask
                    changed = True
    return changed


def _pointing(geo, candidates):
    """A value confined to one row or column of a box leaves that line elsewhere."""
    changed = False
    for box_index, box in enumerate(geo.boxes):
        for value in range(1, geo.size + 1):
            bit = 1 << value
            cells = [index for index in box if candidates[index] & bit]
            if not cells:
                continue
            for line_of, lines in ((geo.row_of, geo.rows), (geo.col_of, geo.cols)):
                line_numbers = {line_of[index] for index in cells}
                if len(line_numbers) != 1:
                    continue
                for index in lines[line_numbers.pop()]:
                    if geo.box_of[index] != box_index and candidates[index] & bit:
                        candidates[index] &= ~bit
                        changed = True
    return changed


def _box_line_reduction(geo, candidates):
    """A value confined to one box within a line leaves that box elsewhere."""
    changed = False
    for line in geo.rows + geo.cols:
        line_cells = set(line)
        for value in range(1, geo.size + 1):
            bit = 1 << value
            cells = [index for index in line if candidates[index] & bit]
            if not cells:
                continue
            box_numbers = {geo.box_of[index] for index in cells}
            if len(box_numbers) != 1:
                continue
            for index in geo.boxes[box_numbers.pop()]:
                if index not in line_cells and candidates[index] & bit:
                    candidates[index] &= ~bit
                    changed = True
    return changed


# --- generation --------------------------------------------------------------

def generate_puzzle(size, difficulty, rng=None, stats=None):
    """Return a unique Puzzle graded as close to difficulty as possible.

    Pass a seeded random.Random as rng for a repeatable puzzle. Pass a dict
    as stats to learn attempts used, the level reached, whether it matched
    exactly, and the number of givens.
    """
    if size not in BOX_SHAPES:
        raise ValueError("Board size must be one of %s" % (BOARD_SIZES,))
    if difficulty not in DIFFICULTY_LEVELS:
        raise ValueError("Difficulty must be one of %s" % (DIFFICULTIES,))
    level = DIFFICULTY_LEVELS[difficulty]
    rng = rng or random.Random()

    best = None
    attempt = 0
    for attempt in range(1, ATTEMPTS + 1):
        solution = full_grid(size, rng)
        cells = remove_clues(flatten(solution), size, level, rng)
        _, hardest = logic_solve(cells, size, level)
        if best is None or hardest > best[0]:
            best = (hardest, solution, cells)
        if hardest == level:
            break

    hardest, solution, cells = best
    if stats is not None:
        stats.update(
            attempts=attempt,
            level=hardest,
            exact=hardest == level,
            givens=sum(1 for value in cells if value),
        )
    return Puzzle(size, to_rows(cells, size), solution, difficulty, hardest)


def remove_clues(solution_cells, size, max_level, rng):
    """Empty cells in symmetric pairs while the grader can still finish.

    Each pair is a cell and its 180-degree rotation. A removal is kept only
    if logic_solve still solves the puzzle with techniques up to max_level.
    """
    cells = list(solution_cells)
    count = len(cells)
    order = list(range(count))
    rng.shuffle(order)
    tried = set()

    for index in order:
        if index in tried:
            continue
        partner = count - 1 - index
        tried.update((index, partner))
        saved = cells[index], cells[partner]
        cells[index] = 0
        cells[partner] = 0
        solved, _ = logic_solve(cells, size, max_level)
        if solved is None:
            cells[index], cells[partner] = saved

    return cells


# --- checking ----------------------------------------------------------------

def is_valid_grid(rows, size):
    """True when every row, column and box of a full grid holds 1..size."""
    geo = geometry(size)
    cells = flatten(rows)
    every_value = set(range(1, size + 1))
    return all({cells[index] for index in unit} == every_value for unit in geo.units)


def is_solved(puzzle, rows):
    """True when the player's rows match the puzzle's one solution."""
    return tuple(tuple(row) for row in rows) == puzzle.solution


def check_puzzle(puzzle):
    """Return a list of problems with a puzzle; an empty list means valid."""
    problems = []
    if not is_valid_grid(puzzle.solution, puzzle.size):
        problems.append("the solution is not a valid grid")
    for (row, col), value in puzzle.givens_by_cell().items():
        if puzzle.solution[row][col] != value:
            problems.append("given at %s disagrees with the solution" % ((row, col),))
    if count_solutions(flatten(puzzle.givens), puzzle.size, limit=2) != 1:
        problems.append("the puzzle does not have exactly one solution")
    return problems