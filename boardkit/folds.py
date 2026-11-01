"""
Folds for boardkit: paper sheets turning over onto board pieces. The
animation Fold made (games/fold/fold_motion.py), taken out so any board can
use it. Pure Python, checked by smokes/boardkit_folds_smoke.py.

Pieces are whatever a board calls its cells: triangles, squares, or tiny
squares cut from one tile. folds never looks inside them. A board hands it

    neighbours(piece)   the pieces sharing an edge with piece
    corners(piece)      the piece's polygon as (x, y) points

and gets back, each frame, the polygon to draw for every sheet in motion.

When   scatter() grows a random spanning forest from start pieces (Fold's
       KAMI-style chains): a piece starts once the piece it hinges on is
       part way over, so the front wanders instead of marching.
How    turn() is a flat (orthographic) view of a polygon rotating about a
       hinge line: every corner keeps its foot on the hinge and its offset
       from the hinge is multiplied by s, from -1 (mirrored over the
       parent) through 0 (edge-on) to 1 (in place). On a lattice the mirror
       image is exactly the parent. A start piece has no parent: its paper
       grows from its centre.

Seen edge-on a sheet is shaded darker, like paper catching the light.
"""

import heapq
import math


# --- editable feel -----------------------------------------------------------

FOLD_SECONDS = 0.45             # one sheet's turn, at full speed
SCATTER_HANDOFF = (0.25, 1.0)   # a child starts when its parent is this far through
SCATTER_SPREAD_SECONDS = 1.6    # big regions are sped up so the last start is by then...
SCATTER_MIN_SPEED = 0.45        # ...but never faster than this share of normal speed
EDGE_ON_SHADE = 0.78            # brightness of a sheet seen edge-on (1 is flat on)


class Fold:
    """One piece's sheet.

    piece         the piece it lands on
    parent        the piece it turns over from, or None to grow from its centre
    colour        what the board shows under the piece once the sheet has
                  done its job (landed, or begun lifting off for undo)
    sheet_colour  the moving sheet's colour
    reverse       True when playing backwards (undo): the sheet lifts off
                  and turns back onto its parent
    """

    def __init__(self, piece, parent, start, seconds, colour=None, sheet_colour=None, reverse=False):
        self.piece = piece
        self.parent = parent
        self.start = start
        self.seconds = seconds
        self.colour = colour
        self.sheet_colour = colour if sheet_colour is None else sheet_colour
        self.reverse = reverse


# --- when ----------------------------------------------------------------------

def scatter(neighbours, region, starts, rng, fold_seconds=FOLD_SECONDS, handoff=SCATTER_HANDOFF,
            spread_seconds=SCATTER_SPREAD_SECONDS, min_speed=SCATTER_MIN_SPEED):
    """(offsets, parents, seconds): a random spanning forest of region grown
    from the start pieces.

    offsets   piece -> seconds after the move begins that its sheet starts
    parents   piece -> the piece it turns over from (None for start pieces)
    seconds   how long each sheet takes

    Grown like Dijkstra's algorithm with random edge weights: a child's start
    is its parent's start plus a random share (handoff) of a turn. A big
    region plays faster by scaling start times and turn length together, so
    every child still waits until its parent is part way over: the chain
    never breaks, it just runs in fast forward.
    """
    offsets = {piece: 0.0 for piece in starts}
    parents = {piece: None for piece in starts}
    settled = set()
    queue = [(0.0, order, piece) for order, piece in enumerate(starts)]
    heapq.heapify(queue)
    pushes = len(queue)
    while queue:
        offset, _, piece = heapq.heappop(queue)
        if piece in settled:
            continue
        settled.add(piece)
        for other in neighbours(piece):
            if other not in region or other in settled:
                continue
            candidate = offset + fold_seconds * rng.uniform(*handoff)
            if candidate < offsets.get(other, float("inf")):
                offsets[other] = candidate
                parents[other] = piece
                heapq.heappush(queue, (candidate, pushes, other))
                pushes += 1
    latest = max(offsets.values())
    speed = 1.0
    if latest > spread_seconds:
        speed = max(min_speed, spread_seconds / latest)
    offsets = {piece: offset * speed for piece, offset in offsets.items()}
    return offsets, parents, fold_seconds * speed


def plan(offsets, parents, seconds, now, colour=None, sheet_colour=None, reverse=False):
    """The Folds for a schedule from scatter(), starting now. Reversed, the
    last sheet to land is the first to lift off."""
    latest = max(offsets.values()) if offsets else 0.0
    folds = []
    for piece, offset in offsets.items():
        start = now + (latest - offset if reverse else offset)
        folds.append(Fold(piece, parents[piece], start, seconds, colour, sheet_colour, reverse))
    return folds


