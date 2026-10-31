"""
Fold motion: when each triangle of a flood changes, and what shape is drawn
over the board while it does. Pure Python: a board view asks for shapes
each frame and draws them; smokes/fold_smoke.py checks the geometry.

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

The turning sheet is a flat (orthographic) view of a triangle rotating
about its hinge: its far corner slides along the line through the hinge's
midpoint, from the mirror image lying over the parent (s = -1) to its own
place (s = 1), with s = -cos(angle). On the triangle lattice the mirror
image is exactly the parent triangle.
"""

import heapq
import math
import random

from boardkit import paths


STYLES = ("scatter", "fold", "ripple", "instant")


# --- editable feel -----------------------------------------------------------

FOLD_SECONDS = 0.45
RIPPLE_SECONDS = 0.28
STEP_SECONDS = 0.05             # fold and ripple: delay between rings
MAX_SPREAD_SECONDS = 1.2        # fold and ripple: furthest triangle starts by then
SCATTER_HANDOFF = (0.25, 1.0)   # scatter: a child starts when its parent is this far through
SCATTER_SPREAD_SECONDS = 1.6    # scatter: big regions are sped up to start within this...
SCATTER_MIN_SPEED = 0.45        # ...but never faster than this share of normal speed
EDGE_ON_SHADE = 0.78            # brightness of a sheet seen edge-on (1 is flat on)


class Fold:
    """One triangle's change.

    colour        what the board shows under this triangle once the fold
                  has done its job (landed, or begun lifting off for undo)
    sheet_colour  the colour of the moving sheet
    reverse       True when playing a move backwards (undo)
    """

    def __init__(self, cell, parent, colour, start, seconds, style,
                 sheet_colour=None, reverse=False):
        self.cell = cell
        self.parent = parent
        self.colour = colour
        self.start = start
        self.seconds = seconds
        self.style = style
        self.sheet_colour = colour if sheet_colour is None else sheet_colour
        self.reverse = reverse


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
    move always grows the same tree (see _scatter_from)."""
    rng = random.Random(hash((move.cell, len(move.cells), move.old_colour, move.new_colour)))
    return _scatter_from(grid, set(move.cells), [move.cell], rng)


def _scatter_from(grid, region, starts, rng):
    """(offsets, parents, speed): a random spanning forest of region grown
    from the start cells, the heart of the scatter style.

    Grown like Dijkstra's algorithm with random edge weights: a child's
    start is its parent's start plus a random share of a fold. Start cells
    have no parent (their paper grows in place).

    A big region plays faster by scaling the whole animation, start times
    and fold length together, so every child still waits until its parent
    is part way over: the chain never breaks, it just runs in fast forward.
    speed (at most 1, at least SCATTER_MIN_SPEED) is that scale.
    """
    offsets = {cell: 0.0 for cell in starts}
    parents = {cell: None for cell in starts}
    settled = set()
    queue = [(0.0, order, cell) for order, cell in enumerate(starts)]
    heapq.heapify(queue)
    pushes = len(queue)
    while queue:
        offset, _, cell = heapq.heappop(queue)
        if cell in settled:
            continue
        settled.add(cell)
        for other in grid.neighbours(cell):
            if other not in region or other in settled:
                continue
            candidate = offset + FOLD_SECONDS * rng.uniform(*SCATTER_HANDOFF)
            if candidate < offsets.get(other, float("inf")):
                offsets[other] = candidate
                parents[other] = cell
                heapq.heappush(queue, (candidate, pushes, other))
                pushes += 1
    latest = max(offsets.values())
    speed = 1.0
    if latest > SCATTER_SPREAD_SECONDS:
        speed = max(SCATTER_MIN_SPEED, SCATTER_SPREAD_SECONDS / latest)
    offsets = {cell: offset * speed for cell, offset in offsets.items()}
    return offsets, parents, speed


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
        eased = smoothstep(t)
        hinge = corners[k]
        apex = corners[(k + 1) % 6]
        if k == 0:
            points = [(centre[0] + (x - centre[0]) * eased, centre[1] + (y - centre[1]) * eased)
                      for x, y in (centre, hinge, apex)]
            triangles.append((points, 1.0))
            continue
        turn = -math.cos(math.pi * eased)
        foot = ((centre[0] + hinge[0]) / 2, (centre[1] + hinge[1]) / 2)
        tip = (foot[0] + turn * (apex[0] - foot[0]), foot[1] + turn * (apex[1] - foot[1]))
        triangles.append(([centre, hinge, tip], EDGE_ON_SHADE + (1 - EDGE_ON_SHADE) * abs(turn)))
    text_start = 5 * CARD_TRIANGLE_GAP + CARD_TRIANGLE_SECONDS
    text_alpha = min(1.0, max(0.0, (elapsed - text_start) / CARD_TEXT_SECONDS))
    return triangles, text_alpha


def progress(fold, now):
    """0 before the fold starts, 1 once it has finished."""
    if fold.seconds <= 0:
        return 1.0 if now >= fold.start else 0.0
    return min(1.0, max(0.0, (now - fold.start) / fold.seconds))


def done(fold, now):
    return now >= fold.start + fold.seconds


def shows_new_colour(fold, now):
    """Whether the board under this triangle shows fold.colour yet.

    A forward hinged fold covers the old colour until its sheet lands.
    Undo, ripple and instant change it as soon as their turn comes.
    Landing uses the same test as done(), so the two never disagree by a
    rounding error.
    """
    if fold.style in ("scatter", "fold") and not fold.reverse:
        return done(fold, now)
    return now >= fold.start


# --- shapes ------------------------------------------------------------------

def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def shape(grid, fold, now):
    """(points, shade) to draw in fold.sheet_colour over the board at now, or None.

    shade multiplies the colour's brightness: 1 for flat paper.
    """
    if fold.style == "instant" or now < fold.start:
        return None
    t = progress(fold, now)
    if t >= 1.0:
        return None
    drawn = grid.corners(fold.cell)
    centre = _centroid(drawn)
    if fold.style == "ripple":
        return _scaled(drawn, centre, paths.pulse_scale(now - fold.start, fold.seconds)), 1.0
    eased = smoothstep(1.0 - t if fold.reverse else t)
    if fold.parent is None:
        return _scaled(drawn, centre, eased), 1.0
    hinge, apex = hinge_and_apex(grid, fold.cell, fold.parent)
    turn = -math.cos(math.pi * eased)
    foot = ((hinge[0][0] + hinge[1][0]) / 2, (hinge[0][1] + hinge[1][1]) / 2)
    tip = (foot[0] + turn * (apex[0] - foot[0]), foot[1] + turn * (apex[1] - foot[1]))
    shade = EDGE_ON_SHADE + (1 - EDGE_ON_SHADE) * abs(turn)
    return [hinge[0], hinge[1], tip], shade


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
