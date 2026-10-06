"""
Number Detective game screen: crack four hidden tiles with question cards.

Lives under the Maths Games shell and uses the header contract from
gamecore/game.py: open_settings() puts a gear in the header, and
header_subtitle names the pool ("Classic · Numbers 1 to 12").

Play: tap one of the two question cards to arm it, tap the tiles it asks
about, then Ask. The answer joins the clue log and two new cards are dealt.
With no card armed, tap a tile to open the number picker: choose a number
to name the tile (a wrong name costs a point), or switch the picker to
Notes to pencil in candidates. The case is cracked when every tile is
named, and the score is compared with par.

"Show what's still possible" (a setting, on by default) shows how many
answers remain and fades ruled-out numbers in the picker. Off, the player
does all the deduction.

UI stability (see JACK_BOOT): every change happens synchronously inside the
tap that caused it, views are created once and only shown, hidden or
re-labelled, and settings are saved immediately.
"""

import json
import os

import ui

from style import theme
from tilegame.cell_picker import CellPicker
from tilegame.widgets import ChoiceRow, make_button, make_label

from games.number_detective import rules
from games.number_detective.game import DetectiveGame
from games.number_detective.views import TilesView


# --- colours, from the shared theme -----------------------------------------

BACKGROUND = theme.color("background")
SURFACE = theme.color("surface")
TEXT = theme.color("text")
MUTED = theme.color("muted")
BUTTON_COLOR = theme.color("button")
ACCENT = theme.color("tile")
SUCCESS = theme.color("success")
MISTAKE = theme.color("coral")

# --- editable layout, in points ---------------------------------------------

SIDE_MARGIN = 12
STATUS_HEIGHT = 24
TILES_HEIGHT = 124
INFO_HEIGHT = 22
CARD_HEIGHT = 60
ASK_HEIGHT = 46
BOTTOM_BAR = 72

POOL_LABELS = tuple(pool.label for pool in rules.POOLS)


