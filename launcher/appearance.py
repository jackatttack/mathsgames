"""
Appearance: the player's theme choices (notes/THEME_EDITOR_SPEC.txt).

Two pages. The list shows "All games" and every game with its current
accent. Tapping one opens its editor: a preview pinned at the top (the
game's own board, drawn in the chosen colours, or a sample card for All
games and for games without a board preview yet) and only the choices that
apply below it. Every choice is saved at once and Reset puts the page back
to its defaults. Back steps from an editor to the list, then home
(handle_back() in gamecore/game.py). The shell repaints the launcher when
this screen closes; its own chrome stays in the theme it opened with.

A game whose entry.py has THEME_ROLES and create_preview() gets the spec v2
game page: its real screen as the preview (built at full game size, then
scaled to fit), "Start from" families, and one row of swatches per role.
Other games keep the v1 page (accent only) with a board-only preview or the
sample card, until they gain roles. Previews never read or write saved
games or settings: create_preview() and the v1 board builders use fixed
samples. Game modules are re-imported while theme.preview_palette() holds
the draft colours, so module-level colour constants follow the draft.

UI stability: every view is built once except the preview board, which is
replaced inside the tap that changed a colour. Nobody touches the board and
nothing is deferred.
"""

import importlib
import math
import random
import traceback

import ui

from feel import tactile
from gamecore.game import refresh_game_modules
from style import theme


# --- editable look and words -------------------------------------------------

MARGIN = 16
GAP = 12
CARD_HEIGHT = 72          # rows on the list page
PREVIEW_HEIGHT = 250      # the pinned preview, at most
SCREEN_PREVIEW_HEIGHT = 340   # taller when the preview is a whole game screen
TILE_HEIGHT = 96          # palette family tiles, label included
DOT_SIZE = 52             # accent circles
RING_WIDTH = 3            # outline on the selected choice
MAX_WIDTH = 440

LIST_SUBTITLE = "Pick what to recolour"
LIST_INTRO = "Tap All games or one game to change its colours."
PALETTE_NOTE = "Changes backgrounds, panels and text in every game."
SAFE_NOTE = "Right shows blue and wrong shows orange."
LOCKED_NOTE = ("Right, wrong and the four operation colours never change, "
               "so they keep their meaning.")

SAMPLE_SEED = 7           # the same sample board every time


def _centred(text, font, color, x, y, width, height):
    """Draw one line of text centred in a rectangle (inside draw())."""
    _, text_height = ui.measure_string(text, font=font, alignment=ui.ALIGN_CENTER)
    ui.draw_string(text, rect=(x, y + (height - text_height) / 2, width, text_height),
                   font=font, color=color, alignment=ui.ALIGN_CENTER)


def _label(text, font, color, alignment=ui.ALIGN_LEFT, lines=1):
    label = ui.Label()
    label.text = text
    label.font = font
    label.text_color = color
    label.alignment = alignment
    label.number_of_lines = lines
    return label


def _button(title, action, background, tint):
    button = ui.Button(title=title)
    button.action = action
    button.background_color = background
    button.tint_color = tint
    button.font = ("AvenirNext-DemiBold", 17)
    button.corner_radius = 12
    return button


def _tapped_inside(view, touch):
    x, y = touch.location
    return 0 <= x <= view.width and 0 <= y <= view.height


# --- real board previews -----------------------------------------------------

def _fill_sample(grid, solution):
    """Write most of the solution into grid so every kind of mark shows.

    Leaves two cells empty (the second with notes) and makes one clash.
    Returns the first empty cell, to show as selected.
    """
    open_cells = grid.empty_cells()
    selected, noted = open_cells[0], open_cells[1]
    for row, col in open_cells[2:]:
        grid.set_value((row, col), solution[row][col])
    row, col = open_cells[-1]
    grid.set_value((row, col), solution[row][(col + 1) % grid.size])
    for value in grid.allowed_values[:2]:
        grid.toggle_note(noted, value)
    return selected


def _notes_of(grid):
    return {cell: grid.notes_at(cell) for cell in grid.empty_cells() if grid.notes_at(cell)}


