"""
Fold compositions: designed, geometric boards in the spirit of KAMI's
player creations, built from shapes that follow the triangle lattice.

Every shape is a lattice polygon: its edges run along the board's own
lines, so no triangle is ever cut and every region has a clean edge. A
point is measured by three lattice coordinates from an anchor corner near
the middle of the board (patterns.lattice_centre):

    u0   across the strips: whole numbers are the strip boundaries
    u1   one diagonal family of lattice lines (about 30 degrees)
    u2   the other diagonal family; u0 = u1 + u2

Whole values of u0, u1 and u2 are lattice lines, and a triangle's centre
never sits on one, so a shape is just a test on (u0, u1, u2) such as
"every |u| <= 3" (a hexagon). Turning the board by 60 degrees about the
anchor, or mirroring it left to right, maps the lattice onto itself, so
rotated and mirrored shapes stay clean too.

A Composition paints layers in order over a background: each layer is a
shape and a colour number, and later layers cover earlier ones. Bands
paint a colour from a formula (rings, spirals, chevrons). Motifs are
seeded recipes that build them: hexagram, rosette, quilt, spiral,
chevrons, weave, honeycomb, and layered (a band motif with a star or
rosette over it). The same motif and seed always give the same board.

Designed in a desktop sandbox against labs/fold_levels_preview-style
sheets; the curated collection (collection.py) stores its boards as data,
so changing a motif never changes a curated level.

Colours are numbers 0..n-1 as in rules; 0 is the background, and a palette
(palettes.py) paints them.
"""

import math
import random

from games.fold import patterns
from games.fold.triangles import DEPTH_PER_SIDE, TriangleGrid


DEPTH = DEPTH_PER_SIDE
BOARD_STRIPS = 10
BOARD_SLOTS = 29


# --- measuring cells -----------------------------------------------------------

class Lattice:
    """Lattice coordinates of every cell's centre, measured from an anchor corner."""

    def __init__(self, grid, anchor=None):
        self.grid = grid
        self.anchor = anchor or patterns.lattice_centre(grid)
        self.offsets = [patterns.offset_from(grid, cell, self.anchor) for cell in grid.cells()]

    def coordinates(self, index, turn=0, shift=(0, 0)):
        """(u0, u1, u2) of cell index, after turning the board by turn * 60
        degrees about the anchor and moving the anchor by shift (whole (u1, u2))."""
        x, y = self.offsets[index]
        if turn:
            angle = math.radians(-60 * turn)
            x, y = x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle)
        u1 = (x * math.cos(math.radians(30)) + y * 0.5) / DEPTH - shift[0]
        u2 = (-x * math.cos(math.radians(30)) + y * 0.5) / DEPTH - shift[1]
        return (u1 + u2, u1, u2)


# --- shapes: tests on (u0, u1, u2) ------------------------------------------------

def hexagon(radius):
    """A regular hexagon round the anchor: six triangles at radius 1."""
    return lambda u: max(abs(u[0]), abs(u[1]), abs(u[2])) <= radius


def ring(inner, outer):
    """The hexagonal band between two radii."""
    return lambda u: inner <= max(abs(u[0]), abs(u[1]), abs(u[2])) <= outer


def triangle(size, flip=False):
    """A big lattice triangle centred on the anchor; flip points it the other way.

    Its vertices sit size * 3 / 2 triangles from the centre; the two flips
    overlap in a hexagon of radius size / 2, making a six-pointed star.
    """
    if flip:
        return lambda u: u[1] <= size and u[2] <= size and u[0] >= -size
    return lambda u: u[1] >= -size and u[2] >= -size and u[0] <= size


def diamond(length, width=None):
    """A rhombus with one corner at the anchor, pointing along +u1 and +u2."""
    width = length if width is None else width
    return lambda u: 0 <= u[1] <= length and 0 <= u[2] <= width


def slab(axis, low, high):
    """Everything between two parallel lattice lines."""
    return lambda u: low <= u[axis] <= high


def union(*shapes):
    return lambda u: any(shape(u) for shape in shapes)


def minus(shape, cut):
    return lambda u: shape(u) and not cut(u)


