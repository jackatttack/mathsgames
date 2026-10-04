"""
TileKit spawn cursor UI.

This is the small reusable version of old Tile Calc's active grid square.
It shows where palette/keyboard-created objects will appear next.
"""
import ui


class SpawnCursorView(ui.View):
    """Lightweight active-cell overlay for palette/keyboard spawning."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = "clear"
        self.touch_enabled = False
        self.position = (180.0, 360.0)
        self.grid = 60.0
        self.border_color = "#5AC8FA"
        self.fill_color = (0.0, 0.48, 1.0, 0.08)
        self.corner_radius = 10

    def set_position(self, position, grid=None):
        if grid is not None:
            self.grid = float(grid or self.grid or 60.0)

        try:
            x, y = position
        except Exception:
            x, y = self.position

        self.position = (float(x), float(y))
        size = float(self.grid or 60.0)
        self.frame = (
            self.position[0] - size / 2.0,
            self.position[1] - size / 2.0,
            size,
            size,
        )

        try:
            self.set_needs_display()
        except Exception:
            pass

    def draw(self):
        try:
            path = ui.Path.rounded_rect(1, 1, max(1, self.width - 2), max(1, self.height - 2), 10)
            ui.set_color(self.fill_color)
            path.fill()
            ui.set_color(self.border_color)
            path.line_width = 3
            path.stroke()
        except Exception:
            pass