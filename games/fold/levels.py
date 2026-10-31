"""
Fold levels: seeded boards with a known par.

generate_level(seed, difficulty) always gives the same level for the same
pair. A level is grown as a handful of random blobs, each painted one of
the level's colours; touching blobs that share a colour become one region.
The solver then finds par, the fewest moves that solve it, and a level
whose par falls outside the difficulty's band is rerolled.

Colours are numbers here. Which paint each number shows is the palette's
job, so any level can be redrawn in any palette.
"""

import random

from games.fold import rules, solver
from games.fold.triangles import TriangleGrid


# --- editable difficulty -----------------------------------------------------
# strips and slots size the board ("columns" layout: strips across the
# phone, slots down it). blobs is the range of painted blobs grown before
# touching ones merge. par is the band a level's fewest moves must land in.

DIFFICULTIES = {
    "easy":   {"strips": 8,  "slots": 23, "colours": 3, "blobs": (7, 10),  "par": (2, 4)},
    "medium": {"strips": 9,  "slots": 27, "colours": 4, "blobs": (12, 16), "par": (4, 6)},
    "hard":   {"strips": 10, "slots": 29, "colours": 5, "blobs": (18, 24), "par": (6, 8)},
}

MAX_ATTEMPTS = 60
SOLVE_BUDGET = 20000    # solver positions per attempt before it is given up


class Level:
    """One puzzle. colours[i] is cell i's colour, cells numbered strip by strip."""

    def __init__(self, seed, difficulty, strips, slots, colour_count, colours,
                 par, par_exact, solution, region_count, attempts):
        self.seed = seed
        self.difficulty = difficulty
        self.strips = strips
        self.slots = slots
        self.colour_count = colour_count
        self.colours = colours
        self.par = par
        self.par_exact = par_exact
        self.solution = solution
        self.region_count = region_count
        self.attempts = attempts

    def grid(self, orientation="columns", margin=0.0, gap=0.0):
        return TriangleGrid(self.strips, self.slots, orientation, margin, gap)

    def colour_map(self, grid):
        return {cell: self.colours[grid.index_of(cell)] for cell in grid.cells()}

    def board(self, grid=None):
        """A fresh FoldBoard dealt with this level."""
        grid = grid or self.grid()
        return rules.FoldBoard(grid, self.colour_map(grid))


def generate_level(seed, difficulty="easy"):
    """The level for this seed and difficulty: always the same for the same pair.

    Each seed picks a target par inside the difficulty's band and rerolls
    until a level hits it, so pars spread across the band instead of
    piling up at its easy end. If no attempt hits the target, returns the
    closest: exact par first, then inside the band, then nearest the target.
    """
    if difficulty not in DIFFICULTIES:
        raise ValueError("difficulty must be one of {}, not {!r}".format(sorted(DIFFICULTIES), difficulty))
    settings = DIFFICULTIES[difficulty]
    low, high = settings["par"]
    rng = random.Random("fold/{}/{}".format(difficulty, seed))
    target = rng.randint(low, high)
    best = None
    best_score = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        grown = _attempt(rng, settings)
        if grown is None:
            continue
        colours, graph, solution = grown
        level = Level(seed, difficulty, settings["strips"], settings["slots"],
                      settings["colours"], colours, solution.length, solution.exact,
                      solution.moves, len(graph), attempt)
        if solution.exact and level.par == target:
            return level
        outside_band = max(low - level.par, level.par - high, 0)
        score = (not solution.exact, outside_band, abs(level.par - target))
        if best is None or score < best_score:
            best, best_score = level, score
    if best is None:
        raise RuntimeError("no {} level grew for seed {!r}".format(difficulty, seed))
    return best


def _attempt(rng, settings):
    """One random board and its solution, or None when it clearly misses the band."""
    grid = TriangleGrid(settings["strips"], settings["slots"])
    colour_count = settings["colours"]
    low, high = settings["par"]

    owner = grow_blobs(grid, rng.randint(*settings["blobs"]), rng)
    blob_count = max(owner.values()) + 1
    touching = [set() for _ in range(blob_count)]
    for cell, blob in owner.items():
        for other in grid.neighbours(cell):
            if owner[other] != blob:
                touching[blob].add(owner[other])
    blob_colours = paint_blobs(blob_count, colour_count, rng, touching)
    colours = [blob_colours[owner[cell]] for cell in grid.cells()]

    graph = rules.region_graph(grid, {cell: colours[grid.index_of(cell)] for cell in grid.cells()})
    if solver.lower_bound(graph.colours) > high:
        return None
    if len(solver.greedy_plan(graph)) < low:
        return None    # greedy is never shorter than par, so par would be too easy
    return colours, graph, solver.solve(graph, SOLVE_BUDGET)


def grow_blobs(grid, blob_count, rng):
    """cell -> blob number. Blobs grow from random seed cells, a random
    frontier cell at a time, which gives ragged, paper-cut shapes."""
    seeds = rng.sample(grid.cells(), blob_count)
    owner = {cell: blob for blob, cell in enumerate(seeds)}
    frontier = list(seeds)
    while frontier:
        cell = frontier.pop(rng.randrange(len(frontier)))
        for other in grid.neighbours(cell):
            if other not in owner:
                owner[other] = owner[cell]
                frontier.append(other)
    return owner


def paint_blobs(blob_count, colour_count, rng, touching=None):
    """A colour per blob, using every colour at least once.

    With touching (blob -> set of touching blobs), each blob avoids the
    colours of touching blobs already painted where it can, so blobs rarely
    merge and the blob count sets the region count.
    """
    if blob_count < colour_count:
        raise ValueError("need at least as many blobs as colours")
    order = list(range(blob_count))
    rng.shuffle(order)
    first_colours = list(range(colour_count))
    rng.shuffle(first_colours)
    colours = [None] * blob_count
    for position, blob in enumerate(order):
        if position < colour_count:
            colours[blob] = first_colours[position]
            continue
        taken = set()
        if touching is not None:
            taken = {colours[other] for other in touching[blob] if colours[other] is not None}
        choices = [colour for colour in range(colour_count) if colour not in taken]
        colours[blob] = rng.choice(choices or list(range(colour_count)))
    return colours
