"""
Fold motion: when each triangle of a flood changes, and what shape is drawn
over the board while it does. Pure Python: a board view asks for shapes
each frame and draws them; smokes/fold_smoke.py checks the geometry.

The paper itself (scatter chains, hinged turns, sheets growing from their
centre) lives in boardkit/folds.py, shared with the other games; this
module keeps what is Fold's own: its styles and feel, triangle hinges, the
winning finale and the hexagon card. smokes/fold_motion_parity_smoke.py
proved the move onto boardkit changed nothing on screen (2026-11-01).

Styles:
    scatter  KAMI-style chain folding. Each region gets a random spanning
             tree; a triangle folds over from its tree parent once the
             parent is part way through its own fold, so paper chains along
             branching paths and the front wanders instead of marching.
    fold     the same hinged folds, spreading in even rings outwards.
    ripple   colours change outwards ring by ring; each triangle swells as
             it changes.
    instant  the whole region changes at once.

In scatter and fold, each triangle's new paper turns over onto it hinged on
the edge it shares with its parent; the tapped triangle's paper grows from
its centre. Seen edge-on mid-turn, the sheet is shaded darker, like paper
catching the light.

plan() plays a move forwards; plan_undo() plays it backwards, last fold
first, each sheet lifting off and turning back onto the triangle it came
from with the old colour underneath. Scatter seeds its randomness from the
move, so undo replays exactly the same tree.
"""

import math
import random

from boardkit import folds, paths


STYLES = ("scatter", "fold", "ripple", "instant")


# --- editable feel -----------------------------------------------------------

FOLD_SECONDS = 0.45
RIPPLE_SECONDS = 0.28
STEP_SECONDS = 0.05             # fold and ripple: delay between rings
MAX_SPREAD_SECONDS = 1.2        # fold and ripple: furthest triangle starts by then
SCATTER_HANDOFF = (0.25, 1.0)   # scatter: a child starts when its parent is this far through
SCATTER_SPREAD_SECONDS = 1.6    # scatter: big regions are sped up to start within this...
SCATTER_MIN_SPEED = 0.45        # ...but never faster than this share of normal speed

EDGE_ON_SHADE = folds.EDGE_ON_SHADE   # boardkit's edge-on brightness, named here for older callers


class Fold(folds.Fold):
    """One triangle's change: a boardkit Fold whose piece is a triangle cell,
    plus Fold's style.

    colour        what the board shows under this triangle once the fold
                  has done its job (landed, or begun lifting off for undo)
    sheet_colour  the colour of the moving sheet
    reverse       True when playing a move backwards (undo)
    """

    def __init__(self, cell, parent, colour, start, seconds, style,
                 sheet_colour=None, reverse=False):
        super().__init__(cell, parent, start, seconds, colour, sheet_colour, reverse)
        self.style = style

    @property
    def cell(self):
        return self.piece

    @cell.setter
    def cell(self, value):
        self.piece = value


# --- timing ------------------------------------------------------------------

def _schedule(move, style, grid):
    """(offsets, parents, seconds): when each cell starts after the move
    begins, which cell it hinges on, and how long each fold takes."""
    if style not in STYLES:
        raise ValueError("style must be one of {}, not {!r}".format(STYLES, style))
    if style == "scatter":
        if grid is None:
            raise ValueError("scatter needs the grid to grow its tree")
        offsets, parents, speed = _scatter_tree(move, grid)
        return offsets, parents, FOLD_SECONDS * speed
    seconds = {"fold": FOLD_SECONDS, "ripple": RIPPLE_SECONDS, "instant": 0.0}[style]
    furthest = max(move.steps) or 1
    step = 0.0 if style == "instant" else min(STEP_SECONDS, MAX_SPREAD_SECONDS / furthest)
    offsets = {cell: steps * step for cell, steps in zip(move.cells, move.steps)}
    parents = dict(zip(move.cells, move.parents))
    return offsets, parents, seconds


