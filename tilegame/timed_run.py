"""A timed run: a fixed number of boards against the clock.

No UIKit lives here.

The run starts when it is created. Solving a board moves on; skipping a
board also moves on but adds skip_penalty seconds to the time. The run
finishes after board_count boards, whether the last was solved or
skipped, and its time is then frozen.

The time is computed on demand from the clock, never ticked by a timer:
screens ask for elapsed() whenever the player acts, which keeps every UI
change inside a tap (see JACK_BOOT, Pythonista UI stability).
"""

import time


class TimedRun:
    """Board count, skips and the clock for one run."""

    def __init__(self, board_count, skip_penalty, clock=time.monotonic):
        if board_count < 1:
            raise ValueError("a run needs at least one board")

        self.board_count = board_count
        self.skip_penalty = skip_penalty
        self.clock = clock

        self.started = clock()
        self.boards_done = 0
        self.skips = 0
        self.finished_seconds = None

    # --- reading -------------------------------------------------------------

    @property
    def is_finished(self):
        return self.finished_seconds is not None

    @property
    def board_number(self):
        """The board being played, 1-based; the last board once finished."""
        return min(self.boards_done + 1, self.board_count)

    @property
    def penalty_seconds(self):
        return self.skips * self.skip_penalty

    def elapsed(self):
        """Seconds so far including penalties; frozen once finished."""
        if self.is_finished:
            return self.finished_seconds
        return self.clock() - self.started + self.penalty_seconds

    # --- the player's actions ------------------------------------------------

    def solve(self):
        """Board solved. Returns True when this finishes the run."""
        return self._board_done()

    def skip(self):
        """Board skipped, adding the penalty. True when the run finishes."""
        self.skips += 1
        return self._board_done()

    def _board_done(self):
        if self.is_finished:
            raise RuntimeError("the run is already finished")

        self.boards_done += 1

        if self.boards_done >= self.board_count:
            self.finished_seconds = (
                self.clock() - self.started + self.penalty_seconds
            )
            return True

        return False