"""
Board geometry for boardkit: where each cell's tile sits inside a board
view, and which cell a touch lands on.

Pure Python with no ui import, so it runs headless in smokes and the same
in Pythonista and PythonIDE. A board view keeps one Grid, calls resize()
from its layout(), and asks the grid for frames and cells.

Cells are (row, col), counted from the top left. Games that number cells
0 to cols * rows - 1 (Gradient does) convert with index_of() and cell_of().
Frames are (x, y, width, height) in the board view's own coordinates.

The board is centred left to right and sits against the top margin. Two
gap styles cover every Maths Games board so far:

    inset    Each cell owns a full slot and its tile is shrunk by the gap
             inside it, half on each side. Gradient uses this; a gap of 0
             gives Sudoku's and KenKen's touching cells.
    between  Gaps run around and between the tiles and take board space,
             so the board has a gap-wide edge all round. Double Up uses this.
"""


GAP_STYLES = ("inset", "between")


class Grid:
    """A board of cols x rows cells fitted into a view of a given size."""

    def __init__(self, cols, rows, margin=0.0, gap=0.0, gap_ratio=None,
                 gap_style="inset", max_aspect=1.0):
        """
        margin      points kept clear on every side of the board
        gap         points between neighbouring tiles
        gap_ratio   the gap as a fraction of a tile's width; overrides gap
        gap_style   "inset" or "between" (see the module docstring)
        max_aspect  the tallest a tile may be, as height / width; 1.0 keeps
                    tiles square, more lets a long board use tall tiles.
                    Tiles are never wider than they are tall.
        """
        if gap_style not in GAP_STYLES:
            raise ValueError("gap_style must be one of {}, not {!r}".format(GAP_STYLES, gap_style))
        self.margin = margin
        self.gap_points = gap
        self.gap_ratio = gap_ratio
        self.gap_style = gap_style
        self.max_aspect = max_aspect
        self.view_width = 0.0
        self.view_height = 0.0
        self.cols = self.rows = 1
        self.set_shape(cols, rows)

    # --- changing the board or the view ----------------------------------------

    def set_shape(self, cols, rows):
        """A new number of columns and rows, for example a new board size."""
        if cols < 1 or rows < 1:
            raise ValueError("a grid needs at least one column and one row")
        self.cols, self.rows = cols, rows
        self._fit()

    def resize(self, width, height):
        """Fit the board to a view this size. Call it from the view's layout()."""
        self.view_width, self.view_height = width, height
        self._fit()

    def _fit(self):
        """Work out tile size, gap and the board's corner for the current view.

        Sets tile_width and tile_height (a tile at the grid's own gap),
        slot_width and slot_height (the step from one tile to the next),
        gap, and left and top (the board's corner).
        """
        room_width = max(0.0, self.view_width - 2 * self.margin)
        room_height = max(0.0, self.view_height - 2 * self.margin)
        if self.gap_style == "between":
            # cols tiles and cols + 1 gaps share the width; likewise rows.
            if self.gap_ratio is not None:
                width = room_width / (self.cols + (self.cols + 1) * self.gap_ratio)
                height_room = room_height / (self.rows + (self.rows + 1) * self.gap_ratio)
            else:
                width = (room_width - (self.cols + 1) * self.gap_points) / self.cols
                height_room = (room_height - (self.rows + 1) * self.gap_points) / self.rows
        else:
            width = room_width / self.cols
            height_room = room_height / self.rows
        height = max(0.0, min(height_room, width * self.max_aspect))
        width = max(0.0, min(width, height))

        self.gap = self._gap_for(width)
        if self.gap_style == "between":
            self.tile_width, self.tile_height = width, height
            self.slot_width, self.slot_height = width + self.gap, height + self.gap
        else:
            self.slot_width, self.slot_height = width, height
            self.tile_width = max(0.0, width - self.gap)
            self.tile_height = max(0.0, height - self.gap)
        self.left = (self.view_width - self.board_frame_size()[0]) / 2
        self.top = self.margin

    def _gap_for(self, width):
        if self.gap_ratio is not None:
            return width * self.gap_ratio
        return self.gap_points

    # --- frames ---------------------------------------------------------------

    def board_frame_size(self):
        """(width, height) of the whole board, edge gaps included."""
        if self.gap_style == "between":
            return (self.cols * self.slot_width + self.gap,
                    self.rows * self.slot_height + self.gap)
        return (self.cols * self.slot_width, self.rows * self.slot_height)

    def board_frame(self):
        """The whole board as a frame: what a board background fills."""
        width, height = self.board_frame_size()
        return (self.left, self.top, width, height)

    def cell_frame(self, cell, gap=None):
        """The tile frame for cell.

        An inset grid may pass gap to draw tiles with another gap for a
        moment, as Gradient does when it closes the gaps on a solved board.
        """
        row, col = cell
        if self.gap_style == "between":
            if gap is not None:
                raise ValueError("only an inset grid can draw with another gap")
            return (self.left + self.gap + col * self.slot_width,
                    self.top + self.gap + row * self.slot_height,
                    self.tile_width, self.tile_height)
        if gap is None:
            gap = self.gap
        return (self.left + col * self.slot_width + gap / 2,
                self.top + row * self.slot_height + gap / 2,
                self.slot_width - gap, self.slot_height - gap)

    def cell_centre(self, cell):
        x, y, width, height = self.cell_frame(cell)
        return (x + width / 2, y + height / 2)

    def lifted_frame(self, cell, grow, centre=None):
        """cell's tile grown by grow (0.1 is 10% larger), centred on centre
        (a finger, say) or on the cell itself."""
        x, y, width, height = self.cell_frame(cell)
        if centre is None:
            centre = (x + width / 2, y + height / 2)
        width, height = width * (1 + grow), height * (1 + grow)
        return (centre[0] - width / 2, centre[1] - height / 2, width, height)

    # --- touches --------------------------------------------------------------

    def cell_at(self, point):
        """The cell under point, or None off the board.

        Between tiles, a point belongs to the nearer tile, so a touch in a
        gap is never lost.
        """
        if self.slot_width <= 0 or self.slot_height <= 0:
            return None
        x = point[0] - self.left
        y = point[1] - self.top
        if self.gap_style == "between":
            x -= self.gap / 2
            y -= self.gap / 2
        col = int(x // self.slot_width)
        row = int(y // self.slot_height)
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return (row, col)
        return None

    # --- cells ----------------------------------------------------------------

    def cells(self):
        """Every cell, row by row from the top left."""
        return [(row, col) for row in range(self.rows) for col in range(self.cols)]

    def index_of(self, cell):
        """A cell's number, 0 at the top left, counting along each row."""
        row, col = cell
        return row * self.cols + col

    def cell_of(self, index):
        """The cell with this number."""
        return divmod(index, self.cols)
