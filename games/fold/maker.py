"""
Fold maker: designing your own puzzles. Pure Python, smoke-tested headless.

A Design is a palette (up to MAX_COLOURS '#rrggbb' strings) and a colour
number for every cell of the 10 x 29 board. Drawing is done with brushes:

    triangle   one triangle
    hexagon    the six triangles round the lattice corner nearest the
               touch: the quickest way to draw isometric cubes and hexagons
    fill       the whole same-coloured region under the touch

and a mirror, which repeats every stroke as the board's own symmetries:
left-right, top-bottom or both. Mirroring a triangle lattice cell by cell
is exact here: strip s maps to strips - 1 - s, and slot k to slots - 1 - k
(the board has an odd number of slots), and both keep each triangle's
shape, so mirrored drawings are always clean.

Palette changes: add a lighter or darker shade of a colour (same hue in
OKLCh, lightness stepped by SHADE_STEP), add the next unused paper colour,
or remove a colour (its triangles take the background colour).

MyPuzzles keeps saved designs in games/fold/my_puzzles.json, each with the
par the solver finds when it is saved, and hands them to the screen as
collection.Puzzle objects ("mine-<n>").
"""

import json
import os

from games.fold import collection, compose, rules, solver
from games.gradient import colour as colour_maths


# --- editable maker settings ---------------------------------------------------

MAX_COLOURS = 8
SHADE_STEP = 0.09             # OKLab lightness added or taken by a shade
HISTORY_LIMIT = 80            # strokes Undo can take back
SAVE_SOLVE_BUDGET = 20000     # solver positions spent proving par on save
EXACT_REGION_LIMIT = 45       # busier designs get the greedy par (an upper bound)

STARTING_PALETTE = ("#26292e", "#efe3c8", "#d9483b")
PAPER_COLOURS = (
    "#26292e", "#efe3c8", "#d9483b", "#2f9c7c", "#a7a39a", "#e8b23a",
    "#3f7f9e", "#2b2a4a", "#f07b5a", "#7fa65a", "#e0457b", "#2bb3c0",
    "#6d4fa1", "#f3ece0", "#8a3a5c", "#6b6a66",
)

BRUSHES = ("triangle", "hexagon", "fill")
MIRRORS = ("off", "left-right", "top-bottom", "both")


# --- colour helpers ----------------------------------------------------------------

def srgb_from_hex(hex_colour):
    return tuple(int(hex_colour[index:index + 2], 16) / 255.0 for index in (1, 3, 5))


def shade(hex_colour, step):
    """The same hue and chroma, lightness moved by step (screen-safe)."""
    lightness, chroma, hue = colour_maths.oklch_from_oklab(colour_maths.oklab_from_srgb(srgb_from_hex(hex_colour)))
    lightness = min(0.97, max(0.12, lightness + step))
    fitted = colour_maths.fit_chroma(lightness, chroma, hue)
    return colour_maths.hex_from_srgb(colour_maths.srgb_from_oklab(colour_maths.oklab_from_oklch(fitted)))


# --- a design ------------------------------------------------------------------------

