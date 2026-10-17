"""
Number tiles under a fill-in board: a second way to enter numbers.

The tiles sit in up to two centred rows (5 + 4 for 1 to 9, 3 + 3 for 1 to
6, one row for 1 to 4). Each tile has a short stack of bars against its
left side, one bar for every copy the board still needs, bottom-aligned
and tucked slightly under the tile. A finished number keeps its tile,
with its number in the completed colour and no bars, and cannot be armed.

Colours come from the board's own theme roles, so the tray always matches
the board: tiles are board cells edged like grid lines, bars are grid-line
coloured, numbers are the player's numbers, and the armed number looks
like the selected cell.

The screen owns what a tap means. The tray only draws and reports the
tapped number through on_tap(value). Sudoku uses a tap to arm that number,
so later taps on cells place it without opening the picker.

UI stability (see JACK_BOOT): one view, drawn in draw(), with no subviews.
show() stores the marks and asks for a redraw; nothing is created, moved or
animated after the view is built. The tray is always two rows tall, so a
board size change never needs a relayout.
"""

import math

import ui

from style import theme


TILE_FILL = theme.color("board")              # tiles, like the cells
TILE_EDGE = theme.color("grid_line")
BAR_COLOR = theme.color("grid_line")          # the stacks of what is left
NUMBER_COLOR = theme.color("player_number")
ARMED_FILL = theme.color("selection_fill")    # the armed number, like the selected cell
ARMED_EDGE = theme.color("selection")
COMPLETE_COLOR = theme.color("success")       # every copy placed


class NumberTray(ui.View):
    """Number tiles with stacks of what is left; reports the tapped number."""

    # --- editable look, in points ------------------------------------------
    MAX_PER_ROW = 5
    ROW_HEIGHT = 52
    ROW_GAP = 8
    HEIGHT = 2 * ROW_HEIGHT + ROW_GAP   # the screen lays the tray out this tall
    SLOT_GAP = 6               # between slots in a row
    MAX_SLOT_WIDTH = 72
    MAX_TILE_SIDE = 46
    CORNER_RADIUS = 9
    EDGE_WIDTH = 1
    ARMED_EDGE_WIDTH = 2
    MAX_DIGIT_SIZE = 26
    FONT_NAME = "AvenirNext-DemiBold"
    STACK_WIDTH = 16           # how wide each bar is
    TUCK = 5                   # how far the bars run under the tile
    BAR_HEIGHT = 3
    BAR_GAP = 1.5
    BAR_RADIUS = 1.5

    def __init__(self, on_tap, **kwargs):
        super().__init__(**kwargs)
        self.on_tap = on_tap
        self.values = ()
        self.remaining = {}
        self.capacity = 0      # copies of each number a finished board holds
        self.armed = None

    def show(self, values, remaining, capacity, armed=None):
        """Show these numbers with how many of each are still to place."""
        self.values = tuple(values)
        self.remaining = dict(remaining)
        self.capacity = capacity
        self.armed = armed
        self.set_needs_display()

    def slot_frames(self):
        """(x, y, width, height) for each number's slot, in centred rows."""
        count = len(self.values)
        if count == 0 or self.width <= 0:
            return []
        rows = int(math.ceil(count / self.MAX_PER_ROW))
        per_row = int(math.ceil(count / rows))
        slot_width = min(self.MAX_SLOT_WIDTH,
                         (self.width - self.SLOT_GAP * (per_row - 1)) / per_row)
        frames = []
        for index in range(count):
            row, column = divmod(index, per_row)
            in_this_row = min(per_row, count - row * per_row)
            row_width = in_this_row * slot_width + self.SLOT_GAP * (in_this_row - 1)
            left = (self.width - row_width) / 2 + column * (slot_width + self.SLOT_GAP)
            top = row * (self.ROW_HEIGHT + self.ROW_GAP)
            frames.append((left, top, slot_width, self.ROW_HEIGHT))
        return frames

    def can_tap(self, value):
        """A number can be armed while copies remain, and disarmed any time."""
        return value == self.armed or self.remaining.get(value, 0) > 0

    def tap(self, value):
        """What a slot tap does: report the number. Smokes call it."""
        if value in self.values and self.can_tap(value):
            self.on_tap(value)

    # --- touch and drawing -------------------------------------------------

    def touch_ended(self, touch):
        x, y = touch.location
        for value, (left, top, width, height) in zip(self.values, self.slot_frames()):
            if left <= x <= left + width and top <= y <= top + height:
                self.tap(value)
                return

    def draw(self):
        for value, slot in zip(self.values, self.slot_frames()):
            self._draw_slot(value, slot)

    def _draw_slot(self, value, slot):
        """Stack and tile as one group, centred in the slot; bars first."""
        left, top, width, height = slot
        remaining = self.remaining.get(value, 0)
        armed = value == self.armed

        stack_visible = self.STACK_WIDTH - self.TUCK
        side = min(height - 4, width - stack_visible, self.MAX_TILE_SIDE)
        group_left = left + (width - (stack_visible + side)) / 2
        tile_left = group_left + stack_visible
        tile_top = top + (height - side) / 2

        bar_color = ARMED_EDGE if armed else BAR_COLOR
        self._draw_stack(remaining, group_left, tile_top + side - 2, bar_color)

        if armed:
            fill, edge, edge_width = ARMED_FILL, ARMED_EDGE, self.ARMED_EDGE_WIDTH
        else:
            fill, edge, edge_width = TILE_FILL, TILE_EDGE, self.EDGE_WIDTH
        ink = COMPLETE_COLOR if remaining == 0 and not armed else NUMBER_COLOR
        self._draw_tile(value, (tile_left, tile_top, side, side), fill, edge, edge_width, ink)

    def _draw_tile(self, value, frame, fill, edge, edge_width, ink):
        left, top, width, height = frame
        path = ui.Path.rounded_rect(left, top, width, height, self.CORNER_RADIUS)
        ui.set_color(fill)
        path.fill()
        ui.set_color(edge)
        path.line_width = edge_width
        path.stroke()

        font = (self.FONT_NAME, min(self.MAX_DIGIT_SIZE, width * 0.6))
        text = str(value)
        text_height = ui.measure_string(text, font=font)[1]
        ui.draw_string(text, rect=(left, top + (height - text_height) / 2, width, text_height),
                       font=font, color=ink, alignment=ui.ALIGN_CENTER)

    def _draw_stack(self, count, left, bottom, color):
        """One bar per copy still to place, piled up from bottom."""
        step = self.BAR_HEIGHT + self.BAR_GAP
        ui.set_color(color)
        for index in range(count):
            bar_top = bottom - self.BAR_HEIGHT - index * step
            ui.Path.rounded_rect(left, bar_top, self.STACK_WIDTH,
                                 self.BAR_HEIGHT, self.BAR_RADIUS).fill()