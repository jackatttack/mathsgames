"""
Gradient levels: turn a seed into a colour-gradient puzzle.

A level is three independent choices:

    1. The colour field: the colour each cell shows when solved. Four
       corner colours are blended across the grid in OKLab (colour.py).
    2. The anchors: cells that never move. They are the player's clues.
    3. The shuffle: which free cells get scrambled.

generate_level(seed, difficulty) makes its random choices from one
random.Random seeded by the difficulty and seed, and keeps the first attempt
that passes the checks below. The same seed and difficulty therefore always
give the same level, which makes a daily level free: seed it by the date.

Cells are numbered row by row: cell = row * cols + col. Tile t belongs in
cell t.

Pure Python, no UI: safe in Pythonista, PythonIDE and Forge RUN.
"""

import math
import random

from games.gradient import colour


# ===========================================================================
# Editable settings
# ===========================================================================

# Each difficulty picks a grid size, an anchor pattern and a shuffle region
# at random from its lists. Sizes are (columns, rows); phones are tall.
# Pattern names are the keys of ANCHOR_PATTERNS further down. Regions:
# "all" shuffles every free cell, "half" one half of the board, "quadrant"
# one quarter of it.
#
# "effort" is the band a dealt level must land in. A level's effort is the
# number of tiles in play, scaled up when colours are closer together:
#     effort = moving tiles * REFERENCE_STEP / typical step
# So a setting that happens to deal an easy level (a small shuffled
# quadrant on a big board, say) is rerolled instead of being called hard.
DIFFICULTIES = {
    "easy": {
        "sizes": ((5, 7), (6, 8)),
        "patterns": ("checker", "border_cross", "rows"),
        "regions": ("all",),
        "effort": (8, 25),
    },
    "medium": {
        "sizes": ((7, 9), (8, 10)),
        "patterns": ("border", "border_cross", "grid", "columns"),
        "regions": ("all", "half"),
        "effort": (25, 60),
    },
    "hard": {
        "sizes": ((9, 12), (11, 13)),
        "patterns": ("corners", "border", "border_cross", "sprinkle"),
        "regions": ("all", "quadrant"),
        "effort": (60, 400),
    },
}

# Fairness and interest checks. Distances are in OKLab, where about 0.02 is
# a small but visible difference.
MIN_NEIGHBOUR_STEP = 0.012    # neighbouring cells must differ by at least this
MIN_TILE_SEPARATION = 0.012   # any two shuffled tiles must differ by at least this
GREY_CHROMA = 0.035           # a cell with less chroma than this looks grey
MAX_GREY_FRACTION = 0.15      # at most this share of cells may look grey
REFERENCE_STEP = 0.03         # typical step at which effort equals the tile count

# Shape of the colour field.
VIVID_CHANCE = 0.6            # share of fields that keep the corners' colourfulness
VIVID_STRENGTH = 0.7          # 0 = plain blend, 1 = full corner chroma everywhere
HUE_STEP_DEGREES = (45, 100)  # how far round the hue wheel each corner moves on
CHROMA_RANGE = (0.09, 0.17)   # corner colourfulness, before fitting into sRGB
LIGHT_CORNER = (0.82, 0.92)   # lightness (OKLab L) of the light corner
DARK_CORNER = (0.42, 0.55)    # lightness of the corner opposite it
MID_CORNERS = (0.58, 0.78)    # lightness of the other two corners

SPRINKLE_FRACTION = 0.10      # share of cells anchored at random by "sprinkle"
MAX_ATTEMPTS = 60             # tries before settling for the best attempt


# ===========================================================================
# Levels
# ===========================================================================

class Level:
    """One puzzle. Tile t belongs in cell t; cells are numbered row by row.

    colours[t]  the sRGB colour of tile t (floats 0..1)
    anchors     frozenset of cells that never move
    start       the dealt arrangement: start[cell] is the tile in that cell
    report      how the level was made and how it scored on the checks
    """

    def __init__(self, seed, difficulty, cols, rows, colours, anchors, start, report):
        self.seed = seed
        self.difficulty = difficulty
        self.cols = cols
        self.rows = rows
        self.colours = colours
        self.anchors = anchors
        self.start = start
        self.report = report


def generate_level(seed, difficulty="medium"):
    """The level for this seed and difficulty: always the same for the same pair.

    Tries up to MAX_ATTEMPTS random levels and returns the first with no
    problems. If none is clean, returns the best attempt; its
    report["problems"] says what fell short.
    """
    settings = DIFFICULTIES[difficulty]
    rng = random.Random("hue:%s:%s" % (difficulty, seed))
    best = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        candidate = _attempt(rng, settings)
        if candidate is None:
            continue
        candidate["report"]["attempts"] = attempt
        if not candidate["report"]["problems"]:
            best = candidate
            break
        if best is None or candidate["score"] > best["score"]:
            best = candidate
    if best is None:
        raise ValueError("no playable level for %s seed %s" % (difficulty, seed))

    cell_count = best["cols"] * best["rows"]
    start = shuffle_cells(cell_count, best["moving"], rng)
    colours = [colour.srgb_from_oklab(lab) for lab in best["field"]]
    return Level(
        seed, difficulty, best["cols"], best["rows"], colours,
        frozenset(best["anchors"]), start, best["report"],
    )


