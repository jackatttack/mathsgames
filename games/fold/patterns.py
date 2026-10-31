"""
Fold patterns: designed boards like KAMI's player creations, built from
the geometry of the triangle lattice rather than grown at random.

Every pattern colours a cell from where its centre sits relative to a
lattice corner near the middle of the board, measured in flat coordinates
with a side of 1 (TriangleGrid.flat_corners). Three families of lattice
lines run through the board, along the strips and at 60 degrees either
side, so the natural shapes are hexagons, diamonds and the rhombus faces
of stacked cubes. Every boundary below runs along lattice lines, so no
triangle is ever cut by one.

    rings     concentric hexagons, colours repeating outwards
    spiral    rings stepped round six 60-degree sectors: a hexagonal pinwheel
    star      diamonds radiating from the centre: a lone-star quilt
    cubes     tumbling blocks: each cube three rhombus faces (uses 3 colours)
    chevrons  zigzag bands across the board
    stripes   straight bands along one lattice direction

Colours are numbers 0..colour_count-1, as in rules; palettes paint them.
The same arguments and rng seed always give the same board; rng picks
colour order, band widths and the like.
"""

import math
import random

from games.fold.triangles import DEPTH_PER_SIDE


DEPTH = DEPTH_PER_SIDE    # spacing of parallel lattice lines when the side is 1

# Unit normals to the three edge directions (0, 60 and 120 degrees).
NORMALS = tuple((math.cos(math.radians(angle)), math.sin(math.radians(angle)))
                for angle in (90, 30, 150))


# --- measuring a cell ----------------------------------------------------------

def centroid(points):
    return (sum(x for x, y in points) / 3.0, sum(y for x, y in points) / 3.0)


def lattice_centre(grid):
    """A lattice corner near the middle of the board, in flat coordinates.

    Corners on lattice line j sit at along = i + (j + 1) / 2 for whole i.
    """
    j = grid.strips // 2
    i = round((grid.slots + 1) / 4.0 - 0.5 * (j + 1))
    return (i + 0.5 * (j + 1), j * DEPTH)


def lattice_numbers(point):
    """(i, j) for a flat lattice corner (the inverse of lattice_centre's rule)."""
    x, y = point
    j = int(round(y / DEPTH))
    return (int(round(x - 0.5 * (j + 1))), j)


def offset_from(grid, cell, centre):
    x, y = centroid(grid.flat_corners(cell))
    return (x - centre[0], y - centre[1])


def hex_radius(offset):
    """Distance from the centre in hexagon rings: 0 for the six triangles
    round the centre corner, 1 for the next eighteen, and so on (as a float)."""
    return max(abs(offset[0] * nx + offset[1] * ny) for nx, ny in NORMALS) / DEPTH


def sector(offset):
    """Which of the six 60-degree wedges round the centre (0-5)."""
    angle = math.degrees(math.atan2(offset[1], offset[0])) % 360
    return int(angle // 60) % 6


def wedge_coordinates(offset, wedge):
    """(a, b) with offset = a * u + b * v, where u and v run along the
    wedge's two edges. Whole a and b mark lattice lines."""
    u_angle = math.radians(60 * wedge)
    v_angle = math.radians(60 * (wedge + 1))
    ux, uy = math.cos(u_angle), math.sin(u_angle)
    vx, vy = math.cos(v_angle), math.sin(v_angle)
    determinant = ux * vy - uy * vx
    a = (offset[0] * vy - offset[1] * vx) / determinant
    b = (ux * offset[1] - uy * offset[0]) / determinant
    return a, b


# --- patterns: each makes painter(cell) -> band number -----------------------

def _rings(grid, centre, rng):
    def painter(cell):
        return int(hex_radius(offset_from(grid, cell, centre)))
    return painter


def _spiral(grid, centre, rng):
    turn = rng.choice((1, -1))

    def painter(cell):
        offset = offset_from(grid, cell, centre)
        return int(hex_radius(offset)) + turn * sector(offset)
    return painter


def _star(grid, centre, rng):
    def painter(cell):
        offset = offset_from(grid, cell, centre)
        a, b = wedge_coordinates(offset, sector(offset))
        return int(math.floor(a + 1e-9)) + int(math.floor(b + 1e-9))
    return painter


def _cubes(grid, centre, rng):
    """Every triangle has one corner of each of three lattice classes; the
    six triangles round each class-0 corner pair up into three rhombi, the
    cube's faces."""
    corner_class = rng.randrange(3)
    pairing = rng.randrange(2)

    def painter(cell):
        corners = grid.flat_corners(cell)
        middle = centroid(corners)
        for corner in corners:
            i, j = lattice_numbers(corner)
            if (i - j - corner_class) % 3 == 0:
                offset = (middle[0] - corner[0], middle[1] - corner[1])
                return ((sector(offset) + pairing) % 6) // 2
        raise AssertionError("a triangle with no corner of each class")
    return painter


def _chevrons(grid, centre, rng):
    width = rng.choice((1, 2))

    def painter(cell):
        x, y = offset_from(grid, cell, centre)
        rise = max(x * NORMALS[1][0] + y * NORMALS[1][1], x * NORMALS[2][0] + y * NORMALS[2][1])
        return int(math.floor(rise / (width * DEPTH)))
    return painter


def _stripes(grid, centre, rng):
    width = rng.choice((1, 2))
    normal = rng.choice(NORMALS)

    def painter(cell):
        x, y = offset_from(grid, cell, centre)
        return int(math.floor((x * normal[0] + y * normal[1]) / (width * DEPTH)))
    return painter


PATTERNS = {
    "rings": _rings,
    "spiral": _spiral,
    "star": _star,
    "cubes": _cubes,
    "chevrons": _chevrons,
    "stripes": _stripes,
}


def paint(name, grid, colour_count, rng=None):
    """Colour numbers for every cell of grid (by index) in the named pattern."""
    if name not in PATTERNS:
        raise ValueError("pattern must be one of {}, not {!r}".format(sorted(PATTERNS), name))
    rng = rng or random.Random(0)
    order = list(range(colour_count))
    rng.shuffle(order)
    painter = PATTERNS[name](grid, lattice_centre(grid), rng)
    return [order[painter(cell) % colour_count] for cell in grid.cells()]
