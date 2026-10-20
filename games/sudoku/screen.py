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

Second way in: the number tray under the board shows each number with a
stack of bars, one for every copy still to place. Tap a number to arm it,
then tap cells
to place it with no picker; tap a cell holding it to clear it. Tap the
armed number again, or beside the board, to disarm. An armed number
disarms itself once every copy is placed. While a number is armed, the
Notes chip at the end of the tray switches cell taps to toggling that
number's pencil mark in empty cells; disarming turns Notes off.

Solving starts a two-second celebration in a random style over the board
(tilegame/flourish_overlay.py, timed by feel/flourish.py), coloured from
the player's theme. It stays until the next deal.

Best times: every solve is stored in records.json under its size and the
level the puzzle actually reached (the subtitle's level), so each board
has its own leaderboard. Settings > Best times lists the ten fastest with
dates. A preview never reads or writes records.

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
from tilegame.number_tray import NumberTray
from tilegame.flourish_overlay import FlourishOverlay
from tilegame.records import TOP_LENGTH, RecordBook, record_key
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
RECORDS_PATH = os.path.join(GAME_DIR, "records.json")   # best times per board

DEFAULT_SETTINGS = {
    "size": 9,
    "difficulty": "easy",
    "show_mistakes": True,
    "tidy_notes": True,
    "highlight": True,
    "highlight_complete": False,
}


# --- theme editor preview ----------------------------------------------------

# The theme editor shows this screen with preview=True: a fixed sample, no
# disk use and no touches. The seed fixes the sample, so every swatch tap
# shows the same board. Completed numbers are highlighted so that mark shows.
PREVIEW_SEED = 2026
PREVIEW_SETTINGS = dict(DEFAULT_SETTINGS, highlight_complete=True)
_preview_puzzle = None      # dealt once, then reused for speed


def preview_puzzle():
    """The sample puzzle, dealt once from PREVIEW_SEED."""
    global _preview_puzzle
    if _preview_puzzle is None:
        from random import Random
        _preview_puzzle = rules.generate_puzzle(9, "easy", rng=Random(PREVIEW_SEED))
    return _preview_puzzle


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

    for key in ("show_mistakes", "tidy_notes", "highlight", "highlight_complete"):
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


def best_times_key(size, level):
    """Records key for a board size and the level a puzzle reached (1 to 3)."""
    return record_key("sudoku", "%dx%d" % (size, size), rules.DIFFICULTIES[level - 1])


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

        self.complete_label = make_label(
            "Highlight completed numbers",
            ("AvenirNext-Medium", 15), TEXT, alignment=ui.ALIGN_LEFT,
        )
        self.complete_label.number_of_lines = 2
        self.complete_switch = ui.Switch()
        self.complete_switch.action = self.complete_changed
        self.highlight_switch = ui.Switch()
        self.highlight_switch.action = self.highlight_changed

        self.new_puzzle_button = make_button(
            "New puzzle", self.new_puzzle_tapped,
            background=theme.color("tile"), title_color=BACKGROUND,
        )
        self.done_button = make_button("Done", self.done_tapped)
        self.best_times_button = make_button("Best times", self.best_times_tapped)

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
            self.complete_label,
            self.complete_switch,
            self.new_puzzle_button,
            self.best_times_button,
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
        y += 56
        self.complete_label.frame = (left, y, column - switch_width - 12, 44)
        self.complete_switch.frame = (left + column - switch_width, y + 6, switch_width, 31)
        y += 68
        self.new_puzzle_button.frame = (left, y, column, 52)
        y += 68
        half = (column - 12) / 2
        self.best_times_button.frame = (left, y, half, 52)
        self.done_button.frame = (left + half + 12, y, half, 52)

    def open(self):
        self.draft = dict(self.screen.settings)
        self.size_control.selected_index = rules.BOARD_SIZES.index(self.draft["size"])
        self.sync_difficulty()
        self.mistakes_switch.value = bool(self.draft["show_mistakes"])
        self.tidy_switch.value = bool(self.draft["tidy_notes"])
        self.highlight_switch.value = bool(self.draft["highlight"])
        self.complete_switch.value = bool(self.draft["highlight_complete"])
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

    def complete_changed(self, sender):
        self.draft["highlight_complete"] = bool(sender.value)

    def new_puzzle_tapped(self, sender):
        if self.screen.apply_settings(self.draft, force_new_puzzle=True):
            self.hidden = True

    def done_tapped(self, sender):
        if self.screen.apply_settings(self.draft):
            self.hidden = True

    def best_times_tapped(self, sender):
        """Show the best times over Settings; its Back returns here."""
        self.screen.open_best_times()


class BestTimesPanel(ui.View):
    """Overlay listing the fastest solves for one board size and level.

    Each size and level is its own leaderboard. It opens on the current
    puzzle's board; Back returns to Settings underneath. Every label is
    made once and only re-labelled when the choice changes.
    """

    TOP = 16
    ROW_HEIGHT = 30

    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.background_color = BACKGROUND
        self.hidden = True
        self.size = rules.BOARD_SIZES[-1]
        self.level = 1

        self.title_label = make_label("Best times", ("AvenirNext-Bold", 24), TEXT)
        self.size_control = ChoiceRow(SIZE_LABELS, self.size_changed)
        self.level_control = ChoiceRow(DIFFICULTY_LABELS, self.level_changed)
        self.empty_label = make_label(
            "No solves on this board yet", ("AvenirNext-Medium", 15), MUTED)

        self.time_labels = []
        self.date_labels = []
        for _ in range(TOP_LENGTH):
            self.time_labels.append(make_label(
                "", ("AvenirNext-DemiBold", 17), TEXT, alignment=ui.ALIGN_LEFT))
            self.date_labels.append(make_label(
                "", ("AvenirNext-Medium", 15), MUTED, alignment=ui.ALIGN_RIGHT))

        self.back_button = make_button("Back to settings", self.back_tapped)

        for view in (
            [self.title_label, self.size_control, self.level_control, self.empty_label]
            + self.time_labels + self.date_labels + [self.back_button]
        ):
            self.add_subview(view)

    def layout(self):
        column = min(320, self.width - 48)
        left = (self.width - column) / 2

        y = self.TOP
        self.title_label.frame = (left, y, column, 36)
        y += 52
        self.size_control.frame = (left, y, column, 40)
        y += 52
        self.level_control.frame = (left, y, column, 40)
        y += 56
        self.empty_label.frame = (left, y, column, 24)
        for index, (time_label, date_label) in enumerate(
                zip(self.time_labels, self.date_labels)):
            row_y = y + index * self.ROW_HEIGHT
            time_label.frame = (left, row_y, column / 2, self.ROW_HEIGHT)
            date_label.frame = (left + column / 2, row_y, column / 2, self.ROW_HEIGHT)
        y += TOP_LENGTH * self.ROW_HEIGHT + 20
        self.back_button.frame = (left, y, column, 52)

    def open(self, size, level):
        self.size = size
        self.level = level
        self.size_control.selected_index = rules.BOARD_SIZES.index(size)
        self.show_board()
        self.hidden = False
        self.bring_to_front()

    def show_board(self):
        """Fade levels this size never reaches, then list its fastest solves."""
        offered = rules.DIFFICULTIES_BY_SIZE[self.size]
        reachable = [difficulty in offered for difficulty in rules.DIFFICULTIES]
        self.level_control.set_enabled(reachable)
        if not reachable[self.level - 1]:
            self.level = rules.DIFFICULTIES.index(offered[-1]) + 1
        self.level_control.selected_index = self.level - 1

        records = self.screen.records
        runs = records.top(best_times_key(self.size, self.level)) if records else []
        self.empty_label.hidden = bool(runs)
        for index, (time_label, date_label) in enumerate(
                zip(self.time_labels, self.date_labels)):
            if index < len(runs):
                run = runs[index]
                time_label.text = "%d.   %s" % (index + 1, format_time(run["seconds"]))
                date_label.text = time.strftime("%d %b %Y", time.localtime(run["when"]))
            else:
                time_label.text = ""
                date_label.text = ""

    def size_changed(self, sender):
        self.size = rules.BOARD_SIZES[sender.selected_index]
        self.show_board()

    def level_changed(self, sender):
        self.level = sender.selected_index + 1
        self.show_board()

    def back_tapped(self, sender):
        self.hidden = True


class SudokuScreen(ui.View):
    """Sudoku under the shell header: one puzzle at a time."""

    SIDE_MARGIN = 16
    BOTTOM_BAR = 80
    TRAY_GAP = 10       # space above and below the number tray

    def __init__(self, preview=False, **kwargs):
        super().__init__(**kwargs)
        self.preview = preview      # theme editor sample: no disk, no touches
        self.background_color = BACKGROUND
        if preview:
            self.settings = dict(PREVIEW_SETTINGS)
            self.records = None     # a preview never reads or writes best times
        else:
            self.settings = load_settings()
            self.records = RecordBook(RECORDS_PATH)

        # Header contract (gamecore/game.py). The shell replaces the callback.
        self.header_subtitle = ""
        self.on_header_changed = None

        self.puzzle = None
        self.grid = None             # FillGrid holding values and notes
        self.selected_cell = None    # the cell the picker is open for
        self.focus_cell = None       # the cell highlighted with its row, column, box and number
        self.armed_value = None      # the tray number that cell taps place, or None
        self.notes_armed = False     # with a number armed, cell taps toggle its note instead
        self.started = None          # when this puzzle was dealt
        self.solve_seconds = None    # set once, in the tap that solves it
        self.run_result = None       # RunResult once a solve is recorded

        self.status_label = make_label("", ("AvenirNext-Medium", 15), MUTED)

        self.board_view = SudokuBoardView()
        self.board_view.background_color = BACKGROUND
        self.board_view.on_cell_tapped = self.cell_tapped

        # The solve celebration: over the board, touches pass through.
        self.flourish = FlourishOverlay()

        self.tray = NumberTray(self.tray_tapped, on_notes=self.tray_notes_tapped)

        self.undo_button = make_button("Undo", self.undo_tapped)
        self.new_button = make_button("New puzzle", self.new_tapped)

        self.picker = CellPicker(self.value_picked, notes_enabled=True)
        self.settings_panel = SettingsPanel(self)
        self.best_times_panel = BestTimesPanel(self)

        for view in (
            self.status_label,
            self.board_view,
            self.flourish,           # over the board, under the tray and picker
            self.tray,
            self.undo_button,
            self.new_button,
            self.picker,             # opens over the tray
            self.settings_panel,     # covers the game
            self.best_times_panel,   # last, so it covers Settings
        ):
            self.add_subview(view)

        if preview:
            self.show_preview_sample()
            self.touch_enabled = False
        elif not self.resume_saved_game():
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

        # The board gets what is left after the status line, the number tray
        # and the buttons; the tray then sits just under the grid, as wide.
        board_top = TOP_GAP + STATUS_HEIGHT + 4
        buttons_y = height - self.BOTTOM_BAR + 16
        tray_space = self.tray.HEIGHT + 2 * self.TRAY_GAP
        self.board_view.frame = (
            0, board_top, width, max(0, buttons_y - 12 - tray_space - board_top))

        self.flourish.frame = self.board_view.frame

        grid_left, grid_top, grid_side = self.board_view.board_rect()
        self.tray.frame = (
            grid_left, board_top + grid_top + grid_side + self.TRAY_GAP,
            grid_side, self.tray.HEIGHT)
        self.tray.set_needs_display()

        button_width = min(160, (width - 3 * margin) / 2)
        row_left = (width - (2 * button_width + 12)) / 2
        self.undo_button.frame = (row_left, buttons_y, button_width, 48)
        self.new_button.frame = (row_left + button_width + 12, buttons_y, button_width, 48)

        self.settings_panel.frame = self.bounds
        self.best_times_panel.frame = self.bounds

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
        self.armed_value = None
        self.notes_armed = False
        self.run_result = None
        self.started = time.time() - seconds_played
        self.solve_seconds = None

        self.stop_flourish()
        self.picker.hide_picker()
        self.picker.set_values(self.grid.allowed_values)
        self.board_view.load_puzzle(self.puzzle, rules.BOX_SHAPES[size])
        self.set_subtitle("%d×%d · %s" % (
            size, size, LEVEL_LABELS.get(self.puzzle.level, "Easy")))
        self.refresh()

    def show_preview_sample(self):
        """Show the fixed sample the theme editor previews. Nothing is saved.

        Every mark a colour choice can affect is on screen: givens, player
        numbers, a completed number, notes, a clash, and a selected cell with
        its row, column, box and matching numbers highlighted. The marks are
        made through the same FillGrid calls as real play.
        """
        puzzle = preview_puzzle()
        grid = self.fresh_grid(puzzle)
        size = puzzle.size
        empty = [
            (row, col)
            for row in range(size) for col in range(size)
            if puzzle.givens[row][col] is None
        ]

        def answer(cell):
            return puzzle.solution[cell[0]][cell[1]]

        # A completed number: every empty cell that should hold it, filled.
        completed_value = answer(empty[0])
        for cell in empty:
            if answer(cell) == completed_value:
                grid.set_value(cell, completed_value, clean_peer_notes=False)
        remaining = [cell for cell in empty if grid.value_at(cell) is None]

        # Notes in two cells: the right answer and one other candidate.
        for cell in remaining[1:3]:
            for value in sorted({answer(cell), answer(cell) % size + 1}):
                grid.toggle_note(cell, value)

        # A clash: a value already given in the same row.
        clash_cell = remaining[-1]
        row_givens = [
            value for value in puzzle.givens[clash_cell[0]]
            if value is not None and value != completed_value
        ]
        if row_givens:
            grid.set_value(clash_cell, row_givens[0], clean_peer_notes=False)

        self.show_puzzle(puzzle, grid, seconds_played=0)
        # Select a placed copy of the completed number, so its row, column,
        # box and matching numbers are highlighted too.
        self.selected_cell = empty[0]
        self.focus_cell = empty[0]
        self.refresh()

    # --- saved game ----------------------------------------------------------

    def save_game(self):
        """Save the puzzle in progress now. A solved puzzle discards the save.

        A preview never touches disk.
        """
        if self.preview:
            return
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
        """Redraw marks, tray and status from the grid. Called after every change.

        An armed number whose copies are all placed (or a solved puzzle)
        disarms here, so placing, undo and new deals all get it right.
        """
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

        remaining_by_value = self.remaining_by_value(values)
        if self.armed_value is not None and (
                self.solved or remaining_by_value.get(self.armed_value, 0) == 0):
            self.armed_value = None
        if self.armed_value is None:
            self.notes_armed = False

        if self.settings["highlight"] and not self.solved:
            focus = self.focus_cell
        else:
            focus = None
        if self.settings["highlight_complete"] and not self.solved:
            completed = self.grid.completed_values()
        else:
            completed = ()
        self.board_view.refresh_marks(
            values, notes, self.selected_cell, conflicts, self.solved,
            focus_cell=focus, completed=completed, armed_value=self.armed_value,
        )
        self.tray.show(
            self.grid.allowed_values, remaining_by_value,
            capacity=self.puzzle.size, armed=self.armed_value,
            notes_on=self.notes_armed,
        )

        if self.solved:
            self.status_label.text = self.solved_text()
            self.status_label.text_color = SUCCESS
        else:
            remaining = len(self.grid.empty_cells())
            self.status_label.text = "Each row, column and box holds 1 to %d · %d to fill" % (
                self.puzzle.size, remaining)
            self.status_label.text_color = MUTED

        self.undo_button.enabled = self.grid.can_undo() and not self.solved

    def remaining_by_value(self, values):
        """How many more copies of each number the board needs.

        Wrong numbers count as placed, so the tray never hints at mistakes.
        """
        placed = {value: 0 for value in self.grid.allowed_values}
        for row in values:
            for value in row:
                if value in placed:
                    placed[value] += 1
        return {
            value: max(0, self.puzzle.size - count)
            for value, count in placed.items()
        }

    def solved_text(self):
        """The status line once solved, with how the time compares."""
        text = "Solved in %s" % format_time(self.solve_seconds)
        result = self.run_result
        if result is None:
            return text
        if result.previous_best is None:
            return text + " · first best time"
        if result.is_best:
            return text + " · new best!"
        return text + " · best %s" % format_time(result.previous_best)

    def puzzle_level(self):
        """The level the current puzzle reached, 1 (Easy) to 3 (Hard)."""
        level = self.puzzle.level
        return level if level in (1, 2, 3) else 1

    def open_best_times(self):
        """Called from Settings: the best times for the current puzzle's board."""
        self.best_times_panel.open(self.puzzle.size, self.puzzle_level())

    def record_solve(self):
        """Add the solve time to its board's best times, saved now.

        A preview records nothing; a failed save is reported, never fatal.
        """
        if self.records is None:
            return
        key = best_times_key(self.puzzle.size, self.puzzle_level())
        try:
            self.run_result = self.records.add(key, self.solve_seconds)
        except OSError as error:
            print("Sudoku: best time not saved: {}".format(error))

    def cell_tapped(self, cell):
        """Highlight the tapped cell and open the picker under the board.

        A given is highlighted but never opens the picker; tapping it again
        clears the highlight. The cell the picker is open for, tapped again,
        closes the picker and clears the highlight, as does a tap beside the
        grid. After a number is placed the highlight stays on its cell.

        With a tray number armed, a tap places it instead (no picker).
        """
        if self.solved or cell is None:
            self.focus_cell = None
            self.armed_value = None
            self.close_picker()
            self.refresh()
            return

        if self.armed_value is not None:
            self.cell_tapped_while_armed(cell)
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
        # so every number on the board stays visible while choosing. It
        # covers the number tray while open. On a short screen it may rest
        # over Undo and New puzzle.
        board_x, board_y = self.board_view.frame[0], self.board_view.frame[1]
        grid_left, grid_top, grid_side = self.board_view.board_rect()
        grid_frame = (board_x + grid_left, board_y + grid_top, grid_side, grid_side)

        self.picker.show_below(
            grid_frame, (0, 0, self.width, self.height),
            current=self.grid.value_at(cell), notes=self.grid.notes_at(cell),
            completed=self.grid.completed_values(),
        )
        self.refresh()

    def cell_tapped_while_armed(self, cell):
        """Place the armed number in cell, or clear it if it is already there.

        Givens are left alone. A different player number is replaced.
        """
        if self.grid.is_given(cell):
            return
        if self.notes_armed:
            # Notes go only in empty cells; a cell holding a number is left alone.
            if self.grid.value_at(cell) is None:
                self.grid.toggle_note(cell, self.armed_value)
                self.refresh()
                self.save_game()
            return
        if self.grid.value_at(cell) == self.armed_value:
            self.grid.clear(cell)
            self.refresh()
            self.save_game()
            return
        self.place_value(cell, self.armed_value)

    def tray_tapped(self, value):
        """Arm a tray number, or disarm it if it is already armed.

        Arming closes the picker and drops the cell highlight, so the board
        highlights every copy of the armed number instead.
        """
        if self.solved:
            return
        self.picker.hide_picker()
        self.selected_cell = None
        self.focus_cell = None
        self.armed_value = None if value == self.armed_value else value
        self.refresh()

    def tray_notes_tapped(self):
        """Toggle Notes for the armed number: cell taps then toggle its pencil
        mark instead of placing it. The tray offers it only while armed."""
        if self.solved or self.armed_value is None:
            return
        self.notes_armed = not self.notes_armed
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

        self.picker.hide_picker()
        self.selected_cell = None
        self.place_value(cell, value)

    def place_value(self, cell, value):
        """Write value into cell, check for a solve, redraw and save, all now.

        The picker and the number tray both place numbers through here.
        """
        changed = self.grid.set_value(
            cell, value, clean_peer_notes=self.settings["tidy_notes"]
        )
        just_solved = changed and rules.is_solved(self.puzzle, self.grid.rows())
        if just_solved:
            self.solve_seconds = time.time() - self.started
            self.record_solve()
        self.refresh()
        self.save_game()
        if just_solved:
            self.start_flourish(cell)

    def start_flourish(self, last_cell):
        """Celebrate a solve in the tap that solved it: a random style, any
        ripple starting from the last cell filled. A preview never celebrates."""
        if self.preview:
            return
        self.board_view.values_hidden = True
        self.board_view.set_needs_display()
        self.flourish.play(
            self.grid.rows(), set(self.puzzle.givens_by_cell()),
            rules.BOX_SHAPES[self.puzzle.size], self.board_view.cell_frame,
            origin=last_cell,
        )

    def stop_flourish(self):
        """Clear the celebration and give the board its numbers back."""
        self.flourish.clear()
        if self.board_view.values_hidden:
            self.board_view.values_hidden = False
            self.board_view.set_needs_display()

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
        highlight, disarms the tray and closes the picker."""
        self.focus_cell = None
        self.armed_value = None
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