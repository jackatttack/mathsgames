"""
Fold stars: how well a puzzle was solved, measured against par and against
a mindless way to solve it.

    ★★★  Perfect: par or better, with no hint
    ★★   Solved: within the star line (below); a hint caps a solve here
    ★    Completed: any finish

The star line sits halfway between par and the corner flood: flooding
from the top corner every time, always with the colour that borders the
corner's region most. No thinking and no choice of where to tap, so it is
a fair, per-puzzle measure of "wasted moves". Across the first 60 Journey
puzzles it averages 1.64 times par. The line is never below par + 1.

Progress counts ★★ or better: a chapter opens once enough puzzles in the
one before reach it (screen.UNLOCK_AFTER). Pure Python, smoke-tested.
"""

import math


PERFECT, SOLVED, COMPLETED = 3, 2, 1
COUNTS_TOWARDS_PROGRESS = SOLVED     # stars a solve needs to open chapters
HINTED_MAX = SOLVED                   # the most stars a hinted solve can earn


def corner_flood_moves(puzzle, limit=500):
    """Moves the corner flood takes on puzzle: always recolour the region
    holding the first cell to the colour bordering it most (by triangles;
    ties go to the lower colour number)."""
    board = puzzle.board()
    grid = board.grid
    corner = grid.cells()[0]
    moves = 0
    while not board.is_solved() and moves < limit:
        region = {cell for cell, steps in board.region_of(corner)}
        border = {}
        for cell in region:
            for other in grid.neighbours(cell):
                if other not in region:
                    colour = board.colours[other]
                    border[colour] = border.get(colour, 0) + 1
        colour = max(sorted(border), key=lambda value: border[value])
        board.flood(corner, colour)
        moves += 1
    return moves


def star_line(par, corner_moves):
    """The most moves that still earn ★★: halfway from par to the corner
    flood, rounded up, and never less than par + 1."""
    return max(par + 1, par + int(math.ceil((corner_moves - par) / 2.0)))


def stars_for(moves, par, line, hinted=False):
    """Stars for a finished puzzle."""
    if moves <= par and not hinted:
        return PERFECT
    if moves <= line:
        return SOLVED
    return COMPLETED


def puzzle_line(puzzle):
    """The puzzle's star line, worked out once and kept on the puzzle."""
    line = getattr(puzzle, "star_line", None)
    if line is None:
        line = star_line(puzzle.par, corner_flood_moves(puzzle))
        puzzle.star_line = line
    return line


def show(stars):
    """'★★☆' for 2 stars."""
    return "★" * stars + "☆" * (3 - stars)