class Layer:
    """One shape in one colour. turns lists the 60-degree turns it is drawn at
    (all six makes it six-fold); shifts lists whole (u1, u2) moves of its anchor."""

    def __init__(self, shape, colour, turns=(0,), shifts=((0, 0),)):
        self.shape = shape
        self.colour = colour
        self.turns = tuple(turns)
        self.shifts = tuple(shifts)


class Composition:
    """A background colour and layers painted over it in order."""

    def __init__(self, background, layers, name=""):
        self.background = background
        self.layers = list(layers)
        self.name = name

    def paint(self, grid, under=None):
        """Colour numbers for every cell. A background of None leaves the
        colours of under (another painting) showing between the layers."""
        lattice = Lattice(grid)
        if self.background is None:
            colours = list(under)
        else:
            colours = [self.background] * len(grid.cells())
        for index in range(len(colours)):
            for layer in self.layers:
                for turn in layer.turns:
                    for shift in layer.shifts:
                        if layer.shape(lattice.coordinates(index, turn, shift)):
                            colours[index] = layer.colour
        return colours


# --- band painters: a colour for every cell from a formula ----------------------------

class Bands:
    """Paints every cell colours[floor(band(u)) % len(colours)]: for stripes,
    rings and spirals. band gets (u0, u1, u2, (x, y)), where (x, y) is the
    cell centre's flat offset from the anchor, for formulas that need an angle."""

    def __init__(self, band, colours, name=""):
        self.band = band
        self.colours = list(colours)
        self.name = name

    def paint(self, grid):
        lattice = Lattice(grid)
        colours = []
        for index in range(len(grid.cells())):
            measure = lattice.coordinates(index) + (lattice.offsets[index],)
            colours.append(self.colours[int(math.floor(self.band(measure))) % len(self.colours)])
        return colours


def hex_distance(u):
    return max(abs(u[0]), abs(u[1]), abs(u[2]))


