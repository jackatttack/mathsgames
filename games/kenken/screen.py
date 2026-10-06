"""
KenKen game screen: status line, board, Undo and New puzzle, settings.

Lives under the Maths Games shell and uses the header contract from
gamecore/game.py: open_settings() puts a gear in the header, and
header_subtitle describes the puzzle ("5×5 · + − × ÷").

Play: tap a cell to open the number picker beside it, then tap a number to
write it, or Clear to empty the cell. Tap the same cell again, or anywhere
off the grid, to close the picker. With "Show mistakes" on, numbers that
repeat in a row or column, and full cages that miss their target, turn
coral. A solved board turns green and locks until New puzzle.

UI stability (see JACK_BOOT): every change happens synchronously inside the
tap that caused it, views are created once and only shown, hidden or
re-labelled, and settings are saved immediately.
"""

import json
import os
import time

import ui

from style import theme
from tilegame.cell_picker import CellPicker
from tilegame.fill_grid import FillGrid
from tilegame import saved_game
from tilegame.widgets import ChoiceRow, ToggleRow, make_button, make_label

from games.kenken import rules
from games.kenken.board_view import KenKenBoardView


# --- colours, from the shared theme -----------------------------------------

BACKGROUND = theme.color("background")
TEXT = theme.color("text")
MUTED = theme.color("muted")
SUCCESS = theme.color("success")

# --- editable layout, in points ---------------------------------------------

TOP_GAP = 8
STATUS_HEIGHT = 28

SIZE_LABELS = tuple("%d×%d" % (size, size) for size in rules.BOARD_SIZES)
OPERATION_LABELS = tuple(rules.OPERATION_SYMBOLS[name] for name in rules.OPERATIONS)


# --- saved settings ---------------------------------------------------------

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(GAME_DIR, "settings.json")
SAVE_PATH = os.path.join(GAME_DIR, "saved_game.json")   # the puzzle in progress

DEFAULT_SETTINGS = {
    "size": 4,
    "operations": list(rules.OPERATIONS),
    "show_mistakes": True,
    "dim_used": False,
}


def load_settings():
    """Return saved settings, using defaults for anything missing or invalid."""
    settings = dict(DEFAULT_SETTINGS)

    try:
        with open(SETTINGS_PATH) as handle:
            saved = json.load(handle)
    except (OSError, ValueError):
        return settings

    if not isinstance(saved, dict):
        return settings

    if saved.get("size") in rules.BOARD_SIZES:
        settings["size"] = saved["size"]

    operations = saved.get("operations")
    if (
        isinstance(operations, list)
        and all(name in rules.OPERATIONS for name in operations)
        and rules.operations_allowed(operations)
    ):
        settings["operations"] = [name for name in rules.OPERATIONS if name in operations]

    for key in ("show_mistakes", "dim_used"):
        if isinstance(saved.get(key), bool):
            settings[key] = saved[key]

    return settings


def save_settings(settings):
    """Save settings now. A failed save is reported but never crashes play."""
    try:
        with open(SETTINGS_PATH, "w") as handle:
            json.dump(settings, handle)
    except OSError as error:
        print("KenKen: could not save settings: {}".format(error))


def describe_operations(operations):
    """Symbols in standard order, e.g. '+ − × ÷'."""
    return " ".join(
        rules.OPERATION_SYMBOLS[name] for name in rules.OPERATIONS if name in operations
    )


def format_time(seconds):
    minutes, seconds = divmod(int(round(seconds)), 60)
    return "%d:%02d" % (minutes, seconds)


