"""
A number picker that opens beside a tapped grid cell, for fill-in games.

KenKen and Sudoku use it. The screen owns which cell is selected; the
picker only shows values and reports the one chosen through on_pick(value),
with None meaning Clear.

With notes_enabled, a Notes button sits beside Clear. In notes mode the
screen toggles pencil marks instead of writing values, and the picker
shows which values are noted. The mode stays as the player left it.

UI stability (see JACK_BOOT): the buttons are made once, up to MAX_VALUES,
and set_values only relabels, shows and hides them. Opening and closing is
a plain show and hide inside the tap that caused it. Nothing is animated.
"""

import math

import ui

from style import theme
from tilegame.widgets import make_button


SURFACE = theme.color("surface")
TEXT = theme.color("text")
MUTED = theme.color("muted")
BACKGROUND = theme.color("background")
BUTTON_COLOR = theme.color("button")
ACCENT = theme.color("tile")       # the cell's current value
NOTE_COLOR = theme.color("sky")    # noted values and the Notes button when on


class CellPicker(ui.View):
    """A small panel of value buttons plus Clear (and Notes), shown beside a cell."""

    MAX_VALUES = 12

    # --- editable layout, in points ------------------------------------------
    BUTTON_SIZE = 48
    GAP = 6
    PADDING = 8
    BOTTOM_HEIGHT = 36
    MIN_WIDTH = 120             # room for Clear on small boards
    MIN_WIDTH_WITH_NOTES = 200  # room for Notes and Clear side by side
    MAX_COLUMNS = 5             # more values than this wrap onto two rows
    DISTANCE_FROM_CELL = 6
    EDGE_INSET = 4

    def __init__(self, on_pick, notes_enabled=False):
        super().__init__()
        self.on_pick = on_pick
        self.notes_enabled = notes_enabled
        self.notes_mode = False
        self.background_color = SURFACE
        self.corner_radius = 14
        self.border_width = 1
        self.border_color = MUTED
        self.hidden = True
        self.values = ()

        # What the buttons currently show, so a mode switch can redraw them.
        self._current = None
        self._dimmed = set()
        self._notes = set()

        self.value_buttons = []
        for _ in range(self.MAX_VALUES):
            button = make_button("", self._value_tapped, font_size=22)
            button.corner_radius = 10
            button.hidden = True
            self.value_buttons.append(button)
            self.add_subview(button)

        self.notes_button = make_button("Notes", self._notes_tapped, font_size=15)
        self.notes_button.corner_radius = 10
        self.notes_button.hidden = not notes_enabled
        self.add_subview(self.notes_button)

        self.clear_button = make_button("Clear", self._clear_tapped, font_size=15)
        self.clear_button.corner_radius = 10
        self.add_subview(self.clear_button)

        self._show_notes_button()

    # --- setup ---------------------------------------------------------------

    def set_values(self, values):
        """Choose which values the buttons offer, in order. Relabels only."""
        self.values = tuple(values)[:self.MAX_VALUES]
        for index, button in enumerate(self.value_buttons):
            if index < len(self.values):
                button.title = str(self.values[index])
                button.hidden = False
            else:
                button.hidden = True

    def columns(self):
        count = max(1, len(self.values))
        if count <= self.MAX_COLUMNS:
            return count
        return math.ceil(count / 2)

    def preferred_size(self):
        columns = self.columns()
        rows = math.ceil(max(1, len(self.values)) / columns)
        width = 2 * self.PADDING + columns * self.BUTTON_SIZE + (columns - 1) * self.GAP
        height = (
            2 * self.PADDING
            + rows * self.BUTTON_SIZE
            + (rows - 1) * self.GAP
            + self.GAP
            + self.BOTTOM_HEIGHT
        )
        minimum = self.MIN_WIDTH_WITH_NOTES if self.notes_enabled else self.MIN_WIDTH
        return max(width, minimum), height

    def layout(self):
        columns = self.columns()
        grid_width = columns * self.BUTTON_SIZE + (columns - 1) * self.GAP
        left = (self.width - grid_width) / 2

        for index in range(len(self.values)):
            row, col = divmod(index, columns)
            self.value_buttons[index].frame = (
                left + col * (self.BUTTON_SIZE + self.GAP),
                self.PADDING + row * (self.BUTTON_SIZE + self.GAP),
                self.BUTTON_SIZE,
                self.BUTTON_SIZE,
            )

        bottom_y = self.height - self.PADDING - self.BOTTOM_HEIGHT
        inner_width = self.width - 2 * self.PADDING
        if self.notes_enabled:
            half = (inner_width - self.GAP) / 2
            self.notes_button.frame = (self.PADDING, bottom_y, half, self.BOTTOM_HEIGHT)
            self.clear_button.frame = (
                self.PADDING + half + self.GAP, bottom_y, half, self.BOTTOM_HEIGHT
            )
        else:
            self.clear_button.frame = (self.PADDING, bottom_y, inner_width, self.BOTTOM_HEIGHT)

    # --- showing -------------------------------------------------------------

    def show_beside(self, anchor_frame, area, current=None, dimmed=(), notes=()):
        """Open beside anchor_frame, kept inside area (both in superview points).

        Opens below the anchor when it fits, otherwise above. current is the
        cell's value, dimmed are values shown muted but still tappable, and
        notes are the cell's pencil marks, shown in notes mode.
        """
        width, height = self.preferred_size()
        anchor_x, anchor_y, anchor_width, anchor_height = anchor_frame
        area_x, area_y, area_width, area_height = area

        x = anchor_x + anchor_width / 2 - width / 2
        x = max(area_x + self.EDGE_INSET,
                min(x, area_x + area_width - width - self.EDGE_INSET))

        below = anchor_y + anchor_height + self.DISTANCE_FROM_CELL
        if below + height <= area_y + area_height - self.EDGE_INSET:
            y = below
        else:
            y = max(area_y + self.EDGE_INSET,
                    anchor_y - height - self.DISTANCE_FROM_CELL)

        self.frame = (x, y, width, height)
        self.layout()
        self.update_marks(current, dimmed, notes)
        self.hidden = False
        self.bring_to_front()

    def update_marks(self, current=None, dimmed=(), notes=()):
        """Redraw which value is current, dimmed or noted, without moving."""
        self._current = current
        self._dimmed = set(dimmed)
        self._notes = set(notes)
        self._show_marks()

    def hide_picker(self):
        self.hidden = True

    def toggle_notes_mode(self):
        """Switch between writing values and toggling notes. Smokes call it."""
        if not self.notes_enabled:
            return
        self.notes_mode = not self.notes_mode
        self._show_notes_button()
        self._show_marks()

    def _show_notes_button(self):
        if self.notes_mode:
            self.notes_button.background_color = NOTE_COLOR
            self.notes_button.tint_color = BACKGROUND
        else:
            self.notes_button.background_color = BUTTON_COLOR
            self.notes_button.tint_color = TEXT

    def _show_marks(self):
        for value, button in zip(self.values, self.value_buttons):
            if self.notes_mode:
                noted = value in self._notes
                button.background_color = NOTE_COLOR if noted else BUTTON_COLOR
                if noted:
                    button.tint_color = BACKGROUND
                elif value in self._dimmed:
                    button.tint_color = MUTED
                else:
                    button.tint_color = TEXT
            elif value == self._current:
                button.background_color = ACCENT
                button.tint_color = BACKGROUND
            elif value in self._dimmed:
                button.background_color = BUTTON_COLOR
                button.tint_color = MUTED
            else:
                button.background_color = BUTTON_COLOR
                button.tint_color = TEXT

    # --- choosing ------------------------------------------------------------

    def pick(self, value):
        """What a button tap does: report value (None for Clear). Smokes call it."""
        if self.on_pick is not None:
            self.on_pick(value)

    def _value_tapped(self, sender):
        self.pick(self.values[self.value_buttons.index(sender)])

    def _clear_tapped(self, sender):
        self.pick(None)

    def _notes_tapped(self, sender):
        self.toggle_notes_mode()