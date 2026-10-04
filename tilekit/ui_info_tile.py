"""Reusable information tile: corner text, primary label and caption.

Apps provide text through metadata; this renderer contains no domain rules.
"""

import ui

from .renderers import BlockTileView, BlockRenderer


class InfoTileView(BlockTileView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.info_corner = ui.Label()
        self.info_caption = ui.Label()
        for label in (self.info_corner, self.info_caption):
            label.touch_enabled = False
            label.text_color = "#202124"
            label.background_color = "clear"
            self.add_subview(label)
        self.info_caption.alignment = ui.ALIGN_CENTER

    def layout(self):
        super().layout()
        if not hasattr(self, "info_caption"):
            return
        scale = getattr(self, "_visual_scale", 1.0)
        width, height = self.width, self.height
        pad = 4 * scale
        self.info_corner.frame = (pad, 2 * scale, width - 2 * pad, height * 0.2)
        self.info_corner.font = ("<System>", 8 * scale)
        self.info_corner.hidden = width < 36

        caption = self.info_caption.text or ""
        show_caption = bool(caption) and width >= 48
        self.info_caption.hidden = not show_caption
        self.label.frame = (
            pad, height * 0.18, width - 2 * pad,
            height * (0.49 if show_caption else 0.65),
        )
        self.label.font = ("<System-Bold>", 20 * scale)
        self.info_caption.frame = (
            pad, height * 0.72, width - 2 * pad, height * 0.22
        )
        font_size = 8 * scale
        if caption:
            measured = ui.measure_string(
                caption, font=("<System>", font_size)
            )[0]
            available = max(1, width - 2 * pad)
            if measured > available:
                font_size *= available / measured
        self.info_caption.font = ("<System>", font_size)


class InfoTileRenderer(BlockRenderer):
    renderer_id = "info"

    def mount(self, board_view, obj):
        coords = board_view.board.coords
        width, height = obj.size or (64, 64)
        x, y = coords.to_screen(obj.position or (0, 0))
        width, height = coords.screen_length(width), coords.screen_length(height)
        self.view = InfoTileView(
            obj, self, frame=(x - width / 2, y - height / 2, width, height)
        )
        board_view.add_subview(self.view)
        self.update(obj)
        return self.view

    def update(self, obj):
        super().update(obj)
        if self.view is None:
            return
        meta = obj.meta
        self.view.info_corner.text = str(meta.get("corner_text", ""))
        self.view.info_caption.text = str(meta.get("caption", ""))
        self.view.alpha = 0.25 if meta.get("dimmed", False) else 1.0
        self.view.layout()