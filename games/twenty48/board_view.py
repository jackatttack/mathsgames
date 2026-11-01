"""
The Double Up board: the background and empty cells drawn in draw(), with the
tiles as a fixed pool of tile views on top.

Tiles are views so they can slide. TileMotion (tile_motion.py) decides
which view shows which tile. play() either moves the views at once or
slides them with ui.animate. That technique was chosen in the 2048
animation lab (labs/twenty48_animation_lab.py, 2026-10-17): with no
completion callbacks Python does nothing mid-slide, and fast swiping plus
bursts of 20 overlapping swipes never crashed. A Python-driven update()
tween survived the same tests but felt no better and costs more.

Tiles are coloured by step (how far along its mode's sequence a tile is),
so one ramp fits every mode and starting number. TILE_RAMP gives every
step its own colour, past both goals (doubling reaches its goal at step
10, Fibonacci at step 16); beyond its end the ramp starts again. The ramp
is fixed, like the operation colours, and every number colour keeps the
3:1 large-text contrast (checked by the screen smoke).

Numbers are sized from their measured width, so long numbers never touch
the tile's edges.

The pool holds 2 × 6 × 6 views, made once with the board: every tile on
the largest board plus every merge partner that may still be fading.
Views are never added or removed during play.
Merges fold (MERGE_STYLE = "fold"): the partner slides to the cell beside
its merge cell while the survivor slides in still showing its old number.
As the slide ends, FoldSheets (a see-through view above every tile, with
its own frame clock) hides the partner and draws it turning over onto the
survivor, the merged tile on its underside; on landing the survivor takes
the merged value. A new swipe, size change or show() lands any fold in
flight first. The new tile then folds in from its cell's centre in tiny
squares on the same frame clock. Both come from boardkit/folds.py (Fold's
paper animation, shared) by way of merge_fold.py, and
follows the frame-clock rules in library/guides/pythonista-ui-stability.md.

Swipes are read here and reported through on_swipe(direction). The view
never changes game state itself.
"""

import os
import time

import ui

from style import theme
from games.twenty48.rules import BOARD_SIZES
from games.twenty48 import merge_fold
from games.twenty48.tile_motion import TileMotion


BOARD_COLOR = theme.color("board")
EMPTY_COLOR = theme.color("grid_line")

DARK_INK = "#172033"
LIGHT_INK = "#FFFFFF"

# (fill, number colour) by step, smallest tile first: pale to warm, round
# through pink and violet to blue, teal and green, then deep colours.
TILE_RAMP = (
    ("#D5DCE8", DARK_INK),    # 0  pale silver
    ("#EADFC4", DARK_INK),    # 1  sand
    ("#F3D98A", DARK_INK),    # 2  pale gold
    ("#F2C14E", DARK_INK),    # 3  gold
    ("#F3A65A", DARK_INK),    # 4  orange
    ("#EE8A6B", DARK_INK),    # 5  coral
    ("#EC7A95", DARK_INK),    # 6  pink
    ("#D58AD9", DARK_INK),    # 7  orchid
    ("#A98BF2", DARK_INK),    # 8  violet
    ("#7FA2F7", DARK_INK),    # 9  periwinkle
    ("#5DBBF2", DARK_INK),    # 10 sky
    ("#4FC9C0", DARK_INK),    # 11 teal
    ("#6FD49A", DARK_INK),    # 12 green
    ("#A8D86A", DARK_INK),    # 13 lime
    ("#3E6FD8", LIGHT_INK),   # 14 royal blue
    ("#8B4FD1", LIGHT_INK),   # 15 purple
    ("#C2367A", LIGHT_INK),   # 16 magenta
    ("#1F8F7A", LIGHT_INK),   # 17 deep teal
)

POOL_SIZE = 2 * max(BOARD_SIZES) ** 2

# --- editable look and feel, in points, seconds or fractions of a cell ------

MARGIN = 12
GAP_RATIO = 0.12          # gap between cells, as a fraction of a cell
CORNER_RATIO = 0.14       # tile corner radius, as a fraction of a cell
MAX_DIGIT_RATIO = 0.45    # number height cap, as a fraction of a cell
TEXT_WIDTH_SHARE = 0.8    # the widest a number may be, as a fraction of a cell
FONT_NAME = "AvenirNext-Bold"
SWIPE_DISTANCE = 24       # points a finger must travel to count as a swipe
SLIDE_SECONDS = 0.16
# A new tile's fold-in timing lives in merge_fold.py (SPAWN_SQUARES and the SPAWN_ knobs).
BREADCRUMBS = False       # log swipes, layouts and folds to board_view.log beside this file
MERGE_STYLE = "fold"      # "fold": a merge partner turns over onto its tile (merge_fold.py)
                          # "fade": it slides onto the tile and fades out


