"""
Fold puzzles: the curated Journey, and Random puzzles by difficulty.

Journey levels are stored as data: their cells run-length encoded (a
letter for the colour, a for colour 0, then how many cells in a row have
it, cells numbered strip by strip on the 10 x 29 board), with their
palette, par and a solution that reaches par. They were picked by a builder script from the
motifs in compose.py and scenes.py and checked by eye; storing them means
a later change to a motif never changes a level someone has already solved.

Random puzzles are grown on demand from motifs with a seed, and rerolled
until their par lands in the difficulty's band.

A Puzzle carries everything the screen needs: colours, palette, par.
"""

import random
import re
import time

from games.fold import compose, rules, scenes, solver


# --- editable random modes -------------------------------------------------------
# motifs: compose.MOTIFS names, or "scene:<name>" for scenes.SCENES.
# par: the band a random puzzle's par must land in.

RANDOM_MODES = (
    ("easy", "Easy", {"motifs": ("quilt", "hexagram", "spiral", "chevrons", "rosette", "scene:stairs"),
                      "par": (2, 3)}),
    ("medium", "Medium", {"motifs": ("rosette", "honeycomb", "chevrons", "layered",
                                     "scene:beams", "scene:blocks"),
                          "par": (4, 5)}),
    ("hard", "Hard", {"motifs": ("layered", "layered", "scene:pillars", "scene:blocks", "scene:beams"),
                      "par": (6, 8)}),
)

RANDOM_ATTEMPTS = 40
RANDOM_MAX_REGIONS = 34      # busier boards are skipped: too slow to prove par
RANDOM_SOLVE_BUDGET = 4000
RANDOM_SECONDS = 2.5         # stop rerolling after this and take the closest

# Palettes for motifs: the first colour paints the biggest area.
PALETTES = {
    "ink":     ("#26292e", "#efe3c8", "#d9483b", "#2f9c7c", "#a7a39a", "#e8b23a"),
    "quilt":   ("#3f7f9e", "#e8b23a", "#c8323c", "#f1e6d0", "#2b2a4a", "#7aa6b8"),
    "sunrise": ("#d9433a", "#ef8a2f", "#f2c938", "#79b543", "#3f8fc4", "#6d4fa1"),
    "ice":     ("#1f2326", "#2bb3c0", "#eef0ea", "#6d7b85", "#0f6f7c", "#f2c230"),
    "ember":   ("#201c1d", "#e0457b", "#f2c230", "#2aa6c9", "#f3ece0", "#8a3a5c"),
    "moss":    ("#f0e6cc", "#2f4a3a", "#7fa65a", "#d8a13a", "#b4553a", "#a9c4b0"),
    "dusk":    ("#2b2d4f", "#f07b5a", "#f5c45e", "#a2577f", "#f3e9dc", "#5f8fb0"),
}

# Palettes for scenes, by scene colour number: background, stone top, side
# and shadow, brick top, side and shadow, ribbon.
SCENE_PALETTES = {
    "stone":  ("#26292e", "#efe3c8", "#a7a39a", "#6b6a66", "#d9483b", "#a3342b", "#6c2420", "#2f9c7c"),
    "paper":  ("#efe6d2", "#f9f5ec", "#9aa3a6", "#4c5559", "#3cb3a6", "#23877d", "#145a54", "#e0574a"),
    "sunset": ("#2b2d4f", "#f5e3c3", "#c9a98a", "#8c6d5a", "#f5a35a", "#d9683b", "#9c3f2a", "#5fa8c9"),
}


class Puzzle:
    """One board to play.

    puzzle_id  "paper-3", or "random-hard-<seed>"
    title      what the screen shows, "Paper 3"
    colours    colour number for every cell, by cell index
    palette    '#rrggbb' for each colour number
    par        fewest moves that solve it
    solution   [(cell index, colour), ...] reaching par, or None
    """

    def __init__(self, puzzle_id, title, colours, palette, par, solution=None,
                 chapter=None, mode=None):
        self.puzzle_id = puzzle_id
        self.title = title
        self.colours = list(colours)
        self.palette = list(palette)
        self.par = par
        self.solution = solution
        self.chapter = chapter
        self.mode = mode

    def grid(self, margin=0.0, gap=0.0):
        return compose.TriangleGrid(compose.BOARD_STRIPS, compose.BOARD_SLOTS, "columns", margin, gap)

    def board(self, grid=None):
        grid = grid or self.grid()
        return rules.FoldBoard(grid, {cell: self.colours[grid.index_of(cell)] for cell in grid.cells()})


