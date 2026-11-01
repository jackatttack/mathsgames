"""
Tile folds for Double Up, built on boardkit/folds.py (Fold's paper animation):

Merges   a merge partner stops one cell short of its merge cell, then turns
         over onto the tile there like a page, hinged on the middle of the
         gap between the two cells. Its underside is the merged tile, so
         the merge is revealed as it lands.
Spawns   a new tile folds in from its cell's centre in tiny squares, in
         Fold's scatter chains; its number fades up once they have landed.

Pure Python: board_view.py asks for sheets each frame and draws them;
smokes/twenty48_fold_smoke.py checks them.
"""

import random

from boardkit import folds


# --- editable feel -----------------------------------------------------------

FOLD_SECONDS = 0.30           # a merge turn, from lifting off to landing
SPAWN_SQUARES = 5             # a new tile is cut into this many squares a side (odd: one middle)
SPAWN_FOLD_SECONDS = 0.16     # each tiny square's turn
SPAWN_SPREAD_SECONDS = 0.30   # the last tiny square starts by then
NUMBER_SECONDS = 0.14         # the new tile's number fading up once the squares land
SQUARE_BLEED = 0.5            # points each tiny square overlaps its neighbours: no seams


# --- merges --------------------------------------------------------------------

class MergeFold:
    """One merge partner's turn onto its merge cell.

    view       the partner's tile view, hidden while its sheet is drawn
    survivor   the tile view at the merge cell, which takes the merged value
               when the sheet lands
    stop_cell  where the partner's slide ends, beside the merge cell
    cell       the merge cell
    front      the partner's value, face up as the sheet lifts
    merged     the merged value, face up as the sheet lands
    start      when the turn begins (the slide has just ended)
    """

    def __init__(self, view, survivor, stop_cell, cell, front, merged, start):
        self.view = view
        self.survivor = survivor
        self.stop_cell = stop_cell
        self.cell = cell
        self.front = front
        self.merged = merged
        self.start = start


def stop_cell(source, target):
    """The cell beside target on the side source comes from (source itself
    when it is already beside target)."""
    return (target[0] + _sign(source[0] - target[0]),
            target[1] + _sign(source[1] - target[1]))


def plan(retired, survivors, before, after, start):
    """The MergeFolds for one swipe.

    retired    MotionPlan.retired: (view, source, target) per merge partner
    survivors  target cell -> tile view that stays there
    before     the board's values before the swipe, after them after it
    start      when the turns begin
    """
    return [MergeFold(view, survivors[target], stop_cell(source, target), target,
                      before[source[0]][source[1]], after[target[0]][target[1]], start)
            for view, source, target in retired]


def progress(fold, now):
    """0 before the turn starts, 1 once it has landed."""
    return min(1.0, max(0.0, (now - fold.start) / FOLD_SECONDS))


def started(fold, now):
    return now >= fold.start


def done(fold, now):
    return now >= fold.start + FOLD_SECONDS


def sheet(fold, stop_frame, target_frame, now):
    """(rect, face, shade, squash, axis) for the turning sheet, or None
    before it starts and once it has landed.

    rect     (x, y, width, height) to draw the tile in
    face     "front" (the partner's value) or "back" (the merged value)
    shade    multiplies the tile colour's brightness
    squash   the sheet's width along the fold as a share of a cell, for
             squeezing its number
    axis     "x" or "y": the direction the sheet travels
    """
    if now < fold.start or done(fold, now):
        return None
    # s runs from 1 (lying on its stop cell) to -1 (lying on the merge cell).
    s = -folds.turn_amount(folds.smoothstep(progress(fold, now)))
    x, y, width, height = stop_frame
    target_x, target_y = target_frame[0], target_frame[1]
    if abs(target_x - x) >= abs(target_y - y):
        middle = (x + target_x + width) / 2.0           # the middle of the gap
        hinge, axis = ((middle, y), (middle, y + height)), "x"
    else:
        middle = (y + target_y + height) / 2.0
        hinge, axis = ((x, middle), (x + width, middle)), "y"
    points = folds.turn(_rect_corners(stop_frame), hinge, s)
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    rect = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
    return rect, "front" if s >= 0 else "back", folds.shade_for(s), abs(s), axis


# --- spawns --------------------------------------------------------------------

class Spawn:
    """A new tile folding in from its cell's centre in tiny squares.

    view, cell, value  the tile view (hidden until the end), its cell and value
    pieces             boardkit SquarePieces over the cell's frame
    folds              one boardkit Fold per tiny square
    start              when the first square begins to grow
    squares_done       when the last square has landed; the number fades up
    end                when the number is fully up and the tile view shows
    """

    def __init__(self, view, cell, value, pieces, sheets, start, squares_done):
        self.view = view
        self.cell = cell
        self.value = value
        self.pieces = pieces
        self.folds = sheets
        self.start = start
        self.squares_done = squares_done
        self.end = squares_done + NUMBER_SECONDS


def plan_spawn(view, cell, value, frame, start, seed=None):
    """The Spawn for a new tile in frame (its cell's frame), starting at start."""
    pieces = folds.SquarePieces(frame, SPAWN_SQUARES, SPAWN_SQUARES, bleed=SQUARE_BLEED)
    offsets, parents, seconds = folds.scatter(
        pieces.neighbours, set(pieces.pieces()), [pieces.middle()], random.Random(seed),
        fold_seconds=SPAWN_FOLD_SECONDS, spread_seconds=SPAWN_SPREAD_SECONDS)
    sheets = folds.plan(offsets, parents, seconds, start)
    squares_done = max(fold.start + fold.seconds for fold in sheets)
    return Spawn(view, cell, value, pieces, sheets, start, squares_done)


def spawn_sheets(spawn, now):
    """[(points, shade)] for every tiny square started by now: landed ones
    flat, the rest part way through their turn."""
    drawn = []
    for fold in spawn.folds:
        if now < fold.start:
            continue
        corners = spawn.pieces.corners(fold.piece)
        if folds.done(fold, now):
            drawn.append((corners, 1.0))
            continue
        hinge = None if fold.parent is None else spawn.pieces.hinge(fold.piece, fold.parent)
        shaped = folds.shape(fold, corners, hinge, now)
        if shaped is not None:
            drawn.append((shaped[0], shaped[1]))
    return drawn


def number_alpha(spawn, now):
    """The new tile's number: 0 until its squares land, then fading up to 1."""
    return min(1.0, max(0.0, (now - spawn.squares_done) / NUMBER_SECONDS))


def spawn_done(spawn, now):
    return now >= spawn.end


# --- helpers -------------------------------------------------------------------

def _rect_corners(frame):
    x, y, width, height = frame
    return [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]


def _sign(number):
    return (number > 0) - (number < 0)