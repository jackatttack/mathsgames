"""Best times and recent history for timed runs, shared by every tile game.

No UIKit lives here.

A record key names everything that makes two times comparable, so a run
only competes with runs played under the same rules. Build keys with
record_key, for example:

    record_key("countdown", "boards-5", "normal", "mix", "skip-60")
    record_key("multiple_merge", "classic", "x25", "targets-7")

Each key keeps its best time and its most recent runs. Saving is
synchronous and replaces the file in one step (write a temporary file,
then os.replace), so a crash mid-save leaves the old file intact.
A file that cannot be read is kept beside it as <name>.bad rather than
silently overwritten.
"""

import json
import os
import time


# --- editable settings ------------------------------------------------------

HISTORY_LENGTH = 20      # recent runs kept per key, newest first


# --- keys and display -------------------------------------------------------

def record_key(*parts):
    """Join rule parts into one key: lower case, joined with '/'."""
    return "/".join(str(part).strip().lower() for part in parts)


def format_duration(seconds):
    """1:05 for runs of a minute or more, 48.3s below a minute."""
    if seconds < 60:
        return "{:.1f}s".format(seconds)

    whole = int(round(seconds))
    return "{}:{:02d}".format(whole // 60, whole % 60)


# --- the record book --------------------------------------------------------

class RunResult:
    """What adding a run changed, for the screen to announce."""

    def __init__(self, seconds, is_best, previous_best):
        self.seconds = seconds
        self.is_best = is_best              # True also for a first run
        self.previous_best = previous_best  # None when this key was empty


class RecordBook:
    """Best times and history, stored as JSON at path."""

    def __init__(self, path):
        self.path = path
        self.entries = self._load()

    # Reading.

    def best(self, key):
        """Best time in seconds for key, or None."""
        entry = self.entries.get(key)
        return entry["best"] if entry else None

    def history(self, key):
        """Recent runs for key, newest first: [{"seconds", "when"}]."""
        entry = self.entries.get(key)
        return list(entry["history"]) if entry else []

    # Writing.

    def add(self, key, seconds, when=None):
        """Record one finished run, save immediately, return a RunResult."""
        seconds = round(float(seconds), 2)
        when = when if when is not None else time.time()

        entry = self.entries.setdefault(key, {"best": None, "history": []})
        previous_best = entry["best"]
        is_best = previous_best is None or seconds < previous_best

        if is_best:
            entry["best"] = seconds

        entry["history"].insert(0, {"seconds": seconds, "when": round(when)})
        del entry["history"][HISTORY_LENGTH:]

        self._save()
        return RunResult(seconds, is_best, previous_best)

    # Storage.

    def _load(self):
        try:
            with open(self.path) as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            self._set_aside()
            return {}

        if not isinstance(data, dict):
            self._set_aside()
            return {}

        entries = {}
        for key, entry in data.items():
            if self._valid_entry(entry):
                entries[key] = entry
        return entries

    @staticmethod
    def _valid_entry(entry):
        return (
            isinstance(entry, dict)
            and (entry.get("best") is None
                 or isinstance(entry.get("best"), (int, float)))
            and isinstance(entry.get("history"), list)
        )

    def _set_aside(self):
        """Keep an unreadable file as .bad so a fresh save cannot lose it."""
        try:
            os.replace(self.path, self.path + ".bad")
        except OSError:
            pass

    def _save(self):
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)

        temporary = self.path + ".tmp"
        with open(temporary, "w") as handle:
            json.dump(self.entries, handle, indent=1, sort_keys=True)
        os.replace(temporary, self.path)