# --- the Journey --------------------------------------------------------------------

def decode_cells(text):
    """Colour numbers from run-length text: "a12b5" is twelve 0s then five 1s."""
    colours = []
    for letter, count in re.findall(r"([a-z])(\d+)", text):
        colours.extend([ord(letter) - ord("a")] * int(count))
    return colours


def encode_cells(colours):
    """The run-length text decode_cells() reads."""
    runs = []
    for colour in colours:
        if runs and runs[-1][0] == colour:
            runs[-1][1] += 1
        else:
            runs.append([colour, 1])
    return "".join(chr(ord("a") + colour) + str(count) for colour, count in runs)


def chapters():
    """[(chapter id, title, [Puzzle, ...]), ...] in play order."""
    found = []
    for chapter_id, title in CHAPTERS:
        rows = [row for row in LEVELS if row["chapter"] == chapter_id]
        puzzles = [Puzzle("{}-{}".format(chapter_id, number), "{} {}".format(title, number),
                          decode_cells(row["cells"]), row["palette"], row["par"],
                          [tuple(step) for step in row["solution"]], chapter=chapter_id)
                   for number, row in enumerate(rows, 1)]
        found.append((chapter_id, title, puzzles))
    return found


def journey():
    """Every Journey puzzle in play order."""
    return [puzzle for chapter_id, title, puzzles in chapters() for puzzle in puzzles]


# --- Random puzzles -------------------------------------------------------------------

def _paint(motif, rng):
    """(colours, palette) for a motif or scene, palette picked by rng."""
    grid = compose.board_grid()
    if motif.startswith("scene:"):
        raw = scenes.render(grid, scenes.build(motif[len("scene:"):], rng))
        used = sorted(set(raw), key=lambda colour: (-raw.count(colour), colour))
        palette = SCENE_PALETTES[rng.choice(sorted(SCENE_PALETTES))]
        mapping = {colour: index for index, colour in enumerate(used)}
        return [mapping[colour] for colour in raw], [palette[colour] for colour in used]
    colours = compose.compact(compose.MOTIFS[motif](rng).paint(grid))
    palette = PALETTES[rng.choice(sorted(PALETTES))]
    return colours, list(palette[:len(set(colours))])


def random_puzzle(mode, seed):
    """A Random puzzle for mode ("easy", "medium" or "hard"): the same seed
    always gives the same puzzle. Returns the first attempt whose exact par
    lands in the band, or the closest found within the time allowed."""
    settings = dict((key, value) for key, title, value in RANDOM_MODES)[mode]
    titles = dict((key, title) for key, title, value in RANDOM_MODES)
    low, high = settings["par"]
    rng = random.Random("fold-random/{}/{}".format(mode, seed))
    began = time.time()
    best, best_score = None, None
    for attempt in range(RANDOM_ATTEMPTS):
        colours, palette = _paint(rng.choice(settings["motifs"]), rng)
        if len(set(colours)) > len(palette):
            continue
        grid = compose.board_grid()
        graph = rules.region_graph(grid, {cell: colours[grid.index_of(cell)] for cell in grid.cells()})
        if len(graph) > RANDOM_MAX_REGIONS or len(graph) < 2:
            continue
        found = solver.solve(graph, RANDOM_SOLVE_BUDGET)
        steps = [(grid.index_of(cell), colour) for cell, colour in found.moves]
        puzzle = Puzzle("random-{}-{}".format(mode, seed), "{} puzzle".format(titles[mode]),
                        colours, palette, found.length, steps, mode=mode)
        miss = max(low - found.length, found.length - high, 0)
        score = (not found.exact, miss)
        if score == (False, 0):
            return puzzle
        if best is None or score < best_score:
            best, best_score = puzzle, score
        if time.time() - began > RANDOM_SECONDS and best is not None:
            break
    if best is None:
        return random_puzzle(mode, "{}+".format(seed))
    return best


# --- the Journey, as data -------------------------------------------------------
# Picked from compose.py and scenes.py motifs (motif and seed kept for
# reference only) and ordered by par within each chapter.

CHAPTERS = (
    ("paper", "Paper"),
    ("stars", "Stars"),
    ("hives", "Hives"),
    ("blocks", "Blocks"),
    ("layers", "Layers"),
    ("towers", "Towers"),
)

