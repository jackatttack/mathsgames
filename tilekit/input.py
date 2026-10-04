"""
TileKit input event models.

This module stays framework-level. It converts UI-specific touch data into
small event objects that interaction controllers can consume without owning
Pythonista view details.
"""


class PointerEvent:
    """Small renderer/UI-neutral pointer event."""

    def __init__(self, phase, point=None, position=None, pointer_id=None,
                 timestamp=None, raw=None):
        self.phase = str(phase or "")
        self.point = point
        self.position = position if position is not None else point
        self.pointer_id = pointer_id
        self.timestamp = timestamp
        self.raw = raw

    @classmethod
    def from_touch(cls, phase, touch, board_view=None):
        point = getattr(touch, "location", None)
        position = point
        if board_view is not None:
            try:
                position = board_view.board.coords.from_screen(point)
            except Exception:
                position = point

        pointer_id = None
        try:
            pointer_id = touch.touch_id
        except Exception:
            pointer_id = id(touch)

        timestamp = getattr(touch, "timestamp", None)

        return cls(
            phase=phase,
            point=point,
            position=position,
            pointer_id=pointer_id,
            timestamp=timestamp,
            raw=touch,
        )


class InputEvent:
    """Renderer-neutral semantic input event."""

    def __init__(self, kind="", value=None, source="", item_id="",
                 category="", label="", spec=None, origin=None,
                 context=None, raw=None):
        self.kind = str(kind or "")
        self.value = value
        self.source = str(source or "")
        self.item_id = str(item_id or "")
        self.category = str(category or "")
        self.label = str(label or "")
        self.spec = dict(spec or {})
        self.origin = origin
        self.context = dict(context or {})
        self.raw = raw


class InputResult:
    """Result returned by an InputSession semantic handler."""

    def __init__(self, handled=False, value=None):
        self.handled = bool(handled)
        self.value = value

    @classmethod
    def consumed(cls, value=None):
        return cls(True, value)

    @classmethod
    def pass_through(cls):
        return cls(False, None)


class DragContext:
    """State for one object drag."""

    def __init__(self, obj=None, start_position=None, offset=(0, 0)):
        self.obj = obj
        self.start_position = start_position
        self.offset = offset