def _sudoku_board():
    rules = importlib.import_module("games.sudoku.rules")
    board_module = importlib.import_module("games.sudoku.board_view")
    fill_grid = importlib.import_module("tilegame.fill_grid")

    puzzle = rules.generate_puzzle(4, "easy", rng=random.Random(SAMPLE_SEED))
    grid = fill_grid.FillGrid(4, givens=puzzle.givens_by_cell(), units=rules.cell_units(4))
    selected = _fill_sample(grid, puzzle.solution)

    view = board_module.SudokuBoardView()
    view.load_puzzle(puzzle, rules.BOX_SHAPES[4])
    view.refresh_marks(grid.rows(), _notes_of(grid), selected, grid.conflicts(), False,
                       focus_cell=selected, completed=grid.completed_values())
    return view


def _kenken_board():
    rules = importlib.import_module("games.kenken.rules")
    board_module = importlib.import_module("games.kenken.board_view")
    fill_grid = importlib.import_module("tilegame.fill_grid")

    puzzle = rules.generate_puzzle(4, rules.OPERATIONS, rng=random.Random(SAMPLE_SEED))
    grid = fill_grid.FillGrid(4)
    selected = _fill_sample(grid, puzzle.solution)
    values = grid.rows()
    wrong_cages = {
        index for index, cage in enumerate(puzzle.cages)
        if rules.cage_status(cage, values) == "wrong"
    }

    view = board_module.KenKenBoardView()
    view.load_puzzle(puzzle)
    view.refresh_marks(values, _notes_of(grid), selected, grid.conflicts(), wrong_cages, False,
                       completed=grid.completed_values())
    return view


# Games whose own board can be previewed. Others show the sample card.
BOARD_PREVIEWS = {
    "sudoku": _sudoku_board,
    "kenken": _kenken_board,
}


def build_board_preview(game_id, colors):
    """The game's own board view, drawn in colors, showing a sample position.

    Returns None for games without a board preview yet.
    """
    builder = BOARD_PREVIEWS.get(game_id)
    if builder is None:
        return None
    theme.preview_palette(colors)
    try:
        refresh_game_modules()
        return builder()
    finally:
        theme.preview_palette(None)


def theme_roles(game_id):
    """A game's THEME_ROLES as (role, name, what it colours) rows.

    None for a game that still uses the v1 accent page: it needs both
    THEME_ROLES and create_preview() in its entry.py.
    """
    try:
        entry = importlib.import_module("games.%s.entry" % game_id)
    except Exception:
        traceback.print_exc()   # a broken game must never break the editor
        return None
    roles = getattr(entry, "THEME_ROLES", None)
    if roles and hasattr(entry, "create_preview"):
        return tuple(roles)
    return None


def build_screen_preview(game_id, colors):
    """The game's real screen from create_preview(), built in colors."""
    theme.preview_palette(colors)
    try:
        refresh_game_modules()
        entry = importlib.import_module("games.%s.entry" % game_id)
        return entry.create_preview()
    finally:
        theme.preview_palette(None)


# --- drawn pieces ------------------------------------------------------------

