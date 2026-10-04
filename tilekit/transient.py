"""
TileKit transient UI manager.

Transient UI is short-lived board UI: floating action menus, hover targets,
temporary panels, previews, and merge hints.

Interaction rules remain renderer-neutral. The transient layer is responsible
for projecting an InteractionPreview into a compact visual hint without
mutating either source or target object.
"""

import ui


class _MergePreviewHint(ui.View):
    """Compact old-TileCalc-inspired live preview next to the target tile."""

    HEIGHT = 54.0
    MIN_WIDTH = 76.0
    MAX_WIDTH = 184.0
    PAD = 8.0

    def __init__(self, board_view):
        super().__init__(frame=(0, 0, 108, self.HEIGHT))
        self.board_view = board_view
        self.touch_enabled = False
        self.background_color = "#2C2C2E"
        self.corner_radius = 12
        self.border_width = 1
        self.border_color = "#3A3A3C"
        self.alpha = 0.0

        self.result_label = ui.Label()
        self.result_label.font = ("<System-Bold>", 16)
        self.result_label.text_color = "#FFFFFF"
        self.result_label.alignment = ui.ALIGN_CENTER
        self.result_label.touch_enabled = False
        self.add_subview(self.result_label)

        self.message_label = ui.Label()
        self.message_label.font = ("<System>", 9)
        self.message_label.text_color = "#A1A1A6"
        self.message_label.alignment = ui.ALIGN_CENTER
        self.message_label.line_break_mode = ui.LB_TRUNCATE_TAIL
        self.message_label.touch_enabled = False
        self.add_subview(self.message_label)

    def layout(self):
        self.result_label.frame = (4, 5, max(1, self.width - 8), 26)
        self.message_label.frame = (4, 32, max(1, self.width - 8), 15)

    @staticmethod
    def _frame_parts(frame):
        try:
            return float(frame.x), float(frame.y), float(frame.width), float(frame.height)
        except Exception:
            try:
                return tuple(float(value) for value in frame)
            except Exception:
                return None

    def _target_frame(self, preview):
        target = getattr(preview, "target", None)
        if target is None:
            return None

        renderer_view = getattr(getattr(target, "renderer", None), "view", None)
        if renderer_view is not None:
            parts = self._frame_parts(getattr(renderer_view, "frame", None))
            if parts is not None:
                return parts

        position = getattr(target, "position", None)
        if position is None:
            return None
        try:
            cx, cy = self.board_view.board.coords.to_screen(position)
            grid = float(getattr(self.board_view.board.coords, "grid", 60) or 60)
            try:
                grid = float(self.board_view.board.coords.screen_length(grid))
            except Exception:
                pass
            span = getattr(target, "cell_span", None) or (1, 1)
            width = max(grid, grid * float(span[0]))
            height = max(grid, grid * float(span[1]))
            return cx - width / 2, cy - height / 2, width, height
        except Exception:
            return None

    def update_preview(self, preview):
        label = str(getattr(preview, "label", None) or "?")
        message = str(getattr(preview, "message", None) or "merge")
        valid = bool(getattr(preview, "valid", True))

        self.result_label.text = label
        self.message_label.text = message
        self.border_color = "#3A3A3C" if valid else "#FF453A"
        self.result_label.text_color = "#FFFFFF" if valid else "#FF9F0A"

        # Keep the old small-cell feel for ordinary symbols/results but allow a
        # wider exact result without truncating useful mathematical content.
        width = 70.0 + max(len(label), min(len(message), 18)) * 4.0
        width = max(self.MIN_WIDTH, min(self.MAX_WIDTH, width))
        self.width = width
        self.height = self.HEIGHT
        self.layout()

        frame = self._target_frame(preview)
        board_w = max(1.0, float(getattr(self.board_view, "width", 1) or 1))
        board_h = max(1.0, float(getattr(self.board_view, "height", 1) or 1))
        if frame is None:
            x = max(self.PAD, (board_w - width) / 2)
            y = self.PAD
        else:
            tx, ty, tw, th = frame
            x = tx + tw / 2 - width / 2
            y = ty - self.HEIGHT - 8
            if y < self.PAD:
                y = ty + th + 8

        x = max(self.PAD, min(board_w - width - self.PAD, x))
        y = max(self.PAD, min(board_h - self.HEIGHT - self.PAD, y))
        self.frame = (x, y, width, self.HEIGHT)

        try:
            self.bring_to_front()
        except Exception:
            pass
        if self.alpha < 0.9:
            try:
                ui.animate(lambda: setattr(self, "alpha", 0.94), duration=0.10)
            except Exception:
                self.alpha = 0.94


