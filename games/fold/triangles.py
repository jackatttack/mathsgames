"""
Triangle board geometry for Fold: which triangles touch, where each one
sits in a board view, and which triangle a touch lands on.

Pure Python with no ui import, so it runs headless in smokes and the same
in Pythonista and PythonIDE. A board view keeps one TriangleGrid, calls
resize() from its layout(), and asks it for corners and cells. Kept beside
Fold until a second game wants triangles; then it moves to boardkit.

A board is a stack of strips. Each strip is a run of equilateral triangles
that point alternately out and back, sharing their slanted edges:

    "rows"     strips run left to right; triangles point up and down
    "columns"  strips run top to bottom; triangles point left and right
               (KAMI's layout, and the better fit for a tall phone)

A cell is (strip, slot): strip counts strips from the top ("rows") or from
the left ("columns"); slot counts along the strip. A cell points out (up,
or left) when strip + slot is even, so (0, 0) points out.

The geometry is worked out once in flat coordinates (along, across): along
the strip and across the strips, as in the "rows" picture. "columns" is the
same picture reflected in the diagonal, which just swaps x and y.

    side     a triangle's edge length
    depth    a strip's thickness, side * sqrt(3) / 2
    slot k   starts k * side / 2 along its strip
"""

import math


ORIENTATIONS = ("rows", "columns")
DEPTH_PER_SIDE = math.sqrt(3) / 2
INRADIUS_PER_SIDE = 1 / (2 * math.sqrt(3))   # centre to edge, per unit of side


