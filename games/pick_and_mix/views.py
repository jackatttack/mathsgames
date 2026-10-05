"""
Pick & Mix's drawn views: the score bar, the shared pool, and a player zone.

Each view is drawn in draw() with no subviews, so a change is a single
set_needs_display(). Views report taps through callbacks and never change
game state themselves; the screen asks the game, then redraws.

A zone keeps only its own selection (which tile is picked up and which
operation is armed). Merging follows Multiple Merge's feel: tap a tile and
it splits into + − × ÷ quadrants around a centre disc; tap a quadrant to
arm it, then tap another tile to merge into it. The centre cancels.
"""

import time

import ui

from style import theme
from tilegame.board_state import OPERATION_SYMBOLS
from tilegame.widgets import draw_centred_text


SURFACE = theme.color("surface")
TEXT = theme.color("text")
MUTED = theme.color("muted")
BUTTON_COLOR = theme.color("button")
TILE = theme.color("tile")
TILE_TEXT = theme.color("tile_text")
SUCCESS = theme.color("success")
PLAYER_COLORS = (theme.color("player_one"), theme.color("player_two"))
OPERATION_COLORS = {
    "+": theme.color("op_add"),
    "-": theme.color("op_subtract"),
    "×": theme.color("op_multiply"),
    "/": theme.color("op_divide"),
}

PLAYER_NAMES = ("Player 1", "Player 2")

# Which operation sits in which quadrant of a picked-up tile: (row, col).
QUADRANTS = {(0, 0): "+", (0, 1): "-", (1, 0): "×", (1, 1): "/"}

# Two taps on empty zone space this close together undo the player's last merge.
DOUBLE_TAP_SECONDS = 0.35


class ScoreBar(ui.View):
    """The target in a big chip, with each player's score either side."""

    # --- editable look -------------------------------------------------------
    CHIP_RADIUS = 16
    CHIP_WIDTH_RATIO = 0.36

    def __init__(self):
        super().__init__()
        self.target = None
        self.scores = (0, 0)

    def show(self, target, scores):
        self.target = target
        self.scores = tuple(scores)
        self.set_needs_display()

    def draw(self):
        width, height = self.width, self.height
        chip_width = min(150, width * self.CHIP_WIDTH_RATIO)
        chip_x = (width - chip_width) / 2

        ui.set_color(TILE)
        ui.Path.rounded_rect(chip_x, 2, chip_width, height - 4, self.CHIP_RADIUS).fill()
        if self.target is not None:
            draw_centred_text(str(self.target), ("AvenirNext-Bold", 40), TILE_TEXT,
                              chip_x, 2, chip_width, height - 4)

        side_width = chip_x - 8
        for player, x in ((0, 0), (1, chip_x + chip_width + 8)):
            draw_centred_text(PLAYER_NAMES[player], ("AvenirNext-DemiBold", 14),
                              PLAYER_COLORS[player], x, 6, side_width, 20)
            draw_centred_text(str(self.scores[player]), ("AvenirNext-Bold", 30),
                              TEXT, x, 26, side_width, height - 30)


class PoolView(ui.View):
    """The shared pool as chips. Taken chips stay, faded, in the taker's colour."""

    # --- editable look -------------------------------------------------------
    COLUMNS = 5
    GAP = 8
    RADIUS = 12
    HEIGHT_RATIO = 0.8      # chip height as a share of its width, at most

    def __init__(self):
        super().__init__()
        self.on_pick = None
        self.numbers = []
        self.taken_by = []
        self.enabled = True

    def show(self, numbers, taken_by, enabled):
        self.numbers = list(numbers)
        self.taken_by = list(taken_by)
        self.enabled = enabled
        self.set_needs_display()

    def chip_frame(self, index):
        count = max(1, len(self.numbers))
        rows = (count + self.COLUMNS - 1) // self.COLUMNS
        chip_width = (self.width - self.GAP * (self.COLUMNS - 1)) / self.COLUMNS
        chip_height = min(chip_width * self.HEIGHT_RATIO,
                          (self.height - self.GAP * (rows - 1)) / rows)
        total_height = rows * chip_height + (rows - 1) * self.GAP
        top = (self.height - total_height) / 2
        row, col = divmod(index, self.COLUMNS)
        return (col * (chip_width + self.GAP), top + row * (chip_height + self.GAP),
                chip_width, chip_height)

    def index_at(self, point):
        x, y = point
        for index in range(len(self.numbers)):
            chip_x, chip_y, chip_width, chip_height = self.chip_frame(index)
            if chip_x <= x < chip_x + chip_width and chip_y <= y < chip_y + chip_height:
                return index
        return None

    def touch_ended(self, touch):
        index = self.index_at(touch.location)
        if index is not None and self.on_pick is not None:
            self.on_pick(index)

    def draw(self):
        for index, value in enumerate(self.numbers):
            x, y, width, height = self.chip_frame(index)
            chip = ui.Path.rounded_rect(x, y, width, height, self.RADIUS)
            owner = self.taken_by[index]
            font = ("AvenirNext-Bold", height * (0.42 if value < 100 else 0.34))

            if owner is None:
                ui.set_color(TILE if self.enabled else BUTTON_COLOR)
                chip.fill()
                draw_centred_text(str(value), font,
                                  TILE_TEXT if self.enabled else MUTED,
                                  x, y, width, height)
            else:
                ui.set_color(BUTTON_COLOR)
                chip.fill()
                chip.line_width = 2
                ui.set_color(PLAYER_COLORS[owner])
                chip.stroke()
                draw_centred_text(str(value), font, PLAYER_COLORS[owner],
                                  x, y, width, height)