def _scatter_tree(move, grid):
    """(offsets, parents, speed) for a random spanning tree of the move's
    region, grown from the tapped cell. Seeded from the move, so the same
    move always grows the same tree."""
    rng = random.Random(hash((move.cell, len(move.cells), move.old_colour, move.new_colour)))
    return _scatter_from(grid, set(move.cells), [move.cell], rng)


def _scatter_from(grid, region, starts, rng):
    """(offsets, parents, speed): boardkit's scatter forest over the triangle
    grid with Fold's feel. speed (at most 1, at least SCATTER_MIN_SPEED) is
    how much a big region was sped up."""
    offsets, parents, seconds = folds.scatter(
        grid.neighbours, region, starts, rng, fold_seconds=FOLD_SECONDS, handoff=SCATTER_HANDOFF,
        spread_seconds=SCATTER_SPREAD_SECONDS, min_speed=SCATTER_MIN_SPEED)
    return offsets, parents, seconds / FOLD_SECONDS


def plan(move, now, style="scatter", grid=None):
    """The Folds that play a rules.Move from now. Scatter needs the grid."""
    if not move.cells:
        return []
    offsets, parents, seconds = _schedule(move, style, grid)
    return [Fold(cell, parents[cell], move.new_colour, now + offsets[cell], seconds, style)
            for cell in move.cells]


def plan_undo(move, now, style="scatter", grid=None):
    """The Folds that play a rules.Move backwards from now, last fold first.

    Each sheet is the move's colour lifting off and turning back onto the
    triangle it came from; the board shows the old colour underneath.
    """
    if not move.cells:
        return []
    offsets, parents, seconds = _schedule(move, style, grid)
    latest = max(offsets.values())
    return [Fold(cell, parents[cell], move.old_colour, now + latest - offsets[cell], seconds, style,
                 sheet_colour=move.new_colour, reverse=True)
            for cell in move.cells]


# --- the winning finale ----------------------------------------------------------------
# Once the board is one colour, every triangle folds over to a new colour, in
# the same scatter chains as a move, closing in from the board's edge; then a
# hexagon card unfolds from the middle, one triangle at a time, and its words
# fade in.

FINALE_STARTS = 6                # edge cells the closing chains start from
CARD_TRIANGLE_SECONDS = 0.24     # each of the card's six triangles unfolding
CARD_TRIANGLE_GAP = 0.11         # delay from one card triangle to the next
CARD_TEXT_SECONDS = 0.3          # words fading in once the hexagon is whole
CARD_TOTAL_SECONDS = 5 * CARD_TRIANGLE_GAP + CARD_TRIANGLE_SECONDS + CARD_TEXT_SECONDS


def plan_finale(grid, colour, now, seed=0):
    """Folds turning every cell to colour, in exactly the scatter style of a
    move: the same random chains, handoffs and speed-up as a big flood. The
    chains start from FINALE_STARTS cells spread round the board's edge, so
    the paper closes in on the middle."""
    rng = random.Random(seed)
    starts = finale_starts(grid, rng)
    offsets, parents, speed = _scatter_from(grid, set(grid.cells()), starts, rng)
    return [Fold(cell, parents[cell], colour, now + offsets[cell], FOLD_SECONDS * speed, "scatter")
            for cell in grid.cells()]


