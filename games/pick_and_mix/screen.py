"""
Pick & Mix game screen: two players on one device, passing it back and forth.

Lives under the Maths Games shell and uses the header contract from
gamecore/game.py: open_settings() puts a gear in the header, and
header_subtitle describes the match ("Primes · first to 30").

Play: the target sits between the scores. Players take turns tapping a pool
tile into their own zone, four picks each. Either player can merge in their
own zone at any time: tap a tile, tap an operation quadrant, tap another of
their tiles. Each zone has its own Undo (merges only; picks are final) and
Lock in. The tile closest to the target counts. Once both lock in, the
results panel shows who won by how much and the best answer each player's
picks could have made. The loser picks first next round.

UI stability (see JACK_BOOT): every change happens synchronously inside the
tap that caused it, views are created once and only shown, hidden or
re-labelled, and settings are saved immediately.
"""

import json
import os

import ui

from style import theme
from tilegame.board_state import OPERATION_SYMBOLS
from tilegame.widgets import (
    ChoiceGrid,
    ChoiceRow,
    draw_centred_text,
    make_button,
    make_label,
)

from games.pick_and_mix import rules
from games.pick_and_mix.game import DRAFT, SCORED, SOLVING, PickAndMixGame
from games.pick_and_mix.views import (
    PLAYER_COLORS,
    PLAYER_NAMES,
    PoolView,
    ScoreBar,
    ZoneView,
)


# --- colours, from the shared theme -----------------------------------------

BACKGROUND = theme.color("background")
SURFACE = theme.color("surface")
TEXT = theme.color("text")
MUTED = theme.color("muted")
SUCCESS = theme.color("success")

# --- editable layout, in points ---------------------------------------------

SIDE_MARGIN = 12
SCORE_BAR_HEIGHT = 72
STATUS_HEIGHT = 24
MIDDLE_HEIGHT = 236        # the pool, or the results panel over it
ZONE_GAP = 10
BUTTON_HEIGHT = 44

# --- match settings ---------------------------------------------------------

MATCH_POINTS_CHOICES = (20, 30, 50)
MATCH_POINTS_LABELS = ("20", "30", "50")


# --- saved settings ---------------------------------------------------------

GAME_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(GAME_DIR, "settings.json")

