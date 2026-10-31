"""
Fold screen: a scrolling library of puzzles, and the board to play them.

    Library  Random cards (Easy, Medium, Hard) at the top, then the Journey:
             chapters of curated puzzles as thumbnails, each with its par
             or your best. A chapter opens once enough of the one before is
             solved (UNLOCK_AFTER), unless UNLOCK_EVERYTHING is on.
    Play     the board, the level's colours along the bottom, Undo and
             Restart. Pick a colour, tap a triangle: its region folds over
             in the KAMI-style scatter chain (fold_motion.py). Solving shows
             Perfect (at par) or your count, then Next or Puzzles.

    Maker    draw your own puzzle (maker.py): brushes, mirrors, a palette
             of up to eight colours with lighter and darker shades. Saved
             designs appear under My puzzles; Edit on any puzzle opens it in
             the maker (your own are edited in place, others copied).

Best results live in games/fold/progress.json (lowest moves per Journey
puzzle; solved and perfect counts per Random mode). preview=True builds the
same screen without reading or writing that file.

Follows library/guides/pythonista-ui-stability.md: views are made once and
shown or hidden, one frame clock (update_interval set once) drives every
fold, no ui.delay, and the settled board is a cached image redrawn only
when a triangle lands. Breadcrumbs go to games/fold/fold.log, with the
previous run kept as fold.prev.log.
"""

import json
import os
import time
import traceback

import ui

from games.fold import collection, fold_motion, maker
from games.fold.triangles import TriangleGrid


GAME_DIR = os.path.dirname(os.path.abspath(__file__))
PROGRESS_PATH = os.path.join(GAME_DIR, "progress.json")
MY_PUZZLES_PATH = os.path.join(GAME_DIR, "my_puzzles.json")
LOG_PATH = os.path.join(GAME_DIR, "fold.log")
PREVIOUS_LOG_PATH = os.path.join(GAME_DIR, "fold.prev.log")


# --- editable feel and layout -----------------------------------------------------

STYLE = "scatter"            # fold_motion style for every move and undo
UNLOCK_AFTER = 4             # puzzles solved in a chapter to open the next
UNLOCK_EVERYTHING = False    # True opens every chapter (handy while testing)

BACKGROUND = "#f4f1ea"
INK = "#3a3a3a"
SOFT_INK = "#8a857c"
CARD = "#e9e4d8"
ACCENT = "#d9483b"
PERFECT = "#c99a2e"
BOARD_GAP = -0.6             # negative bleeds triangles together: no seams
BOARD_MARGIN = 6
THUMB_GAP = -0.3
COLUMNS = 3
PAD = 14
TOP_BAR = 44
BOTTOM_BAR = 64
FONT = "<system>"
BOLD = "<system-bold>"


# --- breadcrumbs -------------------------------------------------------------

def start_log():
    try:
        if os.path.exists(LOG_PATH):
            os.replace(LOG_PATH, PREVIOUS_LOG_PATH)
    except OSError:
        pass


def log(text):
    now = time.time()
    stamp = time.strftime("%H:%M:%S", time.localtime(now)) + ".{:03d}".format(int(now * 1000) % 1000)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write("{} {}\n".format(stamp, text))
    except OSError:
        pass


# --- drawing helpers -----------------------------------------------------------

def rgb(hex_colour):
    return tuple(int(hex_colour[index:index + 2], 16) / 255.0 for index in (1, 3, 5))


def path_from(points):
    path = ui.Path()
    path.move_to(*points[0])
    for point in points[1:]:
        path.line_to(*point)
    path.close()
    return path


def thumbnail(puzzle, width):
    """A ui.Image of the puzzle's starting board, trimmed like the game board."""
    grid = puzzle.grid(gap=THUMB_GAP)
    grid.resize(width, width * 4)
    x, y, trimmed_width, trimmed_height = grid.trimmed_frame()
    palette = [rgb(colour) for colour in puzzle.palette]
    with ui.ImageContext(trimmed_width, trimmed_height) as context:
        for cell in grid.cells():
            ui.set_color(palette[puzzle.colours[grid.index_of(cell)]])
            path_from([(px - x, py - y) for px, py in grid.corners(cell)]).fill()
        return context.get_image()


def trimmed_aspect():
    """height / width of a trimmed board."""
    grid = TriangleGrid(collection.compose.BOARD_STRIPS, collection.compose.BOARD_SLOTS)
    grid.resize(100, 1000)
    x, y, width, height = grid.trimmed_frame()
    return height / width


def new_seed():
    """A fresh seed for a Random puzzle."""
    return int(time.time() * 1000) % 1000000007


def make_label(text="", size=15, colour=INK, bold=False, align=ui.ALIGN_LEFT):
    label = ui.Label()
    label.text = text
    label.font = (BOLD if bold else FONT, size)
    label.text_color = colour
    label.alignment = align
    return label


def make_button(title, action, background=CARD, colour=INK, size=15):
    button = ui.Button(title=title)
    button.action = action
    button.background_color = background
    button.tint_color = colour
    button.corner_radius = 8
    button.font = (FONT, size)
    return button


