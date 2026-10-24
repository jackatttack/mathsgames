"""
The Gradient board: tile views, touches, swaps, the opening shuffle and the
finishing wave.

The screen owns the game; this view shows it. It reads the board model
(rules.GradientBoard) to draw, and asks the screen to make each swap through
on_swap(first, second), which returns True once the swap is made. Only then
does anything move on screen.

Input: drag a tile onto another, or tap one and then another. Anchored tiles
(dotted) never move.

Motion runs on one frame clock: update() with update_interval set once,
idle unless something is moving (see the pythonista-ui-stability guide).

    swap     both tiles travel on arcs that pass beside each other and
             settle with a small overshoot (swap_motion.py), as chosen in
             labs/gradient_swap_lab.py
    intro    a new level shows solved for a moment, then every moved tile
             arcs out to its dealt cell; a touch skips to the end
    wave     once solved, pulses ripple out from the last tile placed, then
             the gaps and dots fade so the gradient shows whole (wave.py)

Lifting a pressed tile and settling a released one use one short
ui.animate inside the touch, with no completion callback.
"""

import math
import random
import time

import ui

from style import theme
from games.gradient import levels, swap_motion, wave


TEXT = theme.color("text")
DOT_COLOR = "#141418"        # anchor dots stay dark on every tile colour

# --- editable look and feel ----------------------------------------------------

MARGIN = 12
GAP = 1.0                    # points between tiles while playing; none once solved
MAX_TILE_ASPECT = 1.3        # tiles may be this much taller than wide, never wider than tall
DOT_RATIO = 0.16             # anchor dot size as a share of the tile's shorter side
SELECT_BORDER = 2.5
HIGHLIGHT_BORDER = 3
LIFT_GROW = 0.18             # a lifted tile grows by this share of its size
LIFT_SECONDS = 0.08
SETTLE_SECONDS = 0.18
SWAP_SECONDS = 0.32
DRAG_START = 8               # points a finger moves before a tap becomes a drag
INTRO_HOLD = 1.0             # the solved board shows this long before the shuffle
INTRO_SECONDS = 0.9          # one tile's flight out to its dealt cell
INTRO_SWEEP = 0.9            # tiles leave in a sweep from the top-left corner over this long
INTRO_BEND = 0.08            # a gentler bow than a swap, so crossing paths stay readable
INTRO_OVERSHOOT = 0.3        # and a softer landing
CLOSE_SECONDS = 0.4          # gaps and dots fading once the wave has passed
FRAME_INTERVAL = 1 / 60

POOL_SIZE = max(
    cols * rows
    for settings in levels.DIFFICULTIES.values()
    for cols, rows in settings["sizes"]
)


class TileView(ui.View):
    """One tile's colour, with a dot when it is anchored. One view per tile, made once."""

    def __init__(self):
        super().__init__()
        self.touch_enabled = False      # touches go to the board underneath
        self.hidden = True
        self.dot = ui.View()
        self.dot.touch_enabled = False
        self.dot.background_color = DOT_COLOR
        self.dot.flex = "LRTB"          # stays centred while the tile grows or shrinks
        self.add_subview(self.dot)

    def dress(self, rgb, anchored, frame):
        """Colour the tile and size its dot for a tile of this frame."""
        self.background_color = rgb
        self.border_width = 0
        self.dot.hidden = not anchored
        size = min(frame[2], frame[3]) * DOT_RATIO
        self.dot.frame = ((frame[2] - size) / 2, (frame[3] - size) / 2, size, size)
        self.dot.corner_radius = size / 2


