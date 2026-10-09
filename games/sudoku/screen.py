"""
Sudoku game screen: status line, board, Undo and New puzzle, settings.

Lives under the Maths Games shell and uses the header contract from
gamecore/game.py: open_settings() puts a gear in the header, and
header_subtitle describes the puzzle ("9×9 · Medium"). The subtitle shows
the level the puzzle actually reached, which is rarely easier than asked.

Play: tap an empty cell to open the number picker under the board, so the
whole grid stays in view. Tap a number to write it, or Clear to empty the
cell. Notes mode in the picker
toggles pencil marks instead, and the picker stays open so several can be
marked. Tapping a given only highlights it. With "Remove notes" on, placing a number
also removes it from notes in the same row, column and box, in one undo
step. With "Show mistakes" on, numbers that clash turn coral.

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
from tilegame.widgets import ChoiceRow, make_button, make_label

from games.sudoku import rules
from games.sudoku.board_view import SudokuBoardView


# --- colours, from the shared theme -----------------------------------------

BACKGROUND = theme.color("background")
TEXT = theme.color("text")
MUTED = theme.color("muted")
SUCCESS = theme.color("success")

# --- editable layout and labels ---------------------------------------------

TOP_GAP = 8
STATUS_HEIGHT = 28

SIZE_LABELS = tuple("%d×%d" % (size, size) for size in rules.BOARD_SIZES)
DIFFICULTY_LABELS = ("Easy", "Medium", "Hard")          # rules.DIFFICULTIES
LEVEL_LABELS = {1: "Easy", 2: "Medium", 3: "Hard"}      # rules levels


# --- saved settings ---------------------------------------------------------

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(GAME_DIR, "settings.json")
SAVE_PATH = os.path.join(GAME_DIR, "saved_game.json")   # the puzzle in progress

DEFAULT_SETTINGS = {
    "size": 9,
    "difficulty": "easy",
    "show_mistakes": True,
    "tidy_notes": True,
    "highlight": True,
}


def hardest_offered(size):
    return rules.DIFFICULTIES_BY_SIZE[size][-1]


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

    offered = rules.DIFFICULTIES_BY_SIZE[settings["size"]]
    if saved.get("difficulty") in offered:
        settings["difficulty"] = saved["difficulty"]
    elif settings["difficulty"] not in offered:
        settings["difficulty"] = hardest_offered(settings["size"])

    for key in ("show_mistakes", "tidy_notes", "highlight"):
        if isinstance(saved.get(key), bool):
            settings[key] = saved[key]

    return settings


def save_settings(settings):
    """Save settings now. A failed save is reported but never crashes play."""
    try:
        with open(SETTINGS_PATH, "w") as handle:
            json.dump(settings, handle)
    except OSError as error:
        print("Sudoku: could not save settings: {}".format(error))


def format_time(seconds):
    minutes, seconds = divmod(int(round(seconds)), 60)
    return "%d:%02d" % (minutes, seconds)


class SettingsPanel(ui.View):
    """Overlay editing a draft of the settings, covering the game area.

    Done adopts the draft, dealing a new puzzle only if the size or the
    difficulty changed. New puzzle adopts it and always deals one.
    Difficulties a size cannot reach are faded out.
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

        self.difficulty_caption = make_label(
            "Difficulty: the hardest technique needed",
            ("AvenirNext-Medium", 15), MUTED,
        )
        self.difficulty_control = ChoiceRow(DIFFICULTY_LABELS, self.difficulty_changed)
        self.difficulty_note = make_label("", ("AvenirNext-Medium", 13), MUTED)

        self.mistakes_label = make_label(
            "Show mistakes", ("AvenirNext-Medium", 15), TEXT, alignment=ui.ALIGN_LEFT
        )
        self.mistakes_switch = ui.Switch()
        self.mistakes_switch.action = self.mistakes_changed

        self.tidy_label = make_label(
            "Remove notes when a number is placed",
            ("AvenirNext-Medium", 15), TEXT, alignment=ui.ALIGN_LEFT,
        )
        self.tidy_label.number_of_lines = 2
        self.tidy_switch = ui.Switch()
        self.tidy_switch.action = self.tidy_changed

        self.highlight_label = make_label(
            "Highlight row, column, box and matching numbers",
            ("AvenirNext-Medium", 15), TEXT, alignment=ui.ALIGN_LEFT,
        )
        self.highlight_label.number_of_lines = 2
        self.highlight_switch = ui.Switch()
        self.highlight_switch.action = self.highlight_changed

        self.new_puzzle_button = make_button(
            "New puzzle", self.new_puzzle_tapped,
            background=theme.color("tile"), title_color=BACKGROUND,
        )
        self.done_button = make_button("Done", self.done_tapped)

        for view in (
            self.title_label,
            self.size_caption,
            self.size_control,
            self.difficulty_caption,
            self.difficulty_control,
            self.difficulty_note,
            self.mistakes_label,
            self.mistakes_switch,
            self.tidy_label,
            self.tidy_switch,
            self.highlight_label,
            self.highlight_switch,
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
        self.difficulty_caption.frame = (left, y, column, 22)
        y += 28
        self.difficulty_control.frame = (left, y, column, 40)
        y += 44
        self.difficulty_note.frame = (left, y, column, 20)
        y += 36
        self.mistakes_label.frame = (left, y, column - switch_width - 12, 44)
        self.mistakes_switch.frame = (left + column - switch_width, y + 6, switch_width, 31)
        y += 56
        self.tidy_label.frame = (left, y, column - switch_width - 12, 44)
        self.tidy_switch.frame = (left + column - switch_width, y + 6, switch_width, 31)
        y += 56
        self.highlight_label.frame = (left, y, column - switch_width - 12, 44)
        self.highlight_switch.frame = (left + column - switch_width, y + 6, switch_width, 31)
        y += 68
        self.new_puzzle_button.frame = (left, y, column, 52)
        y += 68
        self.done_button.frame = (left, y, column, 52)

    def open(self):
        self.draft = dict(self.screen.settings)
        self.size_control.selected_index = rules.BOARD_SIZES.index(self.draft["size"])
        self.sync_difficulty()
        self.mistakes_switch.value = bool(self.draft["show_mistakes"])
        self.tidy_switch.value = bool(self.draft["tidy_notes"])
        self.highlight_switch.value = bool(self.draft["highlight"])
        self.hidden = False
        self.bring_to_front()

    def sync_difficulty(self):
        """Fade unreachable difficulties and move the choice down if needed."""
        size = self.draft["size"]
        offered = rules.DIFFICULTIES_BY_SIZE[size]
        self.difficulty_control.set_enabled(
            [difficulty in offered for difficulty in rules.DIFFICULTIES]
        )
        if self.draft["difficulty"] not in offered:
            self.draft["difficulty"] = hardest_offered(size)
        self.difficulty_control.selected_index = rules.DIFFICULTIES.index(
            self.draft["difficulty"]
        )
        if len(offered) == len(rules.DIFFICULTIES):
            self.difficulty_note.text = ""
        else:
            self.difficulty_note.text = "%d×%d goes up to %s" % (
                size, size, DIFFICULTY_LABELS[rules.DIFFICULTIES.index(offered[-1])]
            )

    def size_changed(self, sender):
        self.draft["size"] = rules.BOARD_SIZES[sender.selected_index]
        self.sync_difficulty()

    def difficulty_changed(self, sender):
        self.draft["difficulty"] = rules.DIFFICULTIES[sender.selected_index]

    def mistakes_changed(self, sender):
        self.draft["show_mistakes"] = bool(sender.value)

    def tidy_changed(self, sender):
        self.draft["tidy_notes"] = bool(sender.value)

    def highlight_changed(self, sender):
        self.draft["highlight"] = bool(sender.value)

    def new_puzzle_tapped(self, sender):
        if self.screen.apply_settings(self.draft, force_new_puzzle=True):
            self.hidden = True

    def done_tapped(self, sender):
        if self.screen.apply_settings(self.draft):
            self.hidden = True


class SudokuScreen(ui.View):
    """Sudoku under the shell header: one puzzle at a time."""

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
        self.grid = None             # FillGrid holding values and notes
        self.selected_cell = None    # the cell the picker is open for
        self.focus_cell = None       # the cell highlighted with its row, column, box and number
        self.started = None          # when this puzzle was dealt
        self.solve_seconds = None    # set once, in the tap that solves it

        self.status_label = make_label("", ("AvenirNext-Medium", 15), MUTED)

        self.board_view = SudokuBoardView()
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
        puzzle = rules.generate_puzzle(self.settings["size"], self.settings["difficulty"])
        self.show_puzzle(puzzle, self.fresh_grid(puzzle), seconds_played=0)
        self.save_game()

    def fresh_grid(self, puzzle):
        """An empty FillGrid for puzzle: its givens, plus boxes as units."""
        return FillGrid(
            puzzle.size,
            givens=puzzle.givens_by_cell(),
            units=rules.cell_units(puzzle.size),
        )

    def show_puzzle(self, puzzle, grid, seconds_played):
        """Put a puzzle and its grid on screen: a new deal or a resumed save."""
        size = puzzle.size
        self.puzzle = puzzle
        self.grid = grid
        self.selected_cell = None
        self.focus_cell = None
        self.started = time.time() - seconds_played
        self.solve_seconds = None

        self.picker.hide_picker()
        self.picker.set_values(self.grid.allowed_values)
        self.board_view.load_puzzle(self.puzzle, rules.BOX_SHAPES[size])
        self.set_subtitle("%d×%d · %s" % (
            size, size, LEVEL_LABELS.get(self.puzzle.level, "Easy")))
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
            grid = self.fresh_grid(puzzle)
            saved_game.restore_marks(grid, data["marks"])
            seconds_played = float(data["seconds_played"])
        except (KeyError, IndexError, TypeError, ValueError) as error:
            print("Sudoku: ignoring saved game: {}".format(error))
            return False
        if rules.is_solved(puzzle, grid.rows()):
            saved_game.discard_game(SAVE_PATH)
            return False
        self.show_puzzle(puzzle, grid, seconds_played)
        return True

    def refresh(self):
        """Redraw marks and status from the grid. Called after every change."""
        values = self.grid.rows()
        notes = {
            cell: self.grid.notes_at(cell)
            for cell in self.grid.empty_cells()
            if self.grid.notes_at(cell)
        }
        if self.settings["show_mistakes"] and not self.solved:
            conflicts = self.grid.conflicts()
        else:
            conflicts = set()

        if self.settings["highlight"] and not self.solved:
            focus = self.focus_cell
        else:
            focus = None
        self.board_view.refresh_marks(
            values, notes, self.selected_cell, conflicts, self.solved,
            focus_cell=focus,
        )

        if self.solved:
            self.status_label.text = "Solved in %s" % format_time(self.solve_seconds)
            self.status_label.text_color = SUCCESS
        else:
            remaining = len(self.grid.empty_cells())
            self.status_label.text = "Each row, column and box holds 1 to %d · %d to fill" % (
                self.puzzle.size, remaining)
            self.status_label.text_color = MUTED

        self.undo_button.enabled = self.grid.can_undo() and not self.solved

    def cell_tapped(self, cell):
        """Highlight the tapped cell and open the picker under the board.

        A given is highlighted but never opens the picker; tapping it again
        clears the highlight. The cell the picker is open for, tapped again,
        closes the picker and clears the highlight, as does a tap beside the
        grid. After a number is placed the highlight stays on its cell.
        """
        if self.solved or cell is None:
            self.focus_cell = None
            self.close_picker()
            self.refresh()
            return

        if self.grid.is_given(cell):
            self.focus_cell = None if cell == self.focus_cell else cell
            self.close_picker()
            self.refresh()
            return

        if cell == self.selected_cell and not self.picker.hidden:
            self.focus_cell = None
            self.close_picker()
            self.refresh()
            return

        self.selected_cell = cell
        self.focus_cell = cell

        # The picker opens under the whole grid rather than beside the cell,
        # so every number on the board stays visible while choosing. On a
        # short screen it may rest over Undo and New puzzle.
        board_x, board_y = self.board_view.frame[0], self.board_view.frame[1]
        grid_left, grid_top, grid_side = self.board_view.board_rect()
        grid_frame = (board_x + grid_left, board_y + grid_top, grid_side, grid_side)

        self.picker.show_below(
            grid_frame, (0, 0, self.width, self.height),
            current=self.grid.value_at(cell), notes=self.grid.notes_at(cell),
        )
        self.refresh()

    def close_picker(self):
        self.picker.hide_picker()
        if self.selected_cell is not None:
            self.selected_cell = None
            self.refresh()

    def value_picked(self, value):
        """Called by the picker: write a value, toggle a note, or clear (None).

        Every change is saved in the same tap.
        """
        cell = self.selected_cell
        if cell is None:
            self.picker.hide_picker()
            return

        if value is None:
            self.grid.clear(cell)
            self.picker.hide_picker()
            self.selected_cell = None
            self.refresh()
            self.save_game()
            return

        if self.picker.notes_mode:
            # Notes keep the picker open so several can be marked in a row.
            self.grid.toggle_note(cell, value)
            self.picker.update_marks(
                current=self.grid.value_at(cell), notes=self.grid.notes_at(cell)
            )
            self.refresh()
            self.save_game()
            return

        changed = self.grid.set_value(
            cell, value, clean_peer_notes=self.settings["tidy_notes"]
        )
        self.picker.hide_picker()
        self.selected_cell = None
        if changed and rules.is_solved(self.puzzle, self.grid.rows()):
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
        """A tap on the background, off the board and buttons, clears the
        highlight and closes the picker."""
        self.focus_cell = None
        self.close_picker()
        self.refresh()

    def apply_settings(self, draft, force_new_puzzle=False):
        """Adopt draft settings and save them.

        Deals a new puzzle if the size or difficulty changed, or when forced.
        Returns False, changing nothing, if the difficulty is not offered
        for the size.
        """
        if draft["difficulty"] not in rules.DIFFICULTIES_BY_SIZE.get(draft["size"], ()):
            return False

        previous = self.settings
        self.settings = dict(draft)

        needs_new = (
            force_new_puzzle
            or self.settings["size"] != previous["size"]
            or self.settings["difficulty"] != previous["difficulty"]
        )
        if needs_new:
            self.new_puzzle()
        else:
            self.refresh()

        if self.settings != previous:
            save_settings(self.settings)
        return True