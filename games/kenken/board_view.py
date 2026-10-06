"""
The KenKen board: cells, grid lines, cage walls, cage labels, numbers and
notes.

Notes sit in a mini grid below the cage label strip: 3 across (2 x 2 on a
4 x 4 board), each value always in the same spot.

One view drawn in draw(), with no subviews, so every change is a single
set_needs_display(). It reports taps as cells through on_cell_tapped(cell),
with None for a tap beside the grid. It never changes game state itself.
"""

import ui

from style import theme
from tilegame.widgets import draw_centred_text


CELL_COLOR = theme.color("surface")
GRID_LINE_COLOR = theme.color("button")
CAGE_WALL_COLOR = theme.color("muted")
TEXT_COLOR = theme.color("text")
NOTE_COLOR = theme.color("muted")
SELECTED_FILL = theme.color("button")
SELECTED_OUTLINE = theme.color("tile")
MISTAKE_COLOR = theme.color("coral")
SOLVED_COLOR = theme.color("success")


class KenKenBoardView(ui.View):
    """Draws a puzzle and the player's values; reports tapped cells."""

    # --- editable look, in points or fractions of a cell ---------------------
    MARGIN = 12
    GRID_LINE_WIDTH = 1
    CAGE_WALL_WIDTH = 3
    SELECTED_OUTLINE_WIDTH = 3
    LABEL_FONT_RATIO = 0.22
    VALUE_FONT_RATIO = 0.5
    NOTE_FONT_RATIO = 0.22
    NOTE_TOP_RATIO = 0.3     # top strip of each cell kept clear for the cage label

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.on_cell_tapped = None
        self.puzzle = None
        self.cage_of = {}
        self.values = []
        self.notes = {}
        self.selected_cell = None
        self.conflicts = set()
        self.wrong_cages = set()
        self.solved = False

    # --- what to show --------------------------------------------------------

    def load_puzzle(self, puzzle):
        self.puzzle = puzzle
        self.cage_of = puzzle.cage_lookup()
        self.values = [[None] * puzzle.size for _ in range(puzzle.size)]
        self.notes = {}
        self.selected_cell = None
        self.conflicts = set()
        self.wrong_cages = set()
        self.solved = False
        self.set_needs_display()

    def refresh_marks(self, values, notes, selected_cell, conflicts, wrong_cages, solved):
        self.values = values
        self.notes = dict(notes)
        self.selected_cell = selected_cell
        self.conflicts = set(conflicts)
        self.wrong_cages = set(wrong_cages)
        self.solved = solved
        self.set_needs_display()

    # --- geometry ------------------------------------------------------------

    def board_rect(self):
        """(left, top, side) of the square grid, centred and top-aligned."""
        side = max(0, min(self.width, self.height) - 2 * self.MARGIN)
        return (self.width - side) / 2, self.MARGIN, side

    def cell_frame(self, cell):
        left, top, side = self.board_rect()
        cell_size = side / self.puzzle.size
        row, col = cell
        return (left + col * cell_size, top + row * cell_size, cell_size, cell_size)

    def cell_at_point(self, point):
        if self.puzzle is None:
            return None
        left, top, side = self.board_rect()
        x, y = point
        if not (left <= x < left + side and top <= y < top + side):
            return None
        cell_size = side / self.puzzle.size
        return int((y - top) // cell_size), int((x - left) // cell_size)

    # --- touch ---------------------------------------------------------------

    def touch_ended(self, touch):
        if self.on_cell_tapped is not None:
            self.on_cell_tapped(self.cell_at_point(touch.location))

    # --- drawing -------------------------------------------------------------

    def draw(self):
        if self.puzzle is None:
            return
        size = self.puzzle.size
        left, top, side = self.board_rect()
        cell_size = side / size

        ui.set_color(CELL_COLOR)
        ui.Path.rect(left, top, side, side).fill()

        if self.selected_cell is not None:
            ui.set_color(SELECTED_FILL)
            ui.Path.rect(*self.cell_frame(self.selected_cell)).fill()

        self._draw_grid_lines(left, top, side, cell_size)
        self._draw_cage_walls(left, top, cell_size)
        self._draw_labels(left, top, cell_size)
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
        for step in range(1, self.puzzle.size):
            offset = step * cell_size
            lines.move_to(left + offset, top)
            lines.line_to(left + offset, top + side)
            lines.move_to(left, top + offset)
            lines.line_to(left + side, top + offset)
        ui.set_color(GRID_LINE_COLOR)
        lines.stroke()

    def _draw_cage_walls(self, left, top, cell_size):
        """Walls where a neighbour is in another cage, plus the outer edge.

        Each cell draws its own top and left walls; the last row and column
        also draw their bottom and right edges, so no wall is missed.
        """
        size = self.puzzle.size
        walls = ui.Path()
        walls.line_width = self.CAGE_WALL_WIDTH
        walls.line_cap_style = ui.LINE_CAP_SQUARE

        for row in range(size):
            for col in range(size):
                cage = self.cage_of[(row, col)]
                x = left + col * cell_size
                y = top + row * cell_size
                if row == 0 or self.cage_of[(row - 1, col)] != cage:
                    walls.move_to(x, y)
                    walls.line_to(x + cell_size, y)
                if col == 0 or self.cage_of[(row, col - 1)] != cage:
                    walls.move_to(x, y)
                    walls.line_to(x, y + cell_size)
                if row == size - 1:
                    walls.move_to(x, y + cell_size)
                    walls.line_to(x + cell_size, y + cell_size)
                if col == size - 1:
                    walls.move_to(x + cell_size, y)
                    walls.line_to(x + cell_size, y + cell_size)

        ui.set_color(CAGE_WALL_COLOR)
        walls.stroke()

    def _draw_labels(self, left, top, cell_size):
        font_size = max(10, cell_size * self.LABEL_FONT_RATIO)
        font = ("AvenirNext-DemiBold", font_size)
        for index, cage in enumerate(self.puzzle.cages):
            row, col = cage.label_cell()
            color = MISTAKE_COLOR if index in self.wrong_cages else TEXT_COLOR
            ui.draw_string(
                cage.label(),
                rect=(left + col * cell_size + 5, top + row * cell_size + 3,
                      cell_size - 8, font_size * 1.4),
                font=font,
                color=color,
                alignment=ui.ALIGN_LEFT,
            )

    def _draw_values(self, left, top, cell_size):
        font = ("AvenirNext-Bold", cell_size * self.VALUE_FONT_RATIO)
        for row, row_values in enumerate(self.values):
            for col, value in enumerate(row_values):
                if value is None:
                    continue
                if self.solved:
                    color = SOLVED_COLOR
                elif (row, col) in self.conflicts:
                    color = MISTAKE_COLOR
                else:
                    color = TEXT_COLOR
                # Nudged down a little so the cage label has room.
                draw_centred_text(
                    str(value), font, color,
                    left + col * cell_size,
                    top + row * cell_size + cell_size * 0.08,
                    cell_size, cell_size,
                )

    def _draw_notes(self, left, top, cell_size):
        """Pencil marks for empty cells, below the cage label strip.

        Three columns suit sizes 3, 5 and 6; a 4 x 4 board uses 2 x 2 so its
        four notes fill the space evenly.
        """
        size = self.puzzle.size
        columns = 2 if size == 4 else 3
        rows = -(-size // columns)    # ceiling division

        strip = cell_size * self.NOTE_TOP_RATIO
        mini_width = cell_size / columns
        mini_height = (cell_size - strip) / rows
        font = ("AvenirNext-Medium", max(8, cell_size * self.NOTE_FONT_RATIO))

        for (row, col), noted in self.notes.items():
            for value in noted:
                mini_row, mini_col = divmod(value - 1, columns)
                draw_centred_text(
                    str(value), font, NOTE_COLOR,
                    left + col * cell_size + mini_col * mini_width,
                    top + row * cell_size + strip + mini_row * mini_height,
                    mini_width, mini_height,
                )
