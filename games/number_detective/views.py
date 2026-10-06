"""
Number Detective's drawn tile row: four face-down tiles, A to D.

Drawn in draw() with no subviews, so a change is a single
set_needs_display(). Each tile shows its letter and then either its
revealed value, the player's own notes in a small grid (each value always
in the same spot), or a question mark. Tiles chosen for the armed question
card get an accent outline and their order (1, 2, 3), because "Which is
bigger" reads them in order. Taps are reported through on_tile_tapped(tile),
with None for a tap between tiles.
"""

import math

import ui

from style import theme
from tilegame.widgets import draw_centred_text

from games.number_detective.rules import TILE_COUNT, TILE_NAMES


SURFACE = theme.color("surface")
TEXT = theme.color("text")
MUTED = theme.color("muted")
BUTTON_COLOR = theme.color("button")
ACCENT = theme.color("tile")          # tiles chosen for a question
OPEN_OUTLINE = theme.color("sky")     # the tile the picker is open for
SUCCESS = theme.color("success")      # revealed values


class TilesView(ui.View):
    """The four hidden tiles in a row."""

    # --- editable look -------------------------------------------------------
    GAP = 8
    RADIUS = 14
    LETTER_HEIGHT = 24

    def __init__(self):
        super().__init__()
        self.on_tile_tapped = None
        self.pool_values = ()
        self.revealed = [None] * TILE_COUNT
        self.notes = [set() for _ in range(TILE_COUNT)]
        self.selection = []
        self.open_tile = None

    def show(self, pool_values, revealed, notes, selection, open_tile):
        self.pool_values = tuple(pool_values)
        self.revealed = list(revealed)
        self.notes = [set(tile_notes) for tile_notes in notes]
        self.selection = list(selection)
        self.open_tile = open_tile
        self.set_needs_display()

    # --- geometry and touch --------------------------------------------------

    def tile_frame(self, tile):
        width = (self.width - self.GAP * (TILE_COUNT - 1)) / TILE_COUNT
        return (tile * (width + self.GAP), 0, width, self.height)

    def tile_at(self, point):
        x, y = point
        for tile in range(TILE_COUNT):
            tile_x, _, width, height = self.tile_frame(tile)
            if tile_x <= x < tile_x + width and 0 <= y < height:
                return tile
        return None

    def touch_ended(self, touch):
        if self.on_tile_tapped is not None:
            self.on_tile_tapped(self.tile_at(touch.location))

    # --- drawing -------------------------------------------------------------

    def draw(self):
        for tile in range(TILE_COUNT):
            self._draw_tile(tile)

    def _draw_tile(self, tile):
        x, y, width, height = self.tile_frame(tile)
        shape = ui.Path.rounded_rect(x + 1, y + 1, width - 2, height - 2, self.RADIUS)
        ui.set_color(SURFACE)
        shape.fill()

        if tile in self.selection:
            shape.line_width = 3
            ui.set_color(ACCENT)
        elif tile == self.open_tile:
            shape.line_width = 3
            ui.set_color(OPEN_OUTLINE)
        else:
            shape.line_width = 1
            ui.set_color(BUTTON_COLOR)
        shape.stroke()

        draw_centred_text(TILE_NAMES[tile], ("AvenirNext-Bold", 16), MUTED,
                          x, y + 4, width, self.LETTER_HEIGHT - 4)
        if tile in self.selection:
            order = self.selection.index(tile) + 1
            draw_centred_text(str(order), ("AvenirNext-Bold", 13), ACCENT,
                              x + width - 22, y + 4, 18, 18)

        body_y = y + self.LETTER_HEIGHT
        body_height = height - self.LETTER_HEIGHT - 6
        big_font = ("AvenirNext-Bold", min(width, body_height) * 0.5)

        value = self.revealed[tile]
        if value is not None:
            draw_centred_text(str(value), big_font, SUCCESS, x, body_y, width, body_height)
        elif self.notes[tile] and self.pool_values:
            self._draw_notes(self.notes[tile], x + 4, body_y, width - 8, body_height)
        else:
            draw_centred_text("?", big_font, MUTED, x, body_y, width, body_height)

    def _draw_notes(self, notes, x, y, width, height):
        count = len(self.pool_values)
        columns = math.ceil(math.sqrt(count))
        rows = math.ceil(count / columns)
        cell_width = width / columns
        cell_height = height / rows
        font = ("AvenirNext-Medium", max(9, min(cell_width, cell_height) * 0.55))
        for index, value in enumerate(self.pool_values):
            if value in notes:
                row, col = divmod(index, columns)
                draw_centred_text(str(value), font, TEXT,
                                  x + col * cell_width, y + row * cell_height,
                                  cell_width, cell_height)