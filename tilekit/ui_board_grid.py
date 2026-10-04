"""Square-board grid projected through the existing viewport."""

import math
import ui


GRID_BACKGROUND = "#28282A"
GRID_COLOR = "#323235"
GRID_LINE_WIDTH = 0.65


def grid_line_positions(coords, width, height):
    """Return visible cell boundaries in screen coordinates.

    Snapped positions are cell centres. Boundaries sit half a logical
    grid cell either side and use the same viewport as the tiles.
    """
    grid = float(getattr(coords, "grid", 0) or 0)
    if grid <= 0 or width <= 0 or height <= 0:
        return [], []

    step = float(coords.screen_length(grid))
    if not math.isfinite(step) or step < 4:
        return [], []

    ox, oy = coords.origin
    start_x, start_y = coords.to_screen(
        (ox - grid / 2, oy - grid / 2)
    )

    def visible_lines(start, extent):
        if not math.isfinite(start) or not math.isfinite(extent):
            return []
        first = int(math.ceil(-start / step))
        last = int(math.floor((extent - start) / step))
        return [
            start + index * step
            for index in range(first, last + 1)
        ]

    return (
        visible_lines(start_x, width),
        visible_lines(start_y, height),
    )


class BoardGridView(ui.View):
    """Non-interactive background beneath tiles and floating controls."""

    def __init__(self, board):
        super().__init__()
        self.board = board
        self.touch_enabled = False
        self.flex = "WH"
        self.background_color = GRID_BACKGROUND

    def draw(self):
        coords = self.board.coords
        if getattr(coords, "name", "") != "freeform_square_grid":
            return

        xs, ys = grid_line_positions(
            coords, self.width, self.height
        )

        path = ui.Path()
        for x in xs:
            path.move_to(x, 0)
            path.line_to(x, self.height)
        for y in ys:
            path.move_to(0, y)
            path.line_to(self.width, y)

        ui.set_color(GRID_COLOR)
        path.line_width = GRID_LINE_WIDTH
        path.stroke()