class PreviewCard(ui.View):
    """A sample board, picker row, tile and button in the draft colours."""

    SAMPLE_VALUES = {
        (0, 0): ("1", "text"), (0, 3): ("4", "text"), (3, 3): ("1", "text"),
        (0, 2): ("3", "success"), (1, 0): ("3", "success"),
        (2, 3): ("3", "success"), (3, 1): ("3", "success"),
        (1, 2): ("2", "sky"), (2, 0): ("2", "mistake"), (2, 1): ("2", "mistake"),
    }
    SELECTED_CELL = (1, 2)

    def __init__(self):
        super().__init__()
        self.background_color = (0, 0, 0, 0)
        self.touch_enabled = False
        self.colors = theme.palette()

    def draw(self):
        colors = self.colors
        width, height = self.width, self.height
        ui.set_color(colors["background"])
        ui.Path.rounded_rect(0, 0, width, height, theme.RADII["card"]).fill()
        board = min(height - 32, width * 0.5)
        left, top = 16, (height - board) / 2
        self._draw_board(colors, left, top, board / 4)
        controls_left = left + board + 16
        self._draw_controls(colors, controls_left, top, width - controls_left - 16, board)

    def _draw_board(self, colors, left, top, cell):
        side = 4 * cell
        ui.set_color(colors["surface"])
        ui.Path.rect(left, top, side, side).fill()
        ui.set_color(colors["assist_peer"])
        ui.Path.rect(left, top + self.SELECTED_CELL[0] * cell, side, cell).fill()

        lines = ui.Path()
        for index in (1, 3):
            lines.move_to(left + index * cell, top)
            lines.line_to(left + index * cell, top + side)
            lines.move_to(left, top + index * cell)
            lines.line_to(left + side, top + index * cell)
        lines.line_width = 1
        ui.set_color(colors["button"])
        lines.stroke()

        walls = ui.Path()
        walls.move_to(left + 2 * cell, top)
        walls.line_to(left + 2 * cell, top + side)
        walls.move_to(left, top + 2 * cell)
        walls.line_to(left + side, top + 2 * cell)
        walls.line_width = 2.5
        ui.set_color(colors["muted"])
        walls.stroke()

        font = ("AvenirNext-Bold", cell * 0.55)
        for (row, col), (text, token) in self.SAMPLE_VALUES.items():
            _centred(text, font, colors[token], left + col * cell, top + row * cell, cell, cell)

        row, col = self.SELECTED_CELL
        outline = ui.Path.rounded_rect(left + col * cell + 2, top + row * cell + 2,
                                       cell - 4, cell - 4, 4)
        outline.line_width = 3
        ui.set_color(colors["tile"])
        outline.stroke()

    def _draw_controls(self, colors, x, y, width, height):
        gap = 6
        size = min(36, (width - 3 * gap) / 4)
        font = ("AvenirNext-DemiBold", size * 0.5)
        for index, (text, kind) in enumerate(
                (("2", "current"), ("1", "plain"), ("3", "complete"), ("4", "plain"))):
            left = x + index * (size + gap)
            current = kind == "current"
            ui.set_color(colors["tile"] if current else colors["button"])
            ui.Path.rounded_rect(left, y, size, size, 8).fill()
            if current:
                ink = colors["tile_text"]
            elif kind == "complete":
                ink = colors["success"]
            else:
                ink = colors["text"]
            _centred(text, font, ink, left, y, size, size)

        tile = max(36, min(64, height - size - 70))
        tile_top = y + size + 14
        ui.set_color(colors["tile"])
        ui.Path.rounded_rect(x, tile_top, tile, tile, 14).fill()
        border = ui.Path.rounded_rect(x + 1, tile_top + 1, tile - 2, tile - 2, 13)
        border.line_width = 2
        ui.set_color(colors["tile_border"])
        border.stroke()
        _centred("12", ("AvenirNext-Bold", tile * 0.42), colors["tile_text"], x, tile_top, tile, tile)

        button_top = y + height - 40
        ui.set_color(colors["tile"])
        ui.Path.rounded_rect(x, button_top, width, 40, 12).fill()
        _centred("New puzzle", ("AvenirNext-DemiBold", 15), colors["tile_text"],
                 x, button_top, width, 40)


class ScopeCard(ui.View):
    """One row on the list page: a badge, a name and its current accent."""

    def __init__(self, scope, title, icon, badge_color, on_tap):
        super().__init__()
        self.scope = scope            # None: All games
        self.title = title
        self.icon = icon
        self.badge_color = badge_color
        self.on_tap = on_tap
        self.subtitle = ""
        self.dot_color = None
        self.background_color = (0, 0, 0, 0)

    def draw(self):
        width, height = self.width, self.height
        ui.set_color(theme.color("surface"))
        ui.Path.rounded_rect(0, 0, width, height, 16).fill()

        badge = height - 20
        ui.set_color(self.badge_color)
        ui.Path.rounded_rect(10, 10, badge, badge, 12).fill()
        _centred(self.icon, ("AvenirNext-Bold", badge * 0.36), theme.color("background"),
                 10, 10, badge, badge)

        text_left = 10 + badge + 14
        right = width - 34
        ui.draw_string(self.title, rect=(text_left, height / 2 - 24, right - text_left, 24),
                       font=("AvenirNext-Bold", 17), color=theme.color("text"))
        subtitle_left = text_left
        if self.dot_color:
            ui.set_color(self.dot_color)
            ui.Path.oval(text_left, height / 2 + 5, 12, 12).fill()
            subtitle_left += 18
        ui.draw_string(self.subtitle, rect=(subtitle_left, height / 2 + 2, right - subtitle_left, 20),
                       font=theme.font("caption"), color=theme.color("muted"))
        _centred("›", ("AvenirNext-Bold", 24), theme.color("muted"), width - 30, 0, 20, height)

    def touch_ended(self, touch):
        if _tapped_inside(self, touch):
            self.on_tap(self.scope)


