"""Fixed-layout board navigation using the existing TileKit viewport."""

import math

from .interactions import InteractionController


class FixedBoardInteractionController(InteractionController):
    """Tap objects or pan the camera without moving board objects."""

    def __init__(self, board_view):
        self._fixed_start = None
        self._fixed_previous = None
        self._fixed_object = None
        super().__init__(board_view)

    def reset_to_neutral(self, clear_selection=True, status="ready"):
        self._fixed_start = None
        self._fixed_previous = None
        self._fixed_object = None
        super().reset_to_neutral(clear_selection, status)

    def begin(self, event):
        self.reset_to_neutral(clear_selection=False, status="ready")
        self._fixed_start = tuple(event.point)
        self._fixed_previous = self._fixed_start
        self._fixed_object = self.view.object_at_point(event.point)
        self.mode = "fixed_tap_pending"
        self.view.transient.hide_action_dock()

    def moved(self, event):
        if self._fixed_start is None:
            return
        point = tuple(event.point)
        if self.mode == "fixed_tap_pending":
            dx = point[0] - self._fixed_start[0]
            dy = point[1] - self._fixed_start[1]
            if math.hypot(dx, dy) < self.tap_move_threshold:
                return
            self.mode = "fixed_pan"

        if self.mode == "fixed_pan":
            previous = self._fixed_previous
            viewport = self.view.board.coords.viewport
            viewport.pan_by((
                point[0] - previous[0],
                point[1] - previous[1],
            ))
            self._fixed_previous = point
            self.view._viewport_changed()

    def ended(self, event):
        if self._fixed_start is None:
            return

        # Release displacement counts even if no move callback arrived.
        self.moved(event)
        is_tap = self.mode == "fixed_tap_pending"
        obj = self._fixed_object
        same_object = (
            obj is not None
            and self.view.object_at_point(event.point) is obj
        )
        self.reset_to_neutral(clear_selection=False, status="ready")

        if not is_tap:
            return
        if not same_object:
            self.view.board.select(None)
            return

        self.view.board.select(obj)
        callback = getattr(self.view, "on_tile_tap", None)
        if callback is not None:
            callback(obj, event)
        else:
            self.view._update_action_dock(origin=event.point)

    def cancelled(self, event):
        self.reset_to_neutral(clear_selection=False, status="cancelled")