"""
A finish celebration drawn over a fill-in board (Sudoku now, KenKen later).

Every cell's fill pops in on a schedule from feel/flourish.py, coloured by
the cell's number from theme.celebration_colors(), so the player's own
colours lead. Each number is drawn again on top in the solved colour and
turns to the given colour as its cell pops. The fills stay until clear().
While it shows, the board should hide its own numbers (Sudoku's board has
values_hidden for this), so nothing is drawn twice.

UI stability (see the pythonista-ui-stability guide): a fixed pool of fills
and labels made once, never added or removed; touch_enabled is False so
taps fall through to the board underneath; the frame clock (update() with
update_interval set once) moves things, never ui.delay or a delayed
ui.animate; update() idles unless a celebration plays and the view is on
screen.
"""

import random
import time

import ui

from feel import flourish
from style import theme


GIVEN_COLOR = theme.color("given")        # a number once its cell has popped
SOLVED_COLOR = theme.color("success")     # a number before its cell pops, as the solved board shows it


class FlourishOverlay(ui.View):
    """Celebration fills and numbers over a solved board; touches pass through."""

    # --- editable look, in points or fractions of a cell ---------------------
    FILL_ALPHA = 0.55          # settled fill strength; numbers stay readable
    FILL_INSET = 1.5           # between a fill and its cell edge
    FILL_CORNER = 4
    VALUE_FONT_RATIO = 0.6     # matches SudokuBoardView
    GIVEN_FONT = "AvenirNext-Bold"
    PLAYER_FONT = "AvenirNext-Medium"
    MAX_SIDE = 9               # the largest board the pool covers
    FRAME_INTERVAL = 1 / 60

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.touch_enabled = False
        self.background_color = (0, 0, 0, 0)
        self.hidden = True
        self.update_interval = self.FRAME_INTERVAL   # set once, never changed

        self.fills = []
        for _ in range(self.MAX_SIDE ** 2):
            fill = ui.View()
            fill.touch_enabled = False
            fill.corner_radius = self.FILL_CORNER
            fill.alpha = 0
            self.add_subview(fill)
            self.fills.append(fill)

        self.labels = []           # added after the fills, so drawn above them
        for _ in range(self.MAX_SIDE ** 2):
            label = ui.Label()
            label.touch_enabled = False
            label.alignment = ui.ALIGN_CENTER
            label.hidden = True
            self.add_subview(label)
            self.labels.append(label)

        self.size = 0
        self.values = []
        self.givens = set()
        self.cell_frame = None     # callable(cell) -> frame in this view's coordinates
        self.starts = {}           # cell -> start seconds, from flourish.schedule
        self.settled = set()       # cells whose pop has finished
        self.run_started = None    # time.time() of the playing celebration, or None

    @property
    def playing(self):
        return self.run_started is not None

    # --- start and stop --------------------------------------------------------

    def play(self, values, givens, box_shape, cell_frame, origin=None, style=None):
        """Start the celebration over a solved board. Call it in the solving tap.

        values:    the solved board as rows of numbers.
        givens:    the given cells, drawn in the bold font.
        box_shape: (box_rows, box_columns).
        cell_frame: callable(cell) -> (x, y, width, height). Frame this view
                   exactly over the board view and the board's own
                   cell_frame works.
        origin:    where a ripple starts; the last cell filled.
        style:     one of flourish.STYLES, or None for a random one.

        Returns the style played, or None for a board too big for the pool.
        Safe to call while playing: it restarts.
        """
        size = len(values)
        if size == 0 or size > self.MAX_SIDE:
            return None
        style = style or random.choice(flourish.STYLES)
        colours = theme.celebration_colors(size)

        self.size = size
        self.values = [list(row) for row in values]
        self.givens = set(givens)
        self.cell_frame = cell_frame
        self.starts = flourish.schedule(style, self.values, box_shape, origin=origin)

        used = size * size
        for index, (fill, label) in enumerate(zip(self.fills, self.labels)):
            fill.alpha = 0
            fill.hidden = index >= used
            label.hidden = index >= used
        for row, column in self.starts:
            index = row * size + column
            value = self.values[row][column]
            self.fills[index].background_color = colours[(value - 1) % len(colours)]
            label = self.labels[index]
            label.text = str(value)
            label.text_color = SOLVED_COLOR

        self.settled = set()
        self.place_cells()
        self.hidden = False
        self.run_started = time.time()
        return style

    def clear(self):
        """Hide the celebration now: a new deal, a resume, or a size change."""
        self.run_started = None
        self.starts = {}
        self.settled = set()
        if not self.hidden:
            for fill in self.fills:
                fill.alpha = 0
            for label in self.labels:
                label.hidden = True
            self.hidden = True

    # --- geometry --------------------------------------------------------------

    def layout(self):
        self.place_cells()

    def place_cells(self):
        """Put every number on its cell, and settled fills at full size."""
        if self.cell_frame is None or not self.starts:
            return
        for cell in self.starts:
            index = cell[0] * self.size + cell[1]
            frame = self.cell_frame(cell)
            label = self.labels[index]
            label.frame = frame
            font_name = self.GIVEN_FONT if cell in self.givens else self.PLAYER_FONT
            label.font = (font_name, frame[2] * self.VALUE_FONT_RATIO)
            if cell in self.settled:
                self.fills[index].frame = self.fill_frame(cell, 1.0)

    def fill_frame(self, cell, size_factor):
        x, y, width, _ = self.cell_frame(cell)
        side = max(0.0, (width - 2 * self.FILL_INSET) * size_factor)
        centre_x, centre_y = x + width / 2, y + width / 2
        return (centre_x - side / 2, centre_y - side / 2, side, side)

    # --- the frame clock ---------------------------------------------------------

    def update(self):
        if self.run_started is None or self.superview is None:
            return
        elapsed = time.time() - self.run_started
        for cell, start in self.starts.items():
            if cell in self.settled or elapsed < start:
                continue
            since_start = elapsed - start
            size_factor, alpha_factor = flourish.pop_shape(since_start, flourish.POP_SECONDS)
            index = cell[0] * self.size + cell[1]
            fill = self.fills[index]
            fill.frame = self.fill_frame(cell, size_factor)
            fill.alpha = self.FILL_ALPHA * alpha_factor
            self.labels[index].text_color = GIVEN_COLOR
            if since_start >= flourish.POP_SECONDS:
                self.settled.add(cell)
        if len(self.settled) == len(self.starts):
            self.run_started = None
