"""Multiple Merge game screen: mode top area, board, buttons, settings.

Lives under the Maths Games shell, which draws the shared header. This view
uses the header contract from gamecore/game.py: open_settings() puts a gear
in the header, and header_subtitle names the current mode.

Two modes share one screen and one board view:

    Classic   find as many multiples as you can on one board (classic.py)
    Target    make one target number, board after board (target_mode.py)

Each mode has a small controller that owns its round and decides what the
top area, status line, subtitle and action button show. The screen owns
layout, the shared buttons, hints and saved settings. The board view owns
tiles, taps and the merge animation, and reports each committed move back
through on_move_committed.

Hints (a setting, off by default): tapping a target asks the solver for the
shortest route from the current board. The first tap arms the route's first
move (tile plus operation); tapping again plays it. Each tap re-plans, so
undo and the player's own moves never confuse it.
Always-visible operation keys (a setting, off by default): every tile shows
its four operation quadrants until a move is armed, so one tap on a quadrant
picks the tile and its operation together.

UI stability (see JACK_BOOT): every change happens synchronously inside the
tap that caused it, views are created once and only shown, hidden or
re-labelled, and settings are saved immediately.
"""

import json
import os
import time

import ui

from style import theme

from . import classic
from . import target_mode
from tilegame.board_state import format_value
from tilegame.records import RecordBook, format_duration, record_key
from tilegame.ui import MultipleMergeBoardView
from tilegame.widgets import (
    ChoiceRow,
    TargetBanner,
    draw_centred_text,
    make_button,
    make_label,
)


# --- colours, from the shared theme -----------------------------------------

BACKGROUND = theme.color("background")
TEXT = theme.color("text")
MUTED = theme.color("muted")
BUTTON_COLOR = theme.color("button")
ACCENT = theme.color("tile")                 # the main action

CHIP_UNREACHABLE = theme.color("chip_disabled")
CHIP_UNREACHABLE_TEXT = theme.color("chip_disabled_text")
CHIP_OPEN = theme.color("button")            # makeable, not found yet
CHIP_FOUND = theme.color("success")          # found, or target mode solved
PLAYER_COLORS = (theme.color("player_one"), theme.color("player_two"))

# --- editable layout, in points ---------------------------------------------

TOP_GAP = 8           # space below the shell's header
TOP_AREA_HEIGHT = 96  # classic rail (two rows) or target banner
PLAYER_ROW_HEIGHT = 40  # two-player name buttons above the board

# --- modes and their labels -------------------------------------------------

MODES = ("classic", "target")
MODE_LABELS = ("Classic", "Target")
DIFFICULTY_LABELS = ("Easy", "Medium", "Hard", "Tricky")  # target_mode.DIFFICULTIES
BOARD_STYLE_LABELS = ("Mixed", "Same", "3 + 1")       # target_mode.BOARD_STYLES

# Classic two-player: tap your name, then merge; the target is yours.
PLAYER_COUNTS = (1, 2)
PLAYER_COUNT_LABELS = ("Solo", "2 players")
PLAYER_NAMES = ("Player 1", "Player 2")


# --- saved settings ---------------------------------------------------------

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(GAME_DIR, "settings.json")
RECORDS_PATH = os.path.join(GAME_DIR, "records.json")

DEFAULT_SETTINGS = {
    "mode": "classic",
    "multiple": classic.DEFAULT_MULTIPLE,
    "hints": False,
    "always_ops": False,
    "difficulty": target_mode.DEFAULT_DIFFICULTY,
    "board_style": target_mode.DEFAULT_BOARD_STYLE,
    "players": 1,
}

# On/off settings that change how the board looks or helps, never the deal:
# changing one keeps the board in play.
DISPLAY_ONLY_SETTINGS = ("hints", "always_ops")

