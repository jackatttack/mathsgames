"""
TileKit reusable palette UI.
This is the first small Pythonista surface for the renderer-neutral palette
model. It borrows the old Tile Calc keyboard mini-bar pattern:
- clear overlay background;
- dark floating key buttons;
- bottom/right show-hide handle;
- two-row horizontal strip when expanded;
- only a compact handle when collapsed.
The palette remains generic. Apps register PaletteItems on the board; this UI
only renders those items and asks the board/view layer to spawn them.
"""
import ui
from .ui_lifecycle import remove_view
def _hex_to_rgba(hex_color, alpha=1.0):
    """Convert '#RRGGBB' to a Pythonista rgba tuple."""
    try:
        s = str(hex_color or "#2C2C2E").strip()
        if s.startswith("#"):
            s = s[1:]
        if len(s) != 6:
            raise ValueError("expected RRGGBB")
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
        return (r, g, b, float(alpha))
    except Exception:
        return (0.17, 0.17, 0.18, float(alpha))


class PaletteKeyButton(ui.View):
    """Palette key view that can draw as a mini tile and still act like a button."""
    def __init__(self, title="", **kwargs):
        super().__init__(**kwargs)
        self.touch_enabled = True
        self.background_color = "clear"
        self.palette_style = {}
        self.draw_tile_like = False
        self.action = None
        self.palette_id = ""
        self.palette_label = ""
        self.palette_item = None
        self.tint_color = "#FFFFFF"
        self.border_color = "#3A3A3C"
        self.border_width = 0
        self.corner_radius = 10

        self._title = str(title or "")
        self.label = ui.Label(frame=self.bounds)
        self.label.flex = "WH"
        self.label.alignment = ui.ALIGN_CENTER
        self.label.number_of_lines = 1
        self.label.background_color = "clear"
        self.label.text = self._title
        self.label.text_color = self.tint_color
        self.label.font = ("<System-Bold>", 15)
        try:
            self.label.touch_enabled = False
        except Exception:
            pass
        self.add_subview(self.label)

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = str(value or "")
        try:
            self.label.text = self._title
        except Exception:
            pass

    def layout(self):
        try:
            self.label.frame = self.bounds
        except Exception:
            pass

    def touch_ended(self, touch):
        action = getattr(self, "action", None)
        if action is not None:
            action(self)

    def draw(self):
        style = getattr(self, "palette_style", {}) or {}
        if not style.get("tile_like"):
            return

        w, h = self.width, self.height
        if w < 1 or h < 1:
            return

        bg = style.get("background_color", "#2C2C2E")
        border_color = style.get("border_color", "#FFFFFF")
        border_width = float(style.get("border_width", 1.5) or 1.5)
        cr = float(style.get("corner_radius", 12) or 12)

        path = ui.Path.rounded_rect(0, 0, w, h, cr)
        ui.set_color(_hex_to_rgba(bg))
        path.fill()

        # Old Tile Calc-style glossy top sweep, deliberately generic.
        with ui.GState():
            ui.Path.rounded_rect(0, 0, w, h, cr).add_clip()
            highlight = ui.Path()
            highlight.move_to(0, 0)
            highlight.line_to(w, 0)
            highlight.line_to(w, h * 0.38)
            highlight.add_curve(w * 0.5, h * 0.52, 0, h * 0.44, 0, 0)
            highlight.close()
            ui.set_color((1, 1, 1, float(style.get("gloss_alpha", 0.24))))
            highlight.fill()

        border = ui.Path.rounded_rect(
            1,
            1,
            max(1, w - 2),
            max(1, h - 2),
            max(1, cr - 1),
        )
        border.line_width = border_width
        ui.set_color(_hex_to_rgba(border_color))
        border.stroke()
