"""
Gradient game screen: moves and par, a message, the board, Hint and New level.

Lives under the Maths Games shell with the header contract from
gamecore/game.py: open_settings() puts a gear in the header, and
header_subtitle names the level ("Medium · 7×9", "Daily · 24 Oct · 7×9").

Play: swap tiles until every colour is back in its place (rules.py). Par is
the fewest swaps that solve the dealt board. The level in progress is saved
after every swap and discarded once solved. Records keep, for each mode, the
solves, the best result against par and the fastest time, plus each day's
Daily result.

UI stability (see the pythonista-ui-stability guide): every change happens
inside the tap or swap that caused it, views are made once, and saves happen
immediately.
"""

import datetime
import json
import os
import random
import time

import ui

from style import theme
from tilegame.widgets import ChoiceRow, make_button, make_label

from games.gradient import levels, rules
from games.gradient.board_view import GradientBoardView


# --- colours, from the shared theme -----------------------------------------

BACKGROUND = theme.color("background")
TEXT = theme.color("text")
MUTED = theme.color("muted")
SUCCESS = theme.color("success")

# --- editable layout, modes and labels -----------------------------------------

TOP_GAP = 8
STATUS_HEIGHT = 28
MESSAGE_HEIGHT = 24

MODES = ("easy", "medium", "hard", "daily")
MODE_LABELS = ("Easy", "Medium", "Hard", "Daily")
MODE_NOTES = {
    "easy": "Small boards with plenty of fixed tiles",
    "medium": "Bigger boards and fewer fixed tiles",
    "hard": "Large boards, subtle steps, few fixed tiles",
    "daily": "One medium level a day, the same for everyone",
}
DAILY_DIFFICULTY = "medium"
PLAY_MESSAGE = "Swap tiles to restore the gradient"

# --- saved files -----------------------------------------------------------------

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(GAME_DIR, "settings.json")
SAVE_PATH = os.path.join(GAME_DIR, "saved_game.json")    # the level in progress
RECORDS_PATH = os.path.join(GAME_DIR, "records.json")
SAVE_VERSION = 1

DEFAULT_SETTINGS = {"mode": "medium"}

# --- theme editor preview ----------------------------------------------------------

PREVIEW_SEED = 7
PREVIEW_DIFFICULTY = "medium"


def read_json(path):
    """The JSON in path, or None if it is missing or unreadable."""
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        print("Gradient: ignoring {}: {}".format(os.path.basename(path), error))
        return None


def write_json(path, data):
    """Save now, replacing the file in one step. A failed save is printed, never fatal."""
    temporary = path + ".tmp"
    try:
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=1, sort_keys=True)
        os.replace(temporary, path)
    except (OSError, TypeError, ValueError) as error:
        print("Gradient: could not save {}: {}".format(os.path.basename(path), error))


def discard(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as error:
        print("Gradient: could not remove {}: {}".format(os.path.basename(path), error))


def load_settings():
    data = read_json(SETTINGS_PATH)
    settings = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict) and data.get("mode") in MODES:
        settings["mode"] = data["mode"]
    return settings


def load_records():
    data = read_json(RECORDS_PATH)
    data = data if isinstance(data, dict) else {}
    modes = data.get("modes")
    daily = data.get("daily")
    return {
        "modes": modes if isinstance(modes, dict) else {},
        "daily": daily if isinstance(daily, dict) else {},
    }


def daily_seed(day=None):
    """The seed for a day's level, the same on every device."""
    return "daily-" + (day or datetime.date.today()).isoformat()


def make_level(mode, seed):
    difficulty = DAILY_DIFFICULTY if mode == "daily" else mode
    return levels.generate_level(seed, difficulty)


def describe(mode, level):
    """The header subtitle for a level."""
    size = "%d×%d" % (level.cols, level.rows)
    if mode == "daily":
        day = datetime.date.today()
        return "Daily · %d %s · %s" % (day.day, day.strftime("%b"), size)
    return "%s · %s" % (MODE_LABELS[MODES.index(mode)], size)


