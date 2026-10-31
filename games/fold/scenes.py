"""
Fold scenes: isometric block pictures drawn onto the triangle board, like
KAMI's pillars, beams and impossible ribbons.

A scene is a list of Boxes in 3D grid units. Each box has three colours,
for its top, its x side and its y side, so a block reads as solid. On the
triangle lattice an isometric cube is exactly a hexagon of six triangles
and each face a rhombus of two, so a block never cuts a triangle.

Projection, in flat coordinates with side 1 ("columns" layout: along runs
down the screen, across runs left to right):

    z  up the screen              e_z = (-1, 0)
    x  down and to the right      e_x = (1/2,  depth)
    y  down and to the left       e_y = (1/2, -depth)

e_x + e_y + e_z = 0, so (1, 1, 1) projects to nothing: the viewer looks
along it. Larger x + y + z is nearer the viewer, so the faces that show are
+x, +y and +z, and drawing unit cubes in order of x + y + z (the painter's
algorithm) leaves the nearest face on top. Cubes with equal x + y + z never
overlap on screen.

Colours are numbers as in rules: background 0, then whatever the boxes use.
"""

import random

from games.fold import patterns
from games.fold.triangles import DEPTH_PER_SIDE


AXIS_X = (0.5, DEPTH_PER_SIDE)
AXIS_Y = (0.5, -DEPTH_PER_SIDE)
AXIS_Z = (-1.0, 0.0)

# Each visible face of the unit cube at (x, y, z): where its rhombus starts
# (as an offset from the cube's corner), the two edges spanning it, and
# which of the box's three colours it takes.
FACE_SHAPES = (
    ((0, 0, 1), AXIS_X, AXIS_Y, 0),    # top
    ((1, 0, 0), AXIS_Y, AXIS_Z, 1),    # x side
    ((0, 1, 0), AXIS_X, AXIS_Z, 2),    # y side
)


# --- editable materials ------------------------------------------------------
# (top, x side, y side) colour numbers. Scene palettes paint these numbers.

STONE = (1, 2, 3)
BRICK = (4, 5, 6)
RIBBON = (7, 7, 7)


class Box:
    """A solid block: its nearest-the-origin corner, its size, and its face colours."""

    def __init__(self, corner, size, faces):
        if min(size) < 1:
            raise ValueError("a box needs a size of at least 1 along every axis")
        self.corner = tuple(corner)
        self.size = tuple(size)
        self.faces = tuple(faces)

    def unit_cubes(self):
        x0, y0, z0 = self.corner
        sx, sy, sz = self.size
        for x in range(x0, x0 + sx):
            for y in range(y0, y0 + sy):
                for z in range(z0, z0 + sz):
                    yield (x, y, z)


def project(origin, point):
    """Flat coordinates of a 3D grid point."""
    x, y, z = point
    return (origin[0] + 0.5 * x + 0.5 * y - z,
            origin[1] + (x - y) * DEPTH_PER_SIDE)


def render(grid, boxes, background=0, origin=None):
    """Colour numbers for every cell of grid (by index) showing these boxes.

    origin is where (0, 0, 0) lands, a flat lattice corner; by default the
    corner nearest the board's middle. Parts off the board are dropped.
    Where boxes share a cube, the later box in the list wins.
    """
    origin = origin or patterns.lattice_centre(grid)
    colours = [background] * len(grid.cells())
    cubes = []
    for order, box in enumerate(boxes):
        for cube in box.unit_cubes():
            cubes.append((sum(cube), order, cube, box.faces))
    cubes.sort(key=lambda item: (item[0], item[1]))
    for depth, order, (x, y, z), faces in cubes:
        for (dx, dy, dz), u, v, face in FACE_SHAPES:
            start = project(origin, (x + dx, y + dy, z + dz))
            # The rhombus splits along its short diagonal u + v into two
            # triangles; their centres are (2u + v) / 3 and (u + 2v) / 3 in.
            for weight_u, weight_v in ((2, 1), (1, 2)):
                point = (start[0] + (weight_u * u[0] + weight_v * v[0]) / 3.0,
                         start[1] + (weight_u * u[1] + weight_v * v[1]) / 3.0)
                cell = grid.flat_cell_at(point)
                if cell is not None:
                    colours[grid.index_of(cell)] = faces[face]
    return colours


# --- scene builders: rng -> list of Boxes, centred on the origin -------------

def _pillars(rng):
    """Square pillars of different heights standing on a brick floor."""
    boxes = [Box((-6, -6, -3), (12, 12, 1), BRICK)]
    spots = [(x, y) for x in range(-3, 4, 2) for y in range(-3, 4, 2)]
    rng.shuffle(spots)
    for x, y in spots[:rng.randint(3, 5)]:
        boxes.append(Box((x, y, -2), (1, 1, rng.randint(2, 5)), STONE))
    return boxes


def _beams(rng):
    """Long beams crossing the board at different heights, in at least two materials."""
    count = rng.randint(3, 5)
    materials = [STONE, rng.choice((BRICK, RIBBON))]
    materials += [rng.choice((STONE, BRICK, RIBBON)) for _ in range(count - 2)]
    rng.shuffle(materials)
    boxes = []
    for material in materials:
        offset = rng.randint(-4, 4)
        height = rng.randint(-3, 3)
        if rng.random() < 0.5:
            boxes.append(Box((-16, offset, height), (32, 1, 1), material))
        else:
            boxes.append(Box((offset, -16, height), (1, 32, 1), material))
    return boxes


def _stairs(rng):
    """A staircase climbing towards the viewer."""
    width = rng.randint(2, 4)
    steps = rng.randint(5, 7)
    return [Box((step - 3, -width // 2, -3), (1, width, step + 1), STONE) for step in range(steps)]


def _blocks(rng):
    """A heap of big cubes stacked to random heights."""
    boxes = []
    for x in range(-1, 2):
        for y in range(-1, 2):
            height = rng.randint(0, 3)
            if height:
                boxes.append(Box((2 * x, 2 * y, -3), (2, 2, 2 * height), rng.choice((STONE, BRICK))))
    return boxes


SCENES = {
    "pillars": _pillars,
    "beams": _beams,
    "stairs": _stairs,
    "blocks": _blocks,
}


def build(name, rng=None):
    """The boxes of a named scene; the same rng seed gives the same scene."""
    if name not in SCENES:
        raise ValueError("scene must be one of {}, not {!r}".format(sorted(SCENES), name))
    return SCENES[name](rng or random.Random(0))
