"""Countdown game screen: target banner, 2 × 3 board, Reset, Skip, settings.

Lives under the Maths Games shell and uses the header contract from
gamecore/game.py: open_settings() puts a gear in the header, and
header_subtitle describes the deal ("1 big · 5 small").

Play: any two tiles merge with + − × ÷; results must be positive whole
numbers (the board's rules enforce this, and only legal destinations light
up). Play is a timed run of RUN_BOARDS boards: the banner shows the board
number and the run time, which updates on every move rather than ticking.
Skip moves on and adds the skip penalty from Settings. A finished run is
stored in records.json under its rules (difficulty, big numbers, penalty),
and a new run shows the best time for those rules.

Hints (a setting, off by default): tap the target. The first tap shows the
next step of a shortest route from the current board, armed on the tiles;
tapping again plays it.

UI stability (see JACK_BOOT): every change happens synchronously inside the
tap that caused it, views are created once and only shown, hidden or
re-labelled, and settings are saved immediately.
"""

import json
import os
import time

import ui

from style import theme
from tilegame.board_state import OPERATION_SYMBOLS, format_value
from tilegame.records import RecordBook, format_duration, record_key
from tilegame.timed_run import TimedRun
from tilegame.ui import MultipleMergeBoardView
from tilegame.widgets import (
    ChoiceRow,
    TargetBanner,
    draw_centred_text,
    make_button,
    make_label,
)

from games.countdown import rules


# --- colours, from the shared theme -----------------------------------------

BACKGROUND = theme.color("background")
TEXT = theme.color("text")
MUTED = theme.color("muted")
BUTTON_COLOR = theme.color("button")
ACCENT = theme.color("tile")

# --- editable layout, in points ---------------------------------------------

TOP_GAP = 8
TOP_AREA_HEIGHT = 96

# The setting adds "random" (Mix) to the real counts; each board then
# deals a random count and the subtitle shows the one dealt.
BIG_COUNT_SETTINGS = rules.BIG_COUNT_CHOICES + (rules.RANDOM_BIG_COUNT,)
BIG_COUNT_LABELS = (
    tuple(str(count) for count in rules.BIG_COUNT_CHOICES) + ("Mix",)
)
DIFFICULTY_LABELS = ("Normal", "5 numbers", "All 6")  # rules.DIFFICULTY_CHOICES

# --- timed runs -------------------------------------------------------------

RUN_BOARDS = 5                        # boards in one timed run
SKIP_PENALTY_CHOICES = (30, 60, 90)   # seconds a skip adds
SKIP_PENALTY_LABELS = ("+30s", "+60s", "+90s")
DEFAULT_SKIP_PENALTY = 60

# Changing any of these starts a new run, since times no longer compare.
RUN_RULE_KEYS = ("big_count", "difficulty", "skip_penalty")


# --- saved settings ---------------------------------------------------------

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(GAME_DIR, "settings.json")
RECORDS_PATH = os.path.join(GAME_DIR, "records.json")