# --- progress -------------------------------------------------------------------

class Progress:
    """Best moves per Journey puzzle, and counts per Random mode, in one JSON file.

    path None keeps everything in memory (previews).
    """

    def __init__(self, path):
        self.path = path
        self.best = {}
        self.random = {}
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as handle:
                    data = json.load(handle)
                self.best = dict(data.get("best", {}))
                self.random = dict(data.get("random", {}))
            except (OSError, ValueError):
                log("progress unreadable; starting fresh")

    def save(self):
        if not self.path:
            return
        try:
            with open(self.path, "w", encoding="utf-8") as handle:
                json.dump({"best": self.best, "random": self.random}, handle, indent=1, sort_keys=True)
        except OSError:
            log("ERROR saving progress: " + traceback.format_exc())

    def record(self, puzzle, moves):
        """Note a solve; True when it beats the puzzle's previous best."""
        if puzzle.mode:
            counts = self.random.setdefault(puzzle.mode, {"solved": 0, "perfect": 0})
            counts["solved"] += 1
            if moves <= puzzle.par:
                counts["perfect"] += 1
            self.save()
            return True
        previous = self.best.get(puzzle.puzzle_id)
        if previous is None or moves < previous:
            self.best[puzzle.puzzle_id] = moves
            self.save()
            return True
        return False

    def solved_in(self, puzzles):
        return sum(1 for puzzle in puzzles if puzzle.puzzle_id in self.best)


# --- the board -----------------------------------------------------------------

class BoardView(ui.View):
    """Draws the board: a cached image of the settled colours, plus any
    sheets in motion on top. One frame clock drives every fold."""

    def __init__(self, on_tap, on_settled):
        super().__init__()
        self.on_tap = on_tap
        self.on_settled = on_settled
        self.background_color = BACKGROUND
        self.grid = None
        self.board = None
        self.palette = []
        self.shown = {}
        self.folds = []
        self.base_image = None
        self.base_dirty = True
        self.update_interval = 1 / 60.0

    def load(self, puzzle):
        self.folds = []
        self.grid = puzzle.grid(margin=BOARD_MARGIN, gap=BOARD_GAP)
        self.board = puzzle.board(self.grid)
        self.palette = [rgb(colour) for colour in puzzle.palette]
        self.shown = dict(self.board.colours)
        self.grid.resize(self.width, self.height)
        self.base_dirty = True
        self.set_needs_display()

    def layout(self):
        if self.grid is not None:
            self.grid.resize(self.width, self.height)
            self.base_dirty = True
            self.set_needs_display()

    # --- moves -------------------------------------------------------------------

    def play(self, cell, colour):
        """Flood cell's region with colour and start its folds. Returns the Move or None."""
        self.finish()
        move = self.board.flood(cell, colour)
        if move is None:
            return None
        self.folds = fold_motion.plan(move, time.time(), STYLE, self.grid)
        self.apply_landed(time.time())
        self.set_needs_display()
        return move

    def undo(self):
        """Take back the last move, playing its folds backwards."""
        self.finish()
        move = self.board.undo()
        if move is not None:
            self.folds = fold_motion.plan_undo(move, time.time(), STYLE, self.grid)
            self.apply_landed(time.time())
            self.set_needs_display()
        return move

    def finish(self):
        """Snap any folds to their end, so a new action starts from a settled board."""
        if self.folds:
            for fold in self.folds:
                self.shown[fold.cell] = fold.colour
            self.folds = []
            self.base_dirty = True
            self.set_needs_display()

    def apply_landed(self, now):
        for fold in self.folds:
            if fold_motion.shows_new_colour(fold, now) and self.shown.get(fold.cell) != fold.colour:
                self.shown[fold.cell] = fold.colour
                self.base_dirty = True

    @property
    def moving(self):
        return bool(self.folds)

    # --- frame clock -------------------------------------------------------------

    def update(self):
        if self.superview is None or not self.folds:
            return
        now = time.time()
        self.apply_landed(now)
        self.folds = [fold for fold in self.folds if not fold_motion.done(fold, now)]
        self.set_needs_display()
        if not self.folds:
            self.on_settled()

    # --- drawing -----------------------------------------------------------------

    def render_base(self):
        with ui.ImageContext(self.width, self.height) as context:
            for cell in self.grid.cells():
                ui.set_color(self.palette[self.shown[cell]])
                path_from(self.grid.corners(cell)).fill()
            return context.get_image()

    def draw(self):
        if self.grid is None or self.width <= 0 or self.height <= 0:
            return
        if self.base_dirty or self.base_image is None:
            self.base_image = self.render_base()
            self.base_dirty = False
        x, y, width, height = self.grid.trimmed_frame()
        with ui.GState():
            ui.Path.rect(x, y, width, height).add_clip()
            self.base_image.draw(0, 0, self.width, self.height)
            now = time.time()
            for fold in self.folds:
                drawn = fold_motion.shape(self.grid, fold, now)
                if drawn is None:
                    continue
                points, shade = drawn
                red, green, blue = self.palette[fold.sheet_colour]
                ui.set_color((red * shade, green * shade, blue * shade))
                path_from(points).fill()

    def touch_began(self, touch):
        try:
            if self.grid is None:
                return
            x, y, width, height = self.grid.trimmed_frame()
            px, py = touch.location
            if not (x <= px <= x + width and y <= py <= y + height):
                return
            cell = self.grid.cell_at(touch.location)
            if cell is not None:
                self.on_tap(cell)
        except Exception:
            log("ERROR in board touch: " + traceback.format_exc())