class TriangleGrid:
    """A board of strips x slots triangles fitted into a view of a given size."""

    def __init__(self, strips, slots, orientation="columns", margin=0.0, gap=0.0):
        """
        strips       how many strips of triangles
        slots        triangles in each strip
        orientation  "rows" or "columns" (see the module docstring)
        margin       points kept clear on every side of the board
        gap          points between neighbouring triangles when drawn
        """
        if orientation not in ORIENTATIONS:
            raise ValueError("orientation must be one of {}, not {!r}".format(ORIENTATIONS, orientation))
        if strips < 1 or slots < 1:
            raise ValueError("a triangle grid needs at least one strip and one slot")
        self.strips = strips
        self.slots = slots
        self.orientation = orientation
        self.margin = margin
        self.gap = gap
        self.view_width = 0.0
        self.view_height = 0.0
        self.side = 0.0
        self.left = 0.0
        self.top = 0.0

    # --- which triangles touch -------------------------------------------------

    def cells(self):
        """Every cell, strip by strip."""
        return [(strip, slot) for strip in range(self.strips) for slot in range(self.slots)]

    def contains(self, cell):
        strip, slot = cell
        return 0 <= strip < self.strips and 0 <= slot < self.slots

    def points_out(self, cell):
        """True for a triangle pointing up ("rows") or left ("columns")."""
        return (cell[0] + cell[1]) % 2 == 0

    def neighbours(self, cell):
        """The cells sharing an edge with cell: two along its strip, one across.

        An outward triangle's flat edge faces the next strip; an inward
        one's faces the strip before.
        """
        strip, slot = cell
        across = strip + 1 if self.points_out(cell) else strip - 1
        candidates = ((strip, slot - 1), (strip, slot + 1), (across, slot))
        return [other for other in candidates if self.contains(other)]

    def index_of(self, cell):
        """A cell's number, 0 for (0, 0), counting along each strip."""
        strip, slot = cell
        return strip * self.slots + slot

    def cell_of(self, index):
        return divmod(index, self.slots)

    # --- fitting the view ------------------------------------------------------

    def resize(self, width, height):
        """Fit the board to a view this size. Call it from the view's layout()."""
        self.view_width, self.view_height = width, height
        self._fit()

    def _fit(self):
        """The largest side that fits; the board is centred left to right and
        sits against the top margin, like boardkit.grid."""
        room_width = max(0.0, self.view_width - 2 * self.margin)
        room_height = max(0.0, self.view_height - 2 * self.margin)
        if self.orientation == "rows":
            along_room, across_room = room_width, room_height
        else:
            along_room, across_room = room_height, room_width
        side = min(along_room / ((self.slots + 1) / 2.0),
                   across_room / (self.strips * DEPTH_PER_SIDE))
        self.side = max(0.0, side)
        width, height = self.board_size()
        self.left = (self.view_width - width) / 2
        self.top = self.margin

    def flat_size(self):
        """(along, across) extent of the whole board."""
        return ((self.slots + 1) * self.side / 2, self.strips * self.side * DEPTH_PER_SIDE)

    def board_size(self):
        """(width, height) of the whole board in the view."""
        along, across = self.flat_size()
        if self.orientation == "rows":
            return (along, across)
        return (across, along)

    def board_frame(self):
        """The board's bounding frame: what a board background fills."""
        width, height = self.board_size()
        return (self.left, self.top, width, height)

    def trimmed_frame(self):
        """The board cut straight across the ends of its strips, as KAMI's
        boards are. Half of each end triangle shows, and it stays tappable;
        a board view clips to this frame."""
        half = self.side / 2
        start, end = half, self.slots * half
        across = self.strips * self.side * DEPTH_PER_SIDE
        if self.orientation == "rows":
            return (self.left + start, self.top, end - start, across)
        return (self.left, self.top + start, across, end - start)

    # --- drawing ---------------------------------------------------------------

    def flat_corners(self, cell, side=1.0):
        """Three corners in flat (along, across) coordinates for a triangle of this side.

        Side 1 by default: what patterns measure, whatever the view size.
        An outward triangle's apex comes first.
        """
        strip, slot = cell
        half = side / 2
        depth = side * DEPTH_PER_SIDE
        start = slot * half
        near = strip * depth
        far = near + depth
        if self.points_out(cell):
            return ((start + half, near), (start + side, far), (start, far))
        return ((start, near), (start + side, near), (start + half, far))

    def _flat_corners(self, cell):
        """Three corners in flat coordinates at the fitted side."""
        return self.flat_corners(cell, self.side)

    def _to_view(self, point):
        along, across = point
        if self.orientation == "rows":
            return (self.left + along, self.top + across)
        return (self.left + across, self.top + along)

    def corners(self, cell, gap=None):
        """The triangle's three corners in view coordinates.

        A positive gap shrinks the triangle towards its centre so neighbours
        sit gap points apart. A small negative gap bleeds it slightly past
        its edges, so touching triangles overlap and no anti-aliasing seam
        shows between them. Pass gap to draw with another gap for a moment.
        """
        points = [self._to_view(point) for point in self._flat_corners(cell)]
        if gap is None:
            gap = self.gap
        inradius = self.side * INRADIUS_PER_SIDE
        if gap == 0 or inradius <= 0:
            return points
        scale = max(0.0, (inradius - gap / 2) / inradius)
        centre_x, centre_y = _centroid(points)
        return [(centre_x + (x - centre_x) * scale, centre_y + (y - centre_y) * scale)
                for x, y in points]

    def centre(self, cell):
        """The triangle's centre (centroid) in view coordinates."""
        return _centroid([self._to_view(point) for point in self._flat_corners(cell)])

    def frame(self, cell, gap=None):
        """The (x, y, width, height) box around the triangle: where a view
        drawing just this triangle sits."""
        points = self.corners(cell, gap)
        xs = [x for x, y in points]
        ys = [y for x, y in points]
        return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))

    # --- touches ---------------------------------------------------------------

    def cell_at(self, point):
        """The cell under a view point, or None off the board.

        Gaps are only drawn, never part of the geometry, so a touch between
        two triangles still lands on one of them.
        """
        if self.side <= 0:
            return None
        x, y = point
        if self.orientation == "rows":
            flat = (x - self.left, y - self.top)
        else:
            flat = (y - self.top, x - self.left)
        return self.flat_cell_at(flat, self.side)

    def flat_cell_at(self, point, side=1.0):
        """The cell whose triangle (at this side) holds a flat (along, across) point, or None."""
        along, across = point
        if side <= 0 or along < 0 or across < 0:
            return None
        strip = int(across // (side * DEPTH_PER_SIDE))
        if strip >= self.strips:
            return None
        nearest_slot = int(along // (side / 2))
        tolerance = 1e-9 * max(1.0, side * side)
        for slot in (nearest_slot, nearest_slot - 1):
            cell = (strip, slot)
            if self.contains(cell) and _inside(point, self.flat_corners(cell, side), tolerance):
                return cell
        return None


def _centroid(points):
    return (sum(x for x, y in points) / 3.0, sum(y for x, y in points) / 3.0)


def _inside(point, triangle, tolerance):
    """True when point lies in the triangle or on its edge."""
    px, py = point
    turns = []
    for index in range(3):
        ax, ay = triangle[index]
        bx, by = triangle[(index + 1) % 3]
        turns.append((bx - ax) * (py - ay) - (by - ay) * (px - ax))
    return min(turns) >= -tolerance or max(turns) <= tolerance