LEVELS = (
    {"chapter": "paper", "motif": "quilt", "seed": 8, "par": 2,
     "palette": ("#f0e6cc", "#2f4a3a", "#7fa65a",),
     "solution": ((12, 0), (0, 2),),
     "cells": "a12b3a25b5a18b17a6c1a6b15a6c3a6b13a6c4a6b13a6c3a6b15a6c2a5b17a6c1a11b5a25b3a14"},
    {"chapter": "paper", "motif": "quilt", "seed": 4, "par": 2,
     "palette": ("#1f2326", "#2bb3c0", "#eef0ea",),
     "solution": ((10, 1), (0, 2),),
     "cells": "b10a7b14a11c1a11b7a9c3a9b4c1b4a4c11a4b4c3b4a4c9a4b4c4b4a4c9a4b4c3b4a4c11a4b4c2b3a9c3a9b4c1b2a11c1a11b14a7b12"},
    {"chapter": "paper", "motif": "quilt", "seed": 0, "par": 3,
     "palette": ("#26292e", "#efe3c8", "#d9483b", "#2f9c7c",),
     "solution": ((10, 1), (0, 3), (0, 2),),
     "cells": "b10a7b14a11c1a11b7a9c3a9b4d1b4a4c11a4b4d3b4a4c9a4b4d4b4a4c9a4b4d3b4a4c11a4b4d2b3a9c3a9b4d1b2a11c1a11b14a7b12"},
    {"chapter": "paper", "motif": "hexagram", "seed": 1, "par": 3,
     "palette": ("#3f7f9e", "#e8b23a", "#c8323c", "#f1e6d0",),
     "solution": ((63, 2), (12, 0), (0, 3),),
     "cells": "a12c3a25c5a18b17a13b15a15b5d3b5a16c1b4d3b4c1a15c3b9c3a13c5b7c5a18b5a25b3a14"},
    {"chapter": "paper", "motif": "spiral", "seed": 6, "par": 3,
     "palette": ("#201c1d", "#e0457b",),
     "solution": ((19, 0), (0, 1), (0, 0),),
     "cells": "a6b12a1b6a9b5a10b6a7b6a11b6a5b6a6b1a6b6a3b6a5b4a6b6a4b6a4b5a6b4a5b6a1b6a6b5a6b11a6b7a6b10a5b6a1b2a6b1a12b6a2"},
    {"chapter": "paper", "motif": "spiral", "seed": 2, "par": 3,
     "palette": ("#d9433a", "#ef8a2f", "#f2c938",),
     "solution": ((19, 1), (8, 0), (4, 2),),
     "cells": "c4a4b1a10c4b4a2c3a4b10a3c4b4a1c2a4b4c1b6a4c4b4c1a4b4c6b3a4c4b3a4b4c4a1c2b4a4c4b2a2b4c4a3b4a4c4b4a3b4c4a4b1a4c4b4a5b4c3a8c4b4a2c1a4b4c8a1c4b4a3c2a4b3c12b4a4"},
    {"chapter": "stars", "motif": "hexagram", "seed": 112, "par": 3,
     "palette": ("#201c1d", "#e0457b", "#f2c230", "#2aa6c9",),
     "solution": ((63, 2), (12, 0), (0, 3),),
     "cells": "a12c3a25c5a18b17a13b5d5b5a15b3d7b3a16c1b2d7b2c1a15c3b2d5b2c3a13c5b7c5a18b5a25b3a14"},
    {"chapter": "stars", "motif": "hexagram", "seed": 104, "par": 4,
     "palette": ("#26292e", "#efe3c8", "#d9483b", "#2f9c7c", "#a7a39a",),
     "solution": ((31, 2), (10, 0), (0, 3), (0, 4),),
     "cells": "a10c7a14b23a7b21a9b7d5b7a11b5d2e3d2b5a12c1b4d2e3d2b4c1a11c3b4d5b4c3a9c5b11c5a7c7b9c7a14b7a12"},
    {"chapter": "stars", "motif": "hexagram", "seed": 108, "par": 4,
     "palette": ("#d9433a", "#ef8a2f", "#f2c938", "#79b543", "#3f8fc4",),
     "solution": ((63, 2), (12, 0), (0, 3), (0, 4),),
     "cells": "a12c3a25c5a18b17a13b5d5b5a15b3d2e3d2b3a16c1b2d2e3d2b2c1a15c3b2d5b2c3a13c5b7c5a18b5a25b3a14"},
    {"chapter": "stars", "motif": "spiral", "seed": 103, "par": 4,
     "palette": ("#2b2d4f", "#f07b5a", "#f5c45e",),
     "solution": ((4, 2), (0, 1), (0, 0), (0, 2),),
     "cells": "c4a4b10c1b4a4c5a4b3c10b4a4c3a4b4c6a1c4b4a4c1a4b4c3a6c4b4a7b4c4a2b1a4c4b4a2c2a4b4c4b3a4c4b4c3a4b4c1b4a4c4b4a1c4a4b8a3c4b4a2b1c4a4b1a8c4b4a3b2c4a12c3b4a4"},
    {"chapter": "stars", "motif": "rosette", "seed": 105, "par": 4,
     "palette": ("#3f7f9e", "#e8b23a", "#c8323c", "#f1e6d0",),
     "solution": ((128, 1), (10, 0), (6, 0), (19, 0),),
     "cells": "a6c2a2b1a8c2a13c2a3b2a5b2a1c2a11c2a5b2a3b2a3c2a9c2a7b2a1b2a5c2a7c2a1b7d3b1a7c2a6c2a7b1d3b7a1c2a7c2a5b2a1b2a7c2a9c2a3b2a3b2a5c2a11c2a1b2a5b2a3c2a13c2a8b1a2c2a8"},
    {"chapter": "stars", "motif": "rosette", "seed": 109, "par": 4,
     "palette": ("#1f2326", "#2bb3c0", "#eef0ea", "#6d7b85",),
     "solution": ((98, 0), (8, 2), (8, 1), (6, 0),),
     "cells": "a6b2a2c1a8b2a13b2a3c2a5c2a1b2a11b2a5c2a3c2a3b2a9b2a6d5c1a5b2a7b2a1c5d7a6b2a6b2a6d7c5a1b2a7b2a5c1d5a6b2a9b2a3c2a3c2a5b2a11b2a1c2a5c2a3b2a13b2a8c1a2b2a8"},
    {"chapter": "hives", "motif": "chevrons", "seed": 209, "par": 4,
     "palette": ("#26292e", "#efe3c8", "#d9483b",),
     "solution": ((10, 1), (6, 0), (2, 2), (158, 2),),
     "cells": "c2a4b4c7b4a4c5a4b4c4a1c4b4a4c3a4b4c4a3c4b4a4c2a3b4c4a5c4b4a4c1a2b4c4a7c4b4a5b4c4a4b1a4c4b4a3b4c4a4b3a4c4b4a2b3c4a4b5a4c4b4a1b2c4a4b7a4c4b5c4a4b4c1b4a4c4b3"},
    {"chapter": "hives", "motif": "honeycomb", "seed": 204, "par": 4,
     "palette": ("#2b2d4f", "#f07b5a", "#f5c45e",),
     "solution": ((18, 1), (9, 0), (0, 2), (0, 1),),
     "cells": "a9b9a9b2a10b7a11b1a10c7a11c1a9c9a9c3a7c11a7c4b7c11b7c3b9c9b9c2b10c7b11c1b10a7b11a1b9a9b9a2"},
    {"chapter": "hives", "motif": "rosette", "seed": 222, "par": 4,
     "palette": ("#3f7f9e", "#e8b23a", "#c8323c", "#f1e6d0", "#2b2a4a",),
     "solution": ((8, 0), (0, 2), (0, 3), (0, 4),),
     "cells": "a8b11a17b2a2c1a6b2a15b2a3c2a3c2a1b2a13b2a4d5c1a3b2a11b2a1c3d2e3d2a4b2a10b2a4d2e3d2c3a1b2a11b2a3c1d5a4b2a13b2a1c2a3c2a3b2a15b2a6c1a2b2a17b11a10"},
    {"chapter": "hives", "motif": "honeycomb", "seed": 200, "par": 4,
     "palette": ("#f0e6cc", "#2f4a3a", "#7fa65a",),
     "solution": ((98, 0), (10, 2), (5, 1), (5, 0),),
     "cells": "a5c5a7c5a12b5a7b5a11b7a5b7a5b1c4b7c5b7c5b1c5b5c7b5c12a5c7a5c11a7c5a7c5a1b4a7b5a7b5a1b5a5b7a5b12c5b7c5b7"},
    {"chapter": "hives", "motif": "chevrons", "seed": 233, "par": 5,
     "palette": ("#1f2326", "#2bb3c0", "#eef0ea", "#6d7b85",),
     "solution": ((10, 1), (6, 3), (2, 2), (0, 3), (0, 1),),
     "cells": "c2d4b4a7b4d4c5d4b4a4c1a4b4d4c3d4b4a4c3a4b4d4c2d3b4a4c5a4b4d4c1d2b4a4c7a4b4d5b4a4c4d1c4a4b4d3b4a4c4d3c4a4b4d2b3a4c4d5c4a4b4d1b2a4c4d7c4a4b5a4c4d4b1d4c4a4b3"},
    {"chapter": "hives", "motif": "rosette", "seed": 230, "par": 5,
     "palette": ("#d9433a", "#ef8a2f", "#f2c938", "#79b543", "#3f8fc4",),
     "solution": ((98, 0), (8, 2), (8, 1), (6, 0), (0, 4),),
     "cells": "a6b2a2c1a8b2a13b2a3c2a5c2a1b2a11b2a5c2a3c2a3b2a9b2a6d5c1a5b2a7b2a1c5d2e3d2a6b2a6b2a6d2e3d2c5a1b2a7b2a5c1d5a6b2a9b2a3c2a3c2a5b2a11b2a1c2a5c2a3b2a13b2a8c1a2b2a8"},
    {"chapter": "blocks", "motif": "scene:stairs", "seed": 303, "par": 3,
     "palette": ("#2b2d4f", "#8c6d5a", "#c9a98a", "#f5e3c3",),
     "solution": ((0, 3), (0, 1), (0, 2),),
     "cells": "a44d1b2a25d1b4a23d1b6a21d1b8a19d1b10a17d2c10a17d1c10a66"},
    {"chapter": "blocks", "motif": "scene:beams", "seed": 306, "par": 6,
     "palette": ("#2b2d4f", "#f5a35a", "#5fa8c9", "#9c3f2a", "#f5e3c3", "#c9a98a",),
     "solution": ((2, 0), (4, 0), (11, 0), (13, 0), (144, 0), (0, 4),),
     "cells": "a2b2c4a3b2d2a15b2c4a5b2d2a13b2c4a7b2d2a11e1b1c4a9b2d2a9e2c4a11b2d2a7e2f1c3a13b2d2a5e2f2c2a15b2d2a3e2f2a1c1a17b2d2a1e2f2a21b2d2e1f2a23b2d2f1a4"},
    {"chapter": "blocks", "motif": "scene:blocks", "seed": 301, "par": 6,
     "palette": ("#efe6d2", "#23877d", "#145a54", "#3cb3a6", "#f9f5ec", "#4c5559", "#9aa3a6",),
     "solution": ((0, 4), (0, 5), (0, 3), (41, 1), (41, 3), (0, 6),),
     "cells": "a12e3f8a13e1f3d1c12a11e3f1d3c12a9d1e3g1d3b4d1c8a7d3e1g3d1b4d3c8a6d3b8e1d3b8a7d1b8e3d1b8a17e3g1d3b4a19e1g3d1b4a34"},
    {"chapter": "blocks", "motif": "scene:blocks", "seed": 305, "par": 6,
     "palette": ("#efe6d2", "#145a54", "#3cb3a6", "#23877d", "#f9f5ec", "#9aa3a6", "#4c5559",),
     "solution": ((168, 2), (108, 0), (0, 4), (0, 6), (0, 5), (0, 1),),
     "cells": "a16e3g4a17e1g4e3f4a16e3g4e1f4a17e3f4e1g3c1b4a14e1f4e3g1c3b4a9c1b8e3c4d4a8c3b8e1c4d4a9c4b8c3d4a11c4b8c1d4a13c3d12a6"},
    {"chapter": "blocks", "motif": "scene:pillars", "seed": 300, "par": 6,
     "palette": ("#d9483b", "#26292e", "#a7a39a", "#6b6a66", "#efe3c8", "#a3342b", "#6c2420",),
     "solution": ((10, 3), (10, 4), (10, 2), (10, 1), (25, 1), (202, 1),),
     "cells": "b10a15g2b11a17g2b9e1d6a12g2b7a1e1c6a13g1b6a14e1d4a4b6a14e1c4a4b7a3e1d3e1d4a9f1b8a2e1c3e1c4a8f2b9a17f2b11a15f2b2"},
    {"chapter": "blocks", "motif": "scene:pillars", "seed": 304, "par": 6,
     "palette": ("#d9483b", "#26292e", "#a7a39a", "#6b6a66", "#efe3c8", "#a3342b", "#6c2420",),
     "solution": ((10, 4), (10, 3), (10, 2), (10, 1), (25, 1), (202, 1),),
     "cells": "b10a2e1d4a8g2b11a3e1c4a9g2b9a4e1d10a4g2b7a5e1c10a5g1b6a8e1d6a8b6a8e1c6a8b7a21f1b8a19f2b9a3e1d8a5f2b11a2e1c8a4f2b2"},
    {"chapter": "layers", "motif": "layered", "seed": 402, "par": 5,
     "palette": ("#1f2326", "#2bb3c0", "#eef0ea", "#6d7b85", "#0f6f7c", "#f2c230",),
     "solution": ((63, 3), (12, 2), (10, 0), (0, 4), (0, 5),),
     "cells": "a10c2d3c2a14c9d5c9a7c2b17c2a4e1a4c2b15c2a4e3a4c2b5f3b5c2a4e4a4c2d1b4f3b4d1c2a4e3a4c2d3b9d3c2a4e2a3c2d5b7d5c2a4e1a2c9b5c9a14c2b3c2a12"},
    {"chapter": "layers", "motif": "layered", "seed": 407, "par": 5,
     "palette": ("#26292e", "#efe3c8", "#d9483b", "#2f9c7c",),
     "solution": ((128, 2), (6, 0), (0, 1), (0, 0), (0, 2),),
     "cells": "a6b12a1b6a9b5a1c1a8b6a7b6a1c2a3c2a3b6a5b6a3c2a1c2a5b6a3b5c5d3c1b1a6b6a4b6a1c1d3c5a5b4a5b5c2b1c2b3a6b5a6b3c2b3c2b1a6b7a6b8c1b1a5b6a1b2a6b1a12b6a2"},
    {"chapter": "layers", "motif": "layered", "seed": 403, "par": 5,
     "palette": ("#201c1d", "#e0457b", "#f2c230", "#2aa6c9", "#f3ece0",),
     "solution": ((63, 2), (8, 4), (8, 1), (4, 3), (0, 2),),
     "cells": "d4b4c4e3c3d1c4b4d5b4c3d1e5d4c4b4d3b3a17c3b4d1b4c1a15d1c4b7c3a5c3a5d3c4b2d2b4c1e1a4c3a4e1b1d4c4d3b3e3a9e3d3c4b1d4b1e5a7e5d1c4b2c1d4b4c1b1a5b2d4c4b3c2d4b6a3b3d3c4b4"},
    {"chapter": "layers", "motif": "layered", "seed": 409, "par": 5,
     "palette": ("#3f7f9e", "#e8b23a", "#c8323c", "#f1e6d0", "#2b2a4a",),
     "solution": ((128, 3), (40, 1), (19, 1), (8, 0), (4, 2),),
     "cells": "c4a4b1a10c4b4a2c3a4b4d1b5a3c4b4a1c2a4b4c1d2b3d2a3c4b4c1a4b4c3d2c1d2b1a4c4b3a4b3d5e3d1b3a4c4b2a2b4c4a1d1e3d5a1c4b4a3b4c3d2a1d2b1a4c4b4a5b4c1d2a3d2a3c4b4a2c1a4b4c6d1c1a1c4b4a3c2a4b3c12b4a4"},
    {"chapter": "layers", "motif": "layered", "seed": 405, "par": 5,
     "palette": ("#f0e6cc", "#2f4a3a", "#7fa65a", "#d8a13a", "#b4553a",),
     "solution": ((63, 3), (34, 2), (5, 1), (0, 4), (0, 3),),
     "cells": "b5c5b2e3b2c5b12d5b1e5b1d5b11d1a17d1b5d1c4d2a15d2c5d1c5d2a5b3a5d2c12b2e1a4b3a4e1b2c11b2e3a9e3b2c5b1d4b1e5a7e5b1d5b1d5b5d1a5d1b5d12c5d2a3d2c5d7"},
    {"chapter": "layers", "motif": "layered", "seed": 406, "par": 6,
     "palette": ("#2b2d4f", "#f07b5a", "#f5c45e", "#a2577f", "#f3e9dc",),
     "solution": ((128, 4), (40, 2), (8, 2), (8, 0), (4, 1), (0, 2),),
     "cells": "b4a4d11c4a4b5a4d2c1b1e1b6d2c4a4b3a4d2c2b1e2b3e2b1d2c4a4b1a4d2c2b3e2a1e2a1b2d2c4a7d2c1e5b3e1a3b2d2c4a2b2a2d2c4b1e1b3e5a1d2b2c4b3a2d2c3e2c1e2c1a4d2b2c4a1b4a2d2c1e2c3e2a3d2b2c4a2c1b4a2d2c1a5e1a2d2b2c4a3c2b4a2d11b2c4a4"},
    {"chapter": "towers", "motif": "scene:blocks", "seed": 503, "par": 6,
     "palette": ("#2b2d4f", "#9c3f2a", "#8c6d5a", "#d9683b", "#f5a35a", "#f5e3c3", "#c9a98a",),
     "solution": ((0, 4), (0, 1), (0, 5), (0, 2), (0, 3), (0, 6),),
     "cells": "a8e3b12a14e3f1c12a14e1f3c12a14f3e1b12a14f1e3b12a14e3d12a15e1d12a17f3g4a23f1g4a38"},
    {"chapter": "towers", "motif": "scene:pillars", "seed": 501, "par": 6,
     "palette": ("#d9483b", "#26292e", "#a7a39a", "#6b6a66", "#a3342b", "#6c2420", "#efe3c8",),
     "solution": ((10, 3), (10, 6), (10, 2), (10, 1), (25, 1), (202, 1),),
     "cells": "b10a15f2b11a17f2b9a6g1d4a8f2b7a7g1c4a9f1b4g1d8a16b4g1c8a16b7a21e1b8a19e2b9a17e2b11a15e2b2"},
    {"chapter": "towers", "motif": "scene:pillars", "seed": 509, "par": 6,
     "palette": ("#f5a35a", "#2b2d4f", "#c9a98a", "#8c6d5a", "#d9683b", "#9c3f2a", "#f5e3c3",),
     "solution": ((10, 6), (10, 3), (10, 2), (10, 1), (25, 1), (202, 1),),
     "cells": "b10a4g1d6a4f2b11a5g1c6a5f2b9a4g1d6a8f2b7a5g1c6a9f1b6a4g1d10a8b6a4g1c10a8b7a21e1b8a19e2b9a17e2b11a15e2b2"},
    {"chapter": "towers", "motif": "scene:blocks", "seed": 507, "par": 6,
     "palette": ("#efe6d2", "#9aa3a6", "#4c5559", "#f9f5ec", "#23877d", "#145a54", "#3cb3a6",),
     "solution": ((8, 0), (11, 0), (0, 2), (40, 2), (0, 3), (0, 1),),
     "cells": "a8g3f12a13d1g3e12a12d3g1e12a12d4b4d1c7d1c4a7d4b4d3c5d3c4a6d3b5d3b5d3b4a7d1b7d1b7d1b4a12d1c12a15d3c12a14d3b12a6"},
    {"chapter": "towers", "motif": "scene:pillars", "seed": 505, "par": 7,
     "palette": ("#d9483b", "#26292e", "#a7a39a", "#6b6a66", "#efe3c8", "#a3342b", "#6c2420",),
     "solution": ((17, 2), (17, 4), (10, 3), (10, 1), (25, 1), (202, 1), (0, 0),),
     "cells": "b10e1d6a8g2b11a1e1c6a9g2b7e1d1e1d10a8g2b6e1c1e1c10a9g1b6a23b6a23b7a7e1d4a9f1b8a6e1c4a8f2b9a3e1d4a9f2b11a2e1c4a8f2b2"},
    {"chapter": "towers", "motif": "weave", "seed": 502, "par": 7,
     "palette": ("#1f2326", "#2bb3c0", "#eef0ea", "#6d7b85",),
     "solution": ((6, 1), (10, 1), (6, 3), (6, 2), (170, 2), (5, 0), (0, 1),),
     "cells": "a5c1d3b1a7c1d3b1a12b1d3c1a7b1d3c1a11b3d1c3a5b3d1c3a5b1a3b4a1c4a3b4a1c4a3b2c1a1b4a3c4a1b4a3c4a1b3c1d1b3a5c3d1b3a5c3d1b3d3b1a7c1d3b1a7c1d3b1a1d3c1a7b1d3c1a7b1d3c1a1b1d1c3a5b3d1c3a5b3d1c3b1a1c4a3b4a1c4a3b4a1c3"},
)