BAR_H = 204
COLLAPSED_H = 48
KEY_SZ = 42
PAD = 5
GAP = 5
class PaletteDock(ui.View):
    """Collapsible bottom palette/spawner strip."""
    def __init__(self, board=None, on_spawn=None, **kwargs):
        super().__init__(**kwargs)
        self.board = board
        self.on_spawn = on_spawn
        self.expanded = False
        self._buttons = []
        self.background_color = "clear"
        self.touch_enabled = True
        self.hidden = False
        self._toggle = ui.Button(title="⌃")
        self._toggle.tint_color = "#FFFFFF"
        self._toggle.background_color = "#1C1C1E"
        self._toggle.corner_radius = 10
        self._toggle.font = ("<System-Bold>", 18)
        self._toggle.action = self.toggle
        self.add_subview(self._toggle)
        self._scroll = ui.ScrollView()
        self._scroll.background_color = "clear"
        self._scroll.shows_horizontal_scroll_indicator = False
        self._scroll.shows_vertical_scroll_indicator = False
        self._scroll.hidden = True
        self.add_subview(self._scroll)
        self.set_board(board)
    def preferred_height(self):
        return BAR_H if self.expanded else COLLAPSED_H
    def set_board(self, board):
        self.board = board
        self._rebuild_buttons()
    def toggle(self, sender=None):
        self.expanded = not self.expanded
        self._sync_visibility()
        self._request_layout()
    def show(self):
        self.expanded = True
        self._sync_visibility()
        self._request_layout()
    def hide(self):
        self.expanded = False
        self._sync_visibility()
        self._request_layout()
    def _request_layout(self):
        parent = getattr(self, "superview", None)
        if parent is not None:
            try:
                parent.layout()
            except Exception:
                pass
        try:
            self.set_needs_display()
        except Exception:
            pass
    def _sync_visibility(self):
        self._scroll.hidden = not self.expanded
        self._toggle.title = "⌄" if self.expanded else "⌃"
    def _ordered_items(self):
        palette = getattr(self.board, "palette", None)
        if palette is None:
            return []

        items = palette.items()

        # Apps can provide explicit keypad-style placement with ui_row/ui_col.
        # This keeps the palette model renderer-neutral while letting UI surfaces
        # honour app-specific ergonomics such as TileCalc's calculator layout.
        positioned = [
            item for item in items
            if getattr(item, "ui_row", None) is not None
            and getattr(item, "ui_col", None) is not None
        ]
        if positioned:
            return sorted(items, key=lambda item: (
                getattr(item, "ui_row", 999) if getattr(item, "ui_row", None) is not None else 999,
                getattr(item, "ui_col", 999) if getattr(item, "ui_col", None) is not None else 999,
                item.order,
                item.category,
                item.label,
                item.id,
            ))

        result = []
        seen = set()
        for category in ("number", "operator"):
            for item in palette.items(category=category):
                if item.id not in seen:
                    result.append(item)
                    seen.add(item.id)
        for item in items:
            if item.id not in seen:
                result.append(item)
                seen.add(item.id)
        return result
    def _clear_buttons(self):
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

    def _style_for_item(self, item):
        """Return generic UI style hints for one palette item."""
        style = {}
        try:
            style.update(getattr(item, "ui_style", None) or {})
        except Exception:
            pass

        if "background_color" not in style:
            try:
                spec = item.to_spec()
                meta = spec.get("meta") or {}
                if meta.get("color"):
                    style["background_color"] = meta.get("color")
            except Exception:
                pass

        if "background_color" not in style:
            category = getattr(item, "category", "")
            if category == "number":
                style["background_color"] = "#FFD60A"
            elif category == "operator":
                style["background_color"] = "#64D2FF"
            else:
                style["background_color"] = "#2C2C2E"

        if "tint_color" not in style:
            bg = str(style.get("background_color") or "")
            if bg.upper() in ("#FFD60A", "#64D2FF", "#30D158", "#FF9F0A"):
                style["tint_color"] = "#202124"
            else:
                style["tint_color"] = "#FFFFFF"

        if "border_color" not in style:
            style["border_color"] = "#FFFFFF" if style.get("tile_like") else "#3A3A3C"
        if "border_width" not in style:
            style["border_width"] = 1.5 if style.get("tile_like") else 0
        if "corner_radius" not in style:
            style["corner_radius"] = 12 if style.get("tile_like") else 10
        if "font_size" not in style:
            style["font_size"] = 18 if style.get("tile_like") else 15

        return style

    def _apply_button_style(self, btn, item):
        """Apply item-provided style hints to a generic palette button."""
        style = self._style_for_item(item)
        tile_like = bool(style.get("tile_like"))
        btn.palette_style = style
        btn.draw_tile_like = tile_like

        # For tile-like keys the custom draw method owns the coloured body.
        # Keeping the view background clear avoids fighting native Pythonista
        # button rendering while title/touch/action behaviour remains generic.
        btn.background_color = "clear" if tile_like else style.get("background_color", "#2C2C2E")
        btn.tint_color = style.get("tint_color", "#FFFFFF")
        btn.corner_radius = style.get("corner_radius", 10)
        btn.border_color = style.get("border_color", "#3A3A3C")
        btn.border_width = style.get("border_width", 0)

        font_size = style.get("font_size", 15)
        try:
            btn.font = ("<System-Bold>", font_size)
        except Exception:
            pass

        label = getattr(btn, "label", None)
        if label is not None:
            try:
                label.text_color = btn.tint_color
                label.font = ("<System-Bold>", font_size)
            except Exception:
                pass

        try:
            btn.set_needs_display()
        except Exception:
            pass

        return btn

    def _rebuild_buttons(self):
        self._clear_buttons()
        for item in self._ordered_items():
            btn = PaletteKeyButton(title=str(item.icon or item.label or item.id))
            self._apply_button_style(btn, item)
            btn.palette_id = item.id
            btn.palette_label = item.label
            btn.palette_item = item
            btn.action = self._button_tapped
            self._scroll.add_subview(btn)
            self._buttons.append(btn)
        self._sync_visibility()
        self.layout()
    def _button_tapped(self, sender):
        item_id = getattr(sender, "palette_id", "")
        if item_id and self.on_spawn is not None:
            self.on_spawn(item_id)
    def layout(self):
        w = max(1, self.width)
        h = max(1, self.height)
        btn_w = 48
        btn_h = 36
        self._toggle.frame = (
            w - btn_w - PAD,
            max(0, h - btn_h - 6),
            btn_w,
            btn_h,
        )

        if not self.expanded:
            return

        scroll_w = max(1, w - btn_w - PAD * 3)
        self._scroll.frame = (0, 0, scroll_w, h)
        buttons = list(self._buttons)

        if not buttons:
            self._scroll.content_size = (scroll_w, h)
            return

        positioned = [
            btn for btn in buttons
            if getattr(getattr(btn, "palette_item", None), "ui_row", None) is not None
            and getattr(getattr(btn, "palette_item", None), "ui_col", None) is not None
        ]

        if positioned:
            max_row = 0
            max_col = 0
            for btn in positioned:
                item = getattr(btn, "palette_item", None)
                try:
                    max_row = max(max_row, int(item.ui_row))
                    max_col = max(max_col, int(item.ui_col))
                except Exception:
                    pass

            rows = max_row + 1
            cols = max_col + 1
            grid_h = rows * KEY_SZ + max(0, rows - 1) * GAP
            y0 = max(PAD, (h - grid_h) / 2.0)

            for btn in buttons:
                item = getattr(btn, "palette_item", None)
                row = getattr(item, "ui_row", None)
                col = getattr(item, "ui_col", None)

                if row is None or col is None:
                    # Non-positioned extras sit after the explicit keypad.
                    row = max_row
                    col = max_col + 1

                try:
                    row = int(row)
                    col = int(col)
                except Exception:
                    row = max_row
                    col = max_col + 1

                x = PAD + col * (KEY_SZ + GAP)
                y = y0 + row * (KEY_SZ + GAP)
                btn.frame = (x, y, KEY_SZ, KEY_SZ)

            total_w = max(cols, max_col + 2) * (KEY_SZ + GAP) + PAD
            self._scroll.content_size = (max(scroll_w, total_w), h)
            return

        half = (len(buttons) + 1) // 2
        row1 = buttons[:half]
        row2 = buttons[half:]
        row1_y = max(0, (h - KEY_SZ * 2 - GAP) / 2.0)
        row2_y = row1_y + KEY_SZ + GAP

        for index, btn in enumerate(row1):
            x = PAD + index * (KEY_SZ + GAP)
            btn.frame = (x, row1_y, KEY_SZ, KEY_SZ)

        for index, btn in enumerate(row2):
            x = PAD + index * (KEY_SZ + GAP)
            btn.frame = (x, row2_y, KEY_SZ, KEY_SZ)

        total_w = max(len(row1), len(row2)) * (KEY_SZ + GAP) + PAD
        self._scroll.content_size = (max(scroll_w, total_w), h)