# --- saved settings ---------------------------------------------------------

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(GAME_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "pool": "classic",
    "hints": True,
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
    if saved.get("pool") in rules.POOL_NAMES:
        settings["pool"] = saved["pool"]
    if isinstance(saved.get("hints"), bool):
        settings["hints"] = saved["hints"]
    return settings


def save_settings(settings):
    """Save settings now. A failed save is reported but never crashes play."""
    try:
        with open(SETTINGS_PATH, "w") as handle:
            json.dump(settings, handle)
    except OSError as error:
        print("Number Detective: could not save settings: {}".format(error))


def par_message(score, par):
    if score < par:
        return "Cracked in %d: %d under par!" % (score, par - score)
    if score == par:
        return "Cracked in %d: level with par" % score
    return "Cracked in %d: %d over par (par %d)" % (score, score - par, par)


class SettingsPanel(ui.View):
    """Overlay editing a draft of the settings, covering the game area.

    A new pool starts a new case when adopted; New case always does.
    """

    TOP = 16

    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.background_color = BACKGROUND
        self.hidden = True
        self.draft = dict(screen.settings)

        self.title_label = make_label("Settings", ("AvenirNext-Bold", 24), TEXT)
        self.pool_caption = make_label("Hidden numbers", ("AvenirNext-Medium", 15), MUTED)
        self.pool_control = ChoiceRow(POOL_LABELS, self.pool_changed)
        self.pool_description = make_label("", ("AvenirNext-Medium", 13), MUTED)

        self.hints_label = make_label(
            "Show what's still possible", ("AvenirNext-Medium", 15), TEXT,
            alignment=ui.ALIGN_LEFT,
        )
        self.hints_switch = ui.Switch()
        self.hints_switch.action = self.hints_changed
        self.hints_note = make_label(
            "Counts the answers left and fades ruled-out numbers",
            ("AvenirNext-Medium", 13), MUTED,
        )
        self.hints_note.number_of_lines = 2

        self.new_case_button = make_button(
            "New case", self.new_case_tapped,
            background=ACCENT, title_color=BACKGROUND,
        )
        self.done_button = make_button("Done", self.done_tapped)

        for view in (
            self.title_label,
            self.pool_caption,
            self.pool_control,
            self.pool_description,
            self.hints_label,
            self.hints_switch,
            self.hints_note,
            self.new_case_button,
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
        self.pool_caption.frame = (left, y, column, 22)
        y += 28
        self.pool_control.frame = (left, y, column, 40)
        y += 46
        self.pool_description.frame = (left, y, column, 20)
        y += 40
        self.hints_label.frame = (left, y, column - switch_width - 12, 44)
        self.hints_switch.frame = (left + column - switch_width, y + 6, switch_width, 31)
        y += 46
        self.hints_note.frame = (left, y, column, 36)
        y += 56
        self.new_case_button.frame = (left, y, column, 52)
        y += 68
        self.done_button.frame = (left, y, column, 52)

    def open(self):
        self.draft = dict(self.screen.settings)
        self.pool_control.selected_index = rules.POOL_NAMES.index(self.draft["pool"])
        self.show_pool_description()
        self.hints_switch.value = bool(self.draft["hints"])
        self.hidden = False
        self.bring_to_front()

    def show_pool_description(self):
        self.pool_description.text = rules.find_pool(self.draft["pool"]).description

    def pool_changed(self, sender):
        self.draft["pool"] = rules.POOL_NAMES[sender.selected_index]
        self.show_pool_description()

    def hints_changed(self, sender):
        self.draft["hints"] = bool(sender.value)

    def new_case_tapped(self, sender):
        self.screen.apply_settings(self.draft, force_new_case=True)
        self.hidden = True

    def done_tapped(self, sender):
        self.screen.apply_settings(self.draft)
        self.hidden = True


class DetectiveScreen(ui.View):
    """Number Detective under the shell header: one case at a time."""

    def __init__(self, rng=None, **kwargs):
        super().__init__(**kwargs)
        self.background_color = BACKGROUND
        self.settings = load_settings()
        self.rng = rng

        # Header contract (gamecore/game.py). The shell replaces the callback.
        self.header_subtitle = ""
        self.on_header_changed = None

        # What the player is doing right now; the case itself lives in game.
        self.armed = None          # index of the armed card in the hand
        self.selection = []        # tiles chosen for the armed card, in order
        self.picker_tile = None    # the tile the picker is open for
        self.message = None        # one-off feedback, such as a wrong guess
        self.notes = [set() for _ in range(rules.TILE_COUNT)]

        self.status_label = make_label("", ("AvenirNext-DemiBold", 15), TEXT)
        self.tiles_view = TilesView()
        self.tiles_view.on_tile_tapped = self.tile_tapped
        self.info_label = make_label("", ("AvenirNext-Medium", 14), MUTED)

        self.card_buttons = [
            make_button("", lambda sender, index=index: self.card_tapped(index), font_size=17)
            for index in range(rules.HAND_SIZE)
        ]
        self.ask_button = make_button(
            "Ask", self.ask_tapped, background=ACCENT, title_color=BACKGROUND)

        self.log_view = ui.TextView()
        self.log_view.editable = False
        self.log_view.background_color = SURFACE
        self.log_view.text_color = TEXT
        self.log_view.font = ("AvenirNext-Medium", 15)
        self.log_view.corner_radius = 12

        self.new_button = make_button("New case", self.new_case_tapped)
        self.picker = CellPicker(self.value_picked, notes_enabled=True)
        self.settings_panel = SettingsPanel(self)

        for view in (
            [self.status_label, self.tiles_view, self.info_label]
            + self.card_buttons
            + [self.ask_button, self.log_view, self.new_button,
               self.picker, self.settings_panel]   # last, so they cover
        ):
            self.add_subview(view)

        self.start_new_game()

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
        width, height = self.width, self.height
        margin = SIDE_MARGIN
        inner = width - 2 * margin

        y = 8
        self.status_label.frame = (margin, y, inner, STATUS_HEIGHT)
        y += STATUS_HEIGHT + 6
        self.tiles_view.frame = (margin, y, inner, TILES_HEIGHT)
        y += TILES_HEIGHT + 6
        self.info_label.frame = (margin, y, inner, INFO_HEIGHT)
        y += INFO_HEIGHT + 8

        count = len(self.card_buttons)
        card_width = (inner - 8 * (count - 1)) / count
        for index, button in enumerate(self.card_buttons):
            button.frame = (margin + index * (card_width + 8), y, card_width, CARD_HEIGHT)
        y += CARD_HEIGHT + 8
        self.ask_button.frame = (margin, y, inner, ASK_HEIGHT)
        y += ASK_HEIGHT + 10

        self.log_view.frame = (margin, y, inner, max(0, height - BOTTOM_BAR - y))
        self.new_button.frame = (margin, height - BOTTOM_BAR + 12, inner, 48)
        self.settings_panel.frame = self.bounds

    # --- game flow -----------------------------------------------------------

    def start_new_game(self):
        """A new game (and case) for the current pool."""
        self.game = DetectiveGame(self.settings["pool"], self.rng)
        pool = self.game.pool
        self.set_subtitle("%s · %s" % (pool.label, pool.description))
        self.reset_case_ui()

    def reset_case_ui(self):
        """Clear everything the player had in progress, for a fresh case."""
        self.armed = None
        self.selection = []
        self.picker_tile = None
        self.message = None
        self.notes = [set() for _ in range(rules.TILE_COUNT)]
        self.picker.hide_picker()
        self.picker.set_values(self.game.pool.values)
        self.refresh()

    def armed_question(self):
        if self.armed is None:
            return None
        return rules.QUESTION_BY_NAME[self.game.hand[self.armed]]

    def question_ready(self):
        question = self.armed_question()
        if question is None or self.game.solved:
            return False
        return question.arity == 0 or len(self.selection) == question.arity

    def ruled_out(self, tile):
        """Pool values the clues rule out for tile; empty with hints off."""
        if not self.settings["hints"]:
            return set()
        possible = set(self.game.possible_values(tile))
        return {value for value in self.game.pool.values if value not in possible}

    def refresh(self):
        """Redraw everything from the game. Called after every change."""
        game = self.game
        open_tile = None if self.picker.hidden else self.picker_tile
        self.tiles_view.show(game.pool.values, game.revealed, self.notes,
                             self.selection, open_tile)

        parts = ["Questions %d" % game.questions_asked]
        if game.wrong_guesses:
            parts.append("Wrong guesses %d" % game.wrong_guesses)
        if self.settings["hints"] and not game.solved:
            parts.append("Possible answers %d" % len(game.candidates))
        self.info_label.text = " · ".join(parts)

        hand = game.hand
        for index, button in enumerate(self.card_buttons):
            if index < len(hand):
                button.title = rules.QUESTION_BY_NAME[hand[index]].title
                button.hidden = False
            else:
                button.hidden = True
            armed = index == self.armed
            button.background_color = ACCENT if armed else BUTTON_COLOR
            button.tint_color = BACKGROUND if armed else TEXT
            button.enabled = not game.solved
            button.alpha = 1.0 if button.enabled else 0.4

        ready = self.question_ready()
        self.ask_button.enabled = ready
        self.ask_button.alpha = 1.0 if ready else 0.4

        self.log_view.text = "\n".join(
            "%d. %s" % (number, clue.text)
            for number, clue in reversed(list(enumerate(game.clues, 1)))
        )
        self._show_status()

    def _show_status(self):
        game = self.game
        question = self.armed_question()
        if game.solved:
            self.status_label.text = par_message(game.score, game.par)
            self.status_label.text_color = SUCCESS if game.score <= game.par else TEXT
        elif self.message:
            self.status_label.text = self.message
            self.status_label.text_color = MISTAKE
        elif question is not None and question.arity == 0:
            self.status_label.text = "This asks about all four tiles: tap Ask"
            self.status_label.text_color = TEXT
        elif question is not None:
            self.status_label.text = "Tap %d tiles, then Ask (%d chosen)" % (
                question.arity, len(self.selection))
            self.status_label.text_color = TEXT
        else:
            self.status_label.text = "Pick a card to ask, or tap a tile to name it"
            self.status_label.text_color = MUTED

    # --- taps ----------------------------------------------------------------

    def card_tapped(self, index):
        if self.game.solved:
            return
        self.message = None
        self.picker.hide_picker()
        self.picker_tile = None
        if self.armed == index:
            self.armed = None
        else:
            self.armed = index
        self.selection = []
        self.refresh()

    def tile_tapped(self, tile):
        self.message = None
        if tile is None or self.game.solved:
            self.close_picker()
            return

        question = self.armed_question()
        if question is not None:
            if question.arity > 0:
                if tile in self.selection:
                    self.selection.remove(tile)
                else:
                    if len(self.selection) >= question.arity:
                        self.selection.pop(0)
                    self.selection.append(tile)
            self.refresh()
            return

        if self.game.revealed[tile] is not None:
            self.close_picker()
            return
        if tile == self.picker_tile and not self.picker.hidden:
            self.close_picker()
            return
        self.open_picker(tile)

    def open_picker(self, tile):
        self.picker_tile = tile
        tile_x, tile_y, tile_width, tile_height = self.tiles_view.tile_frame(tile)
        origin_x, origin_y = self.tiles_view.frame[0], self.tiles_view.frame[1]
        anchor = (origin_x + tile_x, origin_y + tile_y, tile_width, tile_height)
        self.picker.show_beside(
            anchor, (0, 0, self.width, self.height),
            dimmed=self.ruled_out(tile), notes=self.notes[tile],
        )
        self.refresh()

    def close_picker(self):
        self.picker.hide_picker()
        self.picker_tile = None
        self.refresh()

    def value_picked(self, value):
        """Called by the picker: name the tile, toggle a note, or clear notes."""
        tile = self.picker_tile
        if tile is None:
            self.picker.hide_picker()
            return

        if value is None:
            self.notes[tile] = set()
            self.close_picker()
            return

        if self.picker.notes_mode:
            # Notes keep the picker open so several can be marked in a row.
            self.notes[tile] ^= {value}
            self.picker.update_marks(dimmed=self.ruled_out(tile), notes=self.notes[tile])
            self.refresh()
            return

        result = self.game.guess(tile, value)
        self.picker.hide_picker()
        self.picker_tile = None
        if result is False:
            self.notes[tile].discard(value)
            self.message = "No, %s isn't %d (+%d)" % (
                rules.TILE_NAMES[tile], value, rules.WRONG_GUESS_COST)
        elif result:
            self.notes[tile] = set()
        self.refresh()

    def ask_tapped(self, sender=None):
        if not self.question_ready():
            return
        self.game.ask(self.armed, self.selection)
        self.armed = None
        self.selection = []
        self.message = None
        self.refresh()

    def new_case_tapped(self, sender=None):
        self.game.new_case()
        self.reset_case_ui()

    def touch_ended(self, touch):
        """A tap on the background closes the picker."""
        self.close_picker()

    # --- settings ------------------------------------------------------------

    def apply_settings(self, draft, force_new_case=False):
        """Adopt draft settings and save them; a new pool starts a new case."""
        previous = self.settings
        self.settings = dict(draft)
        if self.settings["pool"] != previous["pool"]:
            self.start_new_game()
        elif force_new_case:
            self.game.new_case()
            self.reset_case_ui()
        else:
            self.refresh()
        if self.settings != previous:
            save_settings(self.settings)
        return True