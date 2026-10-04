"""
TileKit renderers.
Renderers turn TileObjects into visible Pythonista UI elements. They do
not own object identity, rules, coordinates, or persistence.
BlockRenderer is the first simple renderer. It is intentionally inspired
by Tile Calc's block tiles, but it is only one renderer skin.
SpriteRenderer is a lightweight image/sprite renderer used by apps that
want asset-backed pieces.
"""
import ui
from .ui_lifecycle import remove_view
def _hex_to_rgba(hex_color, alpha=1.0):
    """Convert '#RRGGBB' to a Pythonista rgba tuple."""
    try:
        s = str(hex_color or "#FFD60A").strip()
        if s.startswith("#"):
            s = s[1:]
        if len(s) != 6:
            raise ValueError("expected RRGGBB")
        r = int(s[0:2], 16) / 255.0
        g = int(s[2:4], 16) / 255.0
        b = int(s[4:6], 16) / 255.0
        return (r, g, b, float(alpha))
    except Exception:
        return (1.0, 0.84, 0.04, float(alpha))
def _darker(hex_color, factor=0.82):
    """Return a darker '#RRGGBB' colour string."""
    try:
        s = str(hex_color or "#FFD60A").strip()
        if s.startswith("#"):
            s = s[1:]
        r = max(0, min(255, int(int(s[0:2], 16) * factor)))
        g = max(0, min(255, int(int(s[2:4], 16) * factor)))
        b = max(0, min(255, int(int(s[4:6], 16) * factor)))
        return "#{:02X}{:02X}{:02X}".format(r, g, b)
    except Exception:
        return "#D4AA00"
_KIND_COLORS = {
    "generic": "#8E8E93",
    "text": "#FFD60A",
    "number": "#FFD60A",
    "fraction": "#FFD60A",
    "expr": "#64D2FF",
    "file": "#30D158",
    "op": "#BF5AF2",
    "chess": "#FFFFFF",
}
_SPRITE_IMAGE_CACHE = {}
def _load_ui_image(path):
    """Load a ui.Image from an absolute/local path with a tiny cache."""
    if not path:
        return None
    cached = _SPRITE_IMAGE_CACHE.get(path)
    if cached is not None:
        return cached
    img = None
    try:
        img = ui.Image.named(path)
    except Exception:
        img = None
    if img is None:
        try:
            with open(path, "rb") as f:
                img = ui.Image.from_data(f.read())
        except Exception:
            img = None
    if img is not None:
        _SPRITE_IMAGE_CACHE[path] = img
    return img
class TileRenderer:
    """Base renderer contract."""
    renderer_id = "base"
    def mount(self, board_view, obj):
        """Create and attach the visual representation."""
        raise NotImplementedError
    def update(self, obj):
        """Sync visual representation from object state/data."""
        raise NotImplementedError
    def unmount(self):
        """Remove visual representation from parent if needed."""
        view = getattr(self, "view", None)
        if view is not None:
            try:
                remove_view(view)
            except Exception:
                pass