def _attempt(rng, settings):
    """One random level, measured. None if it leaves fewer than two tiles to move."""
    cols, rows = rng.choice(settings["sizes"])
    vivid = rng.random() < VIVID_CHANCE
    field = colour_field(cols, rows, pick_corner_colours(rng), vivid)
    pattern = rng.choice(settings["patterns"])
    anchors = pick_anchors(pattern, cols, rows, rng)
    region = rng.choice(settings["regions"])
    moving = sorted(region_cells(region, cols, rows, rng) - anchors)
    if len(moving) < 2:
        return None

    report = {
        "size": "%dx%d" % (cols, rows),
        "field": "vivid" if vivid else "blend",
        "pattern": pattern,
        "region": region,
    }
    report.update(measure_colours(field, cols, rows))
    report["min_separation"] = min_separation(field, moving)
    report["moving"] = len(moving)
    report["effort"] = len(moving) * REFERENCE_STEP / report["typical_step"]
    report["problems"] = find_problems(report, settings["effort"])
    # Fewest problems first, then the clearest colours.
    quality = min(report["min_step"], report["min_separation"]) * (1 - report["grey_fraction"])
    score = (-len(report["problems"]), quality)
    return {
        "cols": cols, "rows": rows, "field": field, "anchors": anchors,
        "moving": moving, "report": report, "score": score,
    }


# ===========================================================================
# 1. The colour field
# ===========================================================================

def pick_corner_colours(rng):
    """Four OKLab corners in the order top-left, top-right, bottom-right, bottom-left.

    The corners walk round the hue wheel in that order, so neighbouring
    corners are related and the diagonals are furthest apart. One corner is
    light and the one opposite it dark, which keeps lightness changing across
    the whole board; lightness is the change people read most easily.
    """
    start_hue = rng.uniform(0, 360)
    hue_step = rng.uniform(*HUE_STEP_DEGREES) * rng.choice((1, -1))
    lightness = [
        rng.uniform(*LIGHT_CORNER),
        rng.uniform(*MID_CORNERS),
        rng.uniform(*DARK_CORNER),
        rng.uniform(*MID_CORNERS),
    ]
    turn = rng.randrange(4)
    lightness = lightness[turn:] + lightness[:turn]

    corners = []
    for index in range(4):
        hue = (start_hue + index * hue_step) % 360
        chroma = rng.uniform(*CHROMA_RANGE)
        corners.append(colour.oklab_from_oklch(colour.fit_chroma(lightness[index], chroma, hue)))
    return corners


def colour_field(cols, rows, corners, vivid):
    """The OKLab colour of every cell, row by row, blended from four corners.

    Each cell mixes the corners by bilinear weights. A plain blend between
    very different hues passes through grey in the middle; a vivid field
    pushes each cell's chroma back towards the blend of the corners' chromas
    to keep it colourful. Every colour is fitted into sRGB, so the field is
    exactly what the screen shows and the checks measure real colours.
    """
    corner_chromas = [math.hypot(lab[1], lab[2]) for lab in corners]
    field = []
    for row in range(rows):
        down = row / (rows - 1)
        for col in range(cols):
            across = col / (cols - 1)
            weights = (
                (1 - across) * (1 - down),   # top-left
                across * (1 - down),         # top-right
                across * down,               # bottom-right
                (1 - across) * down,         # bottom-left
            )
            lab = tuple(
                sum(weight * corner[axis] for weight, corner in zip(weights, corners))
                for axis in range(3)
            )
            if vivid:
                target = sum(weight * chroma for weight, chroma in zip(weights, corner_chromas))
                lab = _push_chroma(lab, target, VIVID_STRENGTH)
            field.append(_displayable(lab))
    return field


def _push_chroma(lab, target, strength):
    """Move a colour's chroma part of the way towards target, keeping its hue."""
    L, a, b = lab
    current = math.hypot(a, b)
    if current < 1e-6:
        return lab
    wanted = current + strength * (target - current)
    scale = wanted / current
    return (L, a * scale, b * scale)


def _displayable(lab):
    L, C, h = colour.oklch_from_oklab(lab)
    return colour.oklab_from_oklch(colour.fit_chroma(L, C, h))


# ===========================================================================
# 2. Anchors
# ===========================================================================
# Each pattern returns a set of (col, row). pick_anchors always adds the
# four corners, because the corners define the gradient.

def _corners(cols, rows, rng):
    return set()


def _border(cols, rows, rng):
    return {
        (col, row)
        for row in range(rows) for col in range(cols)
        if col in (0, cols - 1) or row in (0, rows - 1)
    }


