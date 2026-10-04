"""Hold-then-drag resizing, ported from old TileCalc's touch language.

This subclasses the stable InteractionController so resize remains a framework
seam rather than another TileCalc-specific touch implementation.
"""

import time

from .interactions import InteractionController


class ResizableInteractionController(InteractionController):
    """Long hold on a tile, then drag, to resize its grid-cell footprint."""

    long_press_threshold = 0.35
    long_press_move_limit = 10.0
    min_cells = 1
    max_cells = 10

    def __init__(self, board_view):
        super().__init__(board_view)
        self._hold_started_at = None
        self._resize_start_point = None
        self._resize_start_span = None
        self._resize_start_cell = None
        self._resize_obj = None

    def _now(self, event=None):
        stamp = getattr(event, "timestamp", None)
        try:
            return float(stamp)
        except Exception:
            return time.monotonic()

    def _resizable(self, obj):
        if obj is None:
            return False
        # Assembly/operator tiles have spatial meaning encoded in their shape;
        # arbitrary manual resizing would make their relation map ambiguous.
        return getattr(obj, "kind", None) not in (
            "operator", "fraction_operator", "equals"
        )

    def begin(self, event):
        super().begin(event)
        if self.mode == "tap_pending" and self._resizable(self.drag_obj):
            self._hold_started_at = self._now(event)
            self._resize_start_point = event.point
            self._resize_start_span = None
            self._resize_start_cell = None
            self._resize_obj = None
        else:
            self._hold_started_at = None

    def _hold_elapsed(self, event):
        if self._hold_started_at is None:
            return 0.0
        return max(0.0, self._now(event) - self._hold_started_at)

    def _enter_resize(self, event):
        obj = self.drag_obj
        if obj is None or not self._resizable(obj):
            return False
        span = getattr(obj, "cell_span", None) or (1, 1)
        self._start_drag_history()
        self._drag_history_label = "Resize tile"
        self._resize_obj = obj
        self._resize_start_span = tuple(span)
        self._resize_start_point = self.start_point or event.point
        try:
            self._resize_start_cell = self.view.board.placer.position_to_cell(
                self.view.board, obj.position, obj
            )
        except Exception:
            self._resize_start_cell = None
        self.mode = "resize"
        obj.set_dragging(False)
        self.view.transient.hide_action_dock()
        self.view.transient.clear_preview()
        self.view.set_status("resize {}×{}".format(span[0], span[1]))
        self.view.log_session_event(
            "resize_start",
            object_id=getattr(obj, "id", None),
            object_kind=getattr(obj, "kind", None),
            span=span,
        )
        return True

    def _candidate_clear(self, new_w, new_h):
        """Keep the old top-left cell anchored and refuse occupied growth."""
        obj = self._resize_obj
        board = self.view.board
        placer = getattr(board, "placer", None)
        cell = self._resize_start_cell
        if obj is None or placer is None or cell is None:
            return True
        occupied = placer.occupied_cells(board, exclude=obj)
        col, row = cell
        candidate = set(
            (col + dc, row + dr)
            for dc in range(int(new_w))
            for dr in range(int(new_h))
        )
        return not bool(candidate & occupied)

    def _resize_to_point(self, point):
        obj = self._resize_obj
        if obj is None:
            return
        sx, sy = self._resize_start_point or point
        dx = point[0] - sx
        dy = point[1] - sy
        coords = self.view.board.coords
        grid = float(getattr(coords, "grid", 60) or 60)
        try:
            screen_grid = float(coords.screen_length(grid))
        except Exception:
            screen_grid = grid
        screen_grid = max(8.0, screen_grid)
        start_w, start_h = self._resize_start_span or (1, 1)

        # One visual grid-cell of drag means one cell of resize. round() gives
        # the same useful dead band as old TileCalc.
        dw = int(round(dx / screen_grid))
        dh = int(round(dy / screen_grid))
        new_w = max(self.min_cells, min(self.max_cells, start_w + dw))
        new_h = max(self.min_cells, min(self.max_cells, start_h + dh))
        if getattr(obj, "cell_span", None) == (new_w, new_h):
            return
        if not self._candidate_clear(new_w, new_h):
            self.view.set_status("resize blocked by tile")
            return
        obj.set_cell_span(new_w, new_h, fixed=True)
        obj.meta["manual_size"] = True
        self.view.sync_object(obj)
        self.view.set_status("resize {}×{}".format(new_w, new_h))

    def moved(self, event):
        if self.mode == "resize":
            self._resize_to_point(event.point)
            return

        if self.mode == "tap_pending" and self._resizable(self.drag_obj):
            sx, sy = self.start_point or event.point
            dx = event.point[0] - sx
            dy = event.point[1] - sy
            distance = (dx * dx + dy * dy) ** 0.5
            elapsed = self._hold_elapsed(event)

            if elapsed >= self.long_press_threshold:
                if self._enter_resize(event):
                    self._resize_to_point(event.point)
                    return

            if distance <= self.long_press_move_limit:
                if distance < self.tap_move_threshold:
                    return

        super().moved(event)
        if self.mode != "tap_pending":
            self._hold_started_at = None

    def ended(self, event):
        if self.mode == "resize":
            obj = self._resize_obj
            span = getattr(obj, "cell_span", None) if obj is not None else None
            if obj is not None:
                obj.set_dragging(False)
                self.view.sync_object(obj)
            self.mode = "idle"
            self.drag_obj = None
            self.drag_start_position = None
            self.drag_offset = (0, 0)
            self.start_point = None
            self.pointer_start_position = None
            self._hold_started_at = None
            self._resize_obj = None
            self._resize_start_span = None
            self._resize_start_cell = None
            self._resize_start_point = None
            self.view.transient.clear_preview()
            self._finish_drag_history()
            self.view.set_status("resized {}×{}".format(*(span or (1, 1))))
            self.view.log_session_event(
                "resize_end",
                object_id=getattr(obj, "id", None),
                span=span,
            )
            return

        self._hold_started_at = None
        self._resize_obj = None
        self._resize_start_span = None
        self._resize_start_cell = None
        self._resize_start_point = None
        super().ended(event)
