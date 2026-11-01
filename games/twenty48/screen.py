"""
Double Up game screen: score line, message, board, New game, settings.

Lives under the Maths Games shell with the header contract from
gamecore/game.py: open_settings() puts a gear in the header, and
header_subtitle names the rules ("4×4 · Doubling from 2", "5×5 · Fibonacci").

Play: swipe the board. Every line slides that way and pairs merge
(rules.py). Reaching the goal is announced once and play goes on. The game
in progress is saved after every swipe and discarded once it is over; a
saved game resumes only if it was played under the current settings. The
best score is kept for each board size, mode and starting number.

UI stability (see JACK_BOOT): every change happens synchronously inside the
swipe or tap that caused it, views are made once and only shown, hidden or
re-labelled, and saves happen immediately. With Animate slides on, tiles
slide with ui.animate and no completion callbacks (see board_view.py).
"""

import json
import os
import random

import ui

from style import theme
from tilegame.widgets import ChoiceRow, make_button, make_label

from games.twenty48 import rules
from games.twenty48.board_view import Twenty48BoardView


# --- colours, from the shared theme -----------------------------------------

BACKGROUND = theme.color("background")
TEXT = theme.color("text")
MUTED = theme.color("muted")
SUCCESS = theme.color("success")

# --- editable layout and labels ---------------------------------------------

TOP_GAP = 8
STATUS_HEIGHT = 28
MESSAGE_HEIGHT = 24

SIZE_LABELS = tuple("%d×%d" % (size, size) for size in rules.BOARD_SIZES)
MODE_LABELS = ("Doubling", "Fibonacci")                    # rules.MODES
START_LABELS = tuple(str(number) for number in rules.STARTING_NUMBERS)


# --- saved files -------------------------------------------------------------

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(GAME_DIR, "settings.json")
SAVE_PATH = os.path.join(GAME_DIR, "saved_game.json")    # the game in progress
RECORDS_PATH = os.path.join(GAME_DIR, "records.json")    # best scores

DEFAULT_SETTINGS = {
    "size": rules.DEFAULT_SIZE,
    "mode": rules.DEFAULT_MODE,
    "start": rules.DEFAULT_START,
    "animate": True,
}

# Settings that change the game itself: changing one starts a new game.
RULE_KEYS = ("size", "mode", "start")

# --- theme editor preview ----------------------------------------------------

# A fixed board that shows a long stretch of the tile ramp. Nothing is
# read or written and touches are off.
PREVIEW_SETTINGS = dict(DEFAULT_SETTINGS)
PREVIEW_CELLS = [
    [2, 4, 8, 16],
    [256, 128, 64, 32],
    [512, 1024, 2048, 4096],
    [None, 16384, None, 2],
]
PREVIEW_SCORE = 98412


def read_json(path):
    """The JSON in path, or None if it is missing or unreadable."""
    try:
        with open(path) as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        print("Double Up: ignoring {}: {}".format(os.path.basename(path), error))
        return None


def write_json(path, data):
    """Save now, replacing the file in one step. A failed save is printed, never fatal."""
    temporary = path + ".tmp"
    try:
        with open(temporary, "w") as handle:
            json.dump(data, handle, indent=1, sort_keys=True)
        os.replace(temporary, path)
    except OSError as error:
        print("Double Up: could not save {}: {}".format(os.path.basename(path), error))


def load_settings():
    """Saved settings, using defaults for anything missing or invalid."""
    data = read_json(SETTINGS_PATH)
    data = data if isinstance(data, dict) else {}
    settings = dict(DEFAULT_SETTINGS)
    if data.get("size") in rules.BOARD_SIZES:
        settings["size"] = data["size"]
    if data.get("mode") in rules.MODES:
        settings["mode"] = data["mode"]
    if data.get("start") in rules.STARTING_NUMBERS:
        settings["start"] = data["start"]
    if isinstance(data.get("animate"), bool):
        settings["animate"] = data["animate"]
    return settings


def load_best_scores():
    data = read_json(RECORDS_PATH)
    scores = data.get("best_scores") if isinstance(data, dict) else None
    if not isinstance(scores, dict):
        return {}
    return {key: value for key, value in scores.items() if isinstance(value, int)}


def make_rule(settings):
    return rules.make_rule(settings["mode"], settings["start"])


def describe(settings):
    """The header subtitle for these settings."""
    size = settings["size"]
    if settings["mode"] == "fibonacci":
        return "%d×%d · Fibonacci" % (size, size)
    return "%d×%d · Doubling from %d" % (size, size, settings["start"])


def best_key(settings):
    """Best scores are kept per size, mode and starting number."""
    rule = make_rule(settings)
    return "%s/%d/%dx%d" % (rule.mode, rule.start, settings["size"], settings["size"])


