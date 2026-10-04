"""
TileKit self-pruning JSON storage.

This is for small app-local JSON databases: saved scenes, recent boards,
templates, palettes, etc.

Rule:
Any multi-record JSON store should have a max_records limit and prune itself
on write. No quiet unbounded JSON growth.
"""

import json
import os
import time
import uuid


STORE_VERSION = 1


class JsonRecordStore:
    """Tiny self-pruning JSON record store."""

    def __init__(self, path, max_records=100, id_key="id"):
        self.path = path
        self.max_records = int(max_records or 100)
        self.id_key = str(id_key or "id")

    def load(self):
        """Return records from disk, tolerating older simple list files."""
        if not os.path.exists(self.path):
            return []

        with open(self.path, "r") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            records = data.get("records", [])
            if isinstance(records, list):
                return records

        return []

    def save_all(self, records):
        """Write records after pruning."""
        records = self.prune(records)

        folder = os.path.dirname(os.path.abspath(self.path))
        if folder and not os.path.exists(folder):
            os.makedirs(folder)

        payload = {
            "version": STORE_VERSION,
            "max_records": self.max_records,
            "records": records,
        }

        with open(self.path, "w") as f:
            json.dump(payload, f, indent=2, sort_keys=True)

        return records

    def add(self, record):
        """Add or replace one record and prune."""
        record = dict(record or {})
        now = time.time()

        if not record.get(self.id_key):
            record[self.id_key] = str(uuid.uuid4())

        record.setdefault("created_at", now)
        record["updated_at"] = now

        records = [
            item for item in self.load()
            if item.get(self.id_key) != record.get(self.id_key)
        ]
        records.append(record)
        self.save_all(records)
        return record

    def get(self, record_id):
        """Return one record by id, or None."""
        record_id = str(record_id or "")
        for record in self.load():
            if str(record.get(self.id_key) or "") == record_id:
                return record
        return None

    def delete(self, record_id):
        """Delete one record by id."""
        record_id = str(record_id or "")
        before = self.load()
        after = [
            item for item in before
            if str(item.get(self.id_key) or "") != record_id
        ]
        self.save_all(after)
        return len(after) != len(before)

    def clear(self):
        """Remove all records."""
        self.save_all([])
        return True

    def prune(self, records):
        """Return records sorted newest-first and capped to max_records."""
        records = [dict(item or {}) for item in (records or [])]

        def key(item):
            return (
                float(item.get("updated_at") or item.get("created_at") or 0),
                str(item.get(self.id_key) or ""),
            )

        records.sort(key=key, reverse=True)

        if self.max_records >= 0:
            records = records[:self.max_records]

        return records