"""
Fold scenes: isometric block pictures drawn onto the triangle board, like
KAMI's pillars, woven beams and linked ribbons.

A scene is a list of Boxes in 3D grid units. Each box has a material: the
colour numbers of its top, its x side and its y side, and optionally a
fourth, the colour its top takes in shadow. On the triangle lattice an
isometric cube is exactly a hexagon of six triangles and each face a
rhombus of two, so a block never cuts a triangle.

Projection, in flat coordinates with side 1 ("columns" layout: along runs
down the screen, across runs left to right):

    z  up the screen              e_z = (-1, 0)
    x  down and to the right      e_x = (1/2,  depth)
    y  down and to the left       e_y = (1/2, -depth)

e_x + e_y + e_z = 0, so (1, 1, 1) projects to nothing: the viewer looks
along it. Larger x + y + z is nearer the viewer, so the faces that show are
+x, +y and +z, and drawing unit cubes in order of x + y + z (the painter's
algorithm) leaves the nearest face on top.

Shadows: a visible top face whose material has a shadow colour goes dark
when a cube sits on the line towards the light, (x + k * lx, y + k * ly,
z + k) for k = 1, 2, ...: a sun 45 degrees up, so a shadow is as long as
the block that casts it.

Colour numbers (scene palettes in collection.py paint them):
    0 background   1-3 stone (top, side, shadow side)   4-6 brick
    7 green beam top   8 shadow   9-10 teal ribbon   11 green beam side
    12-13 red ribbon (top, side)
"""

import random

from games.fold import patterns
from games.fold.triangles import DEPTH_PER_SIDE


AXIS_X = (0.5, DEPTH_PER_SIDE)
AXIS_Y = (0.5, -DEPTH_PER_SIDE)
AXIS_Z = (-1.0, 0.0)

# Each visible face of the unit cube at (x, y, z): where its rhombus starts
# (as an offset from the cube's corner), the two edges spanning it, and
# which of the material's colours it takes.
FACE_SHAPES = (
    ((0, 0, 1), AXIS_X, AXIS_Y, 0),    # top
    ((1, 0, 0), AXIS_Y, AXIS_Z, 1),    # x side
    ((0, 1, 0), AXIS_X, AXIS_Z, 2),    # y side
)


# --- editable materials and light ------------------------------------------------
# (top, x side, y side[, top in shadow]) colour numbers.

STONE = (1, 2, 3, 8)
BRICK = (4, 5, 6, 8)
RIBBON = (7, 7, 7)
CREAM_RIBBON = (1, 2, 2)
TEAL_RIBBON = (9, 10, 10)
RED_RIBBON = (12, 13, 13)
CREAM_BEAM = (1, 2, 2, 8)
GREEN_BEAM = (7, 11, 11, 8)

LIGHT = (-1, 0)          # shadows fall towards -lx, -ly on the floor
SHADOW_REACH = 12        # longest shadow, in cubes


class Box:
    """A solid block: its nearest-the-origin corner, its size, and its material."""

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


def render(grid, boxes, background=0, origin=None, light=LIGHT):
    """Colour numbers for every cell of grid (by index) showing these boxes.

    origin is where (0, 0, 0) lands, a flat lattice corner; by default the
    corner nearest the board's middle. Parts off the board are dropped.
    Where boxes share a cube, the later box in the list wins. light None
    turns shadows off.
    """
    origin = origin or patterns.lattice_centre(grid)
    colours = [background] * len(grid.cells())
    shown = [None] * len(grid.cells())
    cubes = []
    solid = set()
    for order, box in enumerate(boxes):
        for cube in box.unit_cubes():
            cubes.append((sum(cube), order, cube, box.faces))
            solid.add(cube)
    cubes.sort(key=lambda item: (item[0], item[1]))
    for depth, order, cube, faces in cubes:
        x, y, z = cube
        for (dx, dy, dz), u, v, face in FACE_SHAPES:
            start = project(origin, (x + dx, y + dy, z + dz))
            # The rhombus splits along its short diagonal u + v into two
            # triangles; their centres are (2u + v) / 3 and (u + 2v) / 3 in.
            for weight_u, weight_v in ((2, 1), (1, 2)):
                point = (start[0] + (weight_u * u[0] + weight_v * v[0]) / 3.0,
                         start[1] + (weight_u * u[1] + weight_v * v[1]) / 3.0)
                cell = grid.flat_cell_at(point)
                if cell is not None:
                    index = grid.index_of(cell)
                    colours[index] = faces[face]
                    shown[index] = (cube, face, faces)
    if light:
        lx, ly = light
        for index, seen in enumerate(shown):
            if seen is None:
                continue
            (x, y, z), face, faces = seen
            if face == 0 and len(faces) > 3 and any(
                    (x + k * lx, y + k * ly, z + k) in solid for k in range(1, SHADOW_REACH)):
                colours[index] = faces[3]
    return colours


