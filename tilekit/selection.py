"""
TileKit selection model.

Selection is framework-level state. UI layers may expose it through taps,
lasso, shift-click, keyboard shortcuts, drag boxes, or app-specific controls,
but the model itself belongs in TileKit core.
"""


class SelectionModel:
    """Owns single-object and group selection for a Board."""

    def __init__(self, board):
        self.board = board
        self.group = []

    def selected(self):
        """Return the board's primary selected object."""
        return getattr(self.board, "selected", None)

    def select_one(self, obj):
        """Select exactly one object and clear previous primary/group selection."""
        self.clear_group()

        old = getattr(self.board, "selected", None)
        if old is not None and old is not obj:
            try:
                old.set_selected(False)
            except Exception:
                pass

        self.board.selected = obj

        if obj is not None:
            try:
                obj.set_selected(True)
            except Exception:
                pass

        return obj

    def clear_primary(self):
        """Clear the primary selected object."""
        return self.select_one(None)

    def clear_group(self):
        """Clear group selection without changing the primary selection."""
        for obj in list(self.group):
            self._set_group_selected(obj, False)
        self.group = []

    def clear_all(self):
        """Clear both primary and group selection."""
        self.clear_primary()
        self.clear_group()

    def set_group(self, objects):
        """Replace group selection with objects, preserving order."""
        self.clear_group()
        seen = set()
        group = []
        for obj in objects or []:
            if obj is None:
                continue
            if id(obj) in seen:
                continue
            seen.add(id(obj))
            group.append(obj)

        self.group = group
        for obj in self.group:
            self._set_group_selected(obj, True)
        return list(self.group)

    def add_to_group(self, obj):
        """Add one object to the group selection."""
        if obj is None:
            return list(self.group)
        if obj not in self.group:
            self.group.append(obj)
            self._set_group_selected(obj, True)
        return list(self.group)

    def remove_from_group(self, obj):
        """Remove one object from the group selection."""
        if obj in self.group:
            self.group.remove(obj)
            self._set_group_selected(obj, False)
        return list(self.group)

    def toggle_group(self, obj):
        """Toggle one object in the group selection."""
        if obj in self.group:
            return self.remove_from_group(obj)
        return self.add_to_group(obj)

    def prune_missing(self):
        """Drop group entries no longer present on the board."""
        live = set(id(obj) for obj in getattr(self.board, "objects", []) or [])
        kept = []
        for obj in list(self.group):
            if id(obj) in live:
                kept.append(obj)
            else:
                self._set_group_selected(obj, False)
        self.group = kept

        selected = getattr(self.board, "selected", None)
        if selected is not None and id(selected) not in live:
            self.board.selected = None

    def contains(self, obj):
        """Return True if obj is in the group selection."""
        return obj in self.group

    def selected_objects(self):
        """Return group selection if present, else the primary selection."""
        if self.group:
            return list(self.group)
        selected = getattr(self.board, "selected", None)
        return [selected] if selected is not None else []

    def _set_group_selected(self, obj, on):
        try:
            obj.state.group_selected = bool(on)
            obj._notify_renderer()
        except Exception:
            pass