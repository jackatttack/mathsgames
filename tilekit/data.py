"""
TileKit data models.

This module contains renderer-neutral data/state classes.

A TileKit tile is not a view. It is an object with identity, kind,
label, payload, metadata, state, and a logical position. Rendering is
handled elsewhere by renderer classes.
"""

import uuid


class TileData:
    """Persistent identity and payload for one TileKit object."""

    def __init__(self, kind="generic", label="", payload=None, meta=None, tile_id=None):
        self.id = tile_id or str(uuid.uuid4())
        self.kind = str(kind or "generic")
        self.label = str(label or "")
        self.payload = payload
        self.meta = dict(meta or {})

    def to_dict(self):
        """Return a JSON-friendly representation."""
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "payload": self.payload,
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data):
        """Build TileData from a dictionary."""
        data = data or {}
        return cls(
            kind=data.get("kind", "generic"),
            label=data.get("label", ""),
            payload=data.get("payload"),
            meta=data.get("meta") or {},
            tile_id=data.get("id"),
        )


class TileState:
    """Transient interaction state for one TileKit object."""

    def __init__(self):
        self.selected = False
        self.dragging = False
        self.group_selected = False
        self.sticky = False
        self.locked = False
        self.hidden = False

    def to_dict(self):
        """Return a JSON-friendly representation."""
        return {
            "selected": bool(self.selected),
            "dragging": bool(self.dragging),
            "group_selected": bool(self.group_selected),
            "sticky": bool(self.sticky),
            "locked": bool(self.locked),
            "hidden": bool(self.hidden),
        }


class TileSpec:
    """Creation spec used by apps, palettes, scene loading, and tests.

    Identity and cell geometry are optional because ordinary spawn specs should
    still receive fresh IDs and app-defined size policies. Saved scenes can set
    these fields to restore an existing mathematical workspace exactly.
    """

    def __init__(self, kind="generic", label="", payload=None, meta=None,
                 position=None, size=None, renderer=None, tile_id=None,
                 w_cells=None, h_cells=None, fixed_size=None):
        self.kind = kind
        self.label = label
        self.payload = payload
        self.meta = dict(meta or {})
        self.position = position
        self.size = size
        self.renderer = renderer
        self.tile_id = tile_id
        self.w_cells = w_cells
        self.h_cells = h_cells
        self.fixed_size = fixed_size

    @classmethod
    def from_dict(cls, data):
        """Build a TileSpec from a dictionary."""
        data = data or {}
        return cls(
            kind=data.get("kind", "generic"),
            label=data.get("label", ""),
            payload=data.get("payload"),
            meta=data.get("meta") or {},
            position=data.get("position"),
            size=data.get("size"),
            renderer=data.get("renderer"),
            tile_id=data.get("id", data.get("tile_id")),
            w_cells=data.get("w_cells"),
            h_cells=data.get("h_cells"),
            fixed_size=data.get("fixed_size"),
        )