VALID_CHOICES = {
    "mode": MODES,
    "multiple": classic.MULTIPLE_CHOICES,
    "difficulty": target_mode.DIFFICULTIES,
    "board_style": target_mode.BOARD_STYLES,
    "players": PLAYER_COUNTS,
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

    for key, choices in VALID_CHOICES.items():
        if saved.get(key) in choices:
            settings[key] = saved[key]

    for key in DISPLAY_ONLY_SETTINGS:
        if isinstance(saved.get(key), bool):
            settings[key] = saved[key]

    return settings


def save_settings(settings):
    """Save settings now. A failed save is reported but never crashes play."""
    try:
        with open(SETTINGS_PATH, "w") as handle:
            json.dump(settings, handle)
    except OSError as error:
        print("Multiple Merge: could not save settings: {}".format(error))


# --- small view helpers -----------------------------------------------------

# make_label, make_button, ChoiceRow and draw_centred_text live in
# tilegame/widgets.py and are imported above.


# --- classic: target rail ---------------------------------------------------

class TargetRail(ui.View):
    """Classic mode's target chips in rows of five, drawn in one pass.

    A tap on a chip calls on_target_tapped(target), set by the screen.
    """

    CHIPS_PER_ROW = 5
    CHIP_GAP = 8
    ROW_GAP = 8
    CHIP_RADIUS = 12

    def __init__(self):
        super().__init__()
        self.background_color = BACKGROUND
        self.round = None
        self.on_target_tapped = None

    def show_round(self, round_):
        self.round = round_
        self.set_needs_display()

    def layout(self):
        self.set_needs_display()

    def chip_frames(self):
        """One frame per target; a short last row is centred."""
        if self.round is None:
            return []

        count = len(self.round.targets)
        per_row = self.CHIPS_PER_ROW
        rows = (count + per_row - 1) // per_row

        width = (self.width - self.CHIP_GAP * (per_row - 1)) / per_row
        height = (self.height - self.ROW_GAP * (rows - 1)) / rows

        frames = []

        for index in range(count):
            row, col = divmod(index, per_row)
            in_row = min(per_row, count - row * per_row)
            row_width = in_row * width + (in_row - 1) * self.CHIP_GAP
            left = (self.width - row_width) / 2

            frames.append((
                left + col * (width + self.CHIP_GAP),
                row * (height + self.ROW_GAP),
                width,
                height,
            ))

        return frames

    @staticmethod
    @staticmethod
    def _colours_for(target, round_):
        if target in round_.found:
            player = round_.found_by.get(target)
            if player is None:
                return CHIP_FOUND, BACKGROUND
            return PLAYER_COLORS[player], BACKGROUND
        if target in round_.reachable:
            return CHIP_OPEN, TEXT
        return CHIP_UNREACHABLE, CHIP_UNREACHABLE_TEXT

    def draw(self):
        round_ = self.round

        if round_ is None or self.width <= 1:
            return

        frames = self.chip_frames()
        targets = round_.targets

        # One font size for all chips, sized so the longest number fits.
        _, _, width, height = frames[0]
        longest = max(2, max(len(str(target)) for target in targets))
        size = max(12, min(26, height * 0.55, width * 1.4 / longest))
        font = ("AvenirNext-Bold", size)

        for (x, y, w, h), target in zip(frames, targets):
            fill, text_color = self._colours_for(target, round_)
            ui.set_color(fill)
            ui.Path.rounded_rect(x, y, w, h, self.CHIP_RADIUS).fill()
            draw_centred_text(str(target), font, text_color, x, y, w, h)

    def touch_ended(self, touch):
        if self.round is None or self.on_target_tapped is None:
            return

        px, py = touch.location

        for (x, y, w, h), target in zip(self.chip_frames(), self.round.targets):
            if x <= px <= x + w and y <= py <= y + h:
                self.on_target_tapped(target)
                return


# --- target mode: banner ----------------------------------------------------

# TargetBanner lives in tilegame/widgets.py and is imported above.


# --- mode controllers -------------------------------------------------------

class ClassicController:
    """Classic Multiples: find as many multiples as possible on one board."""

    def __init__(self, screen):
        self.screen = screen
        self.round = None
        self.started = None   # when this board was dealt
        self.result = None    # RunResult once every makeable target is found
        self.active_player = 0   # two-player: whose merges count, sticky

    @property
    def two_players(self):
        return self.screen.settings.get("players") == 2

    def scores(self):
        """Targets found by each player on this board."""
        scores = [0] * len(PLAYER_NAMES)
        for player in self.round.found_by.values():
            scores[player] += 1
        return scores    # RunResult once every makeable target is found

    def new_round(self):
        return classic.deal_round(self.screen.settings["multiple"])

    def begin(self, round_):
        self.round = round_
        self.started = time.monotonic()
        self.result = None

    def record_key(self):
        """Times compare only for the same multiple and number of targets."""
        round_ = self.round
        return record_key(
            "multiple_merge", "classic",
            "x{}".format(round_.multiple),
            "targets-{}".format(len(round_.reachable)),
        )

    def move_committed(self, result):
        round_ = self.round
        player = self.active_player if self.two_players else None
        newly_found = round_.record(result.value, player)

        # Solo only: the clock stops at the tap that finds the last target.
        if (newly_found and round_.is_complete() and self.result is None
                and not self.two_players):
            seconds = time.monotonic() - self.started
            self.result = self.screen.records.add(self.record_key(), seconds)

    def hint_blocker(self, target):
        """A reason no hint can be given for target, or None."""
        if target not in self.round.reachable:
            return "{} can't be made on this board".format(target)
        return None

    def is_done(self, target):
        return target in self.round.found

    def refresh(self):
        screen = self.screen
        round_ = self.round
        makeable = len(round_.reachable)

        screen.rail.show_round(round_)

        if self.two_players:
            screen.set_subtitle("2 players · multiples of {}".format(round_.multiple))
            scores = self.scores()
            screen.player_row.set_labels([
                "{} · {}".format(name, score)
                for name, score in zip(PLAYER_NAMES, scores)
            ])
            screen.player_row.selected_index = self.active_player
            screen.status_label.text = self.describe_two_players(scores, makeable)
        else:
            screen.set_subtitle("Classic · multiples of {}".format(round_.multiple))
            if round_.is_complete():
                screen.status_label.text = self.describe_result(makeable)
            else:
                text = "{} of {} found · {}".format(
                    len(round_.found), makeable,
                    format_duration(time.monotonic() - self.started),
                )
                best = screen.records.best(self.record_key())
                if best is not None:
                    text += " · best {}".format(format_duration(best))
                screen.status_label.text = text

        screen.show_action("New board", visible=round_.is_complete(),
                           primary=True)

    def describe_two_players(self, scores, makeable):
        if not self.round.is_complete():
            return "{} of {} found · tap your name, then merge".format(
                len(self.round.found), makeable)

        first, second = scores
        if first == second:
            return "Draw {}–{}".format(first, second)

        winner = 0 if first > second else 1
        return "{} wins {}–{}".format(
            PLAYER_NAMES[winner], max(scores), min(scores))

    def describe_result(self, makeable):
        result = self.result

        if result is None:      # completed without a timed finish
            return "All {} found!".format(makeable)

        time_text = format_duration(result.seconds)

        if result.previous_best is None:
            return "All {} found in {} · first time".format(makeable, time_text)
        if result.is_best:
            return "All {} found in {} · New best! Was {}".format(
                makeable, time_text, format_duration(result.previous_best))
        return "All {} found in {} · Best {}".format(
            makeable, time_text, format_duration(result.previous_best))

    def action_tapped(self):
        self.screen.start_new_board()


class TargetController:
    """Target mode: make one number, then the next board, keeping score."""

    def __init__(self, screen):
        self.screen = screen
        self.round = None
        self.session = target_mode.TargetSession()
        self.started = None
        self.solve_seconds = None
        self.last_points = 0
        self.note = None   # e.g. what the last skip scored

    def new_round(self):
        settings = self.screen.settings
        return target_mode.deal_target_round(
            settings["difficulty"], settings["board_style"]
        )

    def begin(self, round_):
        self.round = round_
        self.started = time.monotonic()
        self.solve_seconds = None
        self.last_points = 0

    def move_committed(self, result):
        self.note = None

        # A board scores once: replaying the solve after Undo changes nothing.
        if not self.round.solved and self.round.record(result.value):
            self.solve_seconds = time.monotonic() - self.started
            self.last_points = self.session.finish(self.round)

    def hint_blocker(self, target):
        """Never blocks: after a solve, Undo then hints replay the route."""
        return None

    def is_done(self, target):
        return self.round.solved

    def refresh(self):
        screen = self.screen
        round_ = self.round
        session = self.session

        screen.set_subtitle("Target · {} · {}".format(
            DIFFICULTY_LABELS[target_mode.DIFFICULTIES.index(round_.difficulty)],
            BOARD_STYLE_LABELS[target_mode.BOARD_STYLES.index(round_.style)],
        ))
        screen.banner.show(round_.target, session.score, session.streak,
                           round_.solved)

        if round_.solved:
            text = "Solved in {}s · +{}".format(
                int(round(self.solve_seconds)), self.last_points
            )
        elif round_.best is not None:
            text = "Closest so far: {} ({} away)".format(
                format_value(round_.best),
                format_value(round_.best_distance()),
            )
        elif self.note:
            text = self.note
        else:
            text = "Make {} from the board".format(round_.target)

        screen.status_label.text = text

        if round_.solved:
            screen.show_action("Next board", visible=True, primary=True)
        else:
            screen.show_action("Skip", visible=True, primary=False)

    def action_tapped(self):
        """Next board after a solve; otherwise skip, scoring the closest."""
        if self.screen.board_view.resolving:
            return

        round_ = self.round

        if round_.solved:
            note = None
        else:
            points = self.session.finish(round_)
            note = "Skipped {} · +{}".format(round_.target, points)

        previous_note = self.note
        self.note = note

        if not self.screen.start_new_board():
            self.note = previous_note


# --- settings panel ---------------------------------------------------------

class SettingsPanel(ui.View):
    """Overlay editing a draft of the settings, covering the game area.

    Done adopts the draft (dealing a new board only if something other than
    hints changed). New board adopts it and always deals.
    """

    SECTION_HEIGHT = 230   # the taller of the two sections: Classic
    TOP = 16

    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.background_color = BACKGROUND
        self.hidden = True
        self.draft = dict(screen.settings)

        self.title_label = make_label(
            "Settings", ("AvenirNext-Bold", 24), TEXT
        )
        self.mode_control = ChoiceRow(MODE_LABELS, self.mode_changed)

        # Classic section.
        self.multiple_caption = make_label(
            "Targets are multiples of", ("AvenirNext-Medium", 15), MUTED
        )
        self.minus_button = make_button("−", self.step_down, font_size=28)
        self.multiple_label = make_label("", ("AvenirNext-Bold", 40), TEXT)
        self.plus_button = make_button("+", self.step_up, font_size=28)
        self.preview_label = make_label("", ("AvenirNext-Medium", 14), MUTED)
        self.players_caption = make_label(
            "Players", ("AvenirNext-Medium", 15), MUTED
        )
        self.players_control = ChoiceRow(
            PLAYER_COUNT_LABELS, self.players_changed
        )

        # Target section.
        self.difficulty_caption = make_label(
            "Difficulty", ("AvenirNext-Medium", 15), MUTED
        )
        self.difficulty_control = ChoiceRow(
            DIFFICULTY_LABELS, self.difficulty_changed
        )
        self.style_caption = make_label(
            "Board", ("AvenirNext-Medium", 15), MUTED
        )
        self.style_control = ChoiceRow(BOARD_STYLE_LABELS, self.style_changed)

        # Shared.
        self.hints_label = make_label(
            "Hints: tap a target to see the next move",
            ("AvenirNext-Medium", 15),
            TEXT,
            alignment=ui.ALIGN_LEFT,
        )
        self.hints_label.number_of_lines = 2
        self.hints_switch = ui.Switch()
        self.hints_switch.action = self.hints_changed

        self.ops_label = make_label(
            "Always show operation keys",
            ("AvenirNext-Medium", 15),
            TEXT,
            alignment=ui.ALIGN_LEFT,
        )
        self.ops_switch = ui.Switch()
        self.ops_switch.action = self.ops_changed

        self.new_board_button = make_button(
            "New board", self.new_board_tapped,
            background=ACCENT, title_color=BACKGROUND,
        )
        self.done_button = make_button("Done", self.done_tapped)

        self.classic_views = (
            self.multiple_caption,
            self.minus_button,
            self.multiple_label,
            self.plus_button,
            self.preview_label,
            self.players_caption,
            self.players_control,
        )
        self.target_views = (
            self.difficulty_caption,
            self.difficulty_control,
            self.style_caption,
            self.style_control,
        )

        for view in (
            (self.title_label, self.mode_control)
            + self.classic_views
            + self.target_views
            + (self.hints_label, self.hints_switch,
               self.ops_label, self.ops_switch,
               self.new_board_button, self.done_button)
        ):
            self.add_subview(view)

    def layout(self):
        column = min(320, self.width - 48)
        left = (self.width - column) / 2
        step = 64

        y = self.TOP
        self.title_label.frame = (left, y, column, 36)
        y += 52
        self.mode_control.frame = (left, y, column, 36)
        y += 56
        section_top = y

        # Classic section.
        self.multiple_caption.frame = (left, y, column, 22)
        y += 30
        self.minus_button.frame = (left, y, step, step)
        self.multiple_label.frame = (left + step, y, column - 2 * step, step)
        self.plus_button.frame = (left + column - step, y, step, step)
        y += step + 8
        self.preview_label.frame = (left, y, column, 22)
        y += 34
        self.players_caption.frame = (left, y, column, 22)
        y += 28
        self.players_control.frame = (left, y, column, 36)

        # Target section, in the same space.
        y = section_top
        self.difficulty_caption.frame = (left, y, column, 22)
        y += 28
        self.difficulty_control.frame = (left, y, column, 36)
        y += 48
        self.style_caption.frame = (left, y, column, 22)
        y += 28
        self.style_control.frame = (left, y, column, 36)

        # Shared.
        y = section_top + self.SECTION_HEIGHT + 12
        switch_width = 51
        self.hints_label.frame = (left, y, column - switch_width - 12, 44)
        self.hints_switch.frame = (
            left + column - switch_width, y + 6, switch_width, 31
        )
        y += 56
        self.ops_label.frame = (left, y, column - switch_width - 12, 44)
        self.ops_switch.frame = (
            left + column - switch_width, y + 6, switch_width, 31
        )
        y += 68
        self.new_board_button.frame = (left, y, column, 52)
        y += 68
        self.done_button.frame = (left, y, column, 52)

    def open(self):
        draft = dict(self.screen.settings)
        self.draft = draft

        self.mode_control.selected_index = MODES.index(draft["mode"])
        self.difficulty_control.selected_index = (
            target_mode.DIFFICULTIES.index(draft["difficulty"])
        )
        self.style_control.selected_index = (
            target_mode.BOARD_STYLES.index(draft["board_style"])
        )
        self.players_control.selected_index = PLAYER_COUNTS.index(
            draft["players"]
        )
        self.hints_switch.value = bool(draft["hints"])
        self.ops_switch.value = bool(draft["always_ops"])

        self._show_multiple()
        self._show_section()
        self.hidden = False
        self.bring_to_front()

    def _show_section(self):
        classic_mode = self.draft["mode"] == "classic"

        for view in self.classic_views:
            view.hidden = not classic_mode
        for view in self.target_views:
            view.hidden = classic_mode

    def _show_multiple(self):
        choices = classic.MULTIPLE_CHOICES
        multiple = self.draft["multiple"]
        index = choices.index(multiple)
        targets = classic.targets_for(multiple)

        self.multiple_label.text = str(multiple)
        self.preview_label.text = "{}, {}, {} … {}".format(
            targets[0], targets[1], targets[2], targets[-1]
        )
        self.minus_button.enabled = index > 0
        self.plus_button.enabled = index < len(choices) - 1

    def _step(self, direction):
        choices = classic.MULTIPLE_CHOICES
        index = choices.index(self.draft["multiple"]) + direction

        if 0 <= index < len(choices):
            self.draft["multiple"] = choices[index]
            self._show_multiple()

    def step_down(self, sender):
        self._step(-1)

    def step_up(self, sender):
        self._step(1)

    def mode_changed(self, sender):
        self.draft["mode"] = MODES[sender.selected_index]
        self._show_section()

    def difficulty_changed(self, sender):
        self.draft["difficulty"] = target_mode.DIFFICULTIES[sender.selected_index]

    def style_changed(self, sender):
        self.draft["board_style"] = target_mode.BOARD_STYLES[sender.selected_index]

    def players_changed(self, sender):
        self.draft["players"] = PLAYER_COUNTS[sender.selected_index]

    def hints_changed(self, sender):
        self.draft["hints"] = bool(sender.value)

    def ops_changed(self, sender):
        self.draft["always_ops"] = bool(sender.value)

    def new_board_tapped(self, sender):
        if self.screen.apply_settings(self.draft, force_new_board=True):
            self.hidden = True

    def done_tapped(self, sender):
        if self.screen.apply_settings(self.draft):
            self.hidden = True


# --- the screen -------------------------------------------------------------

class GameScreen(ui.View):
    """Multiple Merge under the shell header: one board, two modes."""

    SIDE_MARGIN = 16
    BOTTOM_BAR = 112      # leaves room above the home indicator

    def __init__(self, board, **kwargs):
        super().__init__(**kwargs)
        self.background_color = BACKGROUND
        self.settings = load_settings()
        self.records = RecordBook(RECORDS_PATH)

        # Header contract (gamecore/game.py). The shell replaces the callback.
        self.header_subtitle = ""
        self.on_header_changed = None

        self.controllers = {
            "classic": ClassicController(self),
            "target": TargetController(self),
        }

        # Top area: one of these shows, depending on the mode.
        self.rail = TargetRail()
        self.rail.on_target_tapped = self.target_tapped
        self.banner = TargetBanner()
        self.banner.on_target_tapped = self.target_tapped

        self.status_label = make_label("", ("AvenirNext-Medium", 15), MUTED)

        # Two-player Classic: tap your name before merging. Sticky.
        self.player_row = ChoiceRow(
            PLAYER_NAMES, self.player_changed, selected_colors=PLAYER_COLORS
        )
        self.player_row.hidden = True

        self.board_view = MultipleMergeBoardView(board=board)
        self.board_view.background_color = BACKGROUND
        self.board_view.on_move_committed = self.move_committed
        self.board_view.always_show_operations = self.settings["always_ops"]

        self.reset_button = make_button("Reset board", self.reset_tapped)
        self.action_button = make_button("", self.action_tapped)
        self.action_button.hidden = True

        self.settings_panel = SettingsPanel(self)

        for view in (
            self.rail,
            self.banner,
            self.status_label,
            self.player_row,
            self.board_view,
            self.reset_button,
            self.action_button,
            self.settings_panel,   # last, so it covers everything
        ):
            self.add_subview(view)

        self.start_new_board()

    @property
    def controller(self):
        return self.controllers[self.settings["mode"]]

    # --- header contract -----------------------------------------------------

    def open_settings(self):
        """Called by the shell's gear."""
        if self.board_view.resolving:
            return
        self.settings_panel.open()

    def set_subtitle(self, text):
        if text == self.header_subtitle:
            return
        self.header_subtitle = text
        if callable(self.on_header_changed):
            self.on_header_changed()

    # --- layout --------------------------------------------------------------

    def shows_player_row(self):
        return (self.settings["mode"] == "classic"
                and self.settings["players"] == 2)

    def layout(self):
        width = self.width
        height = self.height
        margin = self.SIDE_MARGIN

        top = TOP_GAP
        top_area = (margin, top, width - 2 * margin, TOP_AREA_HEIGHT)
        self.rail.frame = top_area
        self.banner.frame = top_area

        status_top = top + TOP_AREA_HEIGHT + 8
        self.status_label.frame = (margin, status_top, width - 2 * margin, 24)

        board_top = status_top + 30

        # Two-player Classic puts the name buttons between status and board.
        self.player_row.hidden = not self.shows_player_row()
        if not self.player_row.hidden:
            self.player_row.frame = (
                margin, board_top, width - 2 * margin, PLAYER_ROW_HEIGHT
            )
            board_top += PLAYER_ROW_HEIGHT + 8

        self.board_view.frame = (
            0,
            board_top,
            width,
            max(0, height - board_top - self.BOTTOM_BAR),
        )

        self._layout_bottom_buttons()
        self.settings_panel.frame = self.bounds

    def _layout_bottom_buttons(self):
        """Centre Reset alone; place it beside the action button when shown."""
        width = self.width
        margin = self.SIDE_MARGIN
        button_width = min(160, (width - 3 * margin) / 2)
        y = self.height - self.BOTTOM_BAR + 16

        if self.action_button.hidden:
            self.reset_button.frame = (
                (width - button_width) / 2, y, button_width, 48
            )
        else:
            self.reset_button.frame = (
                width / 2 - button_width - 6, y, button_width, 48
            )
            self.action_button.frame = (
                width / 2 + 6, y, button_width, 48
            )

    def show_action(self, title, visible, primary):
        """Set the right-hand button; primary uses the accent colour."""
        self.action_button.title = title
        self.action_button.hidden = not visible
        self.action_button.background_color = ACCENT if primary else BUTTON_COLOR
        self.action_button.tint_color = BACKGROUND if primary else TEXT

    # --- game flow -----------------------------------------------------------

    def start_new_board(self):
        """Deal a board for the current mode and settings, and show it.

        Returns False, changing nothing, while a merge is animating.
        """
        controller = self.controller
        round_ = controller.new_round()

        if not self.board_view.load_board_state(round_.starting_board()):
            return False

        controller.begin(round_)
        self.refresh()
        return True

    def refresh(self):
        classic_mode = self.settings["mode"] == "classic"
        self.rail.hidden = not classic_mode
        self.banner.hidden = classic_mode

        self.controller.refresh()
        self._layout_bottom_buttons()

    def move_committed(self, result):
        """Called by the board view for every committed move."""
        self.controller.move_committed(result)
        self.refresh()

    def player_changed(self, sender):
        """A player taps their name: later merges count for them."""
        self.controllers["classic"].active_player = sender.selected_index

    def apply_settings(self, draft, force_new_board=False):
        """Adopt draft settings and save them.

        Deals a new board if anything other than hints changed, or when
        forced. Lays out again when the player row appears or goes.
        Returns False, changing nothing, while a merge is animating.
        """
        previous = self.settings
        needs_board = force_new_board or any(
            draft[key] != previous[key]
            for key in draft if key not in DISPLAY_ONLY_SETTINGS
        )

        self.settings = dict(draft)

        if needs_board and not self.start_new_board():
            self.settings = previous
            return False

        self.board_view.always_show_operations = self.settings["always_ops"]
        self.board_view.apply_move_visuals()

        if self.settings != previous:
            save_settings(self.settings)

        if any(draft[key] != previous[key] for key in ("mode", "players")):
            self.layout()

        return True

    # --- hints ---------------------------------------------------------------

    def target_tapped(self, target):
        """Hint the next move towards target; does nothing with hints off."""
        controller = self.controller

        if not self.settings["hints"] or controller.round is None:
            return

        blocked = controller.hint_blocker(target)
        if blocked is not None:
            self.status_label.text = blocked
            return

        route = classic.solution_moves(self.board_view.board_state, target)

        if route is None:
            self.status_label.text = (
                "{} can't be made from here · Reset or undo".format(target)
            )
            return

        outcome = self.board_view.hint_step(*route[0])

        if outcome == "shown":
            moves = len(route)
            self.status_label.text = "Hint for {}: {} move{} to go".format(
                target, moves, "" if moves == 1 else "s"
            )
        elif outcome == "played" and not controller.is_done(target):
            self.status_label.text = "Tap {} again for the next step".format(
                target
            )

    # --- buttons -------------------------------------------------------------

    def reset_tapped(self, sender):
        """Back to the starting numbers; progress on this board is kept."""
        round_ = self.controller.round
        if self.board_view.load_board_state(round_.starting_board()):
            self.refresh()

    def action_tapped(self, sender):
        self.controller.action_tapped()