def sector(u):
    x, y = u[3]
    return int((math.degrees(math.atan2(y, x)) % 360) // 60) % 6


# --- motifs --------------------------------------------------------------------

def _colours(rng, count):
    """count colour numbers 1..count in a random order: 0 stays the background."""
    order = list(range(1, count + 1))
    rng.shuffle(order)
    return order


def hexagram(rng):
    """A six-pointed star of two big triangles, a hexagon at its heart."""
    a, b, c, d = _colours(rng, 4)
    size = rng.choice((3, 4))
    layers = [Layer(triangle(size), a), Layer(triangle(size, flip=True), b)]
    if rng.random() < 0.7:
        layers.append(Layer(hexagon(size - rng.choice((1, 2))), c))
    if rng.random() < 0.5:
        layers.append(Layer(hexagon(1), d))
    return Composition(0, layers, "hexagram")


def rosette(rng):
    """A hexagon with six diamonds or petals round it: a snowflake."""
    a, b, c, d = _colours(rng, 4)
    petal = rng.choice((2, 3))
    layers = [Layer(ring(petal + 2, petal + 3), d)] if rng.random() < 0.6 else []
    layers += [Layer(diamond(petal + 1, 1), a, turns=range(6)),
               Layer(hexagon(rng.choice((1, 2))), b)]
    if rng.random() < 0.6:
        layers.append(Layer(hexagon(1), c))
    return Composition(0, layers, "rosette")


def quilt(rng):
    """Concentric diamonds radiating from the centre, like a lone-star quilt."""
    count = rng.choice((3, 4))
    width = rng.choice((2, 3))
    colours = list(range(count))
    rng.shuffle(colours)

    def band(u):
        x, y = u[3]
        turn = sector(u)
        angle = math.radians(-60 * turn)
        rx, ry = x * math.cos(angle) - y * math.sin(angle), x * math.sin(angle) + y * math.cos(angle)
        # wedge coordinates along the wedge's two edges (60 degrees apart)
        a = rx - ry / math.sqrt(3)
        b = 2 * ry / math.sqrt(3)
        return max(a, b) / width
    return Bands(band, colours, "quilt")


def spiral(rng):
    """Hexagonal rings stepped round six sectors: a pinwheel spiral.

    Each sector steps the rings out by one whole triangle, so the bands
    stay on lattice lines. One turn climbs 6 triangles, which is 6 / width
    bands, so the colour count must divide that for the seam to match.
    """
    width, count = rng.choice(((2, 3), (2, 3), (3, 2)))
    turn = rng.choice((1, -1))
    colours = list(range(count))
    rng.shuffle(colours)
    return Bands(lambda u: (hex_distance(u) + turn * sector(u)) / width, colours, "spiral")


def chevrons(rng):
    """Wide zigzag bands stacked down the board."""
    count = rng.choice((3, 4))
    width = rng.choice((2, 3))
    colours = list(range(count))
    rng.shuffle(colours)
    if rng.random() < 0.5:
        return Bands(lambda u: max(u[1], u[2]) / width, colours, "chevrons")
    return Bands(lambda u: -min(u[1], u[2]) / width, colours, "chevrons")


def weave(rng):
    """Two families of diagonal bands crossing, a third colour where they meet."""
    a, b, c = _colours(rng, 3)
    width = 2
    gap = rng.choice((3, 4))
    period = width + gap
    first = lambda u: (u[1] % period) < width
    second = lambda u: (u[2] % period) < width
    return Composition(0, [Layer(first, a), Layer(second, b),
                           Layer(lambda u: first(u) and second(u), c)], "weave")


def honeycomb(rng):
    """Big hexagons tiling the board in three colours."""
    radius = rng.choice((2, 3))
    colours = list(range(3))
    rng.shuffle(colours)
    step = radius  # centres of touching hexagons sit (r, r) apart along u1, u2 lines

    def band(u):
        # nearest hexagon centre on the lattice of centres generated by
        # (2r, -r) and (r, r) in (u1, u2); its class mod 3 picks the colour
        best = None
        u1, u2 = u[1], u[2]
        for p in range(-8, 9):
            for q in range(-8, 9):
                c1 = p * 2 * step + q * step
                c2 = -p * step + q * step
                if abs(u1 - c1) > 3 * step or abs(u2 - c2) > 3 * step:
                    continue
                d = max(abs(u1 - c1), abs(u2 - c2), abs(u1 + u2 - c1 - c2))
                if best is None or d < best[0]:
                    best = (d, (p - q) % 3)
        return best[1]
    return Bands(band, colours, "honeycomb")


def layered(rng):
    """A band motif with a star or rosette laid over its middle."""
    base = rng.choice((chevrons, spiral, honeycomb, quilt))(rng)
    top = rng.choice((hexagram, rosette))(rng)
    base_count = len(base.colours)
    # The overlay keeps two of its colours new and borrows the rest from the
    # base, so the whole board stays within five or six colours.
    fresh = [base_count, base_count + 1]
    borrowed = list(range(base_count))
    rng.shuffle(borrowed)
    pool = fresh + borrowed
    mapping = {}
    for layer in top.layers:
        if layer.colour not in mapping:
            mapping[layer.colour] = pool[len(mapping) % len(pool)]
        layer.colour = mapping[layer.colour]
    return Overlay(base, Composition(None, top.layers), "layered " + base.name + "+" + top.name)


class Overlay:
    """One painting laid over another: the top's layers over the base's colours."""

    def __init__(self, base, top, name=""):
        self.base = base
        self.top = top
        self.name = name

    def paint(self, grid):
        return self.top.paint(grid, under=self.base.paint(grid))


MOTIFS = {
    "hexagram": hexagram,
    "rosette": rosette,
    "quilt": quilt,
    "spiral": spiral,
    "chevrons": chevrons,
    "weave": weave,
    "honeycomb": honeycomb,
    "layered": layered,
}


def board_grid():
    return TriangleGrid(BOARD_STRIPS, BOARD_SLOTS)


def compact(colours):
    """Renumber colours 0..n-1 by area, largest first, so a palette's first
    entry always paints the biggest area."""
    counts = {}
    for colour in colours:
        counts[colour] = counts.get(colour, 0) + 1
    order = sorted(counts, key=lambda colour: -counts[colour])
    mapping = {colour: index for index, colour in enumerate(order)}
    return [mapping[colour] for colour in colours]


def paint_motif(name, seed, grid=None):
    """Colour numbers (by cell index, compacted) for a motif and seed."""
    grid = grid or board_grid()
    rng = random.Random("fold-motif/{}/{}".format(name, seed))
    return compact(MOTIFS[name](rng).paint(grid))