DEFAULT_SETTINGS = {
    "big_count": rules.DEFAULT_BIG_COUNT,
    "difficulty": rules.DEFAULT_DIFFICULTY,
    "skip_penalty": DEFAULT_SKIP_PENALTY,
    "hints": False,
    "show_factors": False,
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

    if saved.get("big_count") in BIG_COUNT_SETTINGS:
        settings["big_count"] = saved["big_count"]

    if saved.get("difficulty") in rules.DIFFICULTY_CHOICES:
        settings["difficulty"] = saved["difficulty"]

    if saved.get("skip_penalty") in SKIP_PENALTY_CHOICES:
        settings["skip_penalty"] = saved["skip_penalty"]

    for key in ("hints", "show_factors"):
        if isinstance(saved.get(key), bool):
            settings[key] = saved[key]

    return settings


def save_settings(settings):
    """Save settings now. A failed save is reported but never crashes play."""
    try:
        with open(SETTINGS_PATH, "w") as handle:
            json.dump(settings, handle)
    except OSError as error:
        print("Countdown: could not save settings: {}".format(error))


def describe_step(step):
    left, operation, right, value = step
    return "{} {} {} = {}".format(
        left, OPERATION_SYMBOLS[operation], right, value
    )


# --- factors card -----------------------------------------------------------

class FactorsCard(ui.View):
    """The target's prime factorisation, revealed or hidden by a tap.

    Compact on purpose: the empty board below it stays free for double-tap
    undo. Drawn in one pass; on_toggle() is called on tap.
    """

    RADIUS = 16
    SURFACE = theme.color("surface")

    def __init__(self):
        super().__init__()
        self.background_color = BACKGROUND
        self.target = None
        self.revealed = False
        self.on_toggle = None

    def show(self, target, revealed):
        self.target = target
        self.revealed = revealed
        self.set_needs_display()

    def layout(self):
        self.set_needs_display()

    def draw(self):
        w, h = self.width, self.height

        if w <= 1 or h <= 1 or self.target is None:
            return

        ui.set_color(self.SURFACE)
        ui.Path.rounded_rect(0, 0, w, h, self.RADIUS).fill()

        draw_centred_text("FACTORS", ("AvenirNext-DemiBold", 12), MUTED,
                          0, 8, w, 14)

        if self.revealed:
            text = rules.describe_factors(self.target).split("\n")[0]
            draw_centred_text(text, ("AvenirNext-Bold", 20), ACCENT,
                              0, 22, w, h - 28)
        else:
            draw_centred_text("Tap to reveal", ("AvenirNext-Medium", 16), TEXT,
                              0, 22, w, h - 28)

    def touch_ended(self, touch):
        x, y = touch.location
        if 0 <= x <= self.width and 0 <= y <= self.height:
            if self.on_toggle is not None:
                self.on_toggle()


# --- settings panel ---------------------------------------------------------

class SettingsPanel(ui.View):
    """Overlay editing a draft of the settings, covering the game area.

    Done adopts the draft, starting a new run only if a run rule changed
    (RUN_RULE_KEYS). New board adopts it and always starts a new run.
    """

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
        self.big_caption = make_label(
            "Big numbers (25, 50, 75, 100)", ("AvenirNext-Medium", 15), MUTED
        )
        self.big_control = ChoiceRow(BIG_COUNT_LABELS, self.big_count_changed)

        self.difficulty_caption = make_label(
            "Difficulty: fewest numbers a solution needs",
            ("AvenirNext-Medium", 15), MUTED,
        )
        self.difficulty_control = ChoiceRow(
            DIFFICULTY_LABELS, self.difficulty_changed
        )

        self.penalty_caption = make_label(
            "Each skip adds to the run time", ("AvenirNext-Medium", 15), MUTED,
        )
        self.penalty_control = ChoiceRow(
            SKIP_PENALTY_LABELS, self.penalty_changed
        )

        self.hints_label = make_label(
            "Hints: tap the target to see the next step",
            ("AvenirNext-Medium", 15),
            TEXT,
            alignment=ui.ALIGN_LEFT,
        )
        self.hints_label.number_of_lines = 2
        self.hints_switch = ui.Switch()
        self.hints_switch.action = self.hints_changed

        self.new_board_button = make_button(
            "New run", self.new_board_tapped,
            background=ACCENT, title_color=BACKGROUND,
        )
        self.done_button = make_button("Done", self.done_tapped)

        for view in (
            self.title_label,
            self.big_caption,
            self.big_control,
            self.difficulty_caption,
            self.difficulty_control,
            self.penalty_caption,
            self.penalty_control,
            self.hints_label,
            self.hints_switch,
            self.new_board_button,
            self.done_button,
        ):
            self.add_subview(view)

    def layout(self):
        column = min(320, self.width - 48)
        left = (self.width - column) / 2

        y = self.TOP
        self.title_label.frame = (left, y, column, 36)
        y += 56
        self.big_caption.frame = (left, y, column, 22)
        y += 28
        self.big_control.frame = (left, y, column, 40)
        y += 56
        self.difficulty_caption.frame = (left, y, column, 22)
        y += 28
        self.difficulty_control.frame = (left, y, column, 40)
        y += 56
        self.penalty_caption.frame = (left, y, column, 22)
        y += 28
        self.penalty_control.frame = (left, y, column, 40)
        y += 64

        switch_width = 51
        self.hints_label.frame = (left, y, column - switch_width - 12, 44)
        self.hints_switch.frame = (
            left + column - switch_width, y + 6, switch_width, 31
        )
        y += 68
        self.new_board_button.frame = (left, y, column, 52)
        y += 68
        self.done_button.frame = (left, y, column, 52)

    def open(self):
        self.draft = dict(self.screen.settings)
        self.big_control.selected_index = BIG_COUNT_SETTINGS.index(
            self.draft["big_count"]
        )
        self.difficulty_control.selected_index = (
            rules.DIFFICULTY_CHOICES.index(self.draft["difficulty"])
        )
        self.penalty_control.selected_index = (
            SKIP_PENALTY_CHOICES.index(self.draft["skip_penalty"])
        )
        self.hints_switch.value = bool(self.draft["hints"])
        self.hidden = False
        self.bring_to_front()

    def big_count_changed(self, sender):
        self.draft["big_count"] = BIG_COUNT_SETTINGS[sender.selected_index]

    def difficulty_changed(self, sender):
        self.draft["difficulty"] = rules.DIFFICULTY_CHOICES[sender.selected_index]

    def penalty_changed(self, sender):
        self.draft["skip_penalty"] = SKIP_PENALTY_CHOICES[sender.selected_index]

    def hints_changed(self, sender):
        self.draft["hints"] = bool(sender.value)

    def new_board_tapped(self, sender):
        if self.screen.apply_settings(self.draft, force_new_board=True):
            self.hidden = True

    def done_tapped(self, sender):
        if self.screen.apply_settings(self.draft):
            self.hidden = True


# --- the screen -------------------------------------------------------------

class CountdownScreen(ui.View):
    """Countdown under the shell header: one target, board after board."""

    SIDE_MARGIN = 16
    BOTTOM_BAR = 112      # leaves room above the home indicator
    FACTORS_CARD_HEIGHT = 64   # compact, leaving empty board for undo

    def __init__(self, board, **kwargs):
        super().__init__(**kwargs)
        self.background_color = BACKGROUND
        self.settings = load_settings()
        self.records = RecordBook(RECORDS_PATH)

        # Header contract (gamecore/game.py). The shell replaces the callback.
        self.header_subtitle = ""
        self.on_header_changed = None

        self.run = None          # TimedRun for the current RUN_BOARDS boards
        self.run_key = None      # records key, fixed when the run starts
        self.run_result = None   # RunResult once the run is finished
        self.round = None
        self.started = None      # when this board was dealt
        self.solve_seconds = None
        self.note = None   # e.g. the best for these rules, or a skip's cost

        self.banner = TargetBanner()
        self.banner.on_target_tapped = self.target_tapped

        self.status_label = make_label("", ("AvenirNext-Medium", 15), MUTED)

        self.board_view = MultipleMergeBoardView(board=board)
        self.board_view.background_color = BACKGROUND
        self.board_view.on_move_committed = self.move_committed

        self.reset_button = make_button("Reset board", self.reset_tapped)
        self.action_button = make_button("Skip", self.action_tapped)

        # Factors of the target: a card that reveals and hides on tap.
        self.factors_card = FactorsCard()
        self.factors_card.on_toggle = self.factors_tapped

        self.settings_panel = SettingsPanel(self)

        for view in (
            self.banner,
            self.status_label,
            self.board_view,
            self.factors_card,
            self.reset_button,
            self.action_button,
            self.settings_panel,   # last, so it covers everything
        ):
            self.add_subview(view)

        self.start_new_run()

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

    def layout(self):
        width = self.width
        height = self.height
        margin = self.SIDE_MARGIN

        self.banner.frame = (margin, TOP_GAP, width - 2 * margin, TOP_AREA_HEIGHT)

        status_top = TOP_GAP + TOP_AREA_HEIGHT + 8
        self.status_label.frame = (margin, status_top, width - 2 * margin, 24)

        board_top = status_top + 30
        buttons_y = height - self.BOTTOM_BAR + 16

        # Where the tiles end (three columns make the board width-limited).
        board = self.board_view
        cols, rows = rules.BOARD_COLS, rules.BOARD_ROWS
        side = (
            width - 2 * board.BOARD_MARGIN - (cols - 1) * board.TILE_GAP
        ) / cols
        board_height = (
            rows * side + (rows - 1) * board.TILE_GAP + 2 * board.BOARD_MARGIN
        )

        # The board view runs down to the buttons, so the empty space below
        # the tiles is still board and double-tap undo works there.
        self.board_view.frame = (
            0, board_top, width, max(0, buttons_y - 12 - board_top)
        )

        # The factors card sits just under the tiles, on top of the board.
        card_y = min(
            board_top + board_height,
            buttons_y - 12 - self.FACTORS_CARD_HEIGHT,
        )
        self.factors_card.frame = (
            margin, card_y, width - 2 * margin, self.FACTORS_CARD_HEIGHT
        )

        button_width = min(160, (width - 3 * margin) / 2)
        row_left = (width - (2 * button_width + 12)) / 2
        self.reset_button.frame = (row_left, buttons_y, button_width, 48)
        self.action_button.frame = (
            row_left + button_width + 12, buttons_y, button_width, 48
        )

        self.settings_panel.frame = self.bounds

    def show_action(self, title, primary):
        """Set the right-hand button; primary uses the accent colour."""
        self.action_button.title = title
        self.action_button.background_color = ACCENT if primary else BUTTON_COLOR
        self.action_button.tint_color = BACKGROUND if primary else TEXT

    # --- game flow -----------------------------------------------------------

    def current_record_key(self):
        """The records key for the current settings' run rules."""
        settings = self.settings
        big = settings["big_count"]
        big_part = "mix" if big == rules.RANDOM_BIG_COUNT else "big-{}".format(big)
        return record_key(
            "countdown",
            "boards-{}".format(RUN_BOARDS),
            settings["difficulty"],
            big_part,
            "skip-{}".format(settings["skip_penalty"]),
        )

    def start_new_run(self):
        """Start a timed run on a fresh board, showing the best for its rules.

        Returns False, changing nothing, while a merge is animating.
        """
        previous = (self.run, self.run_key, self.run_result, self.note)

        self.run = TimedRun(RUN_BOARDS, self.settings["skip_penalty"])
        self.run_key = self.current_record_key()
        self.run_result = None

        best = self.records.best(self.run_key)
        self.note = (
            "Best for these rules: {}".format(format_duration(best))
            if best is not None else None
        )

        if not self.start_new_board():
            self.run, self.run_key, self.run_result, self.note = previous
            return False

        return True

    def finish_run(self):
        """Store the finished run's time. Called once, inside the final tap."""
        self.run_result = self.records.add(self.run_key, self.run.elapsed())

    def describe_result(self):
        result = self.run_result
        time_text = format_duration(result.seconds)

        if result.previous_best is None:
            return "Run {} · first time for these rules".format(time_text)
        if result.is_best:
            return "Run {} · New best! Was {}".format(
                time_text, format_duration(result.previous_best))
        return "Run {} · Best {}".format(
            time_text, format_duration(result.previous_best))

    def start_new_board(self):
        """Deal a board for the current settings and show it.

        Returns False, changing nothing, while a merge is animating.
        """
        round_ = rules.deal_round(
            self.settings["big_count"],
            difficulty=self.settings["difficulty"],
        )

        if not self.board_view.load_board_state(round_.starting_board()):
            return False

        self.round = round_
        self.started = time.monotonic()
        self.solve_seconds = None
        self.last_points = 0
        self.refresh()
        return True

    def refresh(self):
        round_ = self.round
        run = self.run
        big = round_.big_count

        self.set_subtitle("{} big · {} small".format(big, rules.TILE_COUNT - big))
        self.banner.show_stats(
            round_.target,
            ("BOARD", "{}/{}".format(run.board_number, run.board_count)),
            ("TIME", format_duration(run.elapsed())),
            round_.solved,
        )

        if run.is_finished:
            text = self.describe_result()
        elif round_.solved:
            text = "Solved in {}s".format(int(round(self.solve_seconds)))
        elif round_.best is not None:
            text = "Closest so far: {} ({} away)".format(
                format_value(round_.best),
                format_value(round_.best_distance()),
            )
        elif self.note:
            text = self.note
        else:
            text = "Make {} from the six numbers".format(round_.target)

        self.status_label.text = text

        if run.is_finished:
            self.show_action("New run", primary=True)
        elif round_.solved:
            self.show_action("Next board", primary=True)
        else:
            self.show_action("Skip", primary=False)

        self._show_factors()

    def move_committed(self, result):
        """Called by the board view for every committed move."""
        self.note = None

        if self.round.record(result.value) and not self.run.is_finished:
            self.solve_seconds = time.monotonic() - self.started
            if self.run.solve():
                self.finish_run()

        self.refresh()

    def apply_settings(self, draft, force_new_board=False):
        """Adopt draft settings and save them.

        Starts a new run if a run rule changed (RUN_RULE_KEYS), or when
        forced. Returns False, changing nothing, while a merge is animating.
        """
        previous = self.settings
        needs_run = force_new_board or any(
            draft[key] != previous[key] for key in RUN_RULE_KEYS
        )

        self.settings = dict(draft)

        if needs_run and not self.start_new_run():
            self.settings = previous
            return False

        if self.settings != previous:
            save_settings(self.settings)

        return True

    # --- hints ---------------------------------------------------------------

    def target_tapped(self, target):
        """Hint the next step towards the target; nothing with hints off."""
        if not self.settings["hints"] or self.round is None:
            return

        if self.round.solved:
            self.status_label.text = "Solved! Tap Next board"
            return

        board = self.board_view.board_state
        step = rules.next_hint_step(self.round, board)
        cells = rules.cells_for_step(board, step) if step else None

        if cells is None:
            self.status_label.text = "No quick hint from here · Reset or undo"
            return

        outcome = self.board_view.hint_step(cells[0], step[1], cells[1])

        if outcome == "shown":
            self.status_label.text = "Hint: {} · tap again to play".format(
                describe_step(step)
            )
        elif outcome == "played" and not self.round.solved:
            self.status_label.text = "Tap {} again for the next step".format(
                target
            )

    # --- buttons -------------------------------------------------------------

    def factors_tapped(self, sender=None):
        """Show or hide the target's factors; the choice is remembered."""
        self.settings["show_factors"] = not self.settings["show_factors"]
        save_settings(self.settings)
        self._show_factors()

    def _show_factors(self):
        target = self.round.target if self.round is not None else None
        self.factors_card.show(target, bool(self.settings["show_factors"]))

    def reset_tapped(self, sender):
        """Back to the starting numbers; the closest value so far is kept."""
        if self.board_view.load_board_state(self.round.starting_board()):
            self.refresh()

    def action_tapped(self, sender):
        """New run after a finish, Next board after a solve, otherwise Skip."""
        if self.board_view.resolving:
            return

        if self.run.is_finished:
            self.start_new_run()
            return

        if self.round.solved:
            previous_note = self.note
            self.note = None
            if not self.start_new_board():
                self.note = previous_note
            return

        # Skip: the penalty is added; skipping the last board ends the run.
        target = self.round.target

        if self.run.skip():
            self.note = None
            self.finish_run()
            self.refresh()
            return

        previous_note = self.note
        self.note = "Skipped {} · +{}s".format(target, self.run.skip_penalty)

        if not self.start_new_board():
            self.note = previous_note