def _border_cross(cols, rows, rng):
    middle_column = {(cols // 2, row) for row in range(rows)}
    middle_row = {(col, rows // 2) for col in range(cols)}
    return _border(cols, rows, rng) | middle_column | middle_row


def _rows(cols, rows, rng):
    return {(col, row) for col in range(cols) for row in (0, rows - 1)}


def _columns(cols, rows, rng):
    return {(col, row) for col in (0, cols - 1) for row in range(rows)}


def _grid(cols, rows, rng):
    return {(col, row) for row in range(0, rows, 2) for col in range(0, cols, 2)}


def _checker(cols, rows, rng):
    return {(col, row) for row in range(rows) for col in range(cols) if (col + row) % 2 == 0}


def _sprinkle(cols, rows, rng):
    cells = [(col, row) for row in range(rows) for col in range(cols)]
    return set(rng.sample(cells, max(1, round(len(cells) * SPRINKLE_FRACTION))))


ANCHOR_PATTERNS = {
    "corners": _corners,
    "border": _border,
    "border_cross": _border_cross,
    "rows": _rows,
    "columns": _columns,
    "grid": _grid,
    "checker": _checker,
    "sprinkle": _sprinkle,
}


def pick_anchors(pattern, cols, rows, rng):
    """The anchored cells (as cell numbers) for a named pattern, corners included."""
    chosen = ANCHOR_PATTERNS[pattern](cols, rows, rng)
    chosen |= {(0, 0), (cols - 1, 0), (0, rows - 1), (cols - 1, rows - 1)}
    return {row * cols + col for col, row in chosen}


# ===========================================================================
# 3. The shuffle
# ===========================================================================

def region_cells(region, cols, rows, rng):
    """The cells a shuffle may move, before anchors are taken out."""
    every_column, every_row = range(cols), range(rows)
    left, right = range((cols + 1) // 2), range(cols // 2, cols)
    top, bottom = range((rows + 1) // 2), range(rows // 2, rows)

    if region == "all":
        columns, row_range = every_column, every_row
    elif region == "half":
        columns, row_range = rng.choice((
            (left, every_row), (right, every_row),
            (every_column, top), (every_column, bottom),
        ))
    elif region == "quadrant":
        columns, row_range = rng.choice((left, right)), rng.choice((top, bottom))
    else:
        raise ValueError("unknown shuffle region: %r" % region)
    return {row * cols + col for row in row_range for col in columns}


def shuffle_cells(cell_count, moving, rng):
    """A dealt arrangement (cell -> tile) that moves every cell in moving.

    Shuffles the tiles among the moving cells, then repairs any tile that
    landed back home by swapping it with the next one in the list. Each
    repair leaves both positions out of place, so no moving tile starts in
    its solved cell.
    """
    tiles = list(moving)
    rng.shuffle(tiles)
    for index in range(len(tiles)):
        if tiles[index] == moving[index]:
            other = (index + 1) % len(tiles)
            tiles[index], tiles[other] = tiles[other], tiles[index]
    arrangement = list(range(cell_count))
    for cell, tile in zip(moving, tiles):
        arrangement[cell] = tile
    return arrangement


# ===========================================================================
# Checks
# ===========================================================================

def measure_colours(field, cols, rows):
    """Neighbour steps and greyness of a field.

    min_step      the smallest difference between side-by-side cells
    typical_step  the median one: lower makes a harder level
    grey_fraction the share of cells that look grey
    """
    steps = []
    for row in range(rows):
        for col in range(cols):
            here = field[row * cols + col]
            if col + 1 < cols:
                steps.append(colour.distance(here, field[row * cols + col + 1]))
            if row + 1 < rows:
                steps.append(colour.distance(here, field[(row + 1) * cols + col]))
    steps.sort()
    grey = sum(1 for lab in field if math.hypot(lab[1], lab[2]) < GREY_CHROMA)
    return {
        "min_step": steps[0],
        "typical_step": steps[len(steps) // 2],
        "grey_fraction": grey / len(field),
    }


def min_separation(field, cells):
    """The smallest difference between any two of these cells' colours.

    Two shuffled tiles that look the same would make a level unfair: the
    player could put them in each other's places and never see it solved.
    """
    closest = float("inf")
    for index, cell in enumerate(cells):
        here = field[cell]
        for other in cells[index + 1:]:
            gap = colour.distance(here, field[other])
            if gap < closest:
                closest = gap
    return closest


def find_problems(report, effort_band):
    """Plain-English reasons a measured level falls short; empty when it is fine."""
    problems = []
    low, high = effort_band
    if report["effort"] < low:
        problems.append("too easy (effort %d, wants %d+)" % (report["effort"], low))
    elif report["effort"] > high:
        problems.append("too hard (effort %d, wants up to %d)" % (report["effort"], high))
    if report["min_step"] < MIN_NEIGHBOUR_STEP:
        problems.append("neighbours too alike (%.3f)" % report["min_step"])
    if report["min_separation"] < MIN_TILE_SEPARATION:
        problems.append("two shuffled tiles too alike (%.3f)" % report["min_separation"])
    if report["grey_fraction"] > MAX_GREY_FRACTION:
        problems.append("too grey (%d%%)" % round(report["grey_fraction"] * 100))
    return problems