def breadcrumb(text):
    """One millisecond-stamped line in board_view.log, when BREADCRUMBS is on."""
    if not BREADCRUMBS:
        return
    now = time.time()
    stamp = time.strftime("%H:%M:%S", time.localtime(now)) + ".{:03d}".format(int(now * 1000) % 1000)
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "board_view.log")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("{} {}\n".format(stamp, text))
    except (OSError, NameError):
        pass


def swipe_direction(start, end, distance):
    """'left', 'right', 'up' or 'down' for a finger that moved far enough, else None."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    if max(abs(dx), abs(dy)) < distance:
        return None
    if abs(dx) > abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"


def digit_font(text, cell_size):
    """The largest font up to the height cap whose text fits the width share."""
    size = cell_size * MAX_DIGIT_RATIO
    width = ui.measure_string(text, font=(FONT_NAME, size))[0]
    limit = cell_size * TEXT_WIDTH_SHARE
    if width > limit:
        size *= limit / width
    return (FONT_NAME, size)


class TileView(ui.View):
    """One reusable tile: a rounded square with its number."""

    def __init__(self):
        super().__init__()
        self.touch_enabled = False      # swipes pass through to the board
        self.hidden = True
        self.label = ui.Label()
        self.label.alignment = ui.ALIGN_CENTER
        self.label.touch_enabled = False
        self.add_subview(self.label)

    def dress(self, value, look, cell_size):
        """Show value in look (fill, number colour) at this cell size."""
        fill, ink = look
        text = str(value)
        self.background_color = fill
        self.corner_radius = cell_size * CORNER_RATIO
        self.label.frame = (0, 0, cell_size, cell_size)
        self.label.text = text
        self.label.text_color = ink
        self.label.font = digit_font(text, cell_size)


def polygon_path(points):
    path = ui.Path()
    path.move_to(*points[0])
    for point in points[1:]:
        path.line_to(*point)
    path.close()
    return path


def draw_number(text, cell_size, centre, ink, squash=1.0, axis="x"):
    """A tile's number centred on centre, squeezed along axis by squash
    (a sheet seen part edge-on). ink may carry an alpha."""
    font = digit_font(text, cell_size)
    width, height = ui.measure_string(text, font=font)
    with ui.GState():
        # Move to the centre, then scale, so the number squeezes about its middle.
        ui.concat_ctm(ui.Transform.translation(*centre))
        ui.concat_ctm(ui.Transform.scale(squash, 1) if axis == "x" else ui.Transform.scale(1, squash))
        ui.draw_string(text, rect=(-width / 2, -height / 2, width, height),
                       font=font, color=ink, alignment=ui.ALIGN_CENTER)


class FoldSheets(ui.View):
    """Draws merge folds in flight above the tiles, and runs their frame clock.

    See-through and untouchable, so swipes reach the board underneath.
    update_interval is set once; update() does nothing without folds.
    """

    def __init__(self, board):
        super().__init__()
        self.board = board
        self.touch_enabled = False
        self.flex = "WH"
        self.update_interval = 1 / 60.0

    def update(self):
        if self.superview is None:
            return
        if self.board.advance_folds(time.time()):
            self.set_needs_display()

    def draw(self):
        board = self.board
        if not board.folds and board.spawn is None:
            return
        now = time.time()
        cell_size = board.cell_metrics()[0]
        radius = cell_size * CORNER_RATIO
        for fold in board.folds:
            drawn = merge_fold.sheet(fold, board.cell_frame(fold.stop_cell),
                                     board.cell_frame(fold.cell), now)
            if drawn is None:
                continue
            (x, y, width, height), face, shade, squash, axis = drawn
            value = fold.front if face == "front" else fold.merged
            fill, ink = board.tile_look(value)
            red, green, blue = ui.parse_color(fill)[:3]
            ui.set_color((red * shade, green * shade, blue * shade))
            ui.Path.rounded_rect(x, y, width, height, min(radius, width / 2, height / 2)).fill()
            if squash >= 0.15:
                draw_number(str(value), cell_size, (x + width / 2, y + height / 2), ink, squash, axis)
        if board.spawn is not None:
            self.draw_spawn(board.spawn, now, cell_size, radius)

    def draw_spawn(self, spawn, now, cell_size, radius):
        """A new tile folding in from its centre in tiny squares, clipped to
        the tile's rounded corners, its number fading up once they land."""
        if now < spawn.start:
            return
        fill, ink = self.board.tile_look(spawn.value)
        red, green, blue = ui.parse_color(fill)[:3]
        x, y, width, height = self.board.cell_frame(spawn.cell)
        with ui.GState():
            ui.Path.rounded_rect(x, y, width, height, radius).add_clip()
            for points, shade in merge_fold.spawn_sheets(spawn, now):
                ui.set_color((red * shade, green * shade, blue * shade))
                polygon_path(points).fill()
        alpha = merge_fold.number_alpha(spawn, now)
        if alpha > 0:
            draw_number(str(spawn.value), cell_size, (x + width / 2, y + height / 2),
                        tuple(ui.parse_color(ink)[:3]) + (alpha,))