class BlockTileView(ui.View):
    """Simple block tile visual used by BlockRenderer."""
    def __init__(self, obj, renderer, frame=(0, 0, 64, 64)):
        super().__init__(frame=frame)
        self.obj = obj
        self.renderer = renderer
        self.touch_enabled = False
        self.background_color = "clear"
        self.corner_radius = 14
        self.border_width = 2
        self.border_color = "#3A3A3C"
        self.label = ui.Label(frame=self.bounds)
        self.label.flex = "WH"
        self.label.alignment = ui.ALIGN_CENTER
        self.label.number_of_lines = 1
        self.label.font = ("<System-Bold>", 20)
        self.label.text_color = "#202124"
        self.label.background_color = "clear"
        try:
            self.label.touch_enabled = False
        except Exception:
            pass
        self.add_subview(self.label)
        self.badge = ui.Label()
        self.badge.alignment = ui.ALIGN_CENTER
        self.badge.font = ("<System-Bold>", 15)
        self.badge.text_color = "#202124"
        self.badge.background_color = (1, 1, 1, 0.72)
        self.badge.corner_radius = 9
        self.badge.hidden = True
        try:
            self.badge.touch_enabled = False
        except Exception:
            pass
        self.add_subview(self.badge)
    # Label sizing. Short labels like "7" keep the full tile font; longer ones
    # such as "sin(30)" shrink so the text stays readable instead of being
    # truncated to "sin...". Old Tile Calc sized tiles to their content; this
    # is the cheap half of that until tile sizing itself is a framework model.
    base_font_size = 20.0
    min_font_size = 9.0
    label_char_width = 0.62

    def _fitted_font_size(self, scale):
        """Return a font size that lets the current label fit the tile width."""
        text = str(getattr(self.label, "text", "") or "")
        if len(text) < 2:
            return self.base_font_size * scale

        available = max(1.0, self.width - 8 * scale)
        estimated = self.base_font_size * scale * len(text) * self.label_char_width
        if estimated <= available:
            return self.base_font_size * scale

        fitted = available / (len(text) * self.label_char_width)
        return max(self.min_font_size * scale, fitted)

    def layout(self):
        scale = getattr(self, '_visual_scale', 1.0)
        self.label.font = ('<System-Bold>', self._fitted_font_size(scale))
        self.badge.font = ('<System-Bold>', 15 * scale)
        self.badge.corner_radius = 9 * scale
        inset = 4 * scale
        self.label.frame = (
            inset,
            inset,
            max(1, self.width - inset * 2),
            max(1, self.height - inset * 2),
        )
        badge_size = 18 * scale
        self.badge.frame = (
            max(0, self.width - badge_size - 5 * scale),
            5 * scale,
            badge_size,
            badge_size,
        )
    def draw(self):
        obj = getattr(self, "obj", None)
        if obj is None:
            return
        w, h = self.width, self.height
        if w < 1 or h < 1:
            return

        scale = getattr(self, '_visual_scale', 1.0)
        cr = 14 * scale
        bw = float(getattr(self, "border_width", 2) or 2)
        meta = getattr(getattr(obj, "data", None), "meta", {}) or {}
        base = meta.get("color") or _KIND_COLORS.get(obj.kind, _KIND_COLORS["generic"])
        color = _darker(base) if obj.state.dragging else base

        path = ui.Path.rounded_rect(0, 0, w, h, cr)
        ui.set_color(_hex_to_rgba(color))
        path.fill()

        # Old Tile Calc-style glossy top sweep.
        with ui.GState():
            ui.Path.rounded_rect(0, 0, w, h, cr).add_clip()
            highlight = ui.Path()
            highlight.move_to(0, 0)
            highlight.line_to(w, 0)
            highlight.line_to(w, h * 0.38)
            highlight.add_curve(w * 0.5, h * 0.48, 0, h * 0.42, 0, 0)
            highlight.close()
            ui.set_color((1, 1, 1, 0.22))
            highlight.fill()

        # Subtle lower shade gives the block more of the original Tile Calc depth.
        with ui.GState():
            ui.Path.rounded_rect(0, 0, w, h, cr).add_clip()
            shadow = ui.Path()
            shadow.move_to(0, h)
            shadow.line_to(w, h)
            shadow.line_to(w, h * 0.68)
            shadow.add_curve(w * 0.5, h * 0.58, 0, h * 0.64, 0, h)
            shadow.close()
            ui.set_color((0, 0, 0, 0.08))
            shadow.fill()

        # Inner ring reads as deliberate tile chrome rather than a flat rectangle.
        inset = bw + 0.5 * scale
        inner = ui.Path.rounded_rect(
            inset,
            inset,
            max(1, w - inset * 2),
            max(1, h - inset * 2),
            max(0, cr - inset),
        )
        inner.line_width = scale
        ui.set_color((1, 1, 1, 0.30))
        inner.stroke()

        border = ui.Path.rounded_rect(
            bw * 0.5,
            bw * 0.5,
            max(1, w - bw),
            max(1, h - bw),
            max(0, cr - bw * 0.5),
        )
        border.line_width = bw
        ui.set_color(_hex_to_rgba(self.border_color))
        border.stroke()
