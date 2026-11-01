"""
Sudoku's board building itself on a new deal, in three parts, built on
boardkit (folds.py for the paper, paths.py for the pop). Pure Python: the
board view asks each frame what to draw; smokes/sudoku_build_smoke.py
checks the plan.

1 Unfold   plain paper squares start at a random corner cell, growing from
           its centre, and spread over the board in Fold's scatter chains:
           each cell's sheet turns over onto it from the neighbour that
           reached it first, so the front wanders instead of marching.
2 Hand-off the finishing corner is the board corner nearest the last square
           to land.
3 Numbers  after a short pause the givens pop into their cells, swelling a
           little past full size and settling, nearest the finishing corner
           first.
4 Swell    the finished board swells a little about its centre and settles.

While it plays the board hides its own numbers; they come back at the end.
"""

import math
import random

from boardkit import folds, paths


# --- editable feel -----------------------------------------------------------

BUILD_FOLD_SECONDS = 0.45     # one square's turn at full speed (Fold's own)
BUILD_SPREAD_SECONDS = 2.0    # big boards are sped up so the last square starts by then...
BUILD_MIN_SPEED = 0.3         # ...but never faster than this share of full speed
SQUARE_BLEED = 0.5            # points each square overlaps its neighbours: no seams
NUMBER_PAUSE_SECONDS = 0.10   # between the last square landing and the first number
NUMBER_POP_SECONDS = 0.36     # one number popping in
NUMBER_STEP_SECONDS = 0.07    # delay per cell of distance from the finishing corner...
NUMBER_SPREAD_SECONDS = 1.0   # ...squeezed so the furthest number starts by then
NUMBER_OVERSHOOT = 1.7        # how far a number swells past full size (0: no swell)
SWELL_PAUSE_SECONDS = 0.05    # between the last number settling and the board swelling
SWELL_SECONDS = 0.45          # the whole board swelling and settling back
SWELL_SCALE = 1.04            # how big the board grows at the top of the swell


class Build:
    """One board building itself.

    rect           (left, top, side) of the board it was planned for
    size           cells a side
    givens         {(row, col): value}
    pieces         boardkit SquarePieces, one per cell
    folds          one boardkit Fold per cell
    corner         the cell the paper starts from
    unfold_end     when the last square has landed
    finish_corner  the board corner nearest that last square; numbers start there
    number_starts  {(row, col): when that given starts popping}
    numbers_end    when the last number has settled
    swell_start    when the finished board starts to swell
    end            when the swell has settled and the build is over
    """

    def __init__(self, rect, size, givens, pieces, sheets, corner):
        self.rect = rect
        self.size = size
        self.givens = givens
        self.pieces = pieces
        self.folds = sheets
        self.corner = corner
        last = max(sheets, key=lambda fold: fold.start + fold.seconds)
        self.unfold_end = last.start + last.seconds
        self.finish_corner = nearest_corner(last.piece, size)
        self.number_starts = number_schedule(givens, self.finish_corner, self.unfold_end + NUMBER_PAUSE_SECONDS)
        latest = max(self.number_starts.values()) if self.number_starts else self.unfold_end
        self.numbers_end = max(self.unfold_end, latest + NUMBER_POP_SECONDS)
        self.swell_start = self.numbers_end + SWELL_PAUSE_SECONDS
        self.end = self.swell_start + SWELL_SECONDS


def plan_build(size, rect, givens, start, rng=None):
    """The Build for a size x size board in rect, starting at start from a random corner."""
    rng = rng or random.Random()
    left, top, side = rect
    corner = rng.choice(corners(size))
    pieces = folds.SquarePieces((left, top, side, side), size, size, bleed=SQUARE_BLEED)
    offsets, parents, seconds = folds.scatter(
        pieces.neighbours, set(pieces.pieces()), [corner], rng,
        fold_seconds=BUILD_FOLD_SECONDS, spread_seconds=BUILD_SPREAD_SECONDS,
        min_speed=BUILD_MIN_SPEED)
    return Build(rect, size, dict(givens), pieces, folds.plan(offsets, parents, seconds, start), corner)


def corners(size):
    last = size - 1
    return [(0, 0), (0, last), (last, 0), (last, last)]


def nearest_corner(cell, size):
    return min(corners(size), key=lambda corner: _distance(cell, corner))


def number_schedule(givens, origin, start):
    """{cell: start time} for each given: later the further from origin,
    squeezed so the furthest starts within NUMBER_SPREAD_SECONDS."""
    if not givens:
        return {}
    furthest = max(_distance(cell, origin) for cell in givens) or 1.0
    step = min(NUMBER_STEP_SECONDS, NUMBER_SPREAD_SECONDS / furthest)
    return {cell: start + _distance(cell, origin) * step for cell in givens}


# --- what to draw at a moment ------------------------------------------------------

def unlanded(build, now):
    """Cells whose paper has not landed yet: the board shows nothing there."""
    return [fold.piece for fold in build.folds if not folds.done(fold, now)]


def sheets(build, now):
    """[(cell, points, shade)] for every square turning at now."""
    turning = []
    for fold in build.folds:
        if now < fold.start or folds.done(fold, now):
            continue
        corners_drawn = build.pieces.corners(fold.piece)
        hinge = None if fold.parent is None else build.pieces.hinge(fold.piece, fold.parent)
        shaped = folds.shape(fold, corners_drawn, hinge, now)
        if shaped is not None:
            turning.append((fold.piece, shaped[0], shaped[1]))
    return turning


def numbers(build, now):
    """[(cell, value, scale)] for every given that has started popping:
    scale rises past 1 and settles to 1."""
    shown = []
    for cell, value in build.givens.items():
        begin = build.number_starts[cell]
        if now < begin:
            continue
        t = (now - begin) / NUMBER_POP_SECONDS
        scale = 1.0 if t >= 1.0 else paths.ease_out_back(t, NUMBER_OVERSHOOT)
        shown.append((cell, value, scale))
    return shown


def board_scale(build, now):
    """The whole board's scale at now: 1 until the swell, rising to
    SWELL_SCALE half way through it and settling back to 1."""
    if now <= build.swell_start or now >= build.end:
        return 1.0
    t = (now - build.swell_start) / SWELL_SECONDS
    return 1.0 + (SWELL_SCALE - 1.0) * math.sin(math.pi * t)


def done(build, now):
    return now >= build.end


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])