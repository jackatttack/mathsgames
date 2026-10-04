"""
TileKit coordinate systems.

The board owns a CoordinateSystem. Tile objects store logical positions;
coordinate systems translate those positions to screen positions, apply
snapping, and describe spatial relations between objects.

TileKit must not assume a square grid forever. FreeformSquareGrid is the
first practical implementation because it matches the feel of Tile Calc.
"""

import math


class DropRelation:
    """Spatial relationship between source and target during a drop."""

    def __init__(self, relation=None, direction=None, distance=None,
                 zone=None, overlap=False, started_adjacent=False,
                 vector=None, drag_direction=None, spawn_direction=None,
                 approach_direction=None, target_zone=None,
                 started_zone=None, profile_position=None, metadata=None):
        self.relation = relation
        self.direction = direction
        self.distance = distance
        self.zone = zone
        self.overlap = bool(overlap)
        self.started_adjacent = bool(started_adjacent)

        # Extra relation data for previews, merge rules, and future overlays.
        self.vector = vector
        self.drag_direction = drag_direction
        self.spawn_direction = spawn_direction
        self.approach_direction = approach_direction
        self.target_zone = target_zone
        self.started_zone = started_zone

        # Profile-facing direction. This lets app profiles use gesture intent
        # without losing richer relation/zone metadata.
        self.profile_position = profile_position

        self.metadata = dict(metadata or {})

    def to_dict(self):
        return {
            "relation": self.relation,
            "direction": self.direction,
            "distance": self.distance,
            "zone": self.zone,
            "overlap": self.overlap,
            "started_adjacent": self.started_adjacent,
            "vector": self.vector,
            "drag_direction": self.drag_direction,
            "spawn_direction": self.spawn_direction,
            "approach_direction": self.approach_direction,
            "target_zone": self.target_zone,
            "started_zone": self.started_zone,
            "profile_position": self.profile_position,
            "metadata": dict(self.metadata),
        }


class CoordinateSystem:
    """Base coordinate system contract."""

    name = "base"

    def __init__(self, viewport=None):
        from .viewport import ViewportTransform
        self.viewport = viewport or ViewportTransform()

    def to_screen(self, position):
        """Convert logical position to screen point."""
        return self.viewport.to_screen(position)

    def from_screen(self, point):
        """Convert screen point to logical position."""
        return self.viewport.from_screen(point)

    def screen_length(self, logical_length):
        """Convert a logical length to screen-space length."""
        return self.viewport.screen_length(logical_length)

    def world_length(self, screen_length):
        """Convert a screen-space length to logical world length."""
        return self.viewport.world_length(screen_length)

    def snap(self, position, obj=None):
        """Return snapped logical position."""
        return position

    def distance(self, a, b):
        """Distance between logical positions."""
        ax, ay = a
        bx, by = b
        return math.hypot(ax - bx, ay - by)

    def relation(self, source, target, drag_context=None):
        """Describe source/target spatial relation."""
        return DropRelation()