def progress(fold, now):
    """0 before the sheet starts, 1 once it has finished."""
    if fold.seconds <= 0:
        return 1.0 if now >= fold.start else 0.0
    return min(1.0, max(0.0, (now - fold.start) / fold.seconds))


def done(fold, now):
    return now >= fold.start + fold.seconds


def landed(fold, now):
    """Whether the board under this piece shows fold.colour yet: once the
    sheet lands, or for undo as soon as it starts lifting off."""
    return now >= fold.start if fold.reverse else done(fold, now)


# --- how -----------------------------------------------------------------------

def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def turn_amount(eased):
    """s for a sheet eased this far over: -1 mirrored over its parent, 1 in place."""
    return -math.cos(math.pi * eased)


def shade_for(s):
    """Brightness multiplier for a sheet at s: 1 flat on, EDGE_ON_SHADE edge-on."""
    return EDGE_ON_SHADE + (1 - EDGE_ON_SHADE) * abs(s)


def turn(points, hinge, s):
    """points turned about the line through hinge's two points, seen flat on:
    each point's offset from its foot on the hinge is multiplied by s."""
    (ax, ay), (bx, by) = hinge
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        raise ValueError("a hinge needs two different points")
    turned = []
    for x, y in points:
        along = ((x - ax) * dx + (y - ay) * dy) / length_squared
        foot_x, foot_y = ax + along * dx, ay + along * dy
        turned.append((foot_x + s * (x - foot_x), foot_y + s * (y - foot_y)))
    return turned


def grow(points, amount):
    """points scaled about their centre by amount (0 a dot, 1 full size)."""
    centre_x = sum(x for x, _ in points) / float(len(points))
    centre_y = sum(y for _, y in points) / float(len(points))
    return [(centre_x + (x - centre_x) * amount, centre_y + (y - centre_y) * amount) for x, y in points]


def shape(fold, corners, hinge, now):
    """(points, shade, s) to draw in fold.sheet_colour at now, or None
    before the sheet starts and once it has finished.

    corners is the piece's drawn polygon; hinge is the two points of the
    line it turns about (the edge it shares with its parent), or None for a
    piece that grows from its centre. s is the turn amount (1 for growing).
    """
    if now < fold.start or done(fold, now):
        return None     # done(), not progress() == 1, so landing and shape always agree
    t = progress(fold, now)
    eased = smoothstep(1.0 - t if fold.reverse else t)
    if fold.parent is None or hinge is None:
        return grow(corners, eased), 1.0, 1.0
    s = turn_amount(eased)
    return turn(corners, hinge, s), shade_for(s), s


def shared_edge(corners_a, corners_b, tolerance=1e-6):
    """The two corners polygon a shares with polygon b, or None when they do
    not share an edge. Compare exact corners, not ones grown for drawing."""
    shared = [point for point in corners_a
              if any(abs(point[0] - x) <= tolerance and abs(point[1] - y) <= tolerance
                     for x, y in corners_b)]
    return shared if len(shared) == 2 else None


# --- tiny squares ------------------------------------------------------------

class SquarePieces:
    """A frame cut into rows x cols squares, as fold pieces (row, col).

    bleed widens each drawn square by that many points on every side, so
    neighbouring squares overlap and show no seams; hinges use exact edges.
    """

    def __init__(self, frame, rows, cols, bleed=0.0):
        self.x, self.y, width, height = frame
        self.rows = rows
        self.cols = cols
        self.width = width / float(cols)
        self.height = height / float(rows)
        self.bleed = bleed

    def pieces(self):
        return [(row, col) for row in range(self.rows) for col in range(self.cols)]

    def corners(self, piece, bleed=None):
        bleed = self.bleed if bleed is None else bleed
        row, col = piece
        left = self.x + col * self.width
        top = self.y + row * self.height
        right, bottom = left + self.width, top + self.height
        return [(left - bleed, top - bleed), (right + bleed, top - bleed),
                (right + bleed, bottom + bleed), (left - bleed, bottom + bleed)]

    def neighbours(self, piece):
        row, col = piece
        found = []
        for other_row, other_col in ((row - 1, col), (row + 1, col), (row, col - 1), (row, col + 1)):
            if 0 <= other_row < self.rows and 0 <= other_col < self.cols:
                found.append((other_row, other_col))
        return found

    def hinge(self, piece, other):
        """The edge piece shares with other, or None."""
        tolerance = 1e-6 * max(1.0, self.width, self.height)
        return shared_edge(self.corners(piece, 0.0), self.corners(other, 0.0), tolerance)

    def middle(self):
        """The middle square (the lower-right of the middle four when even)."""
        return (self.rows // 2, self.cols // 2)