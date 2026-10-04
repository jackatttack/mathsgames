"""
TileKit reusable action UI.

This module renders a MenuModel from tilekit.actions into Pythonista buttons.
It stays UI-specific, while actions themselves remain renderer-neutral and
board/object based.
"""

import math
import ui
from .ui_lifecycle import remove_view


class ActionDock(ui.View):
    """Compact floating action menu for the selected object."""

    ITEM_H = 38
    GAP = 6
    PAD = 6
    MAX_COLS = 3
    MIN_BTN_W = 70
    MAX_BTN_W = 132

    # Widest the dock may be when no width is supplied. Kept below a phone
    # screen so a menu never renders wider than the board it floats over.
    DEFAULT_MAX_WIDTH = 340

    def __init__(self, on_action=None, **kwargs):
        super().__init__(**kwargs)
        self.on_action = on_action
        self.obj = None
        self.board = None
        self.menu = None
        self._buttons = []

        # Deliberately solid. The old Tile Calc menu proved that translucent
        # floating menus feel like they stack/ghost during repeated taps.
        self.background_color = "#1C1C1E"
        self.corner_radius = 12
        self.border_width = 1
        self.border_color = "#3A3A3C"
        self.hidden = True
        self.touch_enabled = True

    def clear(self):
        """Remove all current buttons and hide the dock."""
        for btn in list(self._buttons):
            try:
                btn.action = None
            except Exception:
                pass
            try:
                remove_view(btn)
            except Exception:
                pass

        self._buttons = []
        self.obj = None
        self.board = None
        self.menu = None
        self.hidden = True

        try:
            self.set_needs_display()
        except Exception:
            pass

    def set_menu(self, menu, obj=None, board=None):
        """Render a MenuModel for the current object."""
        self.clear()

        items = list(getattr(menu, "items", []) or [])
        items = [item for item in items if item and item.get("enabled", True)]

        if not items:
            return

        self.obj = obj
        self.board = board
        self.menu = menu
        self.hidden = False

        for item in items:
            self._add_button(item)

        # Size against whatever width the dock has been given, falling back to
        # the parent view. The positioner re-sizes and re-lays out afterwards;
        # sizing here against a fixed default is what used to leave buttons
        # laid out for a different width than the dock ended up with.
        available = getattr(getattr(self, "superview", None), "width", None)
        w, h = self.preferred_size(
            max_width=max(1, available - 16) if available else None
        )
        self.width = w
        self.height = h
        self.layout()

        try:
            self.set_needs_display()
        except Exception:
            pass

    def _button_title(self, item):
        icon = item.get("icon") or ""
        label = item.get("label") or item.get("id") or "Action"
        return ("%s %s" % (icon, label)).strip()

    def _button_width(self, title):
        try:
            measured, _h = ui.measure_string(
                title,
                font=("<System-Bold>", 12),
                max_width=999,
            )
            width = measured + 22
        except Exception:
            width = len(str(title or "")) * 8 + 22

        return max(self.MIN_BTN_W, min(self.MAX_BTN_W, width))

    def _add_button(self, item):
        title = self._button_title(item)

        btn = ui.Button(title=title)
        btn.tint_color = "#FFFFFF"
        btn.background_color = "#2C2C2E"
        btn.font = ("<System-Bold>", 12)
        btn.corner_radius = 9
        btn.action_id = item.get("id") or ""
        btn._preferred_width = self._button_width(title)
        btn.action = self._button_tapped

        self.add_subview(btn)
        self._buttons.append(btn)
        return btn

    def _button_tapped(self, sender):
        if self.on_action is not None:
            self.on_action(sender)

    def _rows(self, max_width=None):
        buttons = list(self._buttons)
        if not buttons:
            return []

        if max_width is None:
            max_width = self.DEFAULT_MAX_WIDTH

        max_inner = max(1, max_width - self.PAD * 2)
        rows = []
        row = []
        row_w = 0

        for btn in buttons:
            bw = getattr(btn, "_preferred_width", self.MIN_BTN_W)
            extra = bw if not row else bw + self.GAP

            if row and (row_w + extra > max_inner or len(row) >= self.MAX_COLS):
                rows.append(row)
                row = [btn]
                row_w = bw
            else:
                row.append(btn)
                row_w += extra

        if row:
            rows.append(row)

        return rows

    def preferred_size(self, max_width=None):
        """Return the dock size for the given available width.

        Rows are laid out on an even grid: every button in the menu gets the
        same width, sized to the widest label. Ragged rows of differently
        sized buttons read as overflow rather than as a menu.
        """
        rows = self._rows(max_width=max_width)
        if not rows:
            return (0, 0)

        limit = self.DEFAULT_MAX_WIDTH if max_width is None else max_width
        columns = max(len(row) for row in rows)
        button_w = self._grid_button_width(columns, limit)

        w = self.PAD * 2 + columns * button_w + self.GAP * max(0, columns - 1)
        h = self.PAD * 2 + len(rows) * self.ITEM_H + max(0, len(rows) - 1) * self.GAP
        return (min(w, limit), h)

    def _grid_button_width(self, columns, max_width):
        """Return one column width that fits every button within max_width."""
        widest = self.MIN_BTN_W
        for btn in self._buttons:
            widest = max(widest, getattr(btn, "_preferred_width", self.MIN_BTN_W))

        available = max_width - self.PAD * 2 - self.GAP * max(0, columns - 1)
        fits = available / float(columns) if columns else widest
        return max(self.MIN_BTN_W, min(widest, fits))

    def preferred_height(self):
        return self.preferred_size()[1]

    def layout(self):
        width = max(1, self.width)
        rows = self._rows(max_width=width)
        if not rows:
            return

        columns = max(len(row) for row in rows)
        button_w = self._grid_button_width(columns, width)

        y = self.PAD
        for row in rows:
            row_w = len(row) * button_w + self.GAP * max(0, len(row) - 1)
            x = self.PAD + max(0, (width - self.PAD * 2 - row_w) / 2.0)

            for btn in row:
                btn.frame = (x, y, button_w, self.ITEM_H)
                x += button_w + self.GAP

            y += self.ITEM_H + self.GAP