class FreeformSquareGrid(CoordinateSystem):
    """
    Square-grid coordinate system with freeform dragging.

    Positions are stored as screen-like centre points for now. Snapping
    rounds object centres to grid cells while preserving the option to
    later swap in hex, chess, radial, or freeform coordinate systems.
    """

    name = "freeform_square_grid"

    def __init__(self, grid=60, origin=(0, 0), viewport=None):
        super().__init__(viewport=viewport)
        self.grid = float(grid or 60)
        self.origin = origin

    def snap(self, position, obj=None):
        """Snap a declared span by its first cell, retaining centre positions."""
        ox, oy = self.origin
        x, y = position
        g = self.grid
        span = getattr(obj, "cell_span", None)
        if span is None:
            return (round((x - ox) / g) * g + ox,
                    round((y - oy) / g) * g + oy)
        dx = (span[0] - 1) * g / 2
        dy = (span[1] - 1) * g / 2
        col = ((x - ox - dx) / g + 0.5) // 1
        row = ((y - oy - dy) / g + 0.5) // 1
        return (ox + col * g + dx, oy + row * g + dy)

    def _object_size(self, obj):
        span = getattr(obj, "cell_span", None)
        if span is not None:
            gutter = float(getattr(self, "gutter", 4) or 4)
            return (max(10.0, span[0] * self.grid - gutter),
                    max(10.0, span[1] * self.grid - gutter))
        size = getattr(obj, "size", None)
        if size:
            try:
                return (float(size[0]), float(size[1]))
            except Exception:
                pass
        return (self.grid, self.grid)

    def _bounds(self, obj):
        cx, cy = getattr(obj, "position", None) or (0, 0)
        w, h = self._object_size(obj)
        return {
            "left": cx - w / 2.0,
            "right": cx + w / 2.0,
            "top": cy - h / 2.0,
            "bottom": cy + h / 2.0,
            "cx": cx,
            "cy": cy,
            "width": w,
            "height": h,
        }

    def _point_direction(self, dx, dy):
        if abs(dx) >= abs(dy):
            return "left" if dx < 0 else "right"
        return "above" if dy < 0 else "below"

    def _movement_direction(self, start, end):
        if start is None or end is None:
            return None
        sx, sy = start
        ex, ey = end
        dx = ex - sx
        dy = ey - sy
        if dx == 0 and dy == 0:
            return None
        return self._point_direction(dx, dy)

    def _spawn_direction(self, start, end):
        """
        Old Tile Calc used this direction for where result/spawn feedback should
        appear relative to the merge target. It is deliberately the opposite of
        raw movement on each axis.
        """
        direction = self._movement_direction(start, end)
        opposites = {
            "left": "right",
            "right": "left",
            "above": "below",
            "below": "above",
        }
        return opposites.get(direction)

    def _zones_for_target(self, target):
        b = self._bounds(target)
        g = self.grid

        left = b["left"]
        right = b["right"]
        top = b["top"]
        bottom = b["bottom"]
        cx = b["cx"]
        cy = b["cy"]
        w = b["width"]
        h = b["height"]

        return {
            "left": (left - g / 2.0, cy, g / 2.0, h / 2.0 + g * 0.1),
            "right": (right + g / 2.0, cy, g / 2.0, h / 2.0 + g * 0.1),
            "above": (cx, top - g / 2.0, w / 2.0 + g * 0.1, g / 2.0),
            "below": (cx, bottom + g / 2.0, w / 2.0 + g * 0.1, g / 2.0),
            "top_left": (left - g / 2.0, top - g / 2.0, g / 2.0, g / 2.0),
            "top_right": (right + g / 2.0, top - g / 2.0, g / 2.0, g / 2.0),
            "bottom_left": (left - g / 2.0, bottom + g / 2.0, g / 2.0, g / 2.0),
            "bottom_right": (right + g / 2.0, bottom + g / 2.0, g / 2.0, g / 2.0),
        }

    def _point_in_zone(self, point, zone, soft=True):
        px, py = point
        zone_cx, zone_cy, half_w, half_h = zone
        dx = abs(px - zone_cx)
        dy = abs(py - zone_cy)

        if dx > half_w or dy > half_h:
            return False

        if not soft:
            return True

        corner_dx = dx - half_w * 0.6
        corner_dy = dy - half_h * 0.6
        if corner_dx > 0 and corner_dy > 0:
            radius = max(half_w, half_h) * 0.5
            return (corner_dx * corner_dx + corner_dy * corner_dy) <= radius * radius

        return True

    def _classify_point_against_target(self, point, target):
        if point is None or target is None:
            return None

        zones = self._zones_for_target(target)
        for name in ("top_left", "top_right", "bottom_left", "bottom_right"):
            if self._point_in_zone(point, zones[name], soft=True):
                return name

        for name in ("left", "right", "above", "below"):
            if self._point_in_zone(point, zones[name], soft=True):
                return name

        return None

    def _overlaps(self, source, target):
        sb = self._bounds(source)
        tb = self._bounds(target)
        return (
            sb["left"] < tb["right"]
            and sb["right"] > tb["left"]
            and sb["top"] < tb["bottom"]
            and sb["bottom"] > tb["top"]
        )

    def relation(self, source, target, drag_context=None):
        if source is None or target is None:
            return DropRelation()

        drag_context = dict(drag_context or {})

        sx, sy = source.position or (0, 0)
        tx, ty = target.position or (0, 0)
        dx = sx - tx
        dy = sy - ty
        dist = math.hypot(dx, dy)

        center_direction = self._point_direction(dx, dy)
        overlap = self._overlaps(source, target)

        current_zone = self._classify_point_against_target((sx, sy), target)
        drag_start = drag_context.get("drag_start_position")
        started_zone = self._classify_point_against_target(drag_start, target)
        started_adjacent = started_zone is not None or current_zone is not None

        drag_direction = self._movement_direction(drag_start, (sx, sy))
        spawn_direction = self._spawn_direction(drag_start, (sx, sy))
        approach_direction = current_zone or center_direction

        relation = current_zone or ("overlap" if overlap else center_direction)

        # Old Tile Calc lesson:
        # profile direction is an interaction intent, not just geometry. The UI
        # layer may pass a live entry/gesture direction learned during drag. Use
        # that first so exact overlap does not collapse to the arbitrary default
        # "right" direction when dx/dy are both zero.
        explicit_profile_position = drag_context.get("profile_position")
        profile_position = (
            explicit_profile_position
            or drag_direction
            or current_zone
            or started_zone
            or approach_direction
            or spawn_direction
        )

        return DropRelation(
            relation=relation,
            direction=center_direction,
            distance=dist,
            zone=current_zone or ("overlap" if overlap else "cell"),
            overlap=overlap,
            started_adjacent=started_adjacent,
            vector=(dx, dy),
            drag_direction=drag_direction,
            spawn_direction=spawn_direction,
            approach_direction=approach_direction,
            target_zone=current_zone,
            started_zone=started_zone,
            profile_position=profile_position,
            metadata={
                "grid": self.grid,
                "source_bounds": self._bounds(source),
                "target_bounds": self._bounds(target),
            },
        )