class SettingsPanel(ui.View):
    """Overlay editing a draft of the settings, covering the game area.

    Done adopts the draft, dealing a new puzzle only if the size or the
    operations changed. New puzzle adopts it and always deals one.
    """

    TOP = 16

    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.background_color = BACKGROUND
        self.hidden = True
        self.draft = dict(screen.settings)

        self.title_label = make_label("Settings", ("AvenirNext-Bold", 24), TEXT)

        self.size_caption = make_label("Board size", ("AvenirNext-Medium", 15), MUTED)
        self.size_control = ChoiceRow(SIZE_LABELS, self.size_changed)

        self.operations_caption = make_label(
            "Operations: + or × must be on", ("AvenirNext-Medium", 15), MUTED
        )
        self.operations_control = ToggleRow(
            OPERATION_LABELS, self.operations_changed, allow=self.operations_allowed
        )

        self.mistakes_label = make_label(
            "Show mistakes", ("AvenirNext-Medium", 15), TEXT, alignment=ui.ALIGN_LEFT
        )
        self.mistakes_switch = ui.Switch()
        self.mistakes_switch.action = self.mistakes_changed

        self.dim_label = make_label(
            "Dim numbers already in the row or column",
            ("AvenirNext-Medium", 15), TEXT, alignment=ui.ALIGN_LEFT,
        )
        self.dim_label.number_of_lines = 2
        self.dim_switch = ui.Switch()
        self.dim_switch.action = self.dim_changed

        self.new_puzzle_button = make_button(
            "New puzzle", self.new_puzzle_tapped,
            background=theme.color("tile"), title_color=BACKGROUND,
        )
        self.done_button = make_button("Done", self.done_tapped)

        for view in (
            self.title_label,
            self.size_caption,
            self.size_control,
            self.operations_caption,
            self.operations_control,
            self.mistakes_label,
            self.mistakes_switch,
            self.dim_label,
            self.dim_switch,
            self.new_puzzle_button,
            self.done_button,
        ):
            self.add_subview(view)

    def layout(self):
        column = min(320, self.width - 48)
        left = (self.width - column) / 2
        switch_width = 51

        y = self.TOP
        self.title_label.frame = (left, y, column, 36)
        y += 56
        self.size_caption.frame = (left, y, column, 22)
        y += 28
        self.size_control.frame = (left, y, column, 40)
        y += 56
        self.operations_caption.frame = (left, y, column, 22)
        y += 28
        self.operations_control.frame = (left, y, column, 44)
        y += 64
        self.mistakes_label.frame = (left, y, column - switch_width - 12, 44)
        self.mistakes_switch.frame = (left + column - switch_width, y + 6, switch_width, 31)
        y += 56
        self.dim_label.frame = (left, y, column - switch_width - 12, 44)
        self.dim_switch.frame = (left + column - switch_width, y + 6, switch_width, 31)
        y += 68
        self.new_puzzle_button.frame = (left, y, column, 52)
        y += 68
        self.done_button.frame = (left, y, column, 52)

    def open(self):
        self.draft = dict(self.screen.settings)
        self.size_control.selected_index = rules.BOARD_SIZES.index(self.draft["size"])
        self.operations_control.selected_indices = {
            index
            for index, name in enumerate(rules.OPERATIONS)
            if name in self.draft["operations"]
        }
        self.mistakes_switch.value = bool(self.draft["show_mistakes"])
        self.dim_switch.value = bool(self.draft["dim_used"])
        self.hidden = False
        self.bring_to_front()

    @staticmethod
    def operations_allowed(indices):
        return rules.operations_allowed([rules.OPERATIONS[index] for index in indices])

    def size_changed(self, sender):
        self.draft["size"] = rules.BOARD_SIZES[sender.selected_index]

    def operations_changed(self, sender):
        self.draft["operations"] = [
            rules.OPERATIONS[index] for index in sorted(sender.selected_indices)
        ]

    def mistakes_changed(self, sender):
        self.draft["show_mistakes"] = bool(sender.value)

    def dim_changed(self, sender):
        self.draft["dim_used"] = bool(sender.value)

    def new_puzzle_tapped(self, sender):
        if self.screen.apply_settings(self.draft, force_new_puzzle=True):
            self.hidden = True

    def done_tapped(self, sender):
        if self.screen.apply_settings(self.draft):
            self.hidden = True


