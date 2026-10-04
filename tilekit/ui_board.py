"""
Pythonista UI board wrapper for TileKit.

UIBoardView mounts TileObjects with renderers and handles basic pointer
input. The model remains in tilekit.board.Board.
"""

import ui
from .ui_lifecycle import remove_view
import time

from .board import Board
from .renderers import default_renderer_registry
from .ui_actions import ActionDock
from .ui_palette import PaletteDock
from .ui_cursor import SpawnCursorView
from .input import PointerEvent
from .interactions import InteractionController
from .transient import TransientUIManager
from .viewport_gestures import ViewportGestureController
from .fixed_interactions import FixedBoardInteractionController
from .ui_board_grid import BoardGridView


def _measure_text(text, font_size):
    """Measure text the way Pythonista will actually draw it.

    tilekit.sizing falls back to an average-character estimate so the core
    stays headless. Once a real board view exists, ui.measure_string is
    available and cell spans should be chosen from true rendered widths.
    """
    return ui.measure_string(
        str(text or ""),
        font=("<System-Bold>", float(font_size)),
        max_width=0,
    )[0]


class UIBoardView(ui.View):
    """Visual Pythonista wrapper around a renderer-neutral Board."""

    def __init__(self, board=None, renderer_registry=None,
                 interaction_mode="edit", on_tile_tap=None, **kwargs):
        # Fixed-board interaction mode.
        if interaction_mode not in ("edit", "fixed"):
            raise ValueError("Unknown board interaction mode")
        if on_tile_tap is not None and not callable(on_tile_tap):
            raise TypeError("on_tile_tap must be callable")
        super().__init__(**kwargs)
        self.interaction_mode = interaction_mode
        self.on_tile_tap = on_tile_tap
        self.board = board or Board()
        self.board.measure_text = _measure_text
        self.renderer_registry = renderer_registry or default_renderer_registry()
        self.background_color = "#1C1C1E"
        self.touch_enabled = True
        self.multitouch_enabled = True

        # Add the background first so tiles and controls stay above it.
        self._grid_view = BoardGridView(self.board)
        self.add_subview(self._grid_view)

        self._hover_target = None
        self._spawn_cursor_position = self.board.coords.snap((180, 360))
        input_session = getattr(self.board, "input_session", None)
        if input_session is not None:
            input_session.set_cursor(self._spawn_cursor_position)
        self._spawn_cursor_touch_start = None
        self._spawn_cursor_touch_candidate = False
        self._last_empty_tap = None
        self._empty_touch_time = None

        self._spawn_cursor = SpawnCursorView()
        self._spawn_cursor.set_position(
            self._spawn_cursor_position,
            grid=getattr(self.board.coords, "grid", 60),
        )
        self.add_subview(self._spawn_cursor)

        self._status = ui.Label()
        self._status.background_color = (0, 0, 0, 0.35)
        self._status.text_color = "#FFFFFF"
        self._status.font = ("<System>", 11)
        self._status.alignment = ui.ALIGN_LEFT
        self._status.text = "TileKit ready"
        try:
            self._status.touch_enabled = False
        except Exception:
            pass
        self.add_subview(self._status)

        self._action_dock = ActionDock(on_action=self._run_action_from_dock)
        self.add_subview(self._action_dock)

        self._palette_dock = PaletteDock(board=self.board, on_spawn=self._spawn_from_palette)
        self.add_subview(self._palette_dock)

        self.transient = TransientUIManager(self)
        controller = (FixedBoardInteractionController
                      if interaction_mode == "fixed"
                      else InteractionController)
        self.interactions = controller(self)

        viewport = getattr(self.board.coords, "viewport", None)
        self.viewport_gestures = ViewportGestureController(
            viewport,
            on_change=self._viewport_changed,
        ) if viewport is not None else None

        self.mount_all()
        self.layout()

    def mount_all(self):
        """Mount renderers for all current objects."""
        for obj in list(self.board.objects):
            self.mount_object(obj)

    def remount_all(self):
        """Rebuild all object renderers after a whole-board model restore."""
        card = getattr(self, "_object_card", None)
        if card is not None:
            card.close(commit=False)
        for sub in list(self.subviews):
            if getattr(sub, "obj", None) is not None:
                try:
                    sub.hidden = True
                    sub.alpha = 0.0
                    sub.touch_enabled = False
                    sub.frame = (0, 0, 0, 0)
                except Exception:
                    pass
                try:
                    if hasattr(sub, "badge"):
                        sub.badge.hidden = True
                        sub.badge.text = ""
                except Exception:
                    pass
                try:
                    if hasattr(sub, "label"):
                        sub.label.hidden = True
                        sub.label.text = ""
                except Exception:
                    pass
                try:
                    sub.obj = None
                except Exception:
                    pass
                try:
                    remove_view(sub)
                except Exception:
                    pass

        for obj in list(self.board.objects):
            try:
                obj.renderer = None
            except Exception:
                pass

        self.mount_all()

        for overlay_name in ("_spawn_cursor", "_status", "_action_dock", "_palette_dock"):
            overlay = getattr(self, overlay_name, None)
            if overlay is not None:
                try:
                    overlay.bring_to_front()
                except Exception:
                    pass

        self.layout()

    def layout(self):
        """Lay out persistent overlays.

        Board-located overlays are projected through the viewport. Screen-fixed
        UI such as palette and status docks remains in view coordinates.
        """
        grid_view = getattr(self, "_grid_view", None)
        if grid_view is not None:
            grid_view.frame = (0, 0, self.width, self.height)
            grid_view.hidden = not (
                getattr(self.board.coords, "name", "")
                == "freeform_square_grid"
                and getattr(self.board, "show_grid", True)
            )
            grid_view.set_needs_display()

        cursor = getattr(self, "_spawn_cursor", None)
        if cursor is not None:
            cursor.hidden = self.interaction_mode == "fixed"
            try:
                coords = self.board.coords
                cursor.set_position(
                    coords.to_screen(self._spawn_cursor_position),
                    grid=coords.screen_length(getattr(coords, "grid", 60)),
                )
            except Exception:
                pass

        palette = getattr(self, "_palette_dock", None)
        palette_top = self.height
        if palette is not None:
            try:
                pal_h = max(1, palette.preferred_height())
            except Exception:
                pal_h = 48
            palette.frame = (
                0,
                max(0, self.height - pal_h),
                max(1, self.width),
                pal_h,
            )
            palette_top = palette.y
            try:
                palette.layout()
            except Exception:
                pass

        if getattr(self, "_status", None) is not None:
            self._status.frame = (
                8,
                max(8, min(self.height - 30, palette_top - 28)),
                max(1, self.width - 16),
                22,
            )
            try:
                self._status.bring_to_front()
            except Exception:
                pass

        dock = getattr(self, "_action_dock", None)
        if dock is not None and not getattr(dock, "hidden", True):
            try:
                dock.bring_to_front()
            except Exception:
                pass

        if palette is not None:
            try:
                palette.bring_to_front()
            except Exception:
                pass

        card = getattr(self, "_object_card", None)
        if card is not None:
            card.frame = self.bounds
            card.layout()
            card.bring_to_front()

    def set_status(self, text):
        """Set the board status/debug strip."""
        if getattr(self, "_status", None) is not None:
            self._status.text = str(text or "")
            try:
                self._status.bring_to_front()
            except Exception:
                pass

    def log_session_event(self, kind, **data):
        """Record a live app-session event when a session logger is attached."""
        logger = getattr(self, "session_log", None)
        if logger is None:
            return None
        try:
            return logger.record(kind, board=self.board, **data)
        except Exception:
            return None

    def _update_action_button(self):
        """Compatibility wrapper while callers migrate to ActionDock."""
        self._update_action_dock()

    def dismiss_transient_ui(self, clear_selection=True):
        """Dismiss temporary UI state such as menus, hover, and drag state."""
        self.interactions.reset_to_neutral(
            clear_selection=clear_selection,
            status="ready",
        )

    def open_card(self, obj):
        """Open an object's profile-provided editor."""
        from .ui_cards import open_object_card
        return open_object_card(self, obj)

    def show_global_actions(self, origin=None):
        """Show board-level actions deliberately, without selecting an object."""
        self.transient.show_global_actions(origin=origin)

    def _position_action_dock(self, obj=None, origin=None):
        """Place the action menu near an object, preferably above it."""
        dock = getattr(self, "_action_dock", None)
        if dock is None or getattr(dock, "hidden", True):
            return

        max_w = max(1, self.width - 16)
        try:
            dock_w, dock_h = dock.preferred_size(max_width=max_w)
        except Exception:
            dock_w = min(max_w, 320)
            dock_h = max(1, dock.preferred_height())

        dock_w = max(1, min(dock_w, max_w))
        dock_h = max(1, dock_h)

        # The dock lays its buttons out for its own width, so the final width
        # must be set before the buttons are placed.
        dock.width = dock_w
        dock.height = dock_h
        try:
            dock.layout()
        except Exception:
            pass

        anchor_x = self.width * 0.5
        anchor_y = 8
        anchor_h = 0

        view = None
        if obj is not None:
            view = getattr(getattr(obj, "renderer", None), "view", None)

        if view is not None:
            anchor_x = view.x + view.width * 0.5
            anchor_y = view.y
            anchor_h = view.height
        elif origin is not None:
            try:
                anchor_x, anchor_y = origin
            except Exception:
                pass

        x = anchor_x - dock_w * 0.5
        x = max(8, min(x, max(8, self.width - dock_w - 8)))

        y = anchor_y - dock_h - 8
        if y < 8:
            y = anchor_y + anchor_h + 8
        y = max(8, min(y, max(8, self.height - dock_h - 38)))

        dock.frame = (x, y, dock_w, dock_h)
        dock.layout()

        try:
            dock.bring_to_front()
        except Exception:
            pass

    def _update_action_dock(self, origin=None):
        """Render the selected object's local action menu."""
        self.transient.show_selected_actions(origin=origin)

    def _run_action_from_dock(self, sender):
        """Run an action selected from the dock."""
        action_id = getattr(sender, "action_id", "") if sender is not None else ""
        if not action_id:
            return

        obj = self.board.selected
        if action_id in ("duplicate-selection", "delete-selection"):
            obj = None

        action = self.board.action_registry.get(action_id)
        restores_board = bool(getattr(action, "restores_board", False))

        origin = getattr(self.transient, "last_action_origin", None) or (90, 110)

        # Old Tile Calc win: dismiss the menu before running the action so
        # repeated taps cannot leave visual ghosts or stale highlighted buttons.
        self.transient.hide_action_dock()

        before = len(self.board.objects)
        result = self.board.run_action(action_id, obj, {
            "view": self,
            "origin": origin,
        })
        after = len(self.board.objects)

        self.log_session_event(
            "action",
            action_id=action_id,
            object_id=getattr(obj, "id", None),
            object_label=getattr(obj, "label", None),
            before_count=before,
            after_count=after,
            result=result,
        )

        if action_id in ("undo", "redo") or restores_board:
            self.remount_all()
            self._update_action_dock()
            self.set_status("action {} -> {}".format(action_id, result))
            return

        for new_obj in list(self.board.objects):
            if getattr(new_obj, "renderer", None) is None:
                self.mount_object(new_obj)

        self.sync_all()
        self._unmount_removed_objects()
        self._update_action_dock()

        if after > before:
            self.set_status("action {} spawned {}".format(action_id, after - before))
        else:
            self.set_status("action {} -> {}".format(action_id, result))

    def toggle_palette(self):
        """Show/hide the bottom palette dock."""
        dock = getattr(self, "_palette_dock", None)
        if dock is not None:
            dock.toggle()

    def show_palette(self):
        """Expand the bottom palette dock."""
        dock = getattr(self, "_palette_dock", None)
        if dock is not None:
            dock.show()

    def hide_palette(self):
        """Collapse the bottom palette dock."""
        dock = getattr(self, "_palette_dock", None)
        if dock is not None:
            dock.hide()

    def set_spawn_cursor_position(self, position):
        """Move the visible spawn cursor to the nearest logical grid cell."""
        try:
            position = self.board.coords.snap(position)
        except Exception:
            pass

        self._spawn_cursor_position = position

        input_session = getattr(self.board, "input_session", None)
        if input_session is not None:
            input_session.set_cursor(position)

        cursor = getattr(self, "_spawn_cursor", None)
        if cursor is not None:
            try:
                coords = self.board.coords
                cursor.set_position(
                    coords.to_screen(position),
                    grid=coords.screen_length(getattr(coords, "grid", 60)),
                )
            except Exception:
                pass

        return position

    def _advance_spawn_cursor_after(self, obj):
        """Advance cursor to the next free cell after a palette spawn."""
        if obj is None:
            return self._spawn_cursor_position

        try:
            placer = self.board.placer
            cell = placer.position_to_cell(
                self.board, getattr(obj, "position", None), obj
            )
            w, _h = placer.object_cells(self.board, obj)
            next_cell = (cell[0] + max(1, w), cell[1])
            found = placer.find_free_cell(self.board, obj, next_cell)
            position = placer.cell_to_position(self.board, found)
        except Exception:
            try:
                x, y = getattr(obj, "position", None) or self._spawn_cursor_position
                grid = float(getattr(self.board.coords, "grid", 60) or 60)
                position = self.board.coords.snap((x + grid, y))
            except Exception:
                position = self._spawn_cursor_position

        return self.set_spawn_cursor_position(position)

    def _track_spawn_cursor_touch_begin(self, point):
        """Start an empty-board tap candidate for cursor movement."""
        if self.interaction_mode == "fixed":
            self._spawn_cursor_touch_start = None
            self._spawn_cursor_touch_candidate = False
            return
        self._spawn_cursor_touch_start = point
        self._spawn_cursor_touch_candidate = self.object_at_point(point) is None

    def _track_spawn_cursor_touch_move(self, point):
        """Cancel cursor movement if the gesture becomes a drag/lasso."""
        if not self._spawn_cursor_touch_candidate:
            return

        start = self._spawn_cursor_touch_start
        if start is None:
            self._spawn_cursor_touch_candidate = False
            return

        try:
            dx = float(point[0]) - float(start[0])
            dy = float(point[1]) - float(start[1])
            if (dx * dx + dy * dy) > 64:
                self._spawn_cursor_touch_candidate = False
        except Exception:
            self._spawn_cursor_touch_candidate = False

    def _commit_spawn_cursor_touch(self, point):
        """Move spawn cursor after a clean empty-board tap."""
        should_move = bool(self._spawn_cursor_touch_candidate)
        self._spawn_cursor_touch_start = None
        self._spawn_cursor_touch_candidate = False

        if not should_move:
            return None

        if self.object_at_point(point) is not None:
            return None

        try:
            position = self.board.coords.from_screen(point)
        except Exception:
            position = point

        position = self.set_spawn_cursor_position(position)
        self.set_status("cursor {}".format(position))
        return position

    def _spawn_from_palette(self, item_id):
        """Spawn a palette item at the visible spawn cursor and mount it."""
        palette = getattr(self.board, "palette", None)
        if palette is None:
            return None

        item = palette.get(item_id)
        if item is None:
            return None

        origin = getattr(self, "_spawn_cursor_position", None)
        if origin is None:
            origin = (
                self.width * 0.5 if self.width else 180,
                max(90, (self.height - 170) if self.height else 300),
            )
            origin = self.set_spawn_cursor_position(origin)

        before = len(self.board.objects)
        obj = palette.spawn(item_id, self.board, origin=origin)
        after = len(self.board.objects)

        if obj is None:
            self.set_status("palette spawn failed {}".format(item_id))
            return None

        if getattr(obj, "renderer", None) is None:
            self.mount_object(obj)

        self.sync_object(obj)

        view_obj = getattr(getattr(obj, "renderer", None), "view", None)
        if view_obj is not None:
            try:
                view_obj.hidden = False
                view_obj.alpha = 1.0
                view_obj.bring_to_front()
            except Exception:
                pass

        self.transient.hide_action_dock()
        if after > before:
            self._advance_spawn_cursor_after(obj)

        self.log_session_event(
            "palette_spawn",
            item_id=item_id,
            item_label=getattr(item, "label", None),
            object_id=getattr(obj, "id", None),
            object_kind=getattr(obj, "kind", None),
            object_label=getattr(obj, "label", None),
            before_count=before,
            after_count=after,
            position=getattr(obj, "position", None),
            cursor_position=getattr(self, "_spawn_cursor_position", None),
        )

        self.set_status("spawned {}".format(getattr(obj, "label", item_id)))
        self.layout()
        return obj
    def _set_hover_target(self, obj):
        """Highlight the current drop target."""
        self.transient.set_hover_target(obj)

    def mount_object(self, obj):
        """Mount one object if it has not already been mounted."""
        if obj.renderer is not None:
            return obj.renderer.view
        renderer = self.renderer_registry.create(obj.renderer_id)
        obj.renderer = renderer
        return renderer.mount(self, obj)

    def add_object(self, obj, position=None, snap=True):
        """Add an object to the model and mount its renderer."""
        self.board.add_object(obj, position=position, snap=snap)
        return self.mount_object(obj)

    def object_at_point(self, point, excluding=None):
        """Return topmost rendered object containing a screen point."""
        px, py = point
        for obj in reversed(self.board.objects):
            if obj is excluding:
                continue
            view = getattr(getattr(obj, "renderer", None), "view", None)
            if view is None:
                continue
            if view.x <= px <= view.x + view.width and view.y <= py <= view.y + view.height:
                return obj
        return None

    def objects_intersecting_rect(self, rect):
        """Return rendered objects whose view frames intersect rect."""
        x, y, w, h = rect
        x2 = x + w
        y2 = y + h
        hits = []

        for obj in list(self.board.objects):
            view = getattr(getattr(obj, "renderer", None), "view", None)
            if view is None:
                continue

            vx = view.x
            vy = view.y
            vw = view.width
            vh = view.height

            if vx < x2 and (vx + vw) > x and vy < y2 and (vy + vh) > y:
                hits.append(obj)

        return hits

    def sync_object(self, obj):
        """Sync one object, safely remounting when its renderer type changes."""
        if obj is None:
            return

        def purge_stale_views(keep=None):
            """Remove orphaned rendered views still pointing at this object."""
            for sub in list(getattr(self, "subviews", []) or []):
                if sub is keep or sub is getattr(self, "_object_card", None):
                    # Editors also expose obj; they are not duplicate renderers.
                    continue
                if getattr(sub, "obj", None) is not obj:
                    continue

                try:
                    remove_view(sub)
                except Exception:
                    try:
                        self.remove_subview(sub)
                    except Exception:
                        # Last-resort neutralisation: an orphaned visual must
                        # no longer participate as a view for this object.
                        try:
                            sub.hidden = True
                            sub.obj = None
                        except Exception:
                            pass

        renderer = getattr(obj, "renderer", None)

        if renderer is not None:
            current_id = getattr(renderer, "renderer_id", None)
            wanted_id = getattr(obj, "renderer_id", None)

            if current_id != wanted_id:
                old_view = getattr(renderer, "view", None)

                try:
                    renderer.unmount()
                except Exception:
                    pass

                # Some Pythonista ui.View instances can survive a renderer
                # unmount during an in-place type change. Explicitly purge the
                # old object-bound view before mounting the replacement.
                if old_view is not None:
                    try:
                        if old_view in self.subviews:
                            remove_view(old_view)
                    except Exception:
                        pass

                purge_stale_views()
                obj.renderer = None
                renderer = None

        if renderer is None:
            # Do not allow an earlier failed/remnant renderer to coexist with
            # the freshly mounted visual.
            purge_stale_views()

            try:
                self.mount_object(obj)
            except Exception:
                return

            renderer = getattr(obj, "renderer", None)

        if renderer is not None:
            renderer.update(obj)

            # Renderer transitions should leave exactly one live visual bound
            # to this object.
            purge_stale_views(keep=getattr(renderer, "view", None))

    def sync_all(self):
        """Sync all object renderers."""
        for obj in self.board.objects:
            self.sync_object(obj)

    def _viewport_changed(self, viewport=None):
        """Refresh board-projected UI after camera pan/zoom."""
        self.sync_all()
        self.layout()
        self.transient.clear_preview()
        try:
            self.set_needs_display()
        except Exception:
            pass

    def _begin_viewport_capture(self):
        """Yield one-pointer interaction state to a two-pointer camera gesture."""
        self._last_empty_tap = None
        self._empty_touch_time = None
        self._spawn_cursor_touch_start = None
        self._spawn_cursor_touch_candidate = False
        self._set_hover_target(None)
        self.interactions.reset_to_neutral(
            clear_selection=False,
            status="viewport",
        )
        self.transient.hide_action_dock()
        self.log_session_event(
            "viewport_begin",
            scale=getattr(getattr(self.board.coords, "viewport", None), "scale", None),
            offset=getattr(getattr(self.board.coords, "viewport", None), "offset", None),
        )

    def _end_viewport_capture(self):
        """Finish a camera gesture without turning the surviving touch into a tap."""
        viewport = getattr(self.board.coords, "viewport", None)
        self.set_status(
            "viewport {:.2f}x".format(
                float(getattr(viewport, "scale", 1.0) or 1.0)
            )
        )
        self.log_session_event(
            "viewport_end",
            scale=getattr(viewport, "scale", None),
            offset=getattr(viewport, "offset", None),
        )

    def _handle_empty_double_tap(self, event):
        """Consume two clean empty-space taps as one undo gesture.

        Distances are screen pixels, independent of board zoom. A first tap
        still places the spawn cursor immediately.
        """
        now = event.timestamp
        if now is None:
            now = time.monotonic()
        start = self._spawn_cursor_touch_start
        started = self._empty_touch_time
        clean = (
            self.interaction_mode == "edit"
            and self._spawn_cursor_touch_candidate
            and self.interactions.mode in ("pan_pending", "idle")
            and start is not None
            and started is not None
            and 0 <= now - started < 0.30
            and self.object_at_point(event.point) is None
        )
        if clean:
            dx = event.point[0] - start[0]
            dy = event.point[1] - start[1]
            clean = dx * dx + dy * dy <= 36

        if not clean:
            self._last_empty_tap = None
            return False

        previous = self._last_empty_tap
        self._last_empty_tap = (now, tuple(event.point))
        if previous is None:
            return False

        previous_time, previous_point = previous
        dx = event.point[0] - previous_point[0]
        dy = event.point[1] - previous_point[1]
        if not (0 <= now - previous_time < 0.30
                and dx * dx + dy * dy < 900):
            return False

        self._last_empty_tap = None
        self._empty_touch_time = None
        self._spawn_cursor_touch_candidate = False
        self._spawn_cursor_touch_start = None
        self.dismiss_transient_ui(clear_selection=False)
        changed = self.board.undo()
        if changed:
            self.remount_all()
        self.set_status("Undone" if changed else "Nothing to undo")
        self.log_session_event("double_tap_undo", changed=changed)
        return True

    def touch_began(self, touch):
        event = PointerEvent.from_touch("began", touch, board_view=self)
        self.log_session_event("touch_began", point=event.point)

        # Viewport multitouch requires a stable platform touch identity.
        # Synthetic/legacy callers without touch_id remain one-pointer only.
        pointer_id = getattr(touch, "touch_id", None)
        gestures = getattr(self, "viewport_gestures", None)
        was_capturing = bool(getattr(gestures, "capturing", False))
        if gestures is not None and pointer_id is not None:
            capturing = gestures.touch_began(pointer_id, event.point)
            if capturing:
                if not was_capturing:
                    self._begin_viewport_capture()
                return

        self._track_spawn_cursor_touch_begin(event.point)
        self._empty_touch_time = (
            event.timestamp if event.timestamp is not None else time.monotonic()
        )
        if not self._spawn_cursor_touch_candidate:
            self._last_empty_tap = None
        self.interactions.begin(event)

    def touch_moved(self, touch):
        event = PointerEvent.from_touch("moved", touch, board_view=self)

        pointer_id = getattr(touch, "touch_id", None)
        gestures = getattr(self, "viewport_gestures", None)
        if gestures is not None and pointer_id is not None:
            capturing = gestures.touch_moved(pointer_id, event.point)
            if capturing:
                self._spawn_cursor_touch_candidate = False
                return

        self._track_spawn_cursor_touch_move(event.point)
        self.interactions.moved(event)
        if (not self._spawn_cursor_touch_candidate
                or self.interactions.mode not in ("pan_pending", "idle")):
            self._last_empty_tap = None

    def touch_ended(self, touch):
        event = PointerEvent.from_touch("ended", touch, board_view=self)

        pointer_id = getattr(touch, "touch_id", None)
        gestures = getattr(self, "viewport_gestures", None)
        if gestures is not None and pointer_id is not None:
            was_capturing = bool(gestures.capturing)
            gestures.touch_ended(pointer_id)
            if was_capturing:
                if not gestures.capturing:
                    self._end_viewport_capture()
                return

        if self._handle_empty_double_tap(event):
            return
        self.interactions.ended(event)
        self._commit_spawn_cursor_touch(event.point)
        self.log_session_event(
            "touch_ended",
            point=event.point,
            mode=getattr(self.interactions, "mode", None),
        )

    def touch_cancelled(self, touch):
        self._last_empty_tap = None
        self._empty_touch_time = None
        self._spawn_cursor_touch_candidate = False
        event = PointerEvent.from_touch("cancelled", touch, board_view=self)

        pointer_id = getattr(touch, "touch_id", None)
        gestures = getattr(self, "viewport_gestures", None)
        if gestures is not None and pointer_id is not None:
            was_capturing = bool(gestures.capturing)
            gestures.touch_cancelled(pointer_id)
            if was_capturing:
                if not gestures.capturing:
                    self._end_viewport_capture()
                return

        self.interactions.cancelled(event)

    def _unmount_object(self, obj):
        """Force-remove one object's renderer view."""
        if obj is None:
            return

        renderer = getattr(obj, "renderer", None)
        view = getattr(renderer, "view", None)

        if view is not None:
            # Pythonista may briefly draw a view after removal is requested.
            # Hide and neutralise it first so dead views cannot remain visible.
            try:
                view.hidden = True
                view.alpha = 0.0
                view.touch_enabled = False
                view.frame = (0, 0, 0, 0)
            except Exception:
                pass
            try:
                if hasattr(view, "label"):
                    view.label.hidden = True
                    view.label.text = ""
            except Exception:
                pass
            try:
                view.obj = None
            except Exception:
                pass
            try:
                remove_view(view)
            except Exception:
                pass

        if renderer is not None:
            try:
                renderer.view = None
            except Exception:
                pass

        obj.renderer = None

    def _unmount_removed_objects(self):
        """Remove renderer views for objects no longer present."""
        live = set([id(o) for o in self.board.objects])
        for sub in list(self.subviews):
            obj = getattr(sub, "obj", None)
            if obj is not None and id(obj) not in live:
                try:
                    sub.hidden = True
                    sub.alpha = 0.0
                    sub.touch_enabled = False
                    sub.frame = (0, 0, 0, 0)
                except Exception:
                    pass
                try:
                    if hasattr(sub, "label"):
                        sub.label.hidden = True
                        sub.label.text = ""
                except Exception:
                    pass
                try:
                    sub.obj = None
                except Exception:
                    pass
                try:
                    remove_view(sub)
                except Exception:
                    pass