class FamilyTile(ui.View):
    """One palette family: its background, surface and text, and its name."""

    def __init__(self, name, on_tap):
        super().__init__()
        self.name = name
        self.on_tap = on_tap
        self.selected = False
        self.background_color = (0, 0, 0, 0)
        # name None is "All games" on a game page; refresh_editor sets its colours.
        self.colors = theme.palette(theme.clean_choices({"family": name or "midnight"}), None)

    def draw(self):
        colors = self.colors
        width, height = self.width, self.height
        swatch = height - 24
        ui.set_color(colors["background"])
        ui.Path.rounded_rect(0, 0, width, swatch, 14).fill()
        ui.set_color(colors["surface"])
        ui.Path.rounded_rect(10, 10, width - 20, swatch - 20, 10).fill()
        _centred("Aa", ("AvenirNext-Bold", 20), colors["text"], 10, 10, width - 20, swatch - 20)
        if self.selected:
            ring = ui.Path.rounded_rect(1.5, 1.5, width - 3, swatch - 3, 14)
            ring.line_width = RING_WIDTH
            ui.set_color(theme.color("text"))
            ring.stroke()
        name = "All games" if self.name is None else theme.FAMILIES[self.name]["label"]
        label = name + (" ✓" if self.selected else "")
        color = theme.color("text") if self.selected else theme.color("muted")
        _centred(label, theme.font("caption"), color, 0, swatch + 4, width, 20)

    def touch_ended(self, touch):
        if _tapped_inside(self, touch):
            self.on_tap(self.name)


class SwatchDot(ui.View):
    """One swatch in a role row.

    swatch_id None is Default: the colour the role has when this game does
    not choose it, drawn as a rounded square so it reads as different.
    A swatch that would fail contrast is dimmed and cannot be tapped; it
    stays in place so nothing moves when choices change.
    """

    def __init__(self, role, swatch_id, on_tap):
        super().__init__()
        self.role = role
        self.swatch_id = swatch_id
        self.on_tap = on_tap
        self.fill = "#000000"
        self.selected = False
        self.available = True
        self.background_color = (0, 0, 0, 0)

    def show(self, fill, selected, available):
        """Mark this swatch. Redraws only when something changed."""
        if (fill, selected, available) == (self.fill, self.selected, self.available):
            return
        self.fill, self.selected, self.available = fill, selected, available
        self.alpha = 1.0 if available else 0.25
        self.touch_enabled = available
        self.set_needs_display()

    def _shape(self, inset):
        size = min(self.width, self.height)
        side = size - 2 * inset
        if self.swatch_id is None:
            return ui.Path.rounded_rect(inset, inset, side, side, 7)
        return ui.Path.oval(inset, inset, side, side)

    def draw(self):
        size = min(self.width, self.height)
        shape = self._shape(5)
        ui.set_color(self.fill)
        shape.fill()
        # A thin edge keeps dark swatches visible on a dark page.
        shape.line_width = 0.5
        ui.set_color(theme.color("muted"))
        shape.stroke()
        if self.selected:
            light = theme.contrast(self.fill, "#FFFFFF") >= theme.contrast(self.fill, "#000000")
            ink = "#FFFFFF" if light else "#000000"
            _centred("✓", ("AvenirNext-Bold", size * 0.4), ink, 0, 0, size, size)
            ring = self._shape(1.5)
            ring.line_width = RING_WIDTH
            ui.set_color(theme.color("text"))
            ring.stroke()

    def touch_ended(self, touch):
        if self.available and _tapped_inside(self, touch):
            self.on_tap(self.role, self.swatch_id)


class RoleRow(ui.View):
    """One role on a game page: its name and current choice, what it
    colours, and one row of swatches with Default first."""

    HEIGHT = 92
    MAX_SWATCH = 44
    MAX_GAP = 10

    def __init__(self, role, name, what, on_tap):
        super().__init__()
        self.role = role
        self.name = name
        self.kind = theme.ROLE_KINDS[role]
        self.background_color = (0, 0, 0, 0)
        self.title = _label(name, ("AvenirNext-DemiBold", 15), theme.color("text"))
        self.note = _label(what, theme.font("caption"), theme.color("muted"))
        self.dots = [SwatchDot(role, None, on_tap)] + [
            SwatchDot(role, swatch_id, on_tap) for swatch_id in theme.swatch_ids(self.kind)
        ]
        for view in [self.title, self.note] + self.dots:
            self.add_subview(view)

    def show(self, choice_label):
        self.title.text = "%s · %s" % (self.name, choice_label)

    def layout(self):
        width = self.width
        self.title.frame = (0, 0, width, 22)
        self.note.frame = (0, 22, width, 18)
        count = len(self.dots)
        size = min(self.MAX_SWATCH, (width - 4 * (count - 1)) / count)
        gap = min(self.MAX_GAP, (width - size * count) / max(1, count - 1))
        for index, dot in enumerate(self.dots):
            dot.frame = (index * (size + gap), 46, size, size)


