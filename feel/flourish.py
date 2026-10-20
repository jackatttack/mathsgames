"""
Timing for the Sudoku finish flourish: when each cell pops, and its shape mid-pop.

Pure Python, no UIKit, so smokes/sudoku_flourish_smoke.py checks every
style headless. A view asks schedule() once when the puzzle is solved,
then asks pop_shape() for each started cell on every frame-clock tick
(update() with update_interval set once; see the pythonista-ui-stability
guide for why not delayed ui.animate).

Cells are (row, column) tuples. box_shape is (box_rows, box_columns): how
many rows and columns one box spans, so a 6x6 board with 2-row, 3-column
boxes is (2, 3).
"""

import math


STYLES = ("cascade", "ripple", "boxes", "diagonal")

# --- editable feel ---------------------------------------------------------------

# Within a group (one number, or one box) cells start spread over this share
# of the step between groups. Keep it below 1 so groups never interleave.
GROUP_SPREAD = 0.4

# How far a pop swells past full size before settling. 0 means no overshoot.
OVERSHOOT = 1.70158

# The whole celebration, and one cell's pop within it, in seconds.
TOTAL_SECONDS = 2.0
POP_SECONDS = 0.35


# --- schedule ----------------------------------------------------------------------

def schedule(style, solution, box_shape, origin=None,
             total_seconds=TOTAL_SECONDS, pop_seconds=POP_SECONDS):
    """Return {cell: start time in seconds}, so the whole flourish fits total_seconds.

    style:     one of STYLES.
                 cascade   every 1, then every 2, and so on
                 ripple    a wave outwards from origin (default: centre cell)
                 boxes     box by box in a clockwise spiral from the top left
                 diagonal  top-left corner to bottom-right corner
    solution:  the solved board as rows of numbers.
    box_shape: (box_rows, box_columns).

    Each cell's pop lasts pop_seconds from its start. The last pop ends at
    total_seconds (cascade and boxes can end a little earlier).
    Raises ValueError for an unknown style.
    """
    size = len(solution)
    cells = all_cells(size)
    available = max(0.0, total_seconds - pop_seconds)

    if style == "cascade":
        values = sorted({value for row in solution for value in row})
        groups = [
            [cell for cell in cells if solution[cell[0]][cell[1]] == value]
            for value in values
        ]
        return _staggered_groups(groups, available)

    if style == "boxes":
        box_rows, box_columns = box_shape
        order = _spiral(size // box_rows, size // box_columns)
        groups = [_box_cells(box, box_shape) for box in order]
        return _staggered_groups(groups, available)

    if style == "ripple":
        if origin is None:
            origin = (size // 2, size // 2)
        distances = {
            cell: math.hypot(cell[0] - origin[0], cell[1] - origin[1])
            for cell in cells
        }
        farthest = max(distances.values()) or 1.0
        return {cell: available * distance / farthest for cell, distance in distances.items()}

    if style == "diagonal":
        span = 2 * (size - 1) or 1
        return {cell: available * (cell[0] + cell[1]) / span for cell in cells}

    raise ValueError(
        "unknown flourish style %r; expected one of %s" % (style, ", ".join(STYLES))
    )


def finish_time(starts, pop_seconds):
    """When the last pop in a schedule ends."""
    return max(starts.values()) + pop_seconds if starts else 0.0


# --- pop shape -----------------------------------------------------------------------

def pop_shape(since_start, pop_seconds):
    """(size_factor, alpha_factor) for a cell this many seconds into its pop.

    Before the pop: (0, 0). After it: (1, 1). In between the fill grows from
    nothing, swells past full size by OVERSHOOT, then settles at 1, while it
    fades in over the first third.
    """
    if since_start <= 0:
        return 0.0, 0.0
    if since_start >= pop_seconds:
        return 1.0, 1.0
    progress = since_start / pop_seconds
    back = progress - 1
    size_factor = 1 + (OVERSHOOT + 1) * back ** 3 + OVERSHOOT * back ** 2
    alpha_factor = min(1.0, progress * 3)
    return max(0.0, size_factor), alpha_factor


# --- helpers -------------------------------------------------------------------------

def all_cells(size):
    return [(row, column) for row in range(size) for column in range(size)]


def _staggered_groups(groups, available):
    """Groups start one step apart; cells within a group spread a little."""
    denominator = len(groups) - 1 + GROUP_SPREAD
    step = available / denominator if denominator > 0 else 0.0
    spread = step * GROUP_SPREAD
    starts = {}
    for index, group in enumerate(groups):
        for position, cell in enumerate(group):
            starts[cell] = index * step + spread * position / len(group)
    return starts


def _box_cells(box, box_shape):
    box_row, box_column = box
    box_rows, box_columns = box_shape
    return [
        (row, column)
        for row in range(box_row * box_rows, (box_row + 1) * box_rows)
        for column in range(box_column * box_columns, (box_column + 1) * box_columns)
    ]


def _spiral(rows, columns):
    """Every (row, column) of a rows x columns grid, clockwise from the top left."""
    top, bottom, left, right = 0, rows - 1, 0, columns - 1
    order = []
    while top <= bottom and left <= right:
        for column in range(left, right + 1):
            order.append((top, column))
        for row in range(top + 1, bottom + 1):
            order.append((row, right))
        if top < bottom:
            for column in range(right - 1, left - 1, -1):
                order.append((bottom, column))
        if left < right:
            for row in range(bottom - 1, top, -1):
                order.append((row, left))
        top, bottom, left, right = top + 1, bottom - 1, left + 1, right - 1
    return order
