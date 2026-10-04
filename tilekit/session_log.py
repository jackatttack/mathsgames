"""
TileKit session logging.

This is a small self-pruning JSON log for live Pythonista testing. It records
what happened during an app session plus compact board snapshots so Forge can
inspect real behaviour after Jack has used the app.
"""

import json
import os
import time
import uuid


def _project_root():
    here = os.path.abspath(os.path.dirname(__file__))
    return os.path.abspath(os.path.join(here, os.pardir))


def _default_log_path():
    return os.path.join(_project_root(), "session_logs", "tilekit_sessions.json")


def _safe_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _safe_value(v) for k, v in value.items()}
    if hasattr(value, "to_dict"):
        try:
            return _safe_value(value.to_dict())
        except Exception:
            pass
    return str(value)


def object_summary(obj):
    if obj is None:
        return None

    return {
        "id": getattr(obj, "id", None),
        "kind": getattr(obj, "kind", None),
        "label": getattr(obj, "label", None),
        "payload": _safe_value(getattr(obj, "payload", None)),
        "position": _safe_value(getattr(obj, "position", None)),
        "size": _safe_value(getattr(obj, "size", None)),
        "meta": _safe_value(getattr(obj, "meta", {}) or {}),
        "state": _safe_value(getattr(getattr(obj, "state", None), "to_dict", lambda: {})()),
    }


def board_summary(board):
    if board is None:
        return {"objects": []}

    selected = getattr(board, "selected", None)
    objects = []
    for obj in list(getattr(board, "objects", []) or []):
        objects.append(object_summary(obj))

    return {
        "target": _safe_value(getattr(board, "target", None)),
        "selected_id": getattr(selected, "id", None),
        "object_count": len(objects),
        "objects": objects,
    }


class TileKitSessionLog:
    """Self-pruning app session log."""

    def __init__(self, app_name="tilekit", path=None, max_sessions=8, max_events=250):
        self.app_name = str(app_name or "tilekit")
        self.path = path or _default_log_path()
        self.max_sessions = int(max_sessions or 8)
        self.max_events = int(max_events or 250)
        self.session_id = "{}_{}".format(
            time.strftime("%Y%m%d_%H%M%S"),
            uuid.uuid4().hex[:6],
        )
        self.started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.events = []

    @classmethod
    def start(cls, app_name="tilekit", board=None, path=None, max_sessions=8, max_events=250):
        logger = cls(
            app_name=app_name,
            path=path,
            max_sessions=max_sessions,
            max_events=max_events,
        )
        logger.record("session_start", board=board)
        return logger

    def _load_sessions(self):
        if not os.path.exists(self.path):
            return []

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []

        if isinstance(data, dict):
            sessions = data.get("sessions", [])
        else:
            sessions = data

        if not isinstance(sessions, list):
            return []
        return sessions

    def _write_sessions(self, sessions):
        folder = os.path.dirname(self.path)
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        payload = {
            "version": 1,
            "max_sessions": self.max_sessions,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "sessions": sessions[-self.max_sessions:],
        }

        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)

    def _session_payload(self, board=None):
        return {
            "id": self.session_id,
            "app": self.app_name,
            "started_at": self.started_at,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "event_count": len(self.events),
            "events": list(self.events[-self.max_events:]),
            "board": board_summary(board),
        }

    def save(self, board=None):
        sessions = self._load_sessions()
        payload = self._session_payload(board=board)

        replaced = False
        for idx, session in enumerate(sessions):
            if session.get("id") == self.session_id:
                sessions[idx] = payload
                replaced = True
                break

        if not replaced:
            sessions.append(payload)

        self._write_sessions(sessions)
        return self.path

    def record(self, kind, board=None, **data):
        event = {
            "t": time.strftime("%H:%M:%S"),
            "kind": str(kind or "event"),
        }

        for key, value in data.items():
            event[str(key)] = _safe_value(value)

        self.events.append(event)
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

        self.save(board=board)
        return event