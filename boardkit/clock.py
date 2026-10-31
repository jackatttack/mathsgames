"""
Tracks for one frame clock: which views are moving, and where each should
be at a given moment. Pure Python: it never touches a view, it only says
what frame to set.

A board view keeps one TrackSet. Its update() (update_interval set once;
see library/guides/pythonista-ui-stability.md) calls step(time.time()) and
sets each (view, frame) it returns. Starting new tracks first snaps every
unfinished track to its end, so a tile is never left part way.

Times are seconds on any clock; use the same clock throughout.
"""

from boardkit import paths


class Track:
    """One view moving from start to end over seconds, after delay, along path."""

    def __init__(self, target, start, end, seconds, delay=0.0, path=None):
        """target is whatever the caller moves, usually a ui.View. path is a
        boardkit.paths path; the default is paths.straight()."""
        if seconds <= 0:
            raise ValueError("a track needs a positive number of seconds")
        self.target = target
        self.start = tuple(start)
        self.end = tuple(end)
        self.seconds = seconds
        self.delay = delay
        self.path = path or paths.straight()

    def progress(self, elapsed):
        """0 at the end of the delay, 1 on arrival; below 0 while waiting."""
        return (elapsed - self.delay) / self.seconds

    def frame_at(self, elapsed):
        """The frame this long after the set started, or None while still waiting."""
        progress = self.progress(elapsed)
        if progress <= 0:
            return None
        return self.path(self.start, self.end, min(progress, 1.0))

    def finished(self, elapsed):
        return self.progress(elapsed) >= 1.0


class TrackSet:
    """The tracks one frame clock is playing, all started together."""

    def __init__(self):
        self.tracks = []
        self.started = None

    @property
    def moving(self):
        return bool(self.tracks)

    def start(self, tracks, now):
        """Play these tracks from now.

        Returns (target, frame) snaps for any tracks still running, which
        the caller sets before the new ones begin.
        """
        snaps = self.finish()
        self.tracks = list(tracks)
        self.started = now
        return snaps

    def step(self, now):
        """(target, frame) for every track under way at now.

        Once every track has arrived they are snapped exactly to their ends
        and the set empties, so update() can idle.
        """
        if not self.tracks:
            return []
        elapsed = now - self.started
        moves = []
        all_arrived = True
        for track in self.tracks:
            frame = track.frame_at(elapsed)
            if frame is not None:
                moves.append((track.target, frame))
            if not track.finished(elapsed):
                all_arrived = False
        if all_arrived:
            return self.finish()
        return moves

    def finish(self):
        """Stop now: (target, end frame) for every track, and empty the set."""
        snaps = [(track.target, track.end) for track in self.tracks]
        self.tracks = []
        self.started = None
        return snaps