class ZoneView(ui.View):
    """One player's hand: a 2 × 2 grid of slots with quadrant merging."""

    # --- editable look -------------------------------------------------------
    TITLE_HEIGHT = 26
    FOOTER_HEIGHT = 22
    PADDING = 8
    GAP = 8
    RADIUS = 14
    TILE_RADIUS = 12
    DISC_RATIO = 0.3        # centre disc radius as a share of the tile size

    def __init__(self, player):
        super().__init__()
        self.player = player
        self.values = [None] * 4
        self.locked = False
        self.active = False
        self.counted = None
        self.distance = None

        self.selected = None          # slot picked up
        self.operation = None         # armed operation
        self._last_empty_tap = None   # when empty zone space was last tapped

        # Set by the screen.
        self.result_of = None    # function(source, destination, operation) -> value or None
        self.on_merge = None     # function(source, destination, operation) -> value or None
        self.on_undo = None      # function(), called by a double-tap on empty zone space     # function(source, destination, operation) -> value or None

    # --- what to show --------------------------------------------------------

    def show(self, values, locked, active, counted, distance):
        self.values = list(values)
        self.locked = locked
        self.active = active
        self.counted = counted
        self.distance = distance
        if locked or (self.selected is not None and self.values[self.selected] is None):
            self.selected = None
            self.operation = None
        self.set_needs_display()

    def clear_selection(self):
        self.selected = None
        self.operation = None
        self.set_needs_display()

    # --- geometry ------------------------------------------------------------

    def tile_frame(self, slot):
        inner_width = self.width - 2 * self.PADDING
        area_height = self.height - self.TITLE_HEIGHT - self.FOOTER_HEIGHT
        size = max(0, min((inner_width - self.GAP) / 2, (area_height - self.GAP) / 2))
        grid = 2 * size + self.GAP
        left = (self.width - grid) / 2
        top = self.TITLE_HEIGHT + (area_height - grid) / 2
        row, col = divmod(slot, 2)
        return (left + col * (size + self.GAP), top + row * (size + self.GAP), size, size)

    def hit(self, point):
        """(slot, part) under point: part is 'tile', 'centre' or an operation."""
        x, y = point
        for slot, value in enumerate(self.values):
            if value is None:
                continue
            tile_x, tile_y, size, _ = self.tile_frame(slot)
            if not (tile_x <= x < tile_x + size and tile_y <= y < tile_y + size):
                continue
            if slot != self.selected:
                return slot, "tile"
            centre_x, centre_y = tile_x + size / 2, tile_y + size / 2
            if (x - centre_x) ** 2 + (y - centre_y) ** 2 <= (size * self.DISC_RATIO) ** 2:
                return slot, "centre"
            row = 0 if y < centre_y else 1
            col = 0 if x < centre_x else 1
            return slot, QUADRANTS[(row, col)]
        return None, None

    # --- touch ---------------------------------------------------------------

    def touch_ended(self, touch):
        self.handle_tap(*self.hit(touch.location))

    def handle_tap(self, slot, part, now=None):
        """Selection, merging and double-tap undo for one tap. Smokes call it.

        A tap on empty zone space clears the selection; a second one within
        DOUBLE_TAP_SECONDS undoes the player's last merge, as on Multiple
        Merge's board. now is the tap time (smokes pass it). Returns the
        merged value when a merge happens, otherwise None.
        """
        if self.locked:
            return None

        if slot is None or self.values[slot] is None:
            now = time.time() if now is None else now
            last = self._last_empty_tap
            if last is not None and now - last <= DOUBLE_TAP_SECONDS:
                self._last_empty_tap = None
                if self.on_undo is not None:
                    self.on_undo()
            else:
                self._last_empty_tap = now
            self.clear_selection()
            return None

        self._last_empty_tap = None

        if self.selected is None:
            self.selected = slot
            self.operation = None
            self.set_needs_display()
            return None

        if slot == self.selected:
            if part in OPERATION_COLORS:
                self.operation = None if part == self.operation else part
                self.set_needs_display()
            else:
                self.clear_selection()
            return None

        if self.operation is None:
            self.selected = slot
            self.set_needs_display()
            return None

        value = None
        if self.on_merge is not None:
            value = self.on_merge(self.selected, slot, self.operation)
        if value is not None:
            self.clear_selection()
        return value

    # --- drawing -------------------------------------------------------------

    def draw(self):
        color = PLAYER_COLORS[self.player]
        frame = ui.Path.rounded_rect(1, 1, self.width - 2, self.height - 2, self.RADIUS)
        ui.set_color(SURFACE)
        frame.fill()
        frame.line_width = 3 if self.active else 1
        ui.set_color(color if self.active else BUTTON_COLOR)
        frame.stroke()

        title = PLAYER_NAMES[self.player] + ("  · locked" if self.locked else "")
        draw_centred_text(title, ("AvenirNext-DemiBold", 15), color,
                          0, 4, self.width, self.TITLE_HEIGHT - 4)

        for slot, value in enumerate(self.values):
            self._draw_slot(slot, value)

        if self.counted is not None:
            off = "exact" if self.distance == 0 else "%d off" % self.distance
            footer = "Counts %d · %s" % (self.counted, off)
        else:
            footer = "Pick tiles"
        draw_centred_text(footer, ("AvenirNext-Medium", 13), MUTED,
                          0, self.height - self.FOOTER_HEIGHT - 2, self.width,
                          self.FOOTER_HEIGHT)

    def _draw_slot(self, slot, value):
        x, y, size, _ = self.tile_frame(slot)
        shape = ui.Path.rounded_rect(x, y, size, size, self.TILE_RADIUS)

        if value is None:
            shape.line_width = 1
            ui.set_color(BUTTON_COLOR)
            shape.stroke()
            return

        font = ("AvenirNext-Bold", size * (0.32 if value < 1000 else 0.24))

        if slot == self.selected and not self.locked:
            self._draw_quadrants(x, y, size, shape)
            radius = size * self.DISC_RATIO
            ui.set_color(TILE)
            ui.Path.oval(x + size / 2 - radius, y + size / 2 - radius,
                         2 * radius, 2 * radius).fill()
            draw_centred_text(str(value), font, TILE_TEXT, x, y, size, size)
            return

        armed = self.selected is not None and self.operation is not None
        valid = (
            armed
            and self.result_of is not None
            and self.result_of(self.selected, slot, self.operation) is not None
        )

        if self.locked or (armed and not valid):
            ui.set_color(BUTTON_COLOR)
            shape.fill()
            draw_centred_text(str(value), font, TEXT if self.locked else MUTED,
                              x, y, size, size)
            return

        ui.set_color(TILE)
        shape.fill()
        draw_centred_text(str(value), font, TILE_TEXT, x, y, size, size)
        if valid:
            shape.line_width = 3
            ui.set_color(SUCCESS)
            shape.stroke()

    def _draw_quadrants(self, x, y, size, shape):
        half = size / 2
        symbol_size = size / 4
        with ui.GState():
            shape.add_clip()
            for (row, col), operation in QUADRANTS.items():
                quad_x, quad_y = x + col * half, y + row * half
                ui.set_color(OPERATION_COLORS[operation])
                ui.Path.rect(quad_x, quad_y, half, half).fill()
                if operation == self.operation:
                    marker = ui.Path.rect(quad_x + 2, quad_y + 2, half - 4, half - 4)
                    marker.line_width = 3
                    ui.set_color(TEXT)
                    marker.stroke()
                draw_centred_text(
                    OPERATION_SYMBOLS[operation], ("AvenirNext-Bold", symbol_size * 0.8), TEXT,
                    quad_x + (0 if col == 0 else half - symbol_size),
                    quad_y + (0 if row == 0 else half - symbol_size),
                    symbol_size, symbol_size,
                )