class ColourBar(ui.View):
    """The puzzle's colours as chips; tap one to choose it."""

    def __init__(self, on_choose):
        super().__init__()
        self.on_choose = on_choose
        self.palette = []
        self.selected = 0

    def draw(self):
        if not self.palette:
            return
        width = self.width / len(self.palette)
        for index, colour in enumerate(self.palette):
            ui.set_color(colour)
            ui.Path.rect(index * width, 0, width + 0.5, self.height).fill()
            if index == self.selected:
                ui.set_color("white")
                ui.Path.rounded_rect(index * width + width * 0.3, 8, width * 0.4, 6, 3).fill()

    def touch_began(self, touch):
        try:
            if self.palette:
                index = int(touch.location[0] // (self.width / len(self.palette)))
                self.on_choose(max(0, min(index, len(self.palette) - 1)))
        except Exception:
            log("ERROR in colour bar: " + traceback.format_exc())


# --- playing a puzzle -----------------------------------------------------------

class PlayView(ui.View):
    """One puzzle: top bar, board, colours, and the result card."""

    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.background_color = BACKGROUND
        self.puzzle = None
        self.solved = False

        self.back_button = make_button("‹ Puzzles", self.back_tapped, background=BACKGROUND)
        self.restart_button = make_button("Restart", self.restart_tapped, background=BACKGROUND)
        self.edit_button = make_button("Edit", self.edit_tapped, background=BACKGROUND)
        self.title_label = make_label(size=17, bold=True, align=ui.ALIGN_CENTER)
        self.status_label = make_label(size=14, colour=SOFT_INK, align=ui.ALIGN_CENTER)
        self.board_view = BoardView(self.tap, self.settled)
        self.undo_button = make_button("Undo", self.undo_tapped, background="#2b2a2a", colour="white")
        self.undo_button.corner_radius = 0
        self.bar = ColourBar(self.choose)

        self.card = ui.View()
        self.card.background_color = (1, 1, 1, 0.96)
        self.card.corner_radius = 14
        self.card_title = make_label(size=26, bold=True, align=ui.ALIGN_CENTER)
        self.card_detail = make_label(size=15, colour=SOFT_INK, align=ui.ALIGN_CENTER)
        self.next_button = make_button("Next", self.next_tapped, background=ACCENT, colour="white")
        self.home_button = make_button("Puzzles", self.back_tapped)
        for view in (self.card_title, self.card_detail, self.next_button, self.home_button):
            self.card.add_subview(view)
        self.card.hidden = True

        for view in (self.back_button, self.restart_button, self.edit_button, self.title_label,
                     self.status_label, self.board_view, self.undo_button, self.bar, self.card):
            self.add_subview(view)

    def layout(self):
        width, height = self.width, self.height
        self.back_button.frame = (6, 6, 96, 32)
        self.restart_button.frame = (width - 76, 6, 70, 32)
        self.edit_button.frame = (width - 126, 6, 48, 32)
        self.title_label.frame = (100, 4, max(0, width - 228), 22)
        self.status_label.frame = (100, 24, max(0, width - 228), 18)
        top = TOP_BAR + 4
        self.board_view.frame = (0, top, width, max(0, height - BOTTOM_BAR - top))
        self.undo_button.frame = (0, height - BOTTOM_BAR, 64, BOTTOM_BAR)
        self.bar.frame = (64, height - BOTTOM_BAR, width - 64, BOTTOM_BAR)
        card_width, card_height = min(300, width - 40), 170
        self.card.frame = ((width - card_width) / 2, (height - card_height) / 2 - 20, card_width, card_height)
        self.card_title.frame = (10, 18, card_width - 20, 34)
        self.card_detail.frame = (10, 56, card_width - 20, 22)
        button_width = (card_width - 3 * 14) / 2
        self.home_button.frame = (14, card_height - 58, button_width, 42)
        self.next_button.frame = (28 + button_width, card_height - 58, button_width, 42)

    def open(self, puzzle):
        self.puzzle = puzzle
        self.solved = False
        self.card.hidden = True
        self.title_label.text = puzzle.title
        self.board_view.load(puzzle)
        self.bar.palette = list(puzzle.palette)
        self.bar.selected = 1 if len(puzzle.palette) > 1 else 0
        self.bar.set_needs_display()
        self.next_button.title = "Another" if puzzle.mode else "Next"
        self.refresh_status()
        log("open {} (par {})".format(puzzle.puzzle_id, puzzle.par))

    def refresh_status(self):
        moves = self.board_view.board.moves_made
        self.status_label.text = "Moves {}  ·  Par {}".format(moves, self.puzzle.par)

    # --- actions ---------------------------------------------------------------

    def choose(self, colour):
        self.bar.selected = colour
        self.bar.set_needs_display()

    def tap(self, cell):
        if self.solved:
            return
        move = self.board_view.play(cell, self.bar.selected)
        if move is None:
            return
        log("tap {} colour {}: {} triangles".format(cell, self.bar.selected, len(move.cells)))
        self.refresh_status()
        if self.board_view.board.is_solved():
            self.solved = True
            moves = self.board_view.board.moves_made
            self.screen.progress.record(self.puzzle, moves)
            log("solved {} in {} (par {})".format(self.puzzle.puzzle_id, moves, self.puzzle.par))

    def settled(self):
        """Called by the board's frame clock once every fold has landed."""
        if self.solved and self.card.hidden:
            self.show_result()

    def show_result(self):
        moves = self.board_view.board.moves_made
        par = self.puzzle.par
        if moves <= par:
            self.card_title.text = "Perfect!"
            self.card_title.text_color = PERFECT
        else:
            self.card_title.text = "Solved"
            self.card_title.text_color = INK
        self.card_detail.text = "{} move{}  ·  par {}".format(moves, "" if moves == 1 else "s", par)
        self.next_button.enabled = bool(self.puzzle.mode) or self.screen.next_puzzle(self.puzzle) is not None
        self.card.hidden = False
        self.card.bring_to_front()

    def undo_tapped(self, sender):
        try:
            if self.solved:
                return
            self.board_view.undo()
            self.refresh_status()
        except Exception:
            log("ERROR in undo: " + traceback.format_exc())

    def restart_tapped(self, sender):
        try:
            self.open(self.puzzle)
        except Exception:
            log("ERROR in restart: " + traceback.format_exc())

    def back_tapped(self, sender):
        self.board_view.finish()
        self.screen.show_library()

    def edit_tapped(self, sender):
        try:
            self.board_view.finish()
            own = self.puzzle.chapter == "mine"
            self.screen.open_maker(maker.Design.from_puzzle(self.puzzle, keep_identity=own))
        except Exception:
            log("ERROR opening the maker: " + traceback.format_exc())

    def next_tapped(self, sender):
        try:
            self.screen.play_next(self.puzzle)
        except Exception:
            log("ERROR in next: " + traceback.format_exc())


# --- the maker -------------------------------------------------------------------

class MakerBoard(ui.View):
    """The design, drawn flat. Touch and drag to paint with the maker's brush."""

    def __init__(self, maker_view):
        super().__init__()
        self.maker_view = maker_view
        self.background_color = BACKGROUND
        self.grid = None
        self.last_cell = None

    def load(self, design):
        self.grid = design.grid.__class__(design.grid.strips, design.grid.slots, "columns",
                                          BOARD_MARGIN, BOARD_GAP)
        self.grid.resize(self.width, self.height)
        self.set_needs_display()

    def layout(self):
        if self.grid is not None:
            self.grid.resize(self.width, self.height)
            self.set_needs_display()

    def draw(self):
        design = self.maker_view.design
        if self.grid is None or design is None or self.width <= 0:
            return
        palette = [rgb(colour) for colour in design.palette]
        x, y, width, height = self.grid.trimmed_frame()
        with ui.GState():
            ui.Path.rect(x, y, width, height).add_clip()
            for cell in self.grid.cells():
                ui.set_color(palette[design.colours[self.grid.index_of(cell)]])
                path_from(self.grid.corners(cell)).fill()

    def flat_point(self, location):
        """A view point in the design's flat coordinates (side 1)."""
        side = self.grid.side or 1.0
        return ((location[1] - self.grid.top) / side, (location[0] - self.grid.left) / side)

    def paint_at(self, location, first):
        cell = self.grid.cell_at(location)
        if cell is None or (cell == self.last_cell and not first):
            return
        self.last_cell = cell
        if self.maker_view.brush == "fill" and not first:
            return
        self.maker_view.dab(cell, self.flat_point(location), first)

    def touch_began(self, touch):
        try:
            if self.grid is not None:
                self.last_cell = None
                self.paint_at(touch.location, True)
        except Exception:
            log("ERROR in maker touch: " + traceback.format_exc())

    def touch_moved(self, touch):
        try:
            if self.grid is not None:
                self.paint_at(touch.location, False)
        except Exception:
            log("ERROR in maker drag: " + traceback.format_exc())


class PaletteStrip(ColourBar):
    """The design's colours; the chosen one is marked, and its number shows."""

    def draw(self):
        super().draw()
        if not self.palette:
            return
        width = self.width / len(self.palette)
        for index in range(len(self.palette)):
            red, green, blue = rgb(self.palette[index])
            light = 0.299 * red + 0.587 * green + 0.114 * blue > 0.6
            ui.draw_string(str(index + 1), rect=(index * width, self.height - 22, width, 18),
                           font=(FONT, 12), color=("#333333" if light else "#ffffff"),
                           alignment=ui.ALIGN_CENTER)


class MakerView(ui.View):
    """Draw a puzzle: brushes, mirrors, palette tools, Undo, Save, Copy, Delete."""

    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.background_color = BACKGROUND
        self.design = None
        self.brush = "triangle"
        self.mirror = "off"
        self.confirm_delete = False

        self.back_button = make_button("‹ Puzzles", self.back_tapped, background=BACKGROUND)
        self.save_button = make_button("Save", self.save_tapped, background=ACCENT, colour="white")
        self.title_label = make_label(size=17, bold=True, align=ui.ALIGN_CENTER)
        self.brush_control = ui.SegmentedControl()
        self.brush_control.segments = ("Triangle", "Hexagon", "Fill")
        self.brush_control.selected_index = 0
        self.brush_control.action = self.brush_changed
        self.mirror_control = ui.SegmentedControl()
        self.mirror_control.segments = ("No mirror", "↔", "↕", "Both")
        self.mirror_control.selected_index = 0
        self.mirror_control.action = self.mirror_changed
        self.undo_button = make_button("Undo", self.undo_tapped)
        self.board = MakerBoard(self)
        self.status_label = make_label(size=13, colour=SOFT_INK, align=ui.ALIGN_CENTER)
        self.strip = PaletteStrip(self.choose)
        self.tool_buttons = [
            make_button("+ Lighter", self.lighter_tapped, size=13),
            make_button("+ Darker", self.darker_tapped, size=13),
            make_button("+ New", self.new_colour_tapped, size=13),
            make_button("Remove", self.remove_tapped, size=13),
            make_button("Copy", self.copy_tapped, size=13),
            make_button("Delete", self.delete_tapped, size=13),
        ]
        for view in [self.back_button, self.save_button, self.title_label, self.brush_control,
                     self.mirror_control, self.undo_button, self.board, self.status_label,
                     self.strip] + self.tool_buttons:
            self.add_subview(view)

    def layout(self):
        width, height = self.width, self.height
        self.back_button.frame = (6, 6, 96, 32)
        self.save_button.frame = (width - 76, 6, 70, 32)
        self.title_label.frame = (104, 8, max(0, width - 188), 26)
        self.brush_control.frame = (PAD, 46, width - 2 * PAD, 30)
        self.mirror_control.frame = (PAD, 82, width - 2 * PAD - 74, 30)
        self.undo_button.frame = (width - PAD - 66, 82, 66, 30)
        tools_top = height - 44
        strip_top = tools_top - 52
        status_top = strip_top - 22
        self.board.frame = (0, 118, width, max(0, status_top - 120))
        self.status_label.frame = (PAD, status_top, width - 2 * PAD, 20)
        self.strip.frame = (0, strip_top, width, 48)
        gap = 6
        button_width = (width - 2 * PAD - gap * (len(self.tool_buttons) - 1)) / len(self.tool_buttons)
        for index, button in enumerate(self.tool_buttons):
            button.frame = (PAD + index * (button_width + gap), tools_top, button_width, 34)

    # --- state -------------------------------------------------------------------

    def open(self, design):
        self.design = design
        self.confirm_delete = False
        self.board.load(design)
        self.strip.selected = 1 if len(design.palette) > 1 else 0
        self.refresh("Pick a colour, then draw. Save works out par.")
        log("maker open {}".format(design.puzzle_id or "new design"))

    def refresh(self, message=None):
        design = self.design
        self.title_label.text = design.title or "New puzzle"
        self.strip.palette = list(design.palette)
        self.strip.selected = min(self.strip.selected, len(design.palette) - 1)
        self.strip.set_needs_display()
        self.board.set_needs_display()
        self.status_label.text = message or design.summary()
        full = not design.can_add()
        for button in self.tool_buttons[:3]:
            button.enabled = not full
            button.alpha = 0.4 if full else 1.0
        own = design.puzzle_id is not None and design.puzzle_id.startswith("mine-")
        self.tool_buttons[5].hidden = not own
        self.tool_buttons[5].title = "Sure?" if self.confirm_delete else "Delete"

    def dab(self, cell, flat_point, first):
        """Called by the board for each new cell under the finger."""
        if first:
            self.design.remember()
        if self.design.dab(self.brush, cell, self.strip.selected, self.mirror, flat_point):
            self.board.set_needs_display()
            self.status_label.text = self.design.summary()

    # --- controls -----------------------------------------------------------------

    def choose(self, index):
        self.strip.selected = index
        self.strip.set_needs_display()

    def brush_changed(self, sender):
        self.brush = maker.BRUSHES[sender.selected_index]

    def mirror_changed(self, sender):
        self.mirror = maker.MIRRORS[sender.selected_index]

    def palette_change(self, change):
        """Run a palette change with Undo support, then select its new colour."""
        try:
            self.confirm_delete = False
            self.design.remember()
            result = change()
            if result is None or result is False:
                self.design.history.pop()
            elif result is not True:
                self.strip.selected = result
            self.refresh()
        except Exception:
            log("ERROR changing the palette: " + traceback.format_exc())

    def lighter_tapped(self, sender):
        self.palette_change(lambda: self.design.add_shade(self.strip.selected, maker.SHADE_STEP))

    def darker_tapped(self, sender):
        self.palette_change(lambda: self.design.add_shade(self.strip.selected, -maker.SHADE_STEP))

    def new_colour_tapped(self, sender):
        self.palette_change(self.design.add_new)

    def remove_tapped(self, sender):
        self.palette_change(lambda: self.design.remove_colour(self.strip.selected))

    def undo_tapped(self, sender):
        if self.design.undo():
            self.refresh()

    def save_tapped(self, sender):
        try:
            self.confirm_delete = False
            if len(set(self.design.colours)) < 2:
                self.refresh("Use at least two colours to make a puzzle.")
                return
            began = time.time()
            record = self.screen.mine.save_design(self.design)
            took = (time.time() - began) * 1000
            par = "par {}".format(record["par"]) if record["exact"] else "par ≤ {}".format(record["par"])
            log("saved {}: {} in {:.0f} ms".format(record["id"], par, took))
            self.refresh("Saved {} · {}".format(record["title"], par))
        except Exception:
            log("ERROR saving: " + traceback.format_exc())
            self.refresh("Couldn't save: the log has the details.")

    def copy_tapped(self, sender):
        """Copy the design as one line of JSON (saved first, so it carries par)."""
        try:
            if self.design.puzzle_id is None or not self.design.puzzle_id.startswith("mine-"):
                self.refresh("Save first, then Copy.")
                return
            record = self.screen.mine.save_design(self.design)
            import clipboard
            clipboard.set(maker.share_text(record))
            self.refresh("Copied {} to the clipboard".format(record["title"]))
        except Exception:
            log("ERROR copying: " + traceback.format_exc())
            self.refresh("Couldn't copy here.")

    def delete_tapped(self, sender):
        if not self.confirm_delete:
            self.confirm_delete = True
            self.refresh("Tap Sure? to delete this puzzle.")
            return
        self.screen.mine.delete(self.design.puzzle_id)
        log("deleted {}".format(self.design.puzzle_id))
        self.screen.show_library()

    def back_tapped(self, sender):
        self.screen.show_library()


# --- the library ------------------------------------------------------------------

class LibraryView(ui.View):
    """Random cards, then every Journey chapter as a grid of thumbnails.

    Pythonista cannot subclass ui.ScrollView, so this view holds one and
    puts everything inside it."""

    def __init__(self, screen):
        super().__init__()
        self.screen = screen
        self.background_color = BACKGROUND
        self.scroll = ui.ScrollView()
        self.scroll.background_color = BACKGROUND
        self.scroll.always_bounce_vertical = True
        self.add_subview(self.scroll)

        self.heading = make_label("Fold", size=34, bold=True)
        self.subheading = make_label("Fold the paper until the board is one colour.", size=14, colour=SOFT_INK)
        self.random_heading = make_label("Random", size=20, bold=True)
        self.random_cards = []
        for mode, title, settings in collection.RANDOM_MODES:
            low, high = settings["par"]
            button = make_button("", self.random_tapped)
            button.name = mode
            title_label = make_label(title, size=16, bold=True, align=ui.ALIGN_CENTER)
            par_label = make_label("par {}–{}".format(low, high), size=13, colour=SOFT_INK, align=ui.ALIGN_CENTER)
            stats_label = make_label("", size=12, colour=SOFT_INK, align=ui.ALIGN_CENTER)
            for label in (title_label, par_label, stats_label):
                label.touch_enabled = False
                button.add_subview(label)
            self.random_cards.append((mode, button, title_label, par_label, stats_label))
            self.scroll.add_subview(button)

        self.mine_heading = make_label("My puzzles", size=20, bold=True)
        self.new_button = make_button("+ New puzzle", self.new_tapped, background=CARD)
        self.mine_tiles = []      # (button, badge) pool, grown as puzzles are saved
        self.mine_puzzles = []
        self.scroll.add_subview(self.mine_heading)
        self.scroll.add_subview(self.new_button)

        self.chapter_rows = []
        for chapter_id, title, puzzles in screen.chapters:
            heading = make_label("{}. {}".format(len(self.chapter_rows) + 1, title), size=20, bold=True)
            count = make_label("", size=13, colour=SOFT_INK, align=ui.ALIGN_RIGHT)
            tiles = []
            for puzzle in puzzles:
                button = ui.Button()
                button.action = self.puzzle_tapped
                button.name = puzzle.puzzle_id
                button.corner_radius = 6
                badge = make_label("", size=12, colour=SOFT_INK, align=ui.ALIGN_CENTER)
                tiles.append((puzzle, button, badge))
                self.scroll.add_subview(button)
                self.scroll.add_subview(badge)
            self.chapter_rows.append((chapter_id, puzzles, heading, count, tiles))
            self.scroll.add_subview(heading)
            self.scroll.add_subview(count)
        for view in (self.heading, self.subheading, self.random_heading):
            self.scroll.add_subview(view)
        self.thumb_width = 0

    def layout(self):
        self.scroll.frame = (0, 0, self.width, self.height)
        width = self.width
        inner = width - 2 * PAD
        y = 18
        self.heading.frame = (PAD, y, inner, 40)
        y += 42
        self.subheading.frame = (PAD, y, inner, 20)
        y += 34
        self.random_heading.frame = (PAD, y, inner, 26)
        y += 32
        count = len(self.random_cards)
        card_width = (inner - (count - 1) * 8) / count
        for index, (mode, button, title_label, par_label, stats_label) in enumerate(self.random_cards):
            button.frame = (PAD + index * (card_width + 8), y, card_width, 84)
            title_label.frame = (0, 12, card_width, 24)
            par_label.frame = (0, 38, card_width, 18)
            stats_label.frame = (0, 58, card_width, 16)
        y += 84 + 26

        tile_width = (inner - (COLUMNS - 1) * 12) / COLUMNS
        tile_height = tile_width * self.screen.aspect

        self.mine_heading.frame = (PAD, y, inner * 0.5, 26)
        self.new_button.frame = (PAD + inner - 130, y - 2, 130, 30)
        y += 34
        for index, (button, badge) in enumerate(self.mine_tiles):
            if index >= len(self.mine_puzzles):
                continue
            row, column = divmod(index, COLUMNS)
            left = PAD + column * (tile_width + 12)
            top = y + row * (tile_height + 34)
            button.frame = (left, top, tile_width, tile_height)
            button.background_image = self.screen.thumbnail_for(self.mine_puzzles[index], tile_width)
            badge.frame = (left, top + tile_height + 4, tile_width, 20)
        rows = (len(self.mine_puzzles) + COLUMNS - 1) // COLUMNS
        y += rows * (tile_height + 34) + 14

        if abs(tile_width - self.thumb_width) > 1:
            self.thumb_width = tile_width
            for chapter_id, puzzles, heading, count, tiles in self.chapter_rows:
                for puzzle, button, badge in tiles:
                    button.background_image = self.screen.thumbnail_for(puzzle, tile_width)
        for chapter_id, puzzles, heading, count, tiles in self.chapter_rows:
            heading.frame = (PAD, y, inner * 0.7, 26)
            count.frame = (PAD + inner * 0.5, y + 4, inner * 0.5, 20)
            y += 34
            for index, (puzzle, button, badge) in enumerate(tiles):
                row, column = divmod(index, COLUMNS)
                left = PAD + column * (tile_width + 12)
                top = y + row * (tile_height + 34)
                button.frame = (left, top, tile_width, tile_height)
                badge.frame = (left, top + tile_height + 4, tile_width, 20)
            rows = (len(tiles) + COLUMNS - 1) // COLUMNS
            y += rows * (tile_height + 34) + 14
        self.scroll.content_size = (width, y + 30)

    def refresh(self):
        """Badges, counts and locks from progress; My puzzles from the maker's file."""
        progress = self.screen.progress
        self.mine_puzzles = self.screen.mine.puzzles()
        while len(self.mine_tiles) < len(self.mine_puzzles):
            button = ui.Button()
            button.action = self.mine_tapped
            button.corner_radius = 6
            badge = make_label("", size=12, colour=SOFT_INK, align=ui.ALIGN_CENTER)
            self.scroll.add_subview(button)
            self.scroll.add_subview(badge)
            self.mine_tiles.append((button, badge))
        for index, (button, badge) in enumerate(self.mine_tiles):
            showing = index < len(self.mine_puzzles)
            button.hidden = badge.hidden = not showing
            if showing:
                puzzle = self.mine_puzzles[index]
                button.name = puzzle.puzzle_id
                self.set_badge(badge, puzzle)
        if self.width > 0:
            self.layout()
        for mode, button, title_label, par_label, stats_label in self.random_cards:
            counts = progress.random.get(mode, {})
            solved = counts.get("solved", 0)
            stats_label.text = "{} ✓  {} ★".format(solved, counts.get("perfect", 0)) if solved else ""
        previous_title = None
        for (chapter_id, puzzles, heading, count, tiles), (same_id, title, same) in zip(
                self.chapter_rows, self.screen.chapters):
            open_ = self.screen.chapter_open(chapter_id)
            solved = progress.solved_in(puzzles)
            if open_:
                count.text = "{} / {}".format(solved, len(puzzles))
            else:
                count.text = "Solve {} in {} to open".format(UNLOCK_AFTER, previous_title)
            previous_title = title
            for puzzle, button, badge in tiles:
                button.enabled = open_
                button.alpha = 1.0 if open_ else 0.3
                self.set_badge(badge, puzzle)

    def set_badge(self, badge, puzzle):
        best = self.screen.progress.best.get(puzzle.puzzle_id)
        if best is None:
            badge.text = "par {}".format(puzzle.par)
            badge.text_color = SOFT_INK
        elif best <= puzzle.par:
            badge.text = "★ Perfect"
            badge.text_color = PERFECT
        else:
            badge.text = "{} moves · par {}".format(best, puzzle.par)
            badge.text_color = INK

    def mine_tapped(self, sender):
        try:
            for puzzle in self.mine_puzzles:
                if puzzle.puzzle_id == sender.name:
                    self.screen.open_puzzle(puzzle)
        except Exception:
            log("ERROR opening my puzzle: " + traceback.format_exc())

    def new_tapped(self, sender):
        try:
            self.screen.open_maker(maker.Design())
        except Exception:
            log("ERROR opening the maker: " + traceback.format_exc())

    def puzzle_tapped(self, sender):
        try:
            self.screen.open_puzzle(self.screen.puzzle_by_id[sender.name])
        except Exception:
            log("ERROR opening puzzle: " + traceback.format_exc())

    def random_tapped(self, sender):
        try:
            seed = new_seed()
            began = time.time()
            puzzle = collection.random_puzzle(sender.name, seed)
            log("random {} seed {}: par {} in {:.0f} ms".format(sender.name, seed, puzzle.par,
                                                                   (time.time() - began) * 1000))
            self.screen.open_puzzle(puzzle)
        except Exception:
            log("ERROR making random puzzle: " + traceback.format_exc())


# --- the screen -----------------------------------------------------------------

class FoldScreen(ui.View):
    """Library and play view, made once; one is shown at a time."""

    def __init__(self, preview=False):
        super().__init__()
        if not preview:
            start_log()
            log("launch")
        self.background_color = BACKGROUND
        self.preview = preview
        self.progress = Progress(None if preview else PROGRESS_PATH)
        self.mine = maker.MyPuzzles(None if preview else MY_PUZZLES_PATH)
        self.chapters = collection.chapters()
        self.journey = [puzzle for chapter_id, title, puzzles in self.chapters for puzzle in puzzles]
        self.puzzle_by_id = {puzzle.puzzle_id: puzzle for puzzle in self.journey}
        self.aspect = trimmed_aspect()
        self.thumbnails = {}
        self.library = LibraryView(self)
        self.player = PlayView(self)
        self.maker = MakerView(self)
        for view in (self.library, self.player, self.maker):
            self.add_subview(view)
        self.player.hidden = True
        self.maker.hidden = True
        # Header contract (gamecore/game.py). The shell replaces the callback.
        self.header_subtitle = "Puzzles"
        self.on_header_changed = None
        if preview:
            self.touch_enabled = False
        self.library.refresh()

    def layout(self):
        for view in (self.library, self.player, self.maker):
            view.frame = (0, 0, self.width, self.height)

    def thumbnail_for(self, puzzle, width):
        key = (puzzle.puzzle_id, int(width), tuple(puzzle.colours), tuple(puzzle.palette))
        if key not in self.thumbnails:
            self.thumbnails[key] = thumbnail(puzzle, width)
        return self.thumbnails[key]

    def chapter_open(self, chapter_id):
        if UNLOCK_EVERYTHING:
            return True
        for index, (this_id, title, puzzles) in enumerate(self.chapters):
            if this_id == chapter_id:
                if index == 0:
                    return True
                return self.progress.solved_in(self.chapters[index - 1][2]) >= UNLOCK_AFTER
        return False

    def next_puzzle(self, puzzle):
        """The Journey puzzle after this one, if its chapter is open, or your
        next saved puzzle; else None."""
        if puzzle.chapter == "mine":
            ids = [mine.puzzle_id for mine in self.library.mine_puzzles]
            if puzzle.puzzle_id in ids and ids.index(puzzle.puzzle_id) + 1 < len(ids):
                return self.library.mine_puzzles[ids.index(puzzle.puzzle_id) + 1]
            return None
        position = self.journey.index(puzzle)
        if position + 1 < len(self.journey):
            following = self.journey[position + 1]
            if self.chapter_open(following.chapter):
                return following
        return None

    def play_next(self, puzzle):
        """Next on the result card: a fresh Random puzzle of the same mode, or
        the next Journey puzzle."""
        if puzzle.mode:
            self.open_puzzle(collection.random_puzzle(puzzle.mode, new_seed()))
            return
        following = self.next_puzzle(puzzle)
        if following is not None:
            self.open_puzzle(following)

    def open_puzzle(self, puzzle):
        self.player.open(puzzle)
        self.show_only(self.player)
        self.set_subtitle(puzzle.title)

    def open_maker(self, design):
        self.maker.open(design)
        self.show_only(self.maker)
        self.set_subtitle("Maker")

    def show_library(self):
        self.library.refresh()
        self.show_only(self.library)
        self.set_subtitle("Puzzles")

    def show_only(self, shown):
        for view in (self.library, self.player, self.maker):
            view.hidden = view is not shown

    # --- header contract -----------------------------------------------------

    def set_subtitle(self, text):
        if text == self.header_subtitle:
            return
        self.header_subtitle = text
        if self.on_header_changed is not None:
            self.on_header_changed()

    def handle_back(self):
        """The shell's Back: from a puzzle or the maker, return to the library and stay in Fold."""
        if not self.player.hidden or not self.maker.hidden:
            self.player.board_view.finish()
            self.show_library()
            return True
        return False