def object_pixel_size(obj, coords=None, default=(64, 64)):
    """Return the logical pixel size an object should be drawn at.

    A declared cell span wins: it is the object's real size, and the grid
    decides how many points that is. Objects with no span fall back to the
    pixel size their spec supplied.

    The span is inset by one gutter so neighbouring tiles do not touch,
    matching old Tile Calc's w_cells * cell_size - gutter.
    """
    span = getattr(obj, "cell_span", None)
    if span is None:
        return getattr(obj, "size", None) or default

    grid = float(getattr(coords, "grid", 60) or 60)
    gutter = float(getattr(coords, "gutter", 4) or 4)
    return (
        max(10.0, span[0] * grid - gutter),
        max(10.0, span[1] * grid - gutter),
    )


class BlockRenderer(TileRenderer):
    """Rounded block renderer for early TileKit demos."""
    renderer_id = "block"
    def __init__(self):
        self.view = None
    def mount(self, board_view, obj):
        coords = board_view.board.coords
        size = object_pixel_size(obj, coords)
        x, y = coords.to_screen(obj.position or (0, 0))
        try:
            sw = coords.screen_length(size[0])
            sh = coords.screen_length(size[1])
        except Exception:
            sw, sh = size
        frame = (x - sw / 2, y - sh / 2, sw, sh)
        self.view = BlockTileView(obj, self, frame=frame)
        board_view.add_subview(self.view)
        self.update(obj)
        return self.view
    def update(self, obj):
        if self.view is None:
            return
        if obj is None:
            return
        if getattr(self.view, "obj", None) is None:
            return

        try:
            coords = self.view.superview.board.coords
            size = object_pixel_size(obj, coords)
            x, y = coords.to_screen(obj.position or (0, 0))
            sw = coords.screen_length(size[0])
            sh = coords.screen_length(size[1])
        except Exception:
            size = object_pixel_size(obj)
            x, y = obj.position or (0, 0)
            sw, sh = size

        self.view.frame = (x - sw / 2, y - sh / 2, sw, sh)
        self.view.label.text = "" if obj.label is None else str(obj.label)

        selected = bool(getattr(obj.state, "selected", False))
        grouped = bool(getattr(obj.state, "group_selected", False))
        dragging = bool(getattr(obj.state, "dragging", False))

        if selected:
            self.view.border_color = "#FFFFFF"
            self.view.border_width = 3
        elif grouped:
            self.view.border_color = "#5AC8FA"
            self.view.border_width = 3
        elif dragging:
            self.view.border_color = "#FF9F0A"
            self.view.border_width = 3
        else:
            self.view.border_color = "#3A3A3C"
            self.view.border_width = 2

        # Scale block visual details with the projected geometry.
        scale = sw / float(size[0]) if size[0] else 1.0
        self.view._visual_scale = scale
        self.view.corner_radius = 14 * scale
        self.view.border_width *= scale
        self.view.layout()

        meta = getattr(getattr(obj, "data", None), "meta", {}) or {}
        important = bool(meta.get("important"))
        self.view.badge.text = "★" if important else ""
        self.view.badge.hidden = not important

        try:
            self.view.set_needs_display()
        except Exception:
            pass
