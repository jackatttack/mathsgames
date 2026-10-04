"""
TileKit viewport transform.

The viewport is renderer-neutral camera state. Board objects remain in logical
world coordinates; UI layers convert between world and screen through this
small transform.

Keeping camera state separate from TileObject data avoids the old Tile Calc
pattern of physically moving every object when the user pans the board.
"""


class ViewportTransform:
    """Translate and scale logical world coordinates into screen coordinates."""

    def __init__(self, offset=(0.0, 0.0), scale=1.0, min_scale=0.5, max_scale=2.0):
        self.offset = self._point(offset)
        self.min_scale = float(min_scale)
        self.max_scale = float(max_scale)
        self.scale = self.clamp_scale(scale)

    def _point(self, value):
        try:
            x, y = value
            return (float(x), float(y))
        except Exception:
            return (0.0, 0.0)

    def clamp_scale(self, scale):
        scale = float(scale or 1.0)
        low = min(self.min_scale, self.max_scale)
        high = max(self.min_scale, self.max_scale)
        return max(low, min(high, scale))

    def to_screen(self, position):
        """Convert a logical world point to a screen point."""
        x, y = self._point(position)
        ox, oy = self.offset
        return (
            x * self.scale + ox,
            y * self.scale + oy,
        )

    def from_screen(self, point):
        """Convert a screen point back to logical world coordinates."""
        x, y = self._point(point)
        ox, oy = self.offset
        scale = self.scale or 1.0
        return (
            (x - ox) / scale,
            (y - oy) / scale,
        )

    def screen_length(self, logical_length):
        """Convert a logical length to its displayed screen length."""
        return float(logical_length) * self.scale

    def world_length(self, screen_length):
        """Convert a displayed screen length back to logical length."""
        scale = self.scale or 1.0
        return float(screen_length) / scale

    def pan_by(self, screen_delta):
        """Move the camera by a screen-space delta."""
        dx, dy = self._point(screen_delta)
        ox, oy = self.offset
        self.offset = (ox + dx, oy + dy)
        return self.offset

    def set_scale(self, scale, anchor_screen=None):
        """Set scale while optionally keeping one screen point anchored.

        When anchor_screen is supplied, the logical point currently beneath
        that screen coordinate stays beneath the same coordinate after scaling.
        """
        new_scale = self.clamp_scale(scale)
        if anchor_screen is None:
            self.scale = new_scale
            return self.scale

        anchor_screen = self._point(anchor_screen)
        anchor_world = self.from_screen(anchor_screen)
        self.scale = new_scale

        wx, wy = anchor_world
        sx, sy = anchor_screen
        self.offset = (
            sx - wx * self.scale,
            sy - wy * self.scale,
        )
        return self.scale

    def zoom_by(self, factor, anchor_screen=None):
        """Multiply scale by factor, optionally around a screen anchor."""
        factor = float(factor or 1.0)
        return self.set_scale(self.scale * factor, anchor_screen=anchor_screen)

    def reset(self):
        """Restore the identity camera."""
        self.offset = (0.0, 0.0)
        self.scale = self.clamp_scale(1.0)