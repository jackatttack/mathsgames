"""
TileKit palette/spawner model.
A palette is renderer-neutral. Apps register PaletteItems that describe objects
which can be spawned onto a Board. UI layers can expose the same palette as a
bottom dock, keyboard, command palette, shortcut bar, or anything else later.
"""
import copy

from .input import InputEvent


class PaletteItem:
    """One spawnable app item."""
    def __init__(self, id, label, spec=None, icon="", category="", order=0,
                 ui_row=None, ui_col=None, spawn_handler=None, ui_style=None):
        self.id = str(id or "")
        self.label = str(label or self.id)
        self.icon = str(icon or "")
        self.category = str(category or "")
        self.order = int(order or 0)
        self.ui_row = ui_row
        self.ui_col = ui_col
        self.spawn_handler = spawn_handler
        self.ui_style = copy.deepcopy(ui_style or {})
        self.spec = copy.deepcopy(spec or {})
    def to_spec(self, context=None):
        """Return a fresh TileSpec-compatible dictionary."""
        return copy.deepcopy(self.spec)
    def to_dict(self):
        data = {
            "id": self.id,
            "label": self.label,
            "icon": self.icon,
            "category": self.category,
            "order": self.order,
            "ui_row": self.ui_row,
            "ui_col": self.ui_col,
            "ui_style": copy.deepcopy(self.ui_style),
            "spec": copy.deepcopy(self.spec),
        }
        if self.spawn_handler is not None:
            data["spawn_handler"] = getattr(self.spawn_handler, "__name__", str(self.spawn_handler))
        return data
class PaletteRegistry:
    """Registry of spawnable palette items for a board/app."""
    def __init__(self):
        self._items = {}
    def register(self, item):
        if isinstance(item, dict):
            item = PaletteItem(**item)
        if item is None or not getattr(item, "id", ""):
            return None
        self._items[item.id] = item
        return item
    def get(self, item_id):
        return self._items.get(str(item_id or ""))
    def items(self, category=None):
        items = list(self._items.values())
        if category is not None:
            category = str(category)
            items = [item for item in items if item.category == category]
        return sorted(items, key=lambda item: (item.order, item.category, item.label, item.id))
    def spawn(self, item_id, board, origin=None, context=None):
        """Handle or spawn one palette item and select its resulting object.

        Palette presses first become semantic InputEvents. The board's
        InputSession may consume an event; otherwise the existing spawn-handler
        or plain-spec creation path remains the fallback.
        """
        item = self.get(item_id)
        if item is None or board is None:
            return None

        before = None
        history = getattr(board, "history", None)
        if history is not None:
            try:
                before = history.snapshot()
            except Exception:
                before = None

        spec = item.to_spec(context=context)
        event = InputEvent(
            kind=spec.get("kind") or item.category or "palette",
            value=spec.get("payload"),
            source="palette",
            item_id=item.id,
            category=item.category,
            label=item.label,
            spec=spec,
            origin=origin,
            context=context,
            raw=item,
        )

        obj = None
        handled = False
        session = getattr(board, "input_session", None)
        if session is not None:
            result = session.dispatch(event)
            handled = bool(getattr(result, "handled", False))
            if handled:
                obj = getattr(result, "value", None)

        if not handled:
            handler = getattr(item, "spawn_handler", None)
            if handler is not None:
                obj = handler(
                    board=board,
                    item=item,
                    origin=origin,
                    context=context,
                )
            else:
                obj = board.spawn_object(spec, origin=origin)

        if obj is not None:
            try:
                # A consumed semantic handler may already have selected the
                # result and established a structured InputSession mode.
                # Avoid selecting the same object again, because Board.select()
                # intentionally resets the default session mode to "edit".
                if getattr(board, "selected", None) is not obj:
                    board.select(obj)
            except Exception:
                pass

        if before is not None:
            try:
                history.record_change(
                    before,
                    label="palette {}".format(item.label),
                )
            except Exception:
                pass

        return obj
