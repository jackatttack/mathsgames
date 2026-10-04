"""
TileKit history / undo support.

History is renderer-neutral. It snapshots Board object state, then restores the
Board model. UI layers can remount/sync renderers after undo/redo.

This deliberately uses whole-board snapshots first. It is simple, universal,
and works across app-specific actions, merge rules, spawned objects, deleted
objects, and metadata changes.
"""

from copy import deepcopy

from .data import TileData
from .object import TileObject


class HistoryEntry:
    """One undo/redo entry."""

    def __init__(self, label="", snapshot=None):
        self.label = str(label or "")
        self.snapshot = snapshot or {}

    def to_dict(self):
        return {
            "label": self.label,
            "snapshot": self.snapshot,
        }


class HistoryStack:
    """Universal board history based on model snapshots."""

    def __init__(self, board=None, limit=100):
        self.board = board
        self.limit = int(limit or 100)
        self._undo = []
        self._redo = []

    def __len__(self):
        return len(self._undo)

    def can_undo(self):
        return bool(self._undo)

    def can_redo(self):
        return bool(self._redo)

    def clear(self):
        self._undo = []
        self._redo = []

    def snapshot(self, board=None):
        """Return a serialisable snapshot of the board model."""
        board = board or self.board
        if board is None:
            return {"objects": [], "selected_id": None}

        selected = getattr(board, "selected", None)
        selected_id = getattr(getattr(selected, "data", None), "id", None)

        objects = []
        for obj in list(getattr(board, "objects", []) or []):
            data = getattr(obj, "data", None)
            state = getattr(obj, "state", None)

            try:
                data_dict = data.to_dict()
            except Exception:
                data_dict = {
                    "kind": getattr(obj, "kind", "generic"),
                    "label": getattr(obj, "label", ""),
                    "payload": getattr(obj, "payload", None),
                    "meta": dict(getattr(obj, "meta", {}) or {}),
                }

            try:
                state_dict = state.to_dict()
            except Exception:
                state_dict = {}

            objects.append({
                "data": deepcopy(data_dict),
                "w_cells": getattr(obj, "w_cells", None),
                "h_cells": getattr(obj, "h_cells", None),
                "fixed_size": bool(getattr(obj, "fixed_size", False)),
                "position": list(getattr(obj, "position", None) or (0, 0)),
                "size": list(getattr(obj, "size", None) or (64, 64)),
                "renderer_id": getattr(obj, "renderer_id", "block"),
                "state": state_dict,
            })

        return {
            "objects": objects,
            "selected_id": selected_id,
        }

    def restore(self, snapshot=None, board=None):
        """Restore a snapshot into the board model."""
        board = board or self.board
        snapshot = snapshot or {}
        if board is None:
            return False

        old_objects = list(getattr(board, "objects", []) or [])
        for obj in old_objects:
            renderer = getattr(obj, "renderer", None)
            if renderer is not None:
                try:
                    renderer.unmount()
                except Exception:
                    pass
                try:
                    renderer.view = None
                except Exception:
                    pass
            try:
                obj.renderer = None
            except Exception:
                pass

        board.objects = []
        board.selected = None

        selected_id = snapshot.get("selected_id")
        selected_obj = None

        for item in snapshot.get("objects", []) or []:
            data = TileData.from_dict(deepcopy(item.get("data") or {}))
            obj = TileObject(
                data=data,
                position=tuple(item.get("position") or (0, 0)),
                size=tuple(item.get("size") or (64, 64)),
                renderer_id=item.get("renderer_id") or "block",
                w_cells=item.get("w_cells"),
                h_cells=item.get("h_cells"),
                fixed_size=item.get("fixed_size", False),
            )
            obj.board = board

            state_data = item.get("state") or {}
            for key, value in state_data.items():
                if hasattr(obj.state, key):
                    try:
                        setattr(obj.state, key, bool(value))
                    except Exception:
                        pass

            obj.renderer = None
            board.objects.append(obj)

            if selected_id and getattr(obj.data, "id", None) == selected_id:
                selected_obj = obj

        if selected_obj is not None:
            board.select(selected_obj)

        return True

    def record_change(self, before_snapshot, label=""):
        """Record a mutation if the current board state differs from before."""
        before_snapshot = before_snapshot or {}
        after_snapshot = self.snapshot()

        if before_snapshot == after_snapshot:
            return False

        self._undo.append(HistoryEntry(label=label, snapshot=before_snapshot))
        if len(self._undo) > self.limit:
            self._undo = self._undo[-self.limit:]

        self._redo = []
        return True

    def capture(self, label=""):
        """Manually push the current board state onto the undo stack."""
        self._undo.append(HistoryEntry(label=label, snapshot=self.snapshot()))
        if len(self._undo) > self.limit:
            self._undo = self._undo[-self.limit:]
        self._redo = []
        return True

    def undo(self):
        """Undo the most recent recorded change."""
        if not self._undo:
            return False

        current = self.snapshot()
        entry = self._undo.pop()
        self._redo.append(HistoryEntry(label=entry.label, snapshot=current))
        self.restore(entry.snapshot)
        return True

    def redo(self):
        """Redo the most recently undone change."""
        if not self._redo:
            return False

        current = self.snapshot()
        entry = self._redo.pop()
        self._undo.append(HistoryEntry(label=entry.label, snapshot=current))
        self.restore(entry.snapshot)
        return True