class KenKenScreen(ui.View):
    """KenKen under the shell header: one puzzle at a time."""

    SIDE_MARGIN = 16
    BOTTOM_BAR = 80

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = BACKGROUND
        self.settings = load_settings()

        # Header contract (gamecore/game.py). The shell replaces the callback.
        self.header_subtitle = ""
        self.on_header_changed = None

        self.puzzle = None
        self.grid = None             # FillGrid holding the player's values
        self.selected_cell = None    # the cell the picker is open for
        self.started = None          # when this puzzle was dealt
        self.solve_seconds = None    # set once, in the tap that solves it

        self.status_label = make_label("", ("AvenirNext-Medium", 15), MUTED)

        self.board_view = KenKenBoardView()
        self.board_view.background_color = BACKGROUND
        self.board_view.on_cell_tapped = self.cell_tapped

        self.undo_button = make_button("Undo", self.undo_tapped)
        self.new_button = make_button("New puzzle", self.new_tapped)

        self.picker = CellPicker(self.value_picked, notes_enabled=True)
        self.settings_panel = SettingsPanel(self)

        for view in (
            self.status_label,
            self.board_view,
            self.undo_button,
            self.new_button,
            self.picker,
            self.settings_panel,   # last, so it covers everything
        ):
            self.add_subview(view)

        if not self.resume_saved_game():
            self.new_puzzle()

    # --- header contract -----------------------------------------------------

    def open_settings(self):
        """Called by the shell's gear."""
        self.close_picker()
        self.settings_panel.open()

    def set_subtitle(self, text):
        if text == self.header_subtitle:
            return
        self.header_subtitle = text
        if self.on_header_changed is not None:
            self.on_header_changed()

    # --- layout --------------------------------------------------------------

    def layout(self):
        width = self.width
        height = self.height
        margin = self.SIDE_MARGIN

        self.status_label.frame = (margin, TOP_GAP, width - 2 * margin, STATUS_HEIGHT)

        board_top = TOP_GAP + STATUS_HEIGHT + 4
        buttons_y = height - self.BOTTOM_BAR + 16
        self.board_view.frame = (0, board_top, width, max(0, buttons_y - 12 - board_top))

        button_width = min(160, (width - 3 * margin) / 2)
        row_left = (width - (2 * button_width + 12)) / 2
        self.undo_button.frame = (row_left, buttons_y, button_width, 48)
        self.new_button.frame = (row_left + button_width + 12, buttons_y, button_width, 48)

        self.settings_panel.frame = self.bounds

    # --- game flow -----------------------------------------------------------

    @property
    def solved(self):
        return self.solve_seconds is not None

    def new_puzzle(self):
        """Deal a puzzle for the current settings, show it and save it."""
        size = self.settings["size"]
        operations = self.settings["operations"]

        puzzle = rules.generate_puzzle(size, operations)
        subtitle = "%d×%d · %s" % (size, size, describe_operations(operations))
        self.show_puzzle(puzzle, FillGrid(size), subtitle, seconds_played=0)
        self.save_game()

    def show_puzzle(self, puzzle, grid, subtitle, seconds_played):
        """Put a puzzle and its grid on screen: a new deal or a resumed save."""
        self.puzzle = puzzle
        self.grid = grid
        self.selected_cell = None
        self.started = time.time() - seconds_played
        self.solve_seconds = None

        self.picker.hide_picker()
        self.picker.set_values(self.grid.allowed_values)
        self.board_view.load_puzzle(self.puzzle)
        self.set_subtitle(subtitle)
        self.refresh()

    # --- saved game ----------------------------------------------------------

    def save_game(self):
        """Save the puzzle in progress now. A solved puzzle discards the save."""
        if self.solved:
            saved_game.discard_game(SAVE_PATH)
            return
        saved_game.save_game(
            SAVE_PATH, rules.puzzle_to_data(self.puzzle), self.grid,
            time.time() - self.started, self.header_subtitle,
        )

    def resume_saved_game(self):
        """Show the saved puzzle if there is a usable one. True when resumed."""
        data = saved_game.load_game(SAVE_PATH)
        if data is None:
            return False
        try:
            puzzle = rules.puzzle_from_data(data["puzzle"])
            grid = FillGrid(puzzle.size)
            saved_game.restore_marks(grid, data["marks"])
            seconds_played = float(data["seconds_played"])
            subtitle = str(data["subtitle"])
        except (KeyError, IndexError, TypeError, ValueError) as error:
            print("KenKen: ignoring saved game: {}".format(error))
            return False
        if rules.is_solved(puzzle, grid.rows()):
            saved_game.discard_game(SAVE_PATH)
            return False
        self.show_puzzle(puzzle, grid, subtitle, seconds_played)
        return True

    def refresh(self):
        """Redraw marks and status from the grid. Called after every change."""
        values = self.grid.rows()

        if self.settings["show_mistakes"] and not self.solved:
            conflicts = self.grid.conflicts()
            wrong_cages = {
                index
                for index, cage in enumerate(self.puzzle.cages)
                if rules.cage_status(cage, values) == "wrong"
            }
        else:
            conflicts = set()
            wrong_cages = set()

        notes = {
            cell: self.grid.notes_at(cell)
            for cell in self.grid.empty_cells()
            if self.grid.notes_at(cell)
        }
        self.board_view.refresh_marks(
            values, notes, self.selected_cell, conflicts, wrong_cages, self.solved
        )

        if self.solved:
            self.status_label.text = "Solved in %s" % format_time(self.solve_seconds)
            self.status_label.text_color = SUCCESS
        else:
            remaining = len(self.grid.empty_cells())
            self.status_label.text = "Use 1 to %d once in each row and column · %d to fill" % (
                self.puzzle.size, remaining)
            self.status_label.text_color = MUTED

        self.undo_button.enabled = self.grid.can_undo() and not self.solved

    def cell_tapped(self, cell):
        """Open the picker beside cell; the same cell again, or None, closes it."""
        if self.solved or cell is None:
            self.close_picker()
            return
        if cell == self.selected_cell and not self.picker.hidden:
            self.close_picker()
            return

        self.selected_cell = cell
        dimmed = self.grid.values_seen_from(cell) if self.settings["dim_used"] else ()

        board_x, board_y = self.board_view.frame[0], self.board_view.frame[1]
        cell_x, cell_y, cell_width, cell_height = self.board_view.cell_frame(cell)
        anchor = (board_x + cell_x, board_y + cell_y, cell_width, cell_height)

        self.picker.show_beside(
            anchor, (0, 0, self.width, self.height),
            current=self.grid.value_at(cell), notes=self.grid.notes_at(cell),
            dimmed=dimmed,
        )
        self.refresh()

    def close_picker(self):
        self.picker.hide_picker()
        if self.selected_cell is not None:
            self.selected_cell = None
            self.refresh()

    def value_picked(self, value):
        """Called by the picker: write a value, toggle a note, or clear (None).

        In Notes mode the picker stays open so several notes can be marked in
        a row; a written value or Clear closes it. Every change is saved.
        """
        cell = self.selected_cell
        if cell is None:
            self.picker.hide_picker()
            return

        if value is not None and self.picker.notes_mode:
            self.grid.toggle_note(cell, value)
            self.picker.update_marks(
                current=self.grid.value_at(cell), notes=self.grid.notes_at(cell)
            )
            self.refresh()
            self.save_game()
            return

        self.picker.hide_picker()
        self.selected_cell = None

        if self.grid.set_value(cell, value):
            if rules.is_solved(self.puzzle, self.grid.rows()):
                self.solve_seconds = time.time() - self.started

        self.refresh()
        self.save_game()

    def undo_tapped(self, sender):
        self.picker.hide_picker()
        self.selected_cell = None
        if not self.solved:
            self.grid.undo()
        self.refresh()
        self.save_game()

    def new_tapped(self, sender):
        self.new_puzzle()

    def touch_ended(self, touch):
        """A tap on the background, off the board and buttons, closes the picker."""
        self.close_picker()

    def apply_settings(self, draft, force_new_puzzle=False):
        """Adopt draft settings and save them.

        Deals a new puzzle if the size or operations changed, or when forced.
        Returns False, changing nothing, if the operations are not allowed.
        """
        if not rules.operations_allowed(draft["operations"]):
            return False

        previous = self.settings
        self.settings = dict(draft)
        self.settings["operations"] = list(draft["operations"])

        needs_new = (
            force_new_puzzle
            or self.settings["size"] != previous["size"]
            or set(self.settings["operations"]) != set(previous["operations"])
        )
        if needs_new:
            self.new_puzzle()
        else:
            self.refresh()

        if self.settings != previous:
            save_settings(self.settings)
        return True