class GradientBoardView(ui.View):
    """Shows a GradientBoard and turns touches into swap requests."""

    def __init__(self):
        super().__init__()
        self.model = None
        self.on_swap = None          # set by the screen: on_swap(first, second) -> bool
        self.locked = False          # the theme preview: touches do nothing
        self.seamless = False        # solved and shown whole: no gaps, no dots
        self.cols, self.rows = 1, 1

        self.tiles = [TileView() for _ in range(POOL_SIZE)]
        for tile in self.tiles:
            self.add_subview(tile)
        self.highlight = ui.View()
        self.highlight.touch_enabled = False
        self.highlight.background_color = (0, 0, 0, 0)
        self.highlight.border_width = HIGHLIGHT_BORDER
        self.highlight.border_color = TEXT
        self.highlight.hidden = True
        self.add_subview(self.highlight)

        self.selected = None         # tap-tap: the first tile picked, by cell
        self.press = None            # the finger currently down, if any
        self.tracks = []             # moving tiles: (tile, start, end, side, delay, seconds, bend, overshoot)
        self.tracks_started = None
        self.intro_playing = False
        self.intro_pending = False   # an intro waiting for the board to have a size
        self.wave_starts = None      # {cell: start seconds} while the wave plays
        self.wave_started = None
        self.wave_raised = set()
        self.laid_out_size = None
        self.rng = random.Random()
        self.update_interval = FRAME_INTERVAL    # set once; update() idles when still

    # --- showing a level -----------------------------------------------------

    def show(self, model, intro=False):
        """Show a level now. With intro it appears solved, then shuffles out."""
        self.stop_motion()
        self.model = model
        self.cols, self.rows = model.cols, model.rows
        self.selected = None
        self.press = None
        self.seamless = model.is_solved()
        self.laid_out_size = (self.width, self.height)
        wants_intro = intro and not model.is_solved()
        if wants_intro and self.width > 0:
            self.intro_pending = False
            self.place_all_tiles(solved_view=True)
            self.start_intro()
        else:
            self.intro_pending = wants_intro
            self.place_all_tiles(solved_view=wants_intro)

    def layout(self):
        size = (self.width, self.height)
        if self.model is None or self.width <= 0 or size == self.laid_out_size:
            return
        self.laid_out_size = size
        if self.intro_pending:
            self.intro_pending = False
            self.place_all_tiles(solved_view=True)
            self.start_intro()
            return
        self.stop_motion()
        self.place_all_tiles()

    def place_all_tiles(self, solved_view=False):
        """Put every tile view in place at once; hide the views this level doesn't use.

        solved_view puts each tile in its home cell instead of where it is now.
        """
        if self.model is None:
            return
        level = self.model.level
        cell_count = level.cols * level.rows
        for cell in range(cell_count):
            number = self.model.tile_in(cell)
            tile = self.tiles[number]
            frame = self.cell_frame(number if solved_view else cell)
            tile.frame = frame
            tile.dress(level.colours[number], number in level.anchors, frame)
            tile.dot.alpha = 0.0 if self.seamless else 1.0
            tile.hidden = False
        for tile in self.tiles[cell_count:]:
            tile.hidden = True
        self.highlight.hidden = True
        if self.selected is not None and not solved_view:
            self.lift(self.selected, selected=True)

    # --- geometry ------------------------------------------------------------------

    def cell_size(self):
        available_width = max(0, self.width - 2 * MARGIN)
        available_height = max(0, self.height - 2 * MARGIN)
        width = available_width / self.cols
        height = min(available_height / self.rows, width * MAX_TILE_ASPECT)
        return min(width, height), height

    def origin(self):
        width, _ = self.cell_size()
        return ((self.width - width * self.cols) / 2, MARGIN)

    def cell_frame(self, cell, gap=None):
        if gap is None:
            gap = 0.0 if self.seamless else GAP
        row, col = divmod(cell, self.cols)
        width, height = self.cell_size()
        left, top = self.origin()
        return (left + col * width + gap / 2, top + row * height + gap / 2,
                width - gap, height - gap)

    def lifted_frame(self, cell, centre=None):
        x, y, width, height = self.cell_frame(cell)
        if centre is None:
            centre = (x + width / 2, y + height / 2)
        width, height = width * (1 + LIFT_GROW), height * (1 + LIFT_GROW)
        return (centre[0] - width / 2, centre[1] - height / 2, width, height)

    def cell_at(self, point):
        width, height = self.cell_size()
        if width <= 0 or height <= 0:
            return None
        left, top = self.origin()
        col = int((point[0] - left) // width)
        row = int((point[1] - top) // height)
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return row * self.cols + col
        return None

    def is_free(self, cell):
        return cell is not None and self.model is not None and not self.model.is_anchor(cell)

    def tile_view(self, cell):
        return self.tiles[self.model.tile_in(cell)]

    # --- touches -------------------------------------------------------------------

    def touch_began(self, touch):
        if self.locked or self.model is None:
            return
        if self.intro_playing:
            self.finish_tracks()        # a touch skips the shuffle
            return
        self.finish_tracks()
        if self.model.is_solved():
            return
        point = tuple(touch.location)
        cell = self.cell_at(point)
        self.press = {"cell": cell, "start": point, "dragging": False}
        if self.is_free(cell):
            self.lift(cell, selected=(cell == self.selected))

    def touch_moved(self, touch):
        press = self.press
        if press is None:
            return
        point = tuple(touch.location)
        if not press["dragging"]:
            moved = math.hypot(point[0] - press["start"][0], point[1] - press["start"][1])
            if moved < DRAG_START:
                return
            press["dragging"] = True
        self.drag_moved(press["cell"], point)

    def touch_ended(self, touch):
        press, self.press = self.press, None
        if press is None:
            return
        if press["dragging"]:
            self.drag_ended(press["cell"], self.cell_at(tuple(touch.location)))
        else:
            self.tapped(press["cell"])

    def tapped(self, cell):
        if not self.is_free(cell):
            self.drop_selection()
        elif self.selected is None:
            self.selected = cell
            self.lift(cell, selected=True)
        elif self.selected == cell:
            self.drop_selection()
        else:
            first, self.selected = self.selected, None
            self.request_swap(first, cell)

    def drag_moved(self, cell, point):
        if not self.is_free(cell):
            return
        if self.selected is not None and self.selected != cell:
            self.drop_selection()
        self.selected = None
        target = self.cell_at(point)
        if self.is_free(target) and target != cell:
            self.highlight.frame = self.cell_frame(target)
            self.highlight.hidden = False
            self.highlight.bring_to_front()
        else:
            self.highlight.hidden = True
        tile = self.tile_view(cell)
        tile.bring_to_front()
        tile.border_width = 0
        tile.frame = self.lifted_frame(cell, centre=point)

    def drag_ended(self, cell, target):
        self.highlight.hidden = True
        if not self.is_free(cell):
            return
        if self.is_free(target) and target != cell:
            self.request_swap(cell, target)
        else:
            self.settle(cell)

    # --- lift and settle -----------------------------------------------------------

    def lift(self, cell, selected=False):
        tile = self.tile_view(cell)
        tile.bring_to_front()
        tile.border_width = SELECT_BORDER if selected else 0
        tile.border_color = TEXT
        frame = self.lifted_frame(cell)

        def grow():
            tile.frame = frame
        ui.animate(grow, duration=LIFT_SECONDS)

    def settle(self, cell):
        tile = self.tile_view(cell)
        tile.border_width = 0
        frame = self.cell_frame(cell)

        def land():
            tile.frame = frame
        ui.animate(land, duration=SETTLE_SECONDS)

    def drop_selection(self):
        if self.selected is not None:
            self.settle(self.selected)
            self.selected = None

    # --- swaps -----------------------------------------------------------------------

    def swap_cells(self, first, second):
        """Swap two cells as if the player had (used by Hint). True when it happened."""
        if self.locked or self.model is None:
            return False
        self.drop_selection()
        self.finish_tracks()
        return self.request_swap(first, second)

    def request_swap(self, first, second):
        """Ask the screen to swap; animate it if made, and start the wave if that solved it."""
        if self.on_swap is None or not self.on_swap(first, second):
            if self.is_free(first):
                self.settle(first)
            return False
        moved = self.tile_view(second)      # the tile that was in first
        other = self.tile_view(first)       # the tile that was in second
        moved.border_width = other.border_width = 0
        other.bring_to_front()
        moved.bring_to_front()
        self.start_tracks([
            (moved, tuple(moved.frame), self.cell_frame(second), 1, 0.0, SWAP_SECONDS,
             swap_motion.ARC_BEND, swap_motion.OVERSHOOT),
            (other, tuple(other.frame), self.cell_frame(first), 1, 0.0, SWAP_SECONDS,
             swap_motion.ARC_BEND, swap_motion.OVERSHOOT),
        ])
        if self.model.is_solved():
            self.celebrate(second)
        return True

    # --- the frame clock -------------------------------------------------------------

    def update(self):
        if self.superview is None:
            return
        now = time.time()
        if self.tracks:
            self.step_tracks(now)
        if self.wave_starts is not None:
            self.step_wave(now)

    def start_tracks(self, tracks):
        self.finish_tracks()
        self.tracks = tracks
        self.tracks_started = time.time()

    def step_tracks(self, now):
        elapsed = now - self.tracks_started
        finished = True
        for tile, start, end, side, delay, seconds, bend, overshoot in self.tracks:
            progress = (elapsed - delay) / seconds
            if progress < 1.0:
                finished = False
            if progress > 0:
                tile.frame = swap_motion.frame_at(
                    start, end, min(progress, 1.0), side, bend=bend, overshoot=overshoot)
        if finished:
            self.finish_tracks()

    def finish_tracks(self):
        """Snap every moving tile to the end of its track."""
        for tile, _, end, *_ in self.tracks:
            tile.frame = end
        self.tracks = []
        self.intro_playing = False

    def start_intro(self):
        """Every tile not already home arcs from its home cell out to where it was dealt."""
        tracks = []
        for cell in range(self.cols * self.rows):
            number = self.model.tile_in(cell)
            if number == cell:
                continue
            # Leave in a sweep from the top-left corner, ordered by home cell.
            home_row, home_col = divmod(number, self.cols)
            sweep = (home_row + home_col) / max(1, self.rows + self.cols - 2)
            delay = INTRO_HOLD + INTRO_SWEEP * sweep
            tracks.append((self.tiles[number], self.cell_frame(number), self.cell_frame(cell),
                           1, delay, INTRO_SECONDS, INTRO_BEND, INTRO_OVERSHOOT))
        self.start_tracks(tracks)
        self.intro_playing = bool(tracks)

    def celebrate(self, origin):
        """Start the finishing wave from origin once the last swap has landed."""
        self.wave_starts = wave.wave_starts(self.cols, self.rows, origin)
        self.wave_started = time.time() + SWAP_SECONDS
        self.wave_raised = set()

    def step_wave(self, now):
        elapsed = now - self.wave_started
        if elapsed < 0:
            return
        pulses_end = wave.wave_length(self.wave_starts)
        if elapsed < pulses_end:
            for cell, start in self.wave_starts.items():
                since = elapsed - start
                if since < 0 or since > wave.PULSE_SECONDS + 0.1:
                    continue
                tile = self.tiles[cell]
                if cell not in self.wave_raised:
                    tile.bring_to_front()
                    self.wave_raised.add(cell)
                tile.frame = wave.scaled(self.cell_frame(cell), wave.pulse_scale(since))
            return
        closing = min(1.0, (elapsed - pulses_end) / CLOSE_SECONDS)
        gap = GAP * (1 - closing)
        for cell in range(self.cols * self.rows):
            tile = self.tiles[cell]
            tile.frame = self.cell_frame(cell, gap)
            tile.dot.alpha = 1 - closing
        if closing >= 1.0:
            self.seamless = True
            self.wave_starts = None

    def end_wave(self):
        if self.wave_starts is not None:
            self.wave_starts = None
            self.seamless = True
            self.place_all_tiles()

    def stop_motion(self):
        """Finish everything moving at once: a new level, a resume or a resize."""
        self.finish_tracks()
        self.end_wave()
        self.highlight.hidden = True
