"""
TileKit viewport gesture state.

This module owns the reusable geometry for two-pointer board navigation.
It deliberately knows nothing about Pythonista views, TileObjects, calculator
rules, lasso selection, or renderer details.

UI adapters feed pointer ids + screen points into this controller and decide
when viewport capture should take priority over their normal one-pointer tools.
"""

import math


class ViewportGestureController:
    """Track a two-pointer pan/zoom gesture for a ViewportTransform."""

    def __init__(self, viewport, on_change=None):
        self.viewport = viewport
        self.on_change = on_change
        self.active_points = {}
        self.capturing = False

        self._gesture_ids = []
        self._start_distance = 1.0
        self._start_midpoint = (0.0, 0.0)
        self._start_scale = 1.0
        self._start_offset = (0.0, 0.0)
        self._anchor_world = (0.0, 0.0)

    def _point(self, point):
        try:
            x, y = point
            return (float(x), float(y))
        except Exception:
            return (0.0, 0.0)

    def _midpoint(self, a, b):
        return (
            (a[0] + b[0]) * 0.5,
            (a[1] + b[1]) * 0.5,
        )

    def _distance(self, a, b):
        return math.hypot(b[0] - a[0], b[1] - a[1])

    def has_pointer(self, pointer_id):
        return pointer_id in self.active_points

    def touch_began(self, pointer_id, point):
        self.active_points[pointer_id] = self._point(point)

        if not self.capturing and len(self.active_points) >= 2:
            self._begin_capture()

        return self.capturing

    def touch_moved(self, pointer_id, point):
        if pointer_id not in self.active_points:
            self.active_points[pointer_id] = self._point(point)
        else:
            self.active_points[pointer_id] = self._point(point)

        if self.capturing:
            self._update_capture()

        return self.capturing

    def touch_ended(self, pointer_id):
        was_capturing = self.capturing
        self.active_points.pop(pointer_id, None)

        # Once a two-pointer gesture has captured the board, keep swallowing
        # the surviving finger until all fingers from that gesture are lifted.
        if was_capturing and not self.active_points:
            self._end_capture()

        return self.capturing

    def touch_cancelled(self, pointer_id):
        return self.touch_ended(pointer_id)

    def reset(self):
        self.active_points = {}
        self._end_capture()

    def _begin_capture(self):
        ids = list(self.active_points.keys())[:2]
        if len(ids) < 2:
            return

        p1 = self.active_points[ids[0]]
        p2 = self.active_points[ids[1]]
        midpoint = self._midpoint(p1, p2)
        distance = max(1.0, self._distance(p1, p2))

        self._gesture_ids = ids
        self._start_distance = distance
        self._start_midpoint = midpoint
        self._start_scale = float(getattr(self.viewport, "scale", 1.0) or 1.0)
        self._start_offset = tuple(getattr(self.viewport, "offset", (0.0, 0.0)))

        ox, oy = self._start_offset
        sx, sy = midpoint
        scale = self._start_scale or 1.0
        self._anchor_world = (
            (sx - ox) / scale,
            (sy - oy) / scale,
        )

        self.capturing = True

    def _update_capture(self):
        if len(self._gesture_ids) < 2:
            return

        id1, id2 = self._gesture_ids[:2]
        if id1 not in self.active_points or id2 not in self.active_points:
            return

        p1 = self.active_points[id1]
        p2 = self.active_points[id2]

        current_midpoint = self._midpoint(p1, p2)
        current_distance = max(1.0, self._distance(p1, p2))
        factor = current_distance / float(self._start_distance or 1.0)

        new_scale = self.viewport.clamp_scale(self._start_scale * factor)
        wx, wy = self._anchor_world
        mx, my = current_midpoint

        self.viewport.scale = new_scale
        self.viewport.offset = (
            mx - wx * new_scale,
            my - wy * new_scale,
        )

        if self.on_change is not None:
            self.on_change(self.viewport)

    def _end_capture(self):
        self.capturing = False
        self._gesture_ids = []
        self._start_distance = 1.0
        self._start_midpoint = (0.0, 0.0)
        self._start_scale = float(getattr(self.viewport, "scale", 1.0) or 1.0)
        self._start_offset = tuple(getattr(self.viewport, "offset", (0.0, 0.0)))