"""
TileKit spatial input-session state.

An InputSession separates "what is currently being typed into" from visual
selection. UI surfaces such as palettes, keyboards, trackpads, or shortcuts can
share the same target, mode, and logical board cursor without owning app logic.

The session is intentionally renderer-neutral. Structured editors can later use
mode/context/handler for states such as fraction numerator/denominator entry,
expression editing, plot parameters, or statistics cells.
"""


from .input import InputResult


class InputSession:
    """Own the current logical input target and spatial cursor for a Board."""

    def __init__(self, board):
        self.board = board
        self.target = None
        self.mode = "spawn"
        self.cursor = None
        self.handler = None
        self.default_handler = None
        self.context = {}

    def _target_is_live(self, target):
        if target is None:
            return False
        try:
            return target in self.board.objects
        except Exception:
            return False

    def current_target(self, kind=None):
        """Return the live target, optionally restricted to one object kind."""
        target = self.target
        if not self._target_is_live(target):
            self.clear_target()
            return None

        if kind is not None and getattr(target, "kind", None) != kind:
            return None

        return target

    def set_target(self, target, mode="edit", handler=None, context=None):
        """Make one live board object the current input target."""
        if target is None or not self._target_is_live(target):
            self.clear_target()
            return None

        self.target = target
        self.mode = str(mode or "edit")
        self.handler = handler
        self.context = dict(context or {})
        return target

    def clear_target(self):
        """Return to cursor/spawn mode while preserving spatial cursor state."""
        self.target = None
        self.mode = "spawn"
        self.handler = None
        self.context = {}
        return None

    def set_default_handler(self, handler):
        """Set the app-level semantic input handler."""
        self.default_handler = handler
        return handler

    def dispatch(self, event):
        """Offer a semantic event to the active/app input handler.

        Returning an unhandled result tells the caller to continue with its
        normal fallback behaviour, such as spawning a palette item.
        """
        handler = self.handler or self.default_handler
        if event is None or handler is None:
            return InputResult.pass_through()

        result = handler(
            session=self,
            event=event,
            board=self.board,
        )

        if isinstance(result, InputResult):
            return result
        if result is None or result is False:
            return InputResult.pass_through()
        if result is True:
            return InputResult.consumed()
        return InputResult.consumed(result)

    def set_cursor(self, position):
        """Store the current logical board cursor position."""
        if position is None:
            self.cursor = None
            return None

        try:
            x, y = position
            self.cursor = (float(x), float(y))
        except Exception:
            self.cursor = position

        return self.cursor

    def begin(self, target=None, mode="edit", handler=None, context=None):
        """Begin or retarget an input mode."""
        if target is not None:
            return self.set_target(
                target,
                mode=mode,
                handler=handler,
                context=context,
            )

        self.target = None
        self.mode = str(mode or "spawn")
        self.handler = handler
        self.context = dict(context or {})
        return None

    def end(self, clear_cursor=False):
        """End the current editing mode."""
        self.clear_target()
        if clear_cursor:
            self.cursor = None

    def snapshot(self):
        """Return simple diagnostic state without serialising board objects."""
        target = self.current_target()
        return {
            "target_id": getattr(target, "id", None),
            "target_kind": getattr(target, "kind", None),
            "mode": self.mode,
            "cursor": self.cursor,
            "has_handler": self.handler is not None,
            "has_default_handler": self.default_handler is not None,
            "context": dict(self.context),
        }