def format_time(seconds):
    seconds = int(round(seconds))
    return "%d:%02d" % (seconds // 60, seconds % 60)


def against_par(moves, par):
    over = moves - par
    return "on par" if over <= 0 else "par +%d" % over


class SettingsPanel(ui.View):
    """Overlay choosing the mode, covering the game.

    Done adopts the choice, starting a new level only if the mode changed.
    New level adopts it and always starts one.
    """

    TOP = 16

    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.background_color = BACKGROUND
        self.hidden = True
        self.draft = dict(screen.settings)

        self.title_label = make_label("Settings", ("AvenirNext-Bold", 24), TEXT)
        self.mode_caption = make_label("Levels", ("AvenirNext-Medium", 15), MUTED)
        self.mode_control = ChoiceRow(MODE_LABELS, self.mode_changed)
        self.mode_note = make_label("", ("AvenirNext-Medium", 13), MUTED)
        self.new_level_button = make_button(
            "New level", self.new_level_tapped,
            background=theme.color("tile"), title_color=BACKGROUND,
        )
        self.done_button = make_button("Done", self.done_tapped)

        for view in (self.title_label, self.mode_caption, self.mode_control,
                     self.mode_note, self.new_level_button, self.done_button):
            self.add_subview(view)

    def layout(self):
        column = min(320, self.width - 48)
        left = (self.width - column) / 2
        y = self.TOP
        self.title_label.frame = (left, y, column, 36)
        y += 56
        self.mode_caption.frame = (left, y, column, 22)
        y += 28
        self.mode_control.frame = (left, y, column, 40)
        y += 44
        self.mode_note.frame = (left, y, column, 20)
        y += 44
        self.new_level_button.frame = (left, y, column, 52)
        y += 68
        self.done_button.frame = (left, y, column, 52)

    def open(self):
        self.draft = dict(self.screen.settings)
        self.mode_control.selected_index = MODES.index(self.draft["mode"])
        self.mode_note.text = MODE_NOTES[self.draft["mode"]]
        self.hidden = False
        self.bring_to_front()

    def mode_changed(self, sender):
        self.draft["mode"] = MODES[sender.selected_index]
        self.mode_note.text = MODE_NOTES[self.draft["mode"]]

    def new_level_tapped(self, sender):
        self.screen.apply_settings(self.draft, force_new_level=True)
        self.hidden = True

    def done_tapped(self, sender):
        self.screen.apply_settings(self.draft)
        self.hidden = True


class GradientScreen(ui.View):
    """Gradient under the shell header: one level at a time."""

    SIDE_MARGIN = 16
    BOTTOM_BAR = 80

    def __init__(self, preview=False, **kwargs):
        super().__init__(**kwargs)
        self.preview = preview      # theme editor sample: no disk, no touches
        self.background_color = BACKGROUND
        self.settings = dict(DEFAULT_SETTINGS) if preview else load_settings()
        self.records = {"modes": {}, "daily": {}} if preview else load_records()

        # Header contract (gamecore/game.py). The shell replaces the callback.
        self.header_subtitle = ""
        self.on_header_changed = None

        self.model = None
        self.mode = self.settings["mode"]     # the mode the current level was dealt in
        self.seconds_before = 0.0             # time played before this sitting
        self.sitting_started = time.time()
        self.solve_seconds = None
        self.hints_used = 0

        self.status_label = make_label("", ("AvenirNext-DemiBold", 17), TEXT)
        self.message_label = make_label("", ("AvenirNext-Medium", 15), MUTED)

        self.board_view = GradientBoardView()
        self.board_view.background_color = BACKGROUND
        self.board_view.on_swap = self.swap_requested

        self.hint_button = make_button("Hint", self.hint_tapped)
        self.new_button = make_button("New level", self.new_tapped)
        self.settings_panel = SettingsPanel(self)

        for view in (self.status_label, self.message_label, self.board_view,
                     self.hint_button, self.new_button,
                     self.settings_panel):     # last, so it covers everything
            self.add_subview(view)

        if preview:
            self.show_preview_sample()
            self.touch_enabled = False
        elif not self.resume_saved_game():
            self.new_level()

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
        width, height = self.width, self.height
        margin = self.SIDE_MARGIN
        self.status_label.frame = (margin, TOP_GAP, width - 2 * margin, STATUS_HEIGHT)
        self.message_label.frame = (margin, TOP_GAP + STATUS_HEIGHT,
                                    width - 2 * margin, MESSAGE_HEIGHT)
        board_top = TOP_GAP + STATUS_HEIGHT + MESSAGE_HEIGHT + 4
        buttons_y = height - self.BOTTOM_BAR + 16
        self.board_view.frame = (0, board_top, width, max(0, buttons_y - 12 - board_top))

        row_width = min(320, width - 2 * margin)
        button_width = (row_width - 12) / 2
        left = (width - row_width) / 2
        self.hint_button.frame = (left, buttons_y, button_width, 48)
        self.new_button.frame = (left + button_width + 12, buttons_y, button_width, 48)
        self.settings_panel.frame = self.bounds

    # --- level flow -------------------------------------------------------------

    def new_level(self):
        """Deal a level for the current mode, show it with the intro and save it."""
        self.mode = self.settings["mode"]
        seed = daily_seed() if self.mode == "daily" else random.randrange(1, 10 ** 9)
        self.model = rules.GradientBoard(make_level(self.mode, seed))
        self.seconds_before = 0.0
        self.sitting_started = time.time()
        self.solve_seconds = None
        self.hints_used = 0
        self.board_view.show(self.model, intro=True)
        self.refresh()
        self.save_game()

    def show_preview_sample(self):
        """A fixed level for the theme editor. Nothing is read or saved."""
        self.model = rules.GradientBoard(levels.generate_level(PREVIEW_SEED, PREVIEW_DIFFICULTY))
        self.board_view.locked = True
        self.board_view.show(self.model)
        self.refresh()

    def seconds_played(self):
        return self.seconds_before + (time.time() - self.sitting_started)

    def swap_requested(self, first, second):
        """Called by the board: make one swap, then record and save, all now."""
        if self.preview or self.model is None or not self.settings_panel.hidden:
            return False
        if self.model.is_solved() or not self.model.swap(first, second):
            return False
        if self.model.is_solved():
            self.finish_level()
        else:
            self.save_game()
        self.refresh()
        return True

    def finish_level(self):
        self.solve_seconds = self.seconds_played()
        self.record_solve()
        discard(SAVE_PATH)

    def hint_tapped(self, sender):
        if self.model is None or self.model.is_solved():
            return
        hint = self.model.hint()
        if hint is not None and self.board_view.swap_cells(*hint):
            self.hints_used += 1
            self.save_game()
            self.refresh()

    def new_tapped(self, sender):
        self.new_level()

    # --- labels ------------------------------------------------------------------

    def refresh(self):
        model = self.model
        self.set_subtitle(describe(self.mode, model.level))
        self.new_button.title = "Replay" if self.mode == "daily" else "New level"
        hints = "" if not self.hints_used else " · %d hint%s" % (
            self.hints_used, "" if self.hints_used == 1 else "s")

        if model.is_solved():
            self.status_label.text = "Solved in %d · Par %d" % (model.moves, model.par)
            seconds = self.solve_seconds or 0
            self.message_label.text = "%s · %s%s" % (
                format_time(seconds), against_par(model.moves, model.par), hints)
            self.message_label.text_color = SUCCESS
            return

        self.status_label.text = "Moves %d · Par %d" % (model.moves, model.par)
        self.message_label.text = self.best_line() or PLAY_MESSAGE
        self.message_label.text_color = MUTED

    def best_line(self):
        """'Best: par +2 · 1:05' for this mode, or today's Daily result."""
        if self.preview:
            return None
        if self.mode == "daily":
            today = self.records["daily"].get(datetime.date.today().isoformat())
            if today:
                return "Done today: %s · %s" % (
                    against_par(today["moves"], today["par"]), format_time(today["seconds"]))
            return None
        best = self.records["modes"].get(self.mode)
        if not best or "best_over_par" not in best:
            return None
        over = best["best_over_par"]
        par_text = "on par" if over <= 0 else "par +%d" % over
        return "Best: %s · %s" % (par_text, format_time(best.get("fastest", 0)))

    # --- saving ----------------------------------------------------------------------

    def record_solve(self):
        if self.preview:
            return
        moves, par, seconds = self.model.moves, self.model.par, self.solve_seconds
        entry = self.records["modes"].setdefault(self.mode, {})
        entry["solved"] = int(entry.get("solved", 0)) + 1
        over = moves - par
        if "best_over_par" not in entry or over < entry["best_over_par"]:
            entry["best_over_par"] = over
        if "fastest" not in entry or seconds < entry["fastest"]:
            entry["fastest"] = round(seconds, 1)
        if self.mode == "daily":
            key = datetime.date.today().isoformat()
            previous = self.records["daily"].get(key)
            if previous is None or moves < previous.get("moves", moves + 1):
                self.records["daily"][key] = {
                    "moves": moves, "par": par, "seconds": round(seconds, 1)}
        write_json(RECORDS_PATH, self.records)

    def save_game(self):
        """Save the level in progress now. A solved level discards the save."""
        if self.preview:
            return
        if self.model.is_solved():
            discard(SAVE_PATH)
            return
        write_json(SAVE_PATH, {
            "version": SAVE_VERSION,
            "mode": self.mode,
            "board": self.model.to_dict(),
            "seconds": round(self.seconds_played(), 1),
            "hints": self.hints_used,
        })

    def resume_saved_game(self):
        """Show the saved level if it fits the current mode (and day). True when resumed."""
        data = read_json(SAVE_PATH)
        if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
            return False
        mode = data.get("mode")
        if mode != self.settings["mode"]:
            return False
        model = rules.GradientBoard.from_dict(data.get("board") or {})
        if model is None or model.is_solved():
            return False
        if mode == "daily" and model.level.seed != daily_seed():
            return False
        try:
            seconds = float(data.get("seconds", 0))
            hints = int(data.get("hints", 0))
        except (TypeError, ValueError):
            seconds, hints = 0.0, 0
        self.mode = mode
        self.model = model
        self.seconds_before = seconds
        self.sitting_started = time.time()
        self.solve_seconds = None
        self.hints_used = hints
        self.board_view.show(model)
        self.refresh()
        return True

    # --- settings ----------------------------------------------------------------------

    def apply_settings(self, draft, force_new_level=False):
        """Adopt the drafted mode and save it; a change of mode deals a new level."""
        changed = draft["mode"] != self.settings["mode"]
        self.settings = dict(draft)
        if not self.preview:
            write_json(SETTINGS_PATH, self.settings)
        if changed or force_new_level:
            self.new_level()
        return True