class Twenty48BoardView(ui.View):
    """Draws a Double Up board, shows its tiles as views and reports swipes."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cells = [[None] * 4 for _ in range(4)]
        self.rule = None
        self.on_swipe = None
        self._touch_start = None
        self.motion = TileMotion(POOL_SIZE)
        self.tiles = [TileView() for _ in range(POOL_SIZE)]
        for tile in self.tiles:
            self.add_subview(tile)
        self.folds = []                     # merge folds in flight (merge_fold.MergeFold)
        self.sheets = FoldSheets(self)      # added last, so drawn above every tile
        self.add_subview(self.sheets)
        self._laid_out_size = None          # layout() only acts when this changes
        self.spawn = None                   # merge_fold.Spawn while a new tile folds in

    # --- what the screen calls -------------------------------------------------

    def show(self, cells, rule):
        """Show these cells at once, starting tile identity afresh.

        For a new game, a resumed game, the preview or a direct board change.
        """
        self.finish_folds()
        self.cells = [list(row) for row in cells]
        self.rule = rule
        self.motion.reset(self.cells)
        self.set_needs_display()
        self.place_all_tiles()

    def play(self, result, cells, animate):
        """Show one swipe (a MoveResult): slide the tiles, or move them at once."""
        self.finish_folds()
        before = self.cells
        self.cells = [list(row) for row in cells]
        plan = self.motion.plan(result, self.cells)
        breadcrumb("play animate={} merges={} style={} (merge_fold build)".format(
            animate, len(plan.retired), MERGE_STYLE))
        if animate:
            self._slide(plan, before)
        else:
            self._jump(plan)

    # --- geometry --------------------------------------------------------------

    @property
    def size(self):
        return len(self.cells)

    def board_rect(self):
        """(left, top, side) of the square board, centred and top-aligned."""
        side = max(0, min(self.width, self.height) - 2 * MARGIN)
        return (self.width - side) / 2, MARGIN, side

    def cell_metrics(self, side=None):
        """(cell size, gap) for a board this many points wide (default: this one)."""
        if side is None:
            side = self.board_rect()[2]
        cell_size = side / (self.size + (self.size + 1) * GAP_RATIO)
        return cell_size, cell_size * GAP_RATIO

    def cell_frame(self, cell):
        left, top, side = self.board_rect()
        cell_size, gap = self.cell_metrics(side)
        row, col = cell
        return (left + gap + col * (cell_size + gap),
                top + gap + row * (cell_size + gap),
                cell_size, cell_size)

    def tile_look(self, value):
        """(fill, number colour) for a tile, by its step along the ramp."""
        return TILE_RAMP[self.rule.step(value) % len(TILE_RAMP)]

    def layout(self):
        """A new size: redraw the cells and put every tile back at once.

        UIKit also calls this when only the tiles change (on device,
        2026-11-01: a few ms after every swipe). Snapping then would cut
        every slide and fold short, so nothing happens unless the size has
        really changed.
        """
        size = (self.width, self.height)
        breadcrumb("layout {:.0f}x{:.0f} folds in flight {} {}".format(
            self.width, self.height, len(self.folds),
            "same size, ignored" if size == self._laid_out_size else "new size"))
        if size == self._laid_out_size:
            return
        self._laid_out_size = size
        self.finish_folds()
        self.sheets.frame = self.bounds
        self.set_needs_display()
        self.place_all_tiles()

    # --- tiles -----------------------------------------------------------------

    def place_all_tiles(self):
        """Put every tile view where the cells say, at once; hide the rest."""
        if self.rule is None:
            return
        showing = set()
        for cell, view in self.motion.at.items():
            self._place(view, cell, self.cells[cell[0]][cell[1]])
            showing.add(view)
        for view, tile in enumerate(self.tiles):
            if view not in showing:
                tile.hidden = True

    def _place(self, view, cell, value, alpha=1.0):
        tile = self.tiles[view]
        tile.frame = self.cell_frame(cell)
        tile.dress(value, self.tile_look(value), self.cell_metrics()[0])
        tile.alpha = alpha
        tile.hidden = False

    def _jump(self, plan):
        for view, _, target, value in plan.moves:
            self._place(view, target, value)
        for view, _, _ in plan.retired:
            self.tiles[view].hidden = True
        if plan.spawn is not None:
            self._place(*plan.spawn)

    def _slide(self, plan, before):
        """Slide with ui.animate. No completion callbacks: nothing runs mid-slide.

        With MERGE_STYLE "fold", partners stop beside their merge cells and
        survivors keep their old numbers; the merge folds (planned here,
        played by FoldSheets' frame clock) finish the job.
        """
        cell_size = self.cell_metrics()[0]
        folding = MERGE_STYLE == "fold" and bool(plan.retired)
        merge_cells = {target for _, _, target in plan.retired}
        for view, source, target, value in plan.moves:
            shown = before[source[0]][source[1]] if folding and target in merge_cells else value
            tile = self.tiles[view]
            tile.dress(shown, self.tile_look(shown), cell_size)
            tile.alpha = 1.0
            tile.hidden = False
        for view, _, _ in plan.retired:
            self.tiles[view].alpha = 1.0
            self.tiles[view].hidden = False
        if folding:
            survivors = {target: view for view, _, target, _ in plan.moves}
            self.folds = merge_fold.plan(plan.retired, survivors, before, self.cells,
                                         time.time() + SLIDE_SECONDS)

        def slide():
            for view, _, target, _ in plan.moves:
                self.tiles[view].frame = self.cell_frame(target)
            for view, source, target in plan.retired:
                if folding:
                    self.tiles[view].frame = self.cell_frame(merge_fold.stop_cell(source, target))
                else:
                    self.tiles[view].frame = self.cell_frame(target)
                    self.tiles[view].alpha = 0.0

        ui.animate(slide, duration=SLIDE_SECONDS)

        if plan.spawn is not None:
            # Folds in from its cell's centre in tiny squares, drawn by FoldSheets
            # on the frame clock (not a delayed ui.animate: those did not show on
            # device); the tile view itself appears once its number is up.
            view, cell, value = plan.spawn
            self._place(view, cell, value)
            self.tiles[view].hidden = True
            delay = SLIDE_SECONDS + (merge_fold.FOLD_SECONDS if folding else 0.0)
            self.spawn = merge_fold.plan_spawn(view, cell, value, self.cell_frame(cell),
                                               time.time() + delay)

    # --- merge folds -------------------------------------------------------------

    def advance_folds(self, now):
        """Frame clock step: grow the new tile, hide each fold's partner as its
        sheet lifts off, and give each survivor its merged value as the sheet
        lands. True while anything is moving."""
        moving = self._advance_spawn(now)
        if not self.folds:
            return moving
        cell_size = self.cell_metrics()[0]
        flying = []
        for fold in self.folds:
            if merge_fold.done(fold, now):
                breadcrumb("fold landed on {}".format(fold.cell))
                self._land(fold, cell_size)
                continue
            if merge_fold.started(fold, now) and not self.tiles[fold.view].hidden:
                breadcrumb("fold lifted from {}".format(fold.stop_cell))
                self.tiles[fold.view].hidden = True
            flying.append(fold)
        self.folds = flying
        return True

    def _advance_spawn(self, now):
        if self.spawn is None:
            return False
        if merge_fold.spawn_done(self.spawn, now):
            self.tiles[self.spawn.view].hidden = False
            self.spawn = None
        return True

    def finish_folds(self):
        """Land every fold in flight and finish the new tile's fold-in at once,
        so a new action starts from a settled board."""
        if self.spawn is not None:
            self.tiles[self.spawn.view].hidden = False
            self.spawn = None
            self.sheets.set_needs_display()
        if not self.folds:
            return
        cell_size = self.cell_metrics()[0]
        for fold in self.folds:
            self._land(fold, cell_size)
        self.folds = []
        self.sheets.set_needs_display()

    def _land(self, fold, cell_size):
        self.tiles[fold.view].hidden = True
        self.tiles[fold.survivor].dress(fold.merged, self.tile_look(fold.merged), cell_size)

    # --- touches ---------------------------------------------------------------

    def touch_began(self, touch):
        self._touch_start = tuple(touch.location)

    def touch_ended(self, touch):
        start, self._touch_start = self._touch_start, None
        if start is None or self.on_swipe is None:
            return
        direction = swipe_direction(start, tuple(touch.location), SWIPE_DISTANCE)
        if direction is not None:
            self.on_swipe(direction)

    # --- drawing ---------------------------------------------------------------

    def draw(self):
        """The board and every empty cell; tile views cover the filled ones."""
        left, top, side = self.board_rect()
        if side <= 0:
            return
        cell_size, _ = self.cell_metrics(side)
        radius = cell_size * CORNER_RATIO

        ui.set_color(BOARD_COLOR)
        ui.Path.rounded_rect(left, top, side, side, radius * 1.2).fill()
        ui.set_color(EMPTY_COLOR)
        for row in range(self.size):
            for col in range(self.size):
                x, y, width, height = self.cell_frame((row, col))
                ui.Path.rounded_rect(x, y, width, height, radius).fill()