class SettingsPanel(ui.View):
    """Overlay editing a draft of the settings, covering the game.

    Done adopts the draft, starting a new game only if something changed.
    New game adopts it and always starts one. The starting number fades
    out for Fibonacci, which always starts from 1 and 2.
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
        self.mode_caption = make_label("Tiles", ("AvenirNext-Medium", 15), MUTED)
        self.mode_control = ChoiceRow(MODE_LABELS, self.mode_changed)
        self.mode_note = make_label("", ("AvenirNext-Medium", 13), MUTED)
        self.start_caption = make_label("Starting number", ("AvenirNext-Medium", 15), MUTED)
        self.start_control = ChoiceRow(START_LABELS, self.start_changed)
        self.animate_label = make_label(
            "Animate slides", ("AvenirNext-Medium", 15), TEXT, alignment=ui.ALIGN_LEFT)
        self.animate_switch = ui.Switch()
        self.animate_switch.action = self.animate_changed
        self.change_note = make_label(
            "Changing size, tiles or start begins a new game",
            ("AvenirNext-Medium", 13), MUTED)

        self.new_game_button = make_button(
            "New game", self.new_game_tapped,
            background=theme.color("tile"), title_color=BACKGROUND,
        )
        self.done_button = make_button("Done", self.done_tapped)

        for view in (
            self.title_label,
            self.size_caption, self.size_control,
            self.mode_caption, self.mode_control, self.mode_note,
            self.start_caption, self.start_control,
            self.animate_label, self.animate_switch,
            self.change_note,
            self.new_game_button, self.done_button,
        ):
            self.add_subview(view)

    def layout(self):
        column = min(320, self.width - 48)
        left = (self.width - column) / 2

        y = self.TOP
        self.title_label.frame = (left, y, column, 36)
        y += 56
        self.size_caption.frame = (left, y, column, 22)
        y += 28
        self.size_control.frame = (left, y, column, 40)
        y += 56
        self.mode_caption.frame = (left, y, column, 22)
        y += 28
        self.mode_control.frame = (left, y, column, 40)
        y += 44
        self.mode_note.frame = (left, y, column, 20)
        y += 36
        self.start_caption.frame = (left, y, column, 22)
        y += 28
        self.start_control.frame = (left, y, column, 40)
        y += 56
        switch_width = 51
        self.animate_label.frame = (left, y, column - switch_width - 12, 44)
        self.animate_switch.frame = (left + column - switch_width, y + 6, switch_width, 31)
        y += 56
        self.change_note.frame = (left, y, column, 20)
        y += 36
        self.new_game_button.frame = (left, y, column, 52)
        y += 68
        self.done_button.frame = (left, y, column, 52)

    def open(self):
        self.draft = dict(self.screen.settings)
        self.size_control.selected_index = rules.BOARD_SIZES.index(self.draft["size"])
        self.mode_control.selected_index = rules.MODES.index(self.draft["mode"])
        self.start_control.selected_index = rules.STARTING_NUMBERS.index(self.draft["start"])
        self.animate_switch.value = bool(self.draft["animate"])
        self.sync_start()
        self.hidden = False
        self.bring_to_front()

    def sync_start(self):
        """Fade the starting number for Fibonacci and describe the merge rule."""
        if self.draft["mode"] == "fibonacci":
            self.start_control.set_enabled([False] * len(rules.STARTING_NUMBERS))
            self.mode_note.text = "Two 1s, or neighbours like 2 and 3, merge"
        else:
            self.start_control.set_enabled([True] * len(rules.STARTING_NUMBERS))
            start = self.draft["start"]
            self.mode_note.text = "Equal tiles merge: %d, %d, %d, %d, …" % (
                start, 2 * start, 4 * start, 8 * start)

    def size_changed(self, sender):
        self.draft["size"] = rules.BOARD_SIZES[sender.selected_index]

    def mode_changed(self, sender):
        self.draft["mode"] = rules.MODES[sender.selected_index]
        self.sync_start()

    def start_changed(self, sender):
        self.draft["start"] = rules.STARTING_NUMBERS[sender.selected_index]
        self.sync_start()

    def animate_changed(self, sender):
        self.draft["animate"] = bool(sender.value)

    def new_game_tapped(self, sender):
        self.screen.apply_settings(self.draft, force_new_game=True)
        self.hidden = True

    def done_tapped(self, sender):
        self.screen.apply_settings(self.draft)
        self.hidden = True


class Twenty48Screen(ui.View):
    """Double Up under the shell header: one game at a time."""

    SIDE_MARGIN = 16
    BOTTOM_BAR = 80

    def __init__(self, preview=False, **kwargs):
        super().__init__(**kwargs)
        self.preview = preview      # theme editor sample: no disk, no touches
        self.background_color = BACKGROUND
        self.settings = dict(PREVIEW_SETTINGS) if preview else load_settings()
        self.best_scores = {} if preview else load_best_scores()

        # Header contract (gamecore/game.py). The shell replaces the callback.
        self.header_subtitle = ""
        self.on_header_changed = None

        self.game = None
        self.last_result = None      # the latest MoveResult, for animation later

        self.score_label = make_label("", ("AvenirNext-DemiBold", 17), TEXT)
        self.message_label = make_label("", ("AvenirNext-Medium", 15), MUTED)

        self.board_view = Twenty48BoardView()
        self.board_view.background_color = BACKGROUND
        self.board_view.on_swipe = self.swipe

        self.new_button = make_button("New game", self.new_tapped)
        self.settings_panel = SettingsPanel(self)

        for view in (
            self.score_label,
            self.message_label,
            self.board_view,
            self.new_button,
            self.settings_panel,   # last, so it covers everything
        ):
            self.add_subview(view)

        if preview:
            self.show_preview_sample()
            self.touch_enabled = False
        elif not self.resume_saved_game():
            self.new_game()

    # --- header contract -----------------------------------------------------

    def open_settings(self):
        """Called by the shell's gear."""
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

        self.score_label.frame = (margin, TOP_GAP, width - 2 * margin, STATUS_HEIGHT)
        self.message_label.frame = (margin, TOP_GAP + STATUS_HEIGHT,
                                    width - 2 * margin, MESSAGE_HEIGHT)

        board_top = TOP_GAP + STATUS_HEIGHT + MESSAGE_HEIGHT + 4
        buttons_y = height - self.BOTTOM_BAR + 16
        self.board_view.frame = (0, board_top, width, max(0, buttons_y - 12 - board_top))
        self.board_view.set_needs_display()

        button_width = min(220, width - 2 * margin)
        self.new_button.frame = ((width - button_width) / 2, buttons_y, button_width, 48)

        self.settings_panel.frame = self.bounds

    # --- game flow -----------------------------------------------------------

    def new_game(self):
        """Start a game for the current settings, show it and save it."""
        rule = make_rule(self.settings)
        self.game = rules.Game.new(self.settings["size"], rule, random.Random())
        self.last_result = None
        self.show_game()
        self.save_game()

    def show_game(self):
        self.set_subtitle(describe(self.settings))
        self.refresh()

    def show_preview_sample(self):
        """The fixed board the theme editor previews. Nothing is saved."""
        game = rules.Game(len(PREVIEW_CELLS), make_rule(self.settings), random.Random(0))
        game.cells = [list(row) for row in PREVIEW_CELLS]
        game.score = PREVIEW_SCORE
        game.won = True
        self.game = game
        self.show_game()

    def current_best(self):
        return self.best_scores.get(best_key(self.settings), 0)

    def refresh(self):
        """Redraw everything from the game at once: board, score and message."""
        self.board_view.show(self.game.cells, self.game.rule)
        self.refresh_labels()

    def refresh_labels(self):
        """Score line and message from the game."""
        game = self.game
        best = max(self.current_best(), game.score)
        self.score_label.text = "Score %d · Best %d" % (game.score, best)

        if game.is_over():
            self.message_label.text = "No moves left · tap New game"
            self.message_label.text_color = MUTED
        elif game.won:
            self.message_label.text = "%d reached · keep going" % game.rule.goal
            self.message_label.text_color = SUCCESS
        else:
            self.message_label.text = "Make %d" % game.rule.goal
            self.message_label.text_color = MUTED

    def swipe(self, direction):
        """Called by the board: play one swipe, then show it and save, all now.

        A swipe that changes nothing does nothing at all.
        """
        if self.preview or self.game is None or not self.settings_panel.hidden:
            return
        result = self.game.move(direction)
        if result is None:
            return
        self.last_result = result
        self.board_view.play(result, self.game.cells, animate=self.settings["animate"])
        self.record_score()
        self.refresh_labels()
        self.save_game()

    # --- saving --------------------------------------------------------------

    def record_score(self):
        """Keep the best score for these settings, saved as soon as it is beaten."""
        if self.preview:
            return
        key = best_key(self.settings)
        if self.game.score > self.best_scores.get(key, 0):
            self.best_scores[key] = self.game.score
            write_json(RECORDS_PATH, {"best_scores": self.best_scores})

    def save_game(self):
        """Save the game in progress now. A finished game discards the save."""
        if self.preview:
            return
        if self.game.is_over():
            try:
                os.remove(SAVE_PATH)
            except FileNotFoundError:
                pass
            except OSError as error:
                print("Double Up: could not discard the save: {}".format(error))
            return
        write_json(SAVE_PATH, self.game.to_data())

    def resume_saved_game(self):
        """Show the saved game if it fits the current settings. True when resumed."""
        data = read_json(SAVE_PATH)
        if data is None:
            return False
        try:
            game = rules.Game.from_data(data)
        except ValueError as error:
            print("Double Up: ignoring saved game: {}".format(error))
            return False
        rule = make_rule(self.settings)
        if (game.size, game.rule.mode, game.rule.start) != (
                self.settings["size"], rule.mode, rule.start):
            return False
        if game.is_over():
            return False
        self.game = game
        self.last_result = None
        self.show_game()
        return True

    # --- buttons and settings -----------------------------------------------

    def new_tapped(self, sender):
        self.new_game()

    def apply_settings(self, draft, force_new_game=False):
        """Adopt draft settings and save them; a rule change starts a new game."""
        changed = any(draft[key] != self.settings[key] for key in RULE_KEYS)
        self.settings = dict(draft)
        if not self.preview:
            write_json(SETTINGS_PATH, self.settings)
        if changed or force_new_game:
            self.new_game()
        return True