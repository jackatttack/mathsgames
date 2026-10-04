"""
TileKit scene persistence.

Scene is the renderer-neutral saved representation of a Board. It stores object
specs and lightweight scene metadata, but not Pythonista views, renderer
instances, transient drag state, or selected state.
"""

import json
import os

from .storage import JsonRecordStore


# v2 adds object identity + cell-span/fixed-size geometry. v1 scenes remain
# valid because every new field is optional on load.
SCENE_VERSION = 2


class Scene:
    """Serializable board scene."""

    def __init__(self, name="Untitled", objects=None, meta=None, version=None):
        self.name = str(name or "Untitled")
        self.objects = list(objects or [])
        self.meta = dict(meta or {})
        self.version = int(version or SCENE_VERSION)

    def to_dict(self):
        return {
            "version": self.version,
            "name": self.name,
            "objects": list(self.objects),
            "meta": dict(self.meta),
        }

    @classmethod
    def from_dict(cls, data):
        data = data or {}
        return cls(
            name=data.get("name", "Untitled"),
            objects=data.get("objects") or [],
            meta=data.get("meta") or {},
            version=data.get("version") or 1,
        )


def object_to_spec(obj):
    """Return a JSON-friendly object spec for one TileObject."""
    data = getattr(obj, "data", None)
    meta = getattr(data, "meta", None)
    payload = getattr(data, "payload", None)

    return {
        "id": getattr(data, "id", None),
        "kind": getattr(obj, "kind", "generic"),
        "label": getattr(obj, "label", ""),
        "payload": payload,
        "meta": dict(meta or {}),
        "position": _list_or_none(getattr(obj, "position", None)),
        "size": _list_or_none(getattr(obj, "size", None)),
        "w_cells": getattr(obj, "w_cells", None),
        "h_cells": getattr(obj, "h_cells", None),
        "fixed_size": bool(getattr(obj, "fixed_size", False)),
        "renderer": getattr(obj, "renderer_id", "block"),
    }


def scene_from_board(board, name="Untitled", meta=None):
    """Build a Scene from a Board."""
    objects = [
        object_to_spec(obj)
        for obj in getattr(board, "objects", [])
    ]
    return Scene(name=name, objects=objects, meta=meta or {})


def _restore_persistent_geometry(obj, spec):
    """Restore saved identity/span without re-running resize anchoring.

    A scene stores the object's already-centred logical position. Calling
    set_cell_span() here would move that centre because that method deliberately
    preserves the first occupied cell during an interactive resize. Loading is
    different: assign the saved span directly.
    """
    tile_id = spec.get("id", spec.get("tile_id"))
    if tile_id:
        try:
            obj.data.id = str(tile_id)
        except Exception:
            pass

    w_cells = spec.get("w_cells")
    h_cells = spec.get("h_cells")
    if w_cells is not None and h_cells is not None:
        try:
            obj.w_cells = max(1, int(w_cells))
            obj.h_cells = max(1, int(h_cells))
        except Exception:
            pass

    if "fixed_size" in spec:
        try:
            obj.fixed_size = bool(spec.get("fixed_size"))
        except Exception:
            pass

    return obj


def apply_scene_to_board(board, scene, clear=True, snap=False):
    """Apply a Scene or scene dict to a Board and return created objects."""
    if isinstance(scene, dict):
        scene = Scene.from_dict(scene)

    if clear:
        board.objects[:] = []
        board.selected = None
        session = getattr(board, "input_session", None)
        if session is not None:
            session.end()

    created = []
    for spec in scene.objects:
        obj = board.create_object(spec)
        _restore_persistent_geometry(obj, spec)
        board.add_object(obj, snap=snap)
        created.append(obj)

    return created


class SceneStore:
    """Tiny single-scene JSON store."""

    def __init__(self, path):
        self.path = path

    def save(self, scene):
        """Save a Scene or scene dict."""
        if isinstance(scene, dict):
            scene = Scene.from_dict(scene)

        folder = os.path.dirname(os.path.abspath(self.path))
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        # Scene files are user work. Stage beside the destination and atomically
        # replace it so an interrupted write cannot truncate the previous save.
        temp_path = self.path + ".tmp"
        with open(temp_path, "w") as f:
            json.dump(scene.to_dict(), f, indent=2, sort_keys=True)
        os.replace(temp_path, self.path)

        return self.path

    def load(self):
        """Load a Scene from disk."""
        with open(self.path, "r") as f:
            return Scene.from_dict(json.load(f))

    def exists(self):
        return os.path.exists(self.path)


class SceneLibrary:
    """Self-pruning multi-scene JSON library."""

    def __init__(self, path, max_scenes=50):
        self.store = JsonRecordStore(path, max_records=max_scenes)

    def all(self):
        """Return saved scene records, newest first."""
        return self.store.load()

    def save_scene(self, scene, scene_id=None):
        """Save a scene record and prune older records."""
        if isinstance(scene, dict):
            scene = Scene.from_dict(scene)

        record = {
            "id": scene_id or scene.name,
            "name": scene.name,
            "scene": scene.to_dict(),
        }
        return self.store.add(record)

    def load_scene(self, scene_id):
        """Load one scene by id, or None."""
        record = self.store.get(scene_id)
        if not record:
            return None
        return Scene.from_dict(record.get("scene") or {})

    def delete_scene(self, scene_id):
        """Delete one scene by id."""
        return self.store.delete(scene_id)

    def clear(self):
        """Delete all saved scenes."""
        return self.store.clear()


def _list_or_none(value):
    if value is None:
        return None
    try:
        return list(value)
    except Exception:
        return value