class Design:
    """The board being drawn: palette, colours by cell index, and undo history."""

    def __init__(self, palette=STARTING_PALETTE, colours=None, puzzle_id=None, title=None):
        self.grid = compose.board_grid()
        self.palette = list(palette)
        self.colours = list(colours) if colours is not None else [0] * len(self.grid.cells())
        self.puzzle_id = puzzle_id
        self.title = title
        self.history = []
        self.corner_cells = self._corner_map()

    @classmethod
    def from_puzzle(cls, puzzle, keep_identity=False):
        """Start from any puzzle; keep its id only when editing your own."""
        return cls(puzzle.palette, puzzle.colours,
                   puzzle.puzzle_id if keep_identity else None,
                   puzzle.title if keep_identity else None)

    # --- undo ---------------------------------------------------------------------

    def remember(self):
        """Call before each stroke or palette change, so Undo can take it back."""
        self.history.append((list(self.palette), list(self.colours)))
        del self.history[:-HISTORY_LIMIT]

    def undo(self):
        if not self.history:
            return False
        self.palette, self.colours = self.history.pop()
        return True

    # --- brushes ------------------------------------------------------------------

    def _corner_map(self):
        """Lattice corner (in half-sides along, strips across) -> the cells touching it."""
        corners = {}
        for cell in self.grid.cells():
            for along, across in self.grid.flat_corners(cell):
                key = (int(round(along * 2)), int(round(across / compose.DEPTH)))
                corners.setdefault(key, []).append(cell)
        return corners

    def brush_cells(self, brush, cell, flat_point=None):
        """The cells one dab of brush covers at cell (flat_point: the touch, side 1)."""
        if brush == "triangle":
            return [cell]
        if brush == "hexagon":
            point = flat_point or compose.patterns.centroid(self.grid.flat_corners(cell))
            nearest = min(self.grid.flat_corners(cell),
                          key=lambda corner: (corner[0] - point[0]) ** 2 + (corner[1] - point[1]) ** 2)
            key = (int(round(nearest[0] * 2)), int(round(nearest[1] / compose.DEPTH)))
            return list(self.corner_cells.get(key, [cell]))
        if brush == "fill":
            board = rules.FoldBoard(self.grid, self.cell_colours())
            return [member for member, steps in board.region_of(cell)]
        raise ValueError("brush must be one of {}, not {!r}".format(BRUSHES, brush))

    def mirrored(self, cells, mirror):
        """cells plus their images under the mirror."""
        strips, slots = self.grid.strips, self.grid.slots
        found = set(cells)
        for strip, slot in cells:
            if mirror in ("left-right", "both"):
                found.add((strips - 1 - strip, slot))
            if mirror in ("top-bottom", "both"):
                found.add((strip, slots - 1 - slot))
            if mirror == "both":
                found.add((strips - 1 - strip, slots - 1 - slot))
        return found

    def paint(self, cells, colour):
        """Colour cells; True when anything changed."""
        changed = False
        for cell in cells:
            index = self.grid.index_of(cell)
            if self.colours[index] != colour:
                self.colours[index] = colour
                changed = True
        return changed

    def dab(self, brush, cell, colour, mirror="off", flat_point=None):
        """One brush dab with the mirror applied; True when anything changed.
        (Fill fills each mirrored region, so symmetric fills stay symmetric.)"""
        if brush == "fill":
            changed = False
            for target in self.mirrored([cell], mirror):
                changed = self.paint(self.brush_cells("fill", target), colour) or changed
            return changed
        return self.paint(self.mirrored(self.brush_cells(brush, cell, flat_point), mirror), colour)

    # --- palette ------------------------------------------------------------------

    def can_add(self):
        return len(self.palette) < MAX_COLOURS

    def add_colour(self, hex_colour):
        """Add a colour; returns its number, or None when the palette is full."""
        if not self.can_add():
            return None
        self.palette.append(hex_colour)
        return len(self.palette) - 1

    def add_shade(self, index, step):
        return self.add_colour(shade(self.palette[index], step))

    def add_new(self):
        unused = [paper for paper in PAPER_COLOURS if paper not in self.palette]
        return self.add_colour(unused[0] if unused else shade(self.palette[-1], SHADE_STEP))

    def remove_colour(self, index):
        """Remove a colour: its triangles take colour 0 (or 1 when removing 0).
        Higher colour numbers move down one. False when only one colour is left."""
        if len(self.palette) <= 1:
            return False
        replacement = 0 if index != 0 else 1
        self.colours = [replacement if value == index else value for value in self.colours]
        self.colours = [value - 1 if value > index else value for value in self.colours]
        del self.palette[index]
        return True

    # --- reading the design ------------------------------------------------------------

    def cell_colours(self):
        return {cell: self.colours[self.grid.index_of(cell)] for cell in self.grid.cells()}

    def region_graph(self):
        return rules.region_graph(self.grid, self.cell_colours())

    def summary(self):
        """'5 colours · 23 regions' for the maker's status line."""
        used = len(set(self.colours))
        return "{} colour{} · {} regions".format(used, "" if used == 1 else "s", len(self.region_graph()))

    def solve(self):
        """(par, exact, solution as (cell index, colour) taps)."""
        graph = self.region_graph()
        if len(graph) > EXACT_REGION_LIMIT:
            moves, exact = solver.best_effort_plan(graph), False
        else:
            found = solver.solve(graph, SAVE_SOLVE_BUDGET)
            moves, exact = found.moves, found.exact
        return len(moves), exact, [(self.grid.index_of(cell), colour) for cell, colour in moves]

    def tidy(self):
        """(palette, colours) with unused colours dropped and the rest renumbered."""
        used = sorted(set(self.colours))
        mapping = {old: new for new, old in enumerate(used)}
        return [self.palette[old] for old in used], [mapping[value] for value in self.colours]


# --- saved designs -----------------------------------------------------------------

class MyPuzzles:
    """Saved designs in one JSON file (path None keeps them in memory only)."""

    def __init__(self, path):
        self.path = path
        self.records = []
        self.next_number = 1
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
                self.records = list(data.get("puzzles", []))
                self.next_number = int(data.get("next_number", len(self.records) + 1))
            except (OSError, ValueError):
                self.records = []

    def save_file(self):
        if not self.path:
            return
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"puzzles": self.records, "next_number": self.next_number}, handle, indent=1)

    def puzzles(self):
        return [self.to_puzzle(record) for record in self.records]

    @staticmethod
    def to_puzzle(record):
        return collection.Puzzle(record["id"], record["title"], collection.decode_cells(record["cells"]),
                                 record["palette"], record["par"],
                                 [tuple(step) for step in record.get("solution", [])], chapter="mine")

    def save_design(self, design):
        """Store the design (new, or over its own earlier save); returns the record."""
        palette, colours = design.tidy()
        tidy = Design(palette, colours)
        par, exact, solution = tidy.solve()
        if design.puzzle_id is None:
            design.puzzle_id = "mine-{}".format(self.next_number)
            design.title = "My puzzle {}".format(self.next_number)
            self.next_number += 1
        record = {"id": design.puzzle_id, "title": design.title, "palette": palette,
                  "cells": collection.encode_cells(colours), "par": par, "exact": exact,
                  "solution": [list(step) for step in solution]}
        for position, existing in enumerate(self.records):
            if existing["id"] == design.puzzle_id:
                self.records[position] = record
                break
        else:
            self.records.append(record)
        self.save_file()
        return record

    def delete(self, puzzle_id):
        self.records = [record for record in self.records if record["id"] != puzzle_id]
        self.save_file()


def share_text(record):
    """One line of JSON for a saved design: paste it to share or to add it to the Journey."""
    return json.dumps({key: record[key] for key in ("title", "palette", "par", "cells")}, separators=(",", ":"))