# --- shape helpers -------------------------------------------------------------------

def frame(corner, first_axis, second_axis, size, faces):
    """A square loop of side size, one cube thick, in the plane of two axes
    (0 x, 1 y, 2 z) with its lowest corner at corner."""
    boxes = []

    def side(offset_first, offset_second, length_first, length_second):
        position = list(corner)
        extent = [1, 1, 1]
        position[first_axis] += offset_first
        position[second_axis] += offset_second
        extent[first_axis] = length_first
        extent[second_axis] = length_second
        boxes.append(Box(tuple(position), tuple(extent), faces))

    side(0, 0, size, 1)
    side(0, size - 1, size, 1)
    side(0, 1, 1, size - 2)
    side(size - 1, 1, 1, size - 2)
    return boxes


# --- scene builders: rng -> list of Boxes, centred on the origin ---------------------

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


def _woven(rng):
    """Beams crossing at two heights over a brick floor, with a few pillars,
    all casting shadows: KAMI's woven beams."""
    boxes = [Box((-15, -15, -4), (30, 30, 1), BRICK)]
    spots = [(-4, -2), (3, -4), (2, 3), (-3, 4), (0, -5), (5, 1)]
    rng.shuffle(spots)
    for x, y in spots[:rng.randint(1, 3)]:
        boxes.append(Box((x, y, -3), (1, 1, rng.randint(3, 5)), STONE))
    low, high = rng.choice(((CREAM_BEAM, GREEN_BEAM), (GREEN_BEAM, CREAM_BEAM)))
    for offset in rng.sample((-5, -2, 1, 4), rng.randint(1, 2)):
        boxes.append(Box((-15, offset, 0), (30, 1, 1), high))
    for offset in rng.sample((-4, -1, 2, 5), rng.randint(1, 2)):
        boxes.append(Box((offset, -15, -2), (1, 30, 1), low))
    return boxes


def _chain(rng):
    """Square loops linked into a chain down the board, alternating planes
    and colours, like KAMI's impossible ribbons. Unlit (see UNLIT)."""
    size = rng.choice((4, 5))
    loops = rng.choice((3, 4))
    first, second = rng.choice(((CREAM_RIBBON, TEAL_RIBBON), (CREAM_RIBBON, RED_RIBBON),
                                (TEAL_RIBBON, RED_RIBBON)))
    flip = rng.random() < 0.5
    top_start = 6 if loops == 4 else 5
    boxes = []
    for index in range(loops):
        top = top_start - index * (size - 1)
        if (index % 2 == 0) != flip:
            boxes += frame((-(size // 2), 0, top - size + 1), 0, 2, size, first)
        else:
            boxes += frame((0, -(size // 2), top - size + 1), 1, 2, size, second)
    return boxes


def _zigzag(rng):
    """One ribbon, or two side by side, stepping down the board in
    alternating runs and colours."""
    run = rng.choice((4, 5))
    pairs = [(CREAM_RIBBON, TEAL_RIBBON), (CREAM_RIBBON, RED_RIBBON), (TEAL_RIBBON, RED_RIBBON)]
    rng.shuffle(pairs)
    # Across the board a cube sits at x - y; a ribbon sweeps from its start
    # to run - 1 further right, so these starts centre one ribbon or two.
    if rng.random() < 0.5:
        ribbons = [(-(run - 1) // 2, pairs[0])]
    else:
        ribbons = [(-run - 1, pairs[0]), (1, pairs[1])]
    boxes = []
    for across, (first, second) in ribbons:
        x, y, z = -6 + across, -6, 6
        for index in range(10):
            material = first if index % 4 < 2 else second
            if index % 2 == 0:
                boxes.append(Box((x, y, z), (run, 1, 1), material))
                x += run - 1
            else:
                boxes.append(Box((x, y, z), (1, run, 1), material))
                y += run - 1
            z -= 1
    return boxes


SCENES = {
    "pillars": _pillars,
    "beams": _beams,
    "stairs": _stairs,
    "blocks": _blocks,
    "woven": _woven,
    "chain": _chain,
    "zigzag": _zigzag,
}

# Scenes drawn without shadows: their material tops sit on the background.
UNLIT = ("chain", "zigzag")


def build(name, rng=None):
    """The boxes of a named scene; the same rng seed gives the same scene."""
    if name not in SCENES:
        raise ValueError("scene must be one of {}, not {!r}".format(sorted(SCENES), name))
    return SCENES[name](rng or random.Random(0))


def paint_scene(name, grid, rng):
    """Colour numbers for a named scene, lit or unlit as the scene wants."""
    return render(grid, build(name, rng), light=None if name in UNLIT else LIGHT)