def finale_starts(grid, rng, count=None):
    """count edge cells spaced evenly round the board, from a random point."""
    count = count or FINALE_STARTS
    centre_strip, centre_slot = (grid.strips - 1) / 2.0, (grid.slots - 1) / 2.0
    edge = [cell for cell in grid.cells() if len(grid.neighbours(cell)) < 3]
    edge.sort(key=lambda cell: math.atan2(cell[0] - centre_strip, (cell[1] - centre_slot) / 2.0))
    first = rng.randrange(len(edge))
    return [edge[(first + index * len(edge) // count) % len(edge)] for index in range(count)]


def hexagon_corners(centre, radius):
    """The six corners of a flat-topped hexagon, starting at the right."""
    return [(centre[0] + radius * math.cos(math.radians(60 * k)),
             centre[1] + radius * math.sin(math.radians(60 * k))) for k in range(6)]


def card_unfold(centre, radius, elapsed):
    """(triangles, text_alpha) for the result card elapsed seconds after it began.

    triangles lists (points, shade) for each of the hexagon's six triangles
    that has started: the first grows from the centre, and each next one
    turns over from the one before, hinged on the spoke they share.
    """
    corners = hexagon_corners(centre, radius)
    triangles = []
    for k in range(6):
        t = (elapsed - k * CARD_TRIANGLE_GAP) / CARD_TRIANGLE_SECONDS
        if t <= 0:
            break
        eased = folds.smoothstep(t)
        hinge = corners[k]
        apex = corners[(k + 1) % 6]
        if k == 0:
            points = [(centre[0] + (x - centre[0]) * eased, centre[1] + (y - centre[1]) * eased)
                      for x, y in (centre, hinge, apex)]
            triangles.append((points, 1.0))
            continue
        s = folds.turn_amount(eased)
        triangles.append((folds.turn([centre, hinge, apex], (centre, hinge), s), folds.shade_for(s)))
    text_start = 5 * CARD_TRIANGLE_GAP + CARD_TRIANGLE_SECONDS
    text_alpha = min(1.0, max(0.0, (elapsed - text_start) / CARD_TEXT_SECONDS))
    return triangles, text_alpha


def progress(fold, now):
    """0 before the fold starts, 1 once it has finished."""
    return folds.progress(fold, now)


def done(fold, now):
    return folds.done(fold, now)


def shows_new_colour(fold, now):
    """Whether the board under this triangle shows fold.colour yet.

    A forward hinged fold covers the old colour until its sheet lands.
    Undo, ripple and instant change it as soon as their turn comes.
    Landing uses the same test as done(), so the two never disagree by a
    rounding error.
    """
    if fold.style in ("scatter", "fold") and not fold.reverse:
        return folds.done(fold, now)
    return now >= fold.start


# --- shapes ------------------------------------------------------------------

smoothstep = folds.smoothstep


def shape(grid, fold, now):
    """(points, shade) to draw in fold.sheet_colour over the board at now, or None.

    shade multiplies the colour's brightness: 1 for flat paper. A hinged
    sheet's points are [hinge corner, hinge corner, tip].
    """
    if fold.style == "instant" or now < fold.start:
        return None
    t = progress(fold, now)
    if t >= 1.0:
        return None
    drawn = grid.corners(fold.cell)
    if fold.style == "ripple":
        return _scaled(drawn, _centroid(drawn), paths.pulse_scale(now - fold.start, fold.seconds)), 1.0
    if fold.parent is None:
        shaped = folds.shape(fold, drawn, None, now)
    else:
        hinge, apex = hinge_and_apex(grid, fold.cell, fold.parent)
        shaped = folds.shape(fold, [hinge[0], hinge[1], apex], hinge, now)
    if shaped is None:
        return None
    points, shade, _ = shaped
    return points, shade


def hinge_and_apex(grid, cell, parent):
    """cell's two drawn corners on the edge it shares with parent, and its third corner."""
    exact = grid.corners(cell, gap=0)
    parent_exact = grid.corners(parent, gap=0)
    drawn = grid.corners(cell)
    near = 1e-6 * max(1.0, grid.side)
    shared = [index for index, point in enumerate(exact)
              if any(abs(point[0] - other[0]) < near and abs(point[1] - other[1]) < near
                     for other in parent_exact)]
    if len(shared) != 2:
        raise ValueError("{} and {} do not share an edge".format(cell, parent))
    apex_index = 3 - sum(shared)
    return [drawn[index] for index in shared], drawn[apex_index]


def _centroid(points):
    return (sum(x for x, y in points) / 3.0, sum(y for x, y in points) / 3.0)


def _scaled(points, centre, factor):
    return [(centre[0] + (x - centre[0]) * factor, centre[1] + (y - centre[1]) * factor)
            for x, y in points]