DEFAULT_SETTINGS = {
    "pool": "standard",
    "match_points": 30,
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
    if saved.get("match_points") in MATCH_POINTS_CHOICES:
        settings["match_points"] = saved["match_points"]
    return settings


def save_settings(settings):
    """Save settings now. A failed save is reported but never crashes play."""
    try:
        with open(SETTINGS_PATH, "w") as handle:
            json.dump(settings, handle)
    except OSError as error:
        print("Pick & Mix: could not save settings: {}".format(error))


# --- describing results -----------------------------------------------------

def distance_text(distance):
    return "exact" if distance == 0 else "%d off" % distance


def step_text(step):
    left, operation, right, value = step
    return "%d %s %d = %d" % (left, OPERATION_SYMBOLS[operation], right, value)


def describe_result(game):
    """What the results panel shows: a title, a card per player, the action.

    Each card has the player's name and colour, the counted value, a caption
    such as 'exact · +6', whether they won, and either the best answer their
    picks could have made (with its steps) or 'Best possible'.
    """
    result = game.result
    score = result.score

    if game.match_winner is not None:
        winner = game.match_winner
        title = "%s wins the match %d–%d" % (
            PLAYER_NAMES[winner], game.scores[winner], game.scores[1 - winner])
        title_color = PLAYER_COLORS[winner]
        action = "New match"
    else:
        if score.winner is None:
            title = "A tie: no points this round"
            title_color = TEXT
        else:
            winner = score.winner
            margin = score.distances[1 - winner] - score.distances[winner]
            title = "%s wins by %d: +%d" % (
                PLAYER_NAMES[winner], margin, score.points[winner])
            title_color = PLAYER_COLORS[winner]
        action = "Next round"

    cards = []
    for player in (0, 1):
        distance = score.distances[player]
        best_value, best_distance, steps = result.best[player]
        if best_distance < distance:
            if best_distance == 0:
                best_title = "Could hit %d exactly" % best_value
            else:
                best_title = "Could reach %d (%d off)" % (best_value, best_distance)
            lines = [step_text(step) for step in steps]
        else:
            best_title = "Best possible"
            lines = []
        cards.append({
            "name": PLAYER_NAMES[player],
            "color": PLAYER_COLORS[player],
            "value": result.values[player],
            "caption": "%s · +%d" % (distance_text(distance), score.points[player]),
            "won": score.winner == player,
            "best_title": best_title,
            "steps": lines,
        })

    return {"title": title, "title_color": title_color, "cards": cards, "action": action}


# --- panels -----------------------------------------------------------------

class ResultsPanel(ui.View):
    """Covers the pool once a round is scored: a title, a card per player, a button.

    The title and button are plain subviews; the two cards are drawn in
    draw() from the summary that describe_result() builds.
    """

    # --- editable layout, in points ------------------------------------------
    PADDING = 12
    TITLE_HEIGHT = 30
    BUTTON_HEIGHT = 44
    CARD_GAP = 10
    CARD_RADIUS = 12
    STEP_LINE_HEIGHT = 16

    def __init__(self, on_action):
        super().__init__()
        self.background_color = SURFACE
        self.corner_radius = 16
        self.hidden = True
        self.cards = []

        self.title_label = make_label("", ("AvenirNext-Bold", 18), TEXT)
        self.action_button = make_button(
            "Next round", on_action,
            background=theme.color("tile"), title_color=BACKGROUND,
        )
        for view in (self.title_label, self.action_button):
            self.add_subview(view)

    def show(self, summary):
        self.title_label.text = summary["title"]
        self.title_label.text_color = summary["title_color"]
        self.cards = summary["cards"]
        self.action_button.title = summary["action"]
        self.hidden = False
        self.bring_to_front()
        self.set_needs_display()

    def layout(self):
        padding = self.PADDING
        self.title_label.frame = (padding, 6, self.width - 2 * padding, self.TITLE_HEIGHT)
        self.action_button.frame = (
            padding, self.height - padding - self.BUTTON_HEIGHT,
            self.width - 2 * padding, self.BUTTON_HEIGHT,
        )

    def card_frame(self, index):
        top = 6 + self.TITLE_HEIGHT + 4
        bottom = self.height - self.PADDING - self.BUTTON_HEIGHT - 8
        width = (self.width - 2 * self.PADDING - self.CARD_GAP) / 2
        return (self.PADDING + index * (width + self.CARD_GAP), top,
                width, max(0, bottom - top))

    def draw(self):
        for index, card in enumerate(self.cards):
            x, y, width, height = self.card_frame(index)
            shape = ui.Path.rounded_rect(x, y, width, height, self.CARD_RADIUS)
            ui.set_color(BACKGROUND)
            shape.fill()
            if card["won"]:
                shape.line_width = 2
                ui.set_color(card["color"])
                shape.stroke()

            line_y = y + 6
            draw_centred_text(card["name"], ("AvenirNext-DemiBold", 14), card["color"],
                              x, line_y, width, 18)
            line_y += 20
            draw_centred_text(str(card["value"]), ("AvenirNext-Bold", 30), TEXT,
                              x, line_y, width, 36)
            line_y += 38
            draw_centred_text(card["caption"], ("AvenirNext-Medium", 13),
                              SUCCESS if card["won"] else MUTED, x, line_y, width, 18)
            line_y += 26

            draw_centred_text(card["best_title"], ("AvenirNext-DemiBold", 12), MUTED,
                              x, line_y, width, self.STEP_LINE_HEIGHT)
            line_y += self.STEP_LINE_HEIGHT + 2
            for step in card["steps"]:
                if line_y + self.STEP_LINE_HEIGHT > y + height:
                    break
                draw_centred_text(step, ("AvenirNext-Medium", 12), TEXT,
                                  x, line_y, width, self.STEP_LINE_HEIGHT)
                line_y += self.STEP_LINE_HEIGHT


class SettingsPanel(ui.View):
    """Overlay editing a draft of the settings, covering the game area.

    The pools are a grid, so any one is a single tap away, with its
    description underneath. Changing the pool or match length starts a new
    match when adopted. New match always starts one.
    """

    TOP = 16
    POOL_ROW_HEIGHT = 44

    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.background_color = BACKGROUND
        self.hidden = True
        self.draft = dict(screen.settings)

        self.title_label = make_label("Settings", ("AvenirNext-Bold", 24), TEXT)
        self.pool_caption = make_label("Number pool", ("AvenirNext-Medium", 15), MUTED)
        self.pool_grid = ChoiceGrid(
            [pool.label for pool in rules.POOLS], self.pool_changed, columns=3
        )
        self.pool_description = make_label("", ("AvenirNext-Medium", 13), MUTED)
        self.pool_description.number_of_lines = 2

        self.points_caption = make_label("Match: first to",
                                         ("AvenirNext-Medium", 15), MUTED)
        self.points_control = ChoiceRow(MATCH_POINTS_LABELS, self.points_changed)
        self.note_label = make_label("Changing these starts a new match",
                                     ("AvenirNext-Medium", 13), MUTED)

        self.new_match_button = make_button(
            "New match", self.new_match_tapped,
            background=theme.color("tile"), title_color=BACKGROUND,
        )
        self.done_button = make_button("Done", self.done_tapped)

        for view in (
            self.title_label,
            self.pool_caption,
            self.pool_grid,
            self.pool_description,
            self.points_caption,
            self.points_control,
            self.note_label,
            self.new_match_button,
            self.done_button,
        ):
            self.add_subview(view)

    def layout(self):
        column = min(320, self.width - 48)
        left = (self.width - column) / 2

        y = self.TOP
        self.title_label.frame = (left, y, column, 36)
        y += 56
        self.pool_caption.frame = (left, y, column, 22)
        y += 28
        grid_height = self.pool_grid.preferred_height(self.POOL_ROW_HEIGHT)
        self.pool_grid.frame = (left, y, column, grid_height)
        y += grid_height + 8
        self.pool_description.frame = (left, y, column, 36)
        y += 48
        self.points_caption.frame = (left, y, column, 22)
        y += 28
        self.points_control.frame = (left, y, column, 40)
        y += 52
        self.note_label.frame = (left, y, column, 20)
        y += 40
        self.new_match_button.frame = (left, y, column, 52)
        y += 68
        self.done_button.frame = (left, y, column, 52)

    def open(self):
        self.draft = dict(self.screen.settings)
        self.pool_grid.selected_index = rules.POOL_NAMES.index(self.draft["pool"])
        self.show_pool_description()
        self.points_control.selected_index = MATCH_POINTS_CHOICES.index(
            self.draft["match_points"])
        self.hidden = False
        self.bring_to_front()

    def show_pool_description(self):
        self.pool_description.text = rules.find_pool(self.draft["pool"]).description

    def pool_changed(self, sender):
        self.draft["pool"] = rules.POOL_NAMES[sender.selected_index]
        self.show_pool_description()

    def points_changed(self, sender):
        self.draft["match_points"] = MATCH_POINTS_CHOICES[sender.selected_index]

    def new_match_tapped(self, sender):
        self.screen.apply_settings(self.draft, force_new_match=True)
        self.hidden = True

    def done_tapped(self, sender):
        self.screen.apply_settings(self.draft)
        self.hidden = True


# --- the screen -------------------------------------------------------------

class PickAndMixScreen(ui.View):
    """Pick & Mix under the shell header: one match, round after round."""

    def __init__(self, rng=None, **kwargs):
        super().__init__(**kwargs)
        self.background_color = BACKGROUND
        self.settings = load_settings()
        self.rng = rng

        # Header contract (gamecore/game.py). The shell replaces the callback.
        self.header_subtitle = ""
        self.on_header_changed = None

        self.score_bar = ScoreBar()
        self.status_label = make_label("", ("AvenirNext-DemiBold", 15), MUTED)

        self.pool_view = PoolView()
        self.pool_view.on_pick = self.pool_tapped

        self.zones = []
        self.undo_buttons = []
        self.lock_buttons = []
        for player in (0, 1):
            zone = ZoneView(player)
            zone.on_merge = lambda source, destination, operation, p=player: (
                self.merge_for(p, source, destination, operation))
            zone.result_of = lambda source, destination, operation, p=player: (
                self.game.hands[p].result_of(source, destination, operation))
            zone.on_undo = lambda p=player: self.undo_for(p)
            self.zones.append(zone)
            self.undo_buttons.append(make_button(
                "Undo", lambda sender, p=player: self.undo_for(p), font_size=15))
            self.lock_buttons.append(make_button(
                "Lock in", lambda sender, p=player: self.lock_for(p), font_size=15,
                background=PLAYER_COLORS[player], title_color=BACKGROUND))

        self.results_panel = ResultsPanel(self.results_tapped)
        self.settings_panel = SettingsPanel(self)

        for view in (
            [self.score_bar, self.status_label, self.pool_view]
            + self.zones + self.undo_buttons + self.lock_buttons
            + [self.results_panel, self.settings_panel]   # last, so they cover
        ):
            self.add_subview(view)

        self.start_new_match()

    # --- header contract -----------------------------------------------------

    def open_settings(self):
        """Called by the shell's gear."""
        for zone in self.zones:
            zone.clear_selection()
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

        self.score_bar.frame = (margin, 4, inner, SCORE_BAR_HEIGHT)
        status_top = 4 + SCORE_BAR_HEIGHT + 4
        self.status_label.frame = (margin, status_top, inner, STATUS_HEIGHT)

        middle_top = status_top + STATUS_HEIGHT + 6
        self.pool_view.frame = (margin, middle_top, inner, MIDDLE_HEIGHT)
        self.results_panel.frame = (margin, middle_top, inner, MIDDLE_HEIGHT)

        zones_top = middle_top + MIDDLE_HEIGHT + 10
        zone_width = (inner - ZONE_GAP) / 2
        zone_height = max(0, height - zones_top - BUTTON_HEIGHT - 16)
        button_width = (zone_width - 6) / 2
        buttons_y = zones_top + zone_height + 8

        for player in (0, 1):
            x = margin + player * (zone_width + ZONE_GAP)
            self.zones[player].frame = (x, zones_top, zone_width, zone_height)
            self.undo_buttons[player].frame = (x, buttons_y, button_width, BUTTON_HEIGHT)
            self.lock_buttons[player].frame = (
                x + button_width + 6, buttons_y, button_width, BUTTON_HEIGHT)

        self.settings_panel.frame = self.bounds

    # --- match flow ----------------------------------------------------------

    def start_new_match(self):
        self.game = PickAndMixGame(
            self.settings["pool"], self.settings["match_points"], self.rng)
        pool = rules.find_pool(self.settings["pool"])
        self.set_subtitle("%s · first to %d" % (pool.label, self.settings["match_points"]))
        for zone in self.zones:
            zone.clear_selection()
        self.refresh()

    def refresh(self):
        """Redraw everything from the game. Called after every change."""
        game = self.game
        self.score_bar.show(game.target, game.scores)
        self.pool_view.show(game.pool, game.taken_by, enabled=game.phase == DRAFT)

        for player in (0, 1):
            hand = game.hands[player]
            counted = hand.closest_to(game.target)
            self.zones[player].show(
                hand.values(),
                locked=not game.can_play(player),
                active=game.phase == DRAFT and game.turn == player,
                counted=counted,
                distance=None if counted is None else abs(counted - game.target),
            )
            self.undo_buttons[player].enabled = game.can_play(player) and hand.can_undo()
            self.lock_buttons[player].enabled = game.can_lock_in(player)
            self.lock_buttons[player].title = "Locked" if game.locked[player] else "Lock in"

        self._show_status()

        if game.phase == SCORED:
            self.results_panel.show(describe_result(game))
        else:
            self.results_panel.hidden = True

    def _show_status(self):
        game = self.game
        if game.phase == DRAFT:
            left = rules.PICKS_PER_PLAYER - game.picks_made(game.turn)
            self.status_label.text = "%s: pick a tile · %d left" % (
                PLAYER_NAMES[game.turn], left)
            self.status_label.text_color = PLAYER_COLORS[game.turn]
        elif game.phase == SOLVING:
            waiting = [PLAYER_NAMES[p] for p in (0, 1) if not game.locked[p]]
            self.status_label.text = "Merge, then lock in · waiting for %s" % (
                " and ".join(waiting))
            self.status_label.text_color = TEXT
        else:
            self.status_label.text = "Round %d scored" % game.round_number
            self.status_label.text_color = MUTED

    # --- taps ----------------------------------------------------------------

    def pool_tapped(self, index):
        if self.game.pick(index):
            self.refresh()

    def merge_for(self, player, source, destination, operation):
        value = self.game.merge(player, source, destination, operation)
        if value is not None:
            self.refresh()
        return value

    def undo_for(self, player):
        self.zones[player].clear_selection()
        if self.game.undo(player):
            self.refresh()

    def lock_for(self, player):
        self.zones[player].clear_selection()
        if self.game.lock_in(player):
            self.refresh()

    def results_tapped(self, sender=None):
        """Next round, or a new match once someone has won."""
        if self.game.match_winner is not None:
            self.game.new_match()
        else:
            self.game.next_round()
        for zone in self.zones:
            zone.clear_selection()
        self.refresh()

    # --- settings ------------------------------------------------------------

    def apply_settings(self, draft, force_new_match=False):
        """Adopt draft settings and save them; a change starts a new match."""
        previous = self.settings
        self.settings = dict(draft)
        if force_new_match or self.settings != previous:
            self.start_new_match()
        if self.settings != previous:
            save_settings(self.settings)
        return True