class AccentDot(ui.View):
    """One accent swatch. name None is "App": follow the app's accent."""

    def __init__(self, name, on_tap):
        super().__init__()
        self.name = name
        self.on_tap = on_tap
        self.selected = False
        self.background_color = (0, 0, 0, 0)
        self.fill, self.ink = theme.ACCENTS[name or "warm"][1:]

    def draw(self):
        size = min(self.width, self.height)
        inset = 6
        ui.set_color(self.fill)
        ui.Path.oval(inset, inset, size - 2 * inset, size - 2 * inset).fill()
        if self.name is None:
            _centred("App", ("AvenirNext-Bold", 12), self.ink, 0, 0, size, size)
        elif self.selected:
            _centred("✓", ("AvenirNext-Bold", 18), self.ink, 0, 0, size, size)
        if self.selected:
            ring = ui.Path.oval(1.5, 1.5, size - 3, size - 3)
            ring.line_width = RING_WIDTH
            ui.set_color(theme.color("text"))
            ring.stroke()

    def touch_ended(self, touch):
        if _tapped_inside(self, touch):
            self.on_tap(self.name)


# --- the screen --------------------------------------------------------------

class AppearanceView(ui.View):
    """Theme choices: a list of scopes, then one editor per scope.

    save(choices) is called after every change and returns the choices it
    kept; the shell passes theme.save_choices, smokes pass a fake.
    """

    def __init__(self, games, save, **kwargs):
        super().__init__(**kwargs)
        self.background_color = theme.color("background")
        self.header_subtitle = LIST_SUBTITLE
        self.on_header_changed = None          # attached by the shell
        self.games = list(games)
        self.titles = {game.game_id: game.title for game in self.games}
        self.save = save
        self.scope = None                      # None: All games; else a game_id
        self.editing = False
        self.draft = theme.clean_choices(theme.current_choices())
        self.roles = None                      # the open game's THEME_ROLES, if it has them
        self.role_rows = []                    # built when a game page opens
        self.board = None                      # the preview board, when there is one

        # Page one: the list.
        self.list_page = ui.ScrollView()
        self.list_page.background_color = theme.color("background")
        self.list_page.shows_vertical_scroll_indicator = False
        self.list_intro = _label(LIST_INTRO, theme.font("body"), theme.color("muted"),
                                 ui.ALIGN_CENTER, lines=2)
        self.scope_cards = [ScopeCard(None, "All games", "All", theme.color("tile"), self.open_scope)]
        self.scope_cards += [
            ScopeCard(game.game_id, game.title, game.icon, theme.color(game.accent), self.open_scope)
            for game in self.games
        ]
        for view in [self.list_intro] + self.scope_cards:
            self.list_page.add_subview(view)
        self.add_subview(self.list_page)

        # Page two: one editor, with the preview pinned above the choices.
        self.edit_page = ui.View()
        self.edit_page.background_color = theme.color("background")
        self.edit_page.hidden = True

        self.preview_holder = ui.View()
        self.preview_holder.corner_radius = theme.RADII["card"]
        self.sample_card = PreviewCard()
        self.preview_holder.add_subview(self.sample_card)

        self.controls = ui.ScrollView()
        self.controls.background_color = theme.color("background")
        self.controls.shows_vertical_scroll_indicator = False

        heading = ("AvenirNext-DemiBold", 17)
        self.palette_title = _label("Palette", heading, theme.color("text"))
        self.palette_note = _label(PALETTE_NOTE, theme.font("caption"), theme.color("muted"), lines=2)
        self.family_tiles = [FamilyTile(name, self.choose_family) for name in theme.FAMILY_ORDER]
        self.same_tile = FamilyTile(None, self.choose_family)   # game pages: follow All games

        self.accent_title = _label("Accent", heading, theme.color("text"))
        self.accent_note = _label("", theme.font("caption"), theme.color("muted"), lines=2)
        self.app_dot = AccentDot(None, self.choose_accent)
        self.accent_dots = [self.app_dot] + [
            AccentDot(name, self.choose_accent) for name in theme.ACCENT_ORDER
        ]

        self.safe_label = _label("Colour-blind friendly feedback", theme.font("body"),
                                 theme.color("text"), lines=2)
        self.safe_switch = ui.Switch()
        self.safe_switch.action = lambda sender: self.set_safe_feedback(bool(sender.value))
        self.safe_note = _label(SAFE_NOTE, theme.font("caption"), theme.color("muted"))

        self.locked_note = _label(LOCKED_NOTE, theme.font("caption"), theme.color("muted"),
                                  ui.ALIGN_CENTER, lines=3)
        self.reset_button = _button("Reset this page", lambda sender: self.reset(),
                                    theme.color("button"), theme.color("text"))

        controls = [self.palette_title, self.palette_note] + self.family_tiles + [self.same_tile]
        controls += [self.accent_title, self.accent_note] + self.accent_dots
        controls += [self.safe_label, self.safe_switch, self.safe_note,
                     self.locked_note, self.reset_button]
        for view in controls:
            self.controls.add_subview(view)
        self.edit_page.add_subview(self.preview_holder)
        self.edit_page.add_subview(self.controls)
        self.add_subview(self.edit_page)

        self.refresh_cards()

    # --- moving between pages (smokes call these too) ------------------------

    def open_scope(self, scope):
        """Open the editor for All games (None) or one game."""
        tactile.haptic_tap()
        self.scope = scope
        self.roles = theme_roles(scope) if scope is not None else None
        self._build_role_rows()
        self.editing = True
        self.list_page.hidden = True
        self.edit_page.hidden = False
        self._set_subtitle(self.titles.get(scope, "All games"))
        self.refresh_editor()
        self.layout()
        self.rebuild_preview()

    def handle_back(self):
        """Back from an editor returns to the list. True when it did."""
        if not self.editing:
            return False
        tactile.haptic_tap()
        self.editing = False
        self._drop_board()
        self._drop_role_rows()
        self.roles = None
        self.edit_page.hidden = True
        self.list_page.hidden = False
        self._set_subtitle(LIST_SUBTITLE)
        self.refresh_cards()
        return True

    def _set_subtitle(self, text):
        self.header_subtitle = text
        if callable(self.on_header_changed):
            self.on_header_changed()

    # --- choices: each one is saved at once ----------------------------------

    def choose_family(self, name):
        """Pick a family: the app's on All games, this game's on a game page.

        On a game page name None means "Same as All games". v1 game pages
        have no families and ignore the tap.
        """
        if self.scope is None:
            if name is None:
                return
            tactile.haptic_tap()
            self.draft["family"] = name
        elif self.roles:
            tactile.haptic_tap()
            self.draft = theme.with_game_family(self.draft, self.scope, name)
        else:
            return
        self.changed()

    def choose_accent(self, name):
        """Pick an accent. name None means "use the app accent" (game scope)."""
        if self.scope is None and name is None:
            return
        tactile.haptic_tap()
        if self.scope is None:
            self.draft["accent"] = name
        else:
            # A game's accent is its tile role; None returns it to Default.
            self.draft = theme.with_game_role(self.draft, self.scope, "tile", name)
        self.changed()

    def set_safe_feedback(self, on):
        self.draft["safe_feedback"] = bool(on)
        self.changed()

    def choose_role(self, role, swatch_id):
        """Pick a swatch for one of this game's roles; None is Default."""
        tactile.haptic_tap()
        self.draft = theme.with_game_role(self.draft, self.scope, role, swatch_id)
        self.changed()

    def reset(self):
        """Put this page back to its defaults."""
        tactile.haptic_tap()
        if self.scope is None:
            self.draft = theme.clean_choices({"games": self.draft["games"]})
        else:
            # Reset this game: its family and every role go back to All games.
            self.draft["games"].pop(self.scope, None)
        self.changed()

    def changed(self):
        """Save the draft now, then show it."""
        try:
            self.draft = theme.clean_choices(self.save(theme.clean_choices(self.draft)))
        except OSError as error:
            print("Maths Games: could not save the theme: {}".format(error))
        self.refresh_editor()
        self.rebuild_preview()

    # --- showing the choices -------------------------------------------------

    def current_accent(self):
        """The chosen accent for the scope; None in game scope means "App"."""
        if self.scope is None:
            return self.draft["accent"]
        return theme.game_role(self.draft, self.scope, "tile")

    def refresh_cards(self):
        """Badges and subtitles on the list page, from the saved draft."""
        app_accent = self.draft["accent"]
        for card in self.scope_cards:
            if card.scope is None:
                card.badge_color = theme.ACCENTS[app_accent][1]
                card.subtitle = "%s palette · %s accent" % (
                    theme.FAMILIES[self.draft["family"]]["label"], theme.ACCENTS[app_accent][0])
            else:
                own = theme.game_role(self.draft, card.scope, "tile")
                card.dot_color = theme.ACCENTS[own or app_accent][1]
                card.subtitle = "%s accent" % theme.ACCENTS[own][0] if own else "Same as app"
            card.set_needs_display()

    def refresh_editor(self):
        """Show and mark the controls for the scope. Never moves anything.

        Three kinds of page: All games (palette, accent, feedback); a game
        with THEME_ROLES (Start from, then one row per role); a game still
        on the v1 page (accent only).
        """
        app_wide = self.scope is None
        roles_page = bool(self.roles)
        for view in [self.palette_title, self.palette_note] + self.family_tiles:
            view.hidden = not (app_wide or roles_page)
        self.same_tile.hidden = not roles_page
        for view in [self.safe_label, self.safe_switch, self.safe_note]:
            view.hidden = not app_wide
        self.accent_title.hidden = roles_page
        self.accent_note.hidden = roles_page
        self.reset_button.title = "Reset this page" if app_wide else "Reset this game"

        if roles_page:
            self.palette_title.text = "Start from"
            self.palette_note.text = "Backgrounds, panels and text for %s only." % (
                self.titles[self.scope])
            for dot in self.accent_dots:
                dot.hidden = True
            self._refresh_game_page()
            return

        self.palette_title.text = "Palette"
        self.palette_note.text = PALETTE_NOTE
        if app_wide:
            self.accent_note.text = "Changes tiles, selections and main buttons in every game."
        else:
            self.accent_note.text = (
                "Changes tiles, selections and main buttons in %s only. "
                "Its palette follows All games." % self.titles[self.scope])

        for tile in self.family_tiles:
            tile.selected = tile.name == self.draft["family"]
            tile.set_needs_display()

        offered = theme.accents_for_family(self.draft["family"])
        chosen = self.current_accent()
        self.app_dot.fill, self.app_dot.ink = theme.ACCENTS[self.draft["accent"]][1:]
        for dot in self.accent_dots:
            dot.hidden = app_wide if dot.name is None else dot.name not in offered
            dot.selected = dot.name == chosen
            dot.set_needs_display()

        self.safe_switch.value = self.draft["safe_feedback"]

    def rebuild_preview(self):
        """Show the scope's preview in the draft colours.

        A game with roles shows its real screen, scaled to fit, or nothing if
        that fails: never a stand-in. A v1 game shows its board or the sample
        card; All games shows the sample card.
        """
        colors = theme.palette(self.draft, self.scope)
        self.preview_holder.background_color = colors["background"]
        self._drop_board()

        board = None
        try:
            if self.roles:
                board = build_screen_preview(self.scope, colors)
            elif self.scope is not None:
                board = build_board_preview(self.scope, colors)
        except Exception:
            traceback.print_exc()   # a preview problem must never break the editor

        if board is None:
            if self.roles:
                self.sample_card.hidden = True
                return
            self.sample_card.colors = colors
            self.sample_card.hidden = False
            self.sample_card.set_needs_display()
            return
        self.sample_card.hidden = True
        board.touch_enabled = False
        self.preview_holder.add_subview(board)
        self.board = board
        if self.roles:
            self._fit_preview()
        else:
            board.background_color = colors["background"]
            board.frame = self.preview_holder.bounds

    def _drop_board(self):
        if self.board is not None:
            self.preview_holder.remove_subview(self.board)
            self.board = None

    def _fit_preview(self):
        """Lay the real screen out at full game size, then scale it to fit
        the preview area, centred."""
        board = self.board
        holder = self.preview_holder
        if board is None or not self.roles:
            return
        width, height = max(1.0, self.width), max(1.0, self.height)
        board.transform = ui.Transform()      # identity before setting the frame
        board.frame = (0, 0, width, height)
        scale = min(holder.width / width, holder.height / height)
        board.transform = ui.Transform.scale(scale, scale)
        board.center = (holder.width / 2, holder.height / 2)

    def _refresh_game_page(self):
        """Mark Start from and every role row from the draft."""
        family = theme.game_family(self.draft, self.scope)
        for tile in self.family_tiles:
            tile.selected = tile.name == family
            tile.set_needs_display()
        self.same_tile.selected = family is None
        self.same_tile.colors = theme.palette(
            theme.clean_choices({"family": self.draft["family"]}), None)
        self.same_tile.set_needs_display()

        for row in self.role_rows:
            chosen = theme.game_role(self.draft, self.scope, row.role)
            offered = set(theme.swatches_for(self.draft, self.scope, row.role))
            default = theme.with_game_role(self.draft, self.scope, row.role, None)
            default_fill = theme.palette(default, self.scope)[row.role]
            for dot in row.dots:
                if dot.swatch_id is None:
                    dot.show(default_fill, chosen is None, True)
                else:
                    fill = theme.role_colors(row.role, dot.swatch_id)[row.role]
                    available = dot.swatch_id in offered or dot.swatch_id == chosen
                    dot.show(fill, dot.swatch_id == chosen, available)
            row.show("Default" if chosen is None else theme.swatch_label(row.kind, chosen))

    def _build_role_rows(self):
        """Rows for the open game's roles: built when its page opens, dropped on Back."""
        self._drop_role_rows()
        for role, name, what in self.roles or ():
            row = RoleRow(role, name, what, self.choose_role)
            self.controls.add_subview(row)
            self.role_rows.append(row)

    def _drop_role_rows(self):
        for row in self.role_rows:
            self.controls.remove_subview(row)
        self.role_rows = []

    # --- layout --------------------------------------------------------------

    def layout(self):
        width, height = self.width, self.height
        inner = min(MAX_WIDTH, width - 2 * MARGIN)
        left = (width - inner) / 2

        self.list_page.frame = self.bounds
        y = MARGIN
        self.list_intro.frame = (left, y, inner, 40)
        y += 52
        for card in self.scope_cards:
            card.frame = (left, y, inner, CARD_HEIGHT)
            y += CARD_HEIGHT + 10
        self.list_page.content_size = (width, y + MARGIN)

        self.edit_page.frame = self.bounds
        if self.roles:
            preview_height = min(SCREEN_PREVIEW_HEIGHT, height * 0.48)
        else:
            preview_height = min(PREVIEW_HEIGHT, height * 0.42)
        self.preview_holder.frame = (left, 8, inner, preview_height)
        self.sample_card.frame = self.preview_holder.bounds
        if self.board is not None:
            if self.roles:
                self._fit_preview()
            else:
                self.board.frame = self.preview_holder.bounds
        top = 8 + preview_height + 8
        self.controls.frame = (0, top, width, max(0, height - top))
        self._layout_controls(width, left, inner)

    def _layout_controls(self, width, left, inner):
        y = 12
        if not self.palette_title.hidden:
            self.palette_title.frame = (left, y, inner, 24)
            y += 26
            self.palette_note.frame = (left, y, inner, 18)
            y += 26
            tiles = [tile for tile in self.family_tiles + [self.same_tile] if not tile.hidden]
            tile_width = (inner - GAP * (len(tiles) - 1)) / len(tiles)
            for index, tile in enumerate(tiles):
                tile.frame = (left + index * (tile_width + GAP), y, tile_width, TILE_HEIGHT)
            y += TILE_HEIGHT + 18

        if not self.accent_title.hidden:
            self.accent_title.frame = (left, y, inner, 24)
            y += 26
            self.accent_note.frame = (left, y, inner, 36)
            y += 42
            dots = [dot for dot in self.accent_dots if not dot.hidden]
            columns = 4 if len(dots) <= 8 else 5
            cell = inner / columns
            for index, dot in enumerate(dots):
                row, col = divmod(index, columns)
                dot.frame = (left + col * cell + (cell - DOT_SIZE) / 2,
                             y + row * (DOT_SIZE + GAP), DOT_SIZE, DOT_SIZE)
            y += math.ceil(len(dots) / columns) * (DOT_SIZE + GAP) + 6

        for role_row in self.role_rows:
            role_row.frame = (left, y, inner, RoleRow.HEIGHT)
            y += RoleRow.HEIGHT + 10

        if not self.safe_switch.hidden:
            switch_width = 51
            self.safe_label.frame = (left, y, inner - switch_width - 12, 44)
            self.safe_switch.frame = (left + inner - switch_width, y + 6, switch_width, 31)
            y += 46
            self.safe_note.frame = (left, y, inner, 18)
            y += 30

        self.locked_note.frame = (left, y, inner, 40)
        y += 52
        self.reset_button.frame = (left, y, inner, 48)
        y += 48 + MARGIN
        self.controls.content_size = (width, y)