class FractionTileView(ui.View):
    """Stacked numerator/denominator visual for a fraction object."""

    def __init__(self, obj, renderer, frame=(0, 0, 64, 128)):
        super().__init__(frame=frame)
        self.obj = obj
        self.renderer = renderer
        self.touch_enabled = False
        self.background_color = "clear"

        self.numerator_label = ui.Label()
        self.numerator_label.alignment = ui.ALIGN_CENTER
        self.numerator_label.font = ("<System-Bold>", 20)
        self.numerator_label.text_color = "#202124"
        self.numerator_label.background_color = "clear"
        try:
            self.numerator_label.touch_enabled = False
        except Exception:
            pass
        self.add_subview(self.numerator_label)

        self.denominator_label = ui.Label()
        self.denominator_label.alignment = ui.ALIGN_CENTER
        self.denominator_label.font = ("<System-Bold>", 20)
        self.denominator_label.text_color = "#202124"
        self.denominator_label.background_color = "clear"
        try:
            self.denominator_label.touch_enabled = False
        except Exception:
            pass
        self.add_subview(self.denominator_label)

    def layout(self):
        pad = 8
        middle = self.height * 0.5

        self.numerator_label.frame = (
            pad,
            pad,
            max(1, self.width - pad * 2),
            max(1, middle - pad - 5),
        )
        self.denominator_label.frame = (
            pad,
            middle + 5,
            max(1, self.width - pad * 2),
            max(1, self.height - middle - pad - 5),
        )

    def draw(self):
        obj = getattr(self, "obj", None)
        if obj is None:
            return

        w, h = self.width, self.height
        if w < 1 or h < 1:
            return

        meta = getattr(getattr(obj, "data", None), "meta", {}) or {}
        base = meta.get("color") or _KIND_COLORS["fraction"]

        body = ui.Path.rounded_rect(0, 0, w, h, 14)
        ui.set_color(_hex_to_rgba(base))
        body.fill()

        line = ui.Path()
        line.move_to(10, h * 0.5)
        line.line_to(max(10, w - 10), h * 0.5)
        line.line_width = 2.5
        ui.set_color((0.12, 0.13, 0.14, 0.95))
        line.stroke()

        if getattr(obj.state, "selected", False):
            border_color = "#FFFFFF"
            border_width = 3
        elif getattr(obj.state, "group_selected", False):
            border_color = "#5AC8FA"
            border_width = 3
        elif getattr(obj.state, "dragging", False):
            border_color = "#FF9F0A"
            border_width = 3
        else:
            border_color = "#3A3A3C"
            border_width = 2

        border = ui.Path.rounded_rect(
            border_width * 0.5,
            border_width * 0.5,
            max(1, w - border_width),
            max(1, h - border_width),
            14,
        )
        border.line_width = border_width
        ui.set_color(_hex_to_rgba(border_color))
        border.stroke()


class FractionRenderer(TileRenderer):
    """Renderer for structured fraction objects."""

    renderer_id = "fraction"

    def __init__(self):
        self.view = None

    def mount(self, board_view, obj):
        size = obj.size or (64, 128)
        coords = board_view.board.coords
        x, y = coords.to_screen(obj.position or (0, 0))

        try:
            sw = coords.screen_length(size[0])
            sh = coords.screen_length(size[1])
        except Exception:
            sw, sh = size

        self.view = FractionTileView(
            obj,
            self,
            frame=(x - sw / 2, y - sh / 2, sw, sh),
        )
        board_view.add_subview(self.view)
        self.update(obj)
        return self.view

    def update(self, obj):
        if self.view is None or obj is None:
            return

        size = obj.size or (64, 128)

        try:
            coords = self.view.superview.board.coords
            x, y = coords.to_screen(obj.position or (0, 0))
            sw = coords.screen_length(size[0])
            sh = coords.screen_length(size[1])
        except Exception:
            x, y = obj.position or (0, 0)
            sw, sh = size

        self.view.frame = (
            x - sw / 2,
            y - sh / 2,
            sw,
            sh,
        )

        meta = getattr(getattr(obj, "data", None), "meta", {}) or {}
        payload = getattr(obj, "payload", None)
        if not isinstance(payload, dict):
            payload = {}

        numer = meta.get("numerator", payload.get("numerator"))
        denom = meta.get("denominator", payload.get("denominator"))

        self.view.numerator_label.text = (
            str(numer) if numer not in (None, "") else "□"
        )
        self.view.denominator_label.text = (
            str(denom) if denom not in (None, "") else "□"
        )

        try:
            self.view.layout()
            self.view.alpha = 0.62 if obj.state.dragging else 1.0
            self.view.set_needs_display()
        except Exception:
            pass


