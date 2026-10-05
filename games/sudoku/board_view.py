"""
The Sudoku board: cells, grid lines, box walls, givens, player values and
notes.

One view drawn in draw(), with no subviews, so every change is a single
set_needs_display(). It reports taps as cells through on_cell_tapped(cell),
with None for a tap beside the grid. It never changes game state itself.

Notes sit in a mini grid shaped like a box: 3 x 3 on 9 x 9, 2 x 3 on 6 x 6
and 2 x 2 on 4 x 4, each value always in the same spot.
"""

import ui

from style import theme
from tilegame.widgets import draw_centred_text


CELL_COLOR = theme.color("surface")
GRID_LINE_COLOR = theme.color("button")
BOX_WALL_COLOR = theme.color("muted")
GIVEN_COLOR = theme.color("text")
PLAYER_COLOR = theme.color("sky")
NOTE_COLOR = theme.color("muted")
SELECTED_FILL = theme.color("button")
SELECTED_OUTLINE = theme.color("tile")
MISTAKE_COLOR = theme.color("coral")
SOLVED_COLOR = theme.color("success")


class SudokuBoardView(ui.View):
    """Draws a Sudoku with the player's values and notes; reports tapped cells."""

    # --- editable look, in points or fractions of a cell ---------------------
    MARGIN = 8
    GRID_LINE_WIDTH = 1
    BOX_WALL_WIDTH = 3
    SELECTED_OUTLINE_WIDTH = 3
    VALUE_FONT_RATIO = 0.6
    NOTE_FONT_RATIO = 0.26

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.on_cell_tapped = None
        self.size = 0
        self.box_rows = 1
        self.box_cols = 1
        self.givens = set()
        self.values = []
        self.notes = {}
        self.selected_cell = None
        self.conflicts = set()
        self.solved = False

    # --- what to show --------------------------------------------------------

    def load_puzzle(self, puzzle, box_shape):
        self.size = puzzle.size
        self.box_rows, self.box_cols = box_shape
        self.givens = set(puzzle.givens_by_cell())
        self.values = [list(row) for row in puzzle.givens]
        self.notes = {}
        self.selected_cell = None
        self.conflicts = set()
        self.solved = False
        self.set_needs_display()

    def refresh_marks(self, values, notes, selected_cell, conflicts, solved):
        self.values = values
        self.notes = dict(notes)
        self.selected_cell = selected_cell
        self.conflicts = set(conflicts)
        self.solved = solved
        self.set_needs_display()

    # --- geometry ------------------------------------------------------------

    def board_rect(self):
        """(left, top, side) of the square grid, centred and top-aligned."""
        side = max(0, min(self.width, self.height) - 2 * self.MARGIN)
        return (self.width - side) / 2, self.MARGIN, side

    def cell_frame(self, cell):
        left, top, side = self.board_rect()
        cell_size = side / self.size
        row, col = cell
        return (left + col * cell_size, top + row * cell_size, cell_size, cell_size)

    def cell_at_point(self, point):
        if not self.size:
            return None
        left, top, side = self.board_rect()
        x, y = point
        if not (left <= x < left + side and top <= y < top + side):
            return None
        cell_size = side / self.size
        return int((y - top) // cell_size), int((x - left) // cell_size)

    # --- touch ---------------------------------------------------------------

    def touch_ended(self, touch):
        if self.on_cell_tapped is not None:
            self.on_cell_tapped(self.cell_at_point(touch.location))

    # --- drawing -------------------------------------------------------------

    def draw(self):
        if not self.size:
            return
        left, top, side = self.board_rect()
        cell_size = side / self.size

        ui.set_color(CELL_COLOR)
        ui.Path.rect(left, top, side, side).fill()

        if self.selected_cell is not None:
            ui.set_color(SELECTED_FILL)
            ui.Path.rect(*self.cell_frame(self.selected_cell)).fill()

        self._draw_grid_lines(left, top, side, cell_size)
        self._draw_box_walls(left, top, side, cell_size)
        self._draw_values(left, top, cell_size)
        self._draw_notes(left, top, cell_size)

        if self.selected_cell is not None:
            inset = self.SELECTED_OUTLINE_WIDTH
            x, y, width, height = self.cell_frame(self.selected_cell)
            outline = ui.Path.rect(x + inset, y + inset,
                                   width - 2 * inset, height - 2 * inset)
            outline.line_width = self.SELECTED_OUTLINE_WIDTH
            ui.set_color(SELECTED_OUTLINE)
            outline.stroke()

    def _draw_grid_lines(self, left, top, side, cell_size):
        lines = ui.Path()
        lines.line_width = self.GRID_LINE_WIDTH
        for step in range(1, self.size):
            offset = step * cell_size
            lines.move_to(left + offset, top)
            lines.line_to(left + offset, top + side)
            lines.move_to(left, top + offset)
            lines.line_to(left + side, top + offset)
        ui.set_color(GRID_LINE_COLOR)
        lines.stroke()

    def _draw_box_walls(self, left, top, side, cell_size):
        walls = ui.Path()
        walls.line_width = self.BOX_WALL_WIDTH
        walls.line_cap_style = ui.LINE_CAP_SQUARE
        for row in range(0, self.size + 1, self.box_rows):
            walls.move_to(left, top + row * cell_size)
            walls.line_to(left + side, top + row * cell_size)
        for col in range(0, self.size + 1, self.box_cols):
            walls.move_to(left + col * cell_size, top)
            walls.line_to(left + col * cell_size, top + side)
        ui.set_color(BOX_WALL_COLOR)
        walls.stroke()

    def _draw_values(self, left, top, cell_size):
        given_font = ("AvenirNext-Bold", cell_size * self.VALUE_FONT_RATIO)
        player_font = ("AvenirNext-Medium", cell_size * self.VALUE_FONT_RATIO)
        for row, row_values in enumerate(self.values):
            for col, value in enumerate(row_values):
                if value is None:
                    continue
                cell = (row, col)
                given = cell in self.givens
                if self.solved:
                    color = SOLVED_COLOR
                elif cell in self.conflicts and not given:
                    color = MISTAKE_COLOR
                else:
                    color = GIVEN_COLOR if given else PLAYER_COLOR
                draw_centred_text(
                    str(value), given_font if given else player_font, color,
                    left + col * cell_size, top + row * cell_size,
                    cell_size, cell_size,
                )

    def _draw_notes(self, left, top, cell_size):
        font = ("AvenirNext-Medium", max(8, cell_size * self.NOTE_FONT_RATIO))
        mini_width = cell_size / self.box_cols
        mini_height = cell_size / self.box_rows
        for (row, col), noted in self.notes.items():
            for value in noted:
                mini_row, mini_col = divmod(value - 1, self.box_cols)
                draw_centred_text(
                    str(value), font, NOTE_COLOR,
                    left + col * cell_size + mini_col * mini_width,
                    top + row * cell_size + mini_row * mini_height,
                    mini_width, mini_height,
                )