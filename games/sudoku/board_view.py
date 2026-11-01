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
from games.sudoku import board_build
from tilegame.widgets import draw_centred_text


CELL_COLOR = theme.color("board")
GRID_LINE_COLOR = theme.color("grid_line")
BOX_WALL_COLOR = theme.color("box_wall")
GIVEN_COLOR = theme.color("given")
PLAYER_COLOR = theme.color("player_number")
NOTE_COLOR = theme.color("note")
SELECTED_FILL = theme.color("selection_fill")
SELECTED_OUTLINE = theme.color("selection")
MISTAKE_COLOR = theme.color("mistake")
SOLVED_COLOR = theme.color("success")
COMPLETE_COLOR = theme.color("success")       # every copy of a number placed size times
PEER_FILL = theme.color("assist_peer")        # row, column and box of the focus cell
MATCH_FILL = theme.color("assist_match")      # cells holding the focus cell's number
MATCH_NOTE_COLOR = theme.color("sky")         # pencil marks of the focus number


class SudokuBoardView(ui.View):
    """Draws a Sudoku with the player's values and notes; reports tapped cells."""

    # --- editable look, in points or fractions of a cell ---------------------
    MARGIN = 8
    GRID_LINE_WIDTH = 1
    BOX_WALL_WIDTH = 3
    SELECTED_OUTLINE_WIDTH = 3
    VALUE_FONT_RATIO = 0.6
    NOTE_FONT_RATIO = 0.26
    armed_value = None   # the tray's armed number; refresh_marks sets it
    values_hidden = False   # True while the solve celebration or the new-deal build draws the numbers

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
        self.focus_cell = None
        self.completed = set()

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
        self.focus_cell = None
        self.completed = set()
        self.set_needs_display()

    def refresh_marks(self, values, notes, selected_cell, conflicts, solved,
                      focus_cell=None, completed=(), armed_value=None):
        """Show the player's marks. focus_cell, when given, is highlighted
        with its row, column, box and every copy of its number. Numbers in
        completed are drawn green wherever they appear. armed_value, the
        number armed in the tray, has every copy highlighted, focus or not."""
        self.completed = set(completed)
        self.values = values
        self.notes = dict(notes)
        self.selected_cell = selected_cell
        self.conflicts = set(conflicts)
        self.solved = solved
        self.focus_cell = focus_cell
        self.armed_value = armed_value
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
        self._draw_assist(left, top, cell_size)

        if self.selected_cell is not None:
            ui.set_color(SELECTED_FILL)
            ui.Path.rect(*self.cell_frame(self.selected_cell)).fill()

        self._draw_grid_lines(left, top, side, cell_size)
        self._draw_box_walls(left, top, side, cell_size)
        self._draw_values(left, top, cell_size)
        self._draw_notes(left, top, cell_size)

        # The picker's cell, or else the highlighted cell (a given has no
        # picker), gets the outline so it reads as the one tapped.
        if self.selected_cell is not None:
            outlined = self.selected_cell
        else:
            outlined = self.focus_cell
        if outlined is not None:
            inset = self.SELECTED_OUTLINE_WIDTH
            x, y, width, height = self.cell_frame(outlined)
            outline = ui.Path.rect(x + inset, y + inset,
                                   width - 2 * inset, height - 2 * inset)
            outline.line_width = self.SELECTED_OUTLINE_WIDTH
            ui.set_color(SELECTED_OUTLINE)
            outline.stroke()

    def focus_value(self):
        """The number in the focus cell, or None."""
        if self.focus_cell is None:
            return None
        row, col = self.focus_cell
        return self.values[row][col]

    def _draw_assist(self, left, top, cell_size):
        """Shade the focus cell's row, column and box, then its number's copies.

        A number armed in the tray is matched instead, with or without a
        focus cell. Drawn first, under the selection, grid lines and numbers.
        """
        if self.focus_cell is None and self.armed_value is None:
            return
        if self.armed_value is not None:
            match = self.armed_value
        else:
            match = self.focus_value()

        focus_box = None
        if self.focus_cell is not None:
            focus_row, focus_col = self.focus_cell
            focus_box = (focus_row // self.box_rows, focus_col // self.box_cols)

        for row in range(self.size):
            for col in range(self.size):
                if match is not None and self.values[row][col] == match:
                    ui.set_color(MATCH_FILL)
                elif focus_box is not None and (
                        row == focus_row or col == focus_col
                        or (row // self.box_rows, col // self.box_cols) == focus_box):
                    ui.set_color(PEER_FILL)
                else:
                    continue
                ui.Path.rect(left + col * cell_size, top + row * cell_size,
                             cell_size, cell_size).fill()

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
        if self.values_hidden:      # the celebration overlay draws them instead
            return
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
                elif value in self.completed:
                    color = COMPLETE_COLOR
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
        # Same rule as _draw_assist: an armed tray number wins over the focus cell.
        if self.armed_value is not None:
            match = self.armed_value
        else:
            match = self.focus_value()
        for (row, col), noted in self.notes.items():
            for value in noted:
                mini_row, mini_col = divmod(value - 1, self.box_cols)
                color = MATCH_NOTE_COLOR if value == match else NOTE_COLOR
                draw_centred_text(
                    str(value), font, color,
                    left + col * cell_size + mini_col * mini_width,
                    top + row * cell_size + mini_row * mini_height,
                    mini_width, mini_height,
                )

    # --- unfolding on a new deal -----------------------------------------------

    def build_show(self, start, rng=None):
        """A BuildShow unfolding the current puzzle from a random corner at
        start, for a boardkit FoldLayer over this board; None before layout."""
        left, top, side = self.board_rect()
        if not self.size or side <= 0:
            return None
        givens = {cell: self.values[cell[0]][cell[1]] for cell in self.givens}
        return BuildShow(self, board_build.plan_build(self.size, (left, top, side), givens, start, rng))

    def draw_build(self, build, now):
        """Draw build (board_build.Build) part way, inside the overlay's draw().

        Cells whose paper has not landed are covered in this view's
        background, so the board shows only where paper has settled; turning
        squares are drawn as plain paper in the cell colour. Once the paper
        has all landed the givens pop in (the board's own numbers stay
        hidden until the build ends).
        """
        ui.set_color(self.background_color)
        for cell in board_build.unlanded(build, now):
            ui.Path.rect(*self.cell_frame(cell)).fill()
        red, green, blue = _rgb(CELL_COLOR)
        for cell, points, shade in board_build.sheets(build, now):
            ui.set_color((red * shade, green * shade, blue * shade))
            sheet = ui.Path()
            sheet.move_to(*points[0])
            for point in points[1:]:
                sheet.line_to(*point)
            sheet.close()
            sheet.fill()
        cell_size = build.rect[2] / build.size
        font = ("AvenirNext-Bold", cell_size * self.VALUE_FONT_RATIO)
        for cell, value, scale in board_build.numbers(build, now):
            x, y, width, height = self.cell_frame(cell)
            with ui.GState():
                # Move to the cell's centre, then scale, so the number pops about its middle.
                ui.concat_ctm(ui.Transform.translation(x + width / 2, y + height / 2))
                ui.concat_ctm(ui.Transform.scale(scale, scale))
                draw_centred_text(str(value), font, GIVEN_COLOR,
                                  -cell_size / 2, -cell_size / 2, cell_size, cell_size)


class BuildShow:
    """The board building itself on a new deal, as a show for boardkit's
    FoldLayer. The board hides its own numbers until the swell.

    For the swell the finished board is drawn once into an image, which the
    overlay draws scaled about the board's centre. The board view itself is
    never transformed: the screen re-lays it out often, and a frame set on
    a transformed view is unreliable.
    """

    def __init__(self, board_view, build):
        self.board_view = board_view
        self.build = build
        self.rect = build.rect      # the screen drops the show if the board moves
        self.snapshot = None        # the finished board, made when the swell starts
        board_view.values_hidden = True
        board_view.set_needs_display()

    def done(self, now):
        return board_build.done(self.build, now)

    def draw(self, now):
        if now < self.build.swell_start:
            self.board_view.draw_build(self.build, now)
            return
        board = self.board_view
        if self.snapshot is None:
            board.values_hidden = False
            board.set_needs_display()
            with ui.ImageContext(board.width, board.height) as context:
                board.draw()
                self.snapshot = context.get_image()
        scale = board_build.board_scale(self.build, now)
        left, top, side = self.build.rect
        centre_x, centre_y = left + side / 2, top + side / 2
        self.snapshot.draw(centre_x - centre_x * scale, centre_y - centre_y * scale,
                           board.width * scale, board.height * scale)

    def finished(self):
        """Ended or skipped: the board shows its own numbers again."""
        self.board_view.values_hidden = False
        self.board_view.set_needs_display()


def _rgb(colour):
    """(red, green, blue) from a theme colour, as a hex string or a tuple."""
    if isinstance(colour, (tuple, list)):
        return tuple(colour[:3])
    return tuple(ui.parse_color(colour)[:3])