class SpriteTileView(ui.View):
    """Sprite/image tile visual used by SpriteRenderer."""
    def __init__(self, obj, renderer, frame=(0, 0, 64, 64)):
        super().__init__(frame=frame)
        self.obj = obj
        self.renderer = renderer
        self.touch_enabled = False
        self.background_color = "clear"
        self.image_view = ui.ImageView(frame=self.bounds)
        self.image_view.flex = "WH"
        self.image_view.content_mode = ui.CONTENT_SCALE_ASPECT_FIT
        self.image_view.background_color = "clear"
        try:
            self.image_view.touch_enabled = False
        except Exception:
            pass
        self.add_subview(self.image_view)
        self.fallback_label = ui.Label(frame=self.bounds)
        self.fallback_label.flex = "WH"
        self.fallback_label.alignment = ui.ALIGN_CENTER
        self.fallback_label.font = ("<System-Bold>", 22)
        self.fallback_label.text_color = "#FFFFFF"
        self.fallback_label.background_color = "clear"
        self.fallback_label.hidden = True
        try:
            self.fallback_label.touch_enabled = False
        except Exception:
            pass
        self.add_subview(self.fallback_label)
    def layout(self):
        self.image_view.frame = self.bounds
        self.fallback_label.frame = self.bounds
    def draw(self):
        obj = getattr(self, "obj", None)
        if obj is None:
            return
        w, h = self.width, self.height
        if w < 1 or h < 1:
            return
        if getattr(obj.state, "selected", False):
            path = ui.Path.rounded_rect(1, 1, max(1, w - 2), max(1, h - 2), 12)
            path.line_width = 3
            ui.set_color((1, 1, 1, 0.95))
            path.stroke()
class SpriteRenderer(TileRenderer):
    """Renderer for sprite/image based objects."""
    renderer_id = "sprite"
    def __init__(self):
        self.view = None
    def mount(self, board_view, obj):
        size = obj.size or (64, 64)
        coords = board_view.board.coords
        x, y = coords.to_screen(obj.position or (0, 0))
        try:
            sw = coords.screen_length(size[0])
            sh = coords.screen_length(size[1])
        except Exception:
            sw, sh = size
        frame = (x - sw / 2, y - sh / 2, sw, sh)
        self.view = SpriteTileView(obj, self, frame=frame)
        board_view.add_subview(self.view)
        self.update(obj)
        return self.view
    def update(self, obj):
        if self.view is None:
            return
        if obj is None:
            return
        size = obj.size or (64, 64)
        try:
            coords = self.view.superview.board.coords
            x, y = coords.to_screen(obj.position or (0, 0))
            sw = coords.screen_length(size[0])
            sh = coords.screen_length(size[1])
        except Exception:
            x, y = obj.position or (0, 0)
            sw, sh = size
        self.view.frame = (x - sw / 2, y - sh / 2, sw, sh)
        meta = getattr(getattr(obj, "data", None), "meta", {}) or {}
        path = meta.get("sprite_path") or meta.get("image_path")
        img = _load_ui_image(path)
        self.view.image_view.image = img
        self.view.image_view.hidden = img is None
        self.view.fallback_label.text = obj.label or "?"
        self.view.fallback_label.hidden = img is not None
        try:
            self.view.alpha = 0.62 if obj.state.dragging else 1.0
        except Exception:
            pass
        try:
            self.view.set_needs_display()
        except Exception:
            pass
class RendererRegistry:
    """Registry mapping renderer id to renderer factory."""
    def __init__(self):
        self._factories = {}
    def register(self, renderer_id, factory):
        self._factories[renderer_id] = factory
    def create(self, renderer_id):
        factory = self._factories.get(renderer_id) or self._factories.get("block")
        if factory is None:
            raise KeyError("no renderer registered for {}".format(renderer_id))
        return factory()
def default_renderer_registry():
    """Return a registry with the default TileKit renderers."""
    reg = RendererRegistry()
    reg.register("block", BlockRenderer)
    reg.register("fraction", FractionRenderer)
    reg.register("sprite", SpriteRenderer)
    return reg