class TransientUIManager:
    """Owns temporary UI state for a board view."""

    def __init__(self, board_view):
        self.view = board_view
        self.last_action_origin = None
        self.preview_state = None
        self._preview_view = None

    def clear_hover(self):
        """Clear the current hover/drop target."""
        view = self.view
        old = getattr(view, "_hover_target", None)
        view._hover_target = None

        if old is not None and old is not view.board.selected:
            try:
                old.set_selected(False)
                view.sync_object(old)
            except Exception:
                pass

    def set_hover_target(self, obj):
        """Highlight the current drop target."""
        view = self.view

        if obj is getattr(view, "_hover_target", None):
            return

        old = getattr(view, "_hover_target", None)
        view._hover_target = obj

        if old is not None and old is not view.board.selected:
            try:
                old.set_selected(False)
                view.sync_object(old)
            except Exception:
                pass

        if obj is not None and obj is not view.board.selected:
            try:
                obj.set_selected(True)
                view.sync_object(obj)
            except Exception:
                pass

    def set_preview(self, preview):
        """Show renderer-neutral interaction preview as a live merge hint."""
        if preview is None:
            self.clear_preview()
            return
        self.preview_state = preview

        hint = self._preview_view
        if hint is None or getattr(hint, "superview", None) is not self.view:
            hint = _MergePreviewHint(self.view)
            self.view.add_subview(hint)
            self._preview_view = hint
        try:
            hint.update_preview(preview)
        except Exception:
            # Preview UI is advisory. It must never break drag/drop truth.
            self.clear_preview()

    def clear_preview(self):
        """Clear current interaction preview and remove its visual hint."""
        self.preview_state = None
        hint = self._preview_view
        self._preview_view = None
        if hint is None:
            return
        try:
            parent = getattr(hint, "superview", None)
            if parent is not None:
                parent.remove_subview(hint)
        except Exception:
            pass

    def hide_action_dock(self):
        """Hide and clear the floating action dock."""
        dock = getattr(self.view, "_action_dock", None)
        if dock is not None:
            dock.clear()

    def show_action_menu(self, obj=None, origin=None):
        """Show a registered editor, or fall back to ordinary actions."""
        view = self.view
        if obj is not None and view.board.card_for(obj) is not None:
            view.open_card(obj)
            return
        dock = getattr(view, "_action_dock", None)
        if dock is None:
            return

        if obj is None:
            view.board.select(None)

        self.last_action_origin = origin
        dock.set_menu(view.board.menu_for(obj), obj=obj, board=view.board)

        if getattr(dock, "hidden", True):
            view.layout()
            return

        view._position_action_dock(obj=obj, origin=origin)
        view.layout()

    def show_selected_actions(self, origin=None):
        """Show actions for the current selected object or selected group."""
        view = self.view
        board = view.board

        group = []
        try:
            group = board.selected_objects()
        except Exception:
            group = []

        if len(group) > 1:
            self.show_group_actions(origin=origin)
            return

        obj = board.selected
        if obj is None:
            self.hide_action_dock()
            view.layout()
            return

        self.show_action_menu(obj=obj, origin=origin)

    def show_group_actions(self, origin=None):
        """Show actions that apply to the current board selection group."""
        view = self.view
        board = view.board
        dock = getattr(view, "_action_dock", None)
        if dock is None:
            return

        self.clear_hover()
        self.clear_preview()
        self.last_action_origin = origin

        try:
            menu = board.menu_for(None)
        except Exception:
            menu = None

        items = []
        for item in list(getattr(menu, "items", []) or []):
            action_id = str(item.get("id") or "")
            if action_id in ("duplicate-selection", "delete-selection"):
                items.append(item)

        if not items:
            self.hide_action_dock()
            view.layout()
            return

        try:
            from .actions import MenuModel
            menu = MenuModel(items)
        except Exception:
            menu.items = items

        dock.set_menu(menu, obj=None, board=board)
        if getattr(dock, "hidden", True):
            view.layout()
            return

        view._position_action_dock(obj=None, origin=origin)
        view.layout()
        view.set_status("group actions")

    def show_global_actions(self, origin=None):
        """Show board-level actions deliberately."""
        self.clear_hover()
        self.clear_preview()
        self.show_action_menu(obj=None, origin=origin)
        self.view.set_status("actions")

    def reset(self, clear_selection=True, status="ready"):
        """Clear transient UI and optionally clear board selection."""
        view = self.view

        self.clear_hover()
        self.clear_preview()
        self.hide_action_dock()
        self.last_action_origin = None

        if clear_selection:
            view.board.select(None)

        view.set_status(status)