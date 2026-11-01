"""
FoldLayer: the ui adapter for boardkit/folds.py. A see-through view laid
over a board that plays one show at a time on its own frame clock.

A show is any object with

    done(now)   True once it has finished
    draw(now)   draws the current frame with ui, inside the layer's draw()
    finished()  optional: called once when the show ends or is skipped

The layer redraws every frame while a show plays and drops it once done.
While a show plays a tap skips it (the tap is used up); otherwise
touch_enabled is False, so touches reach the board underneath. Lay it over
the board with the board's frame, so both share coordinates.

Follows library/guides/pythonista-ui-stability.md: update_interval is set
once and update() idles without a show or a superview; nothing is added or
removed while playing.
"""

import time

import ui


class FoldLayer(ui.View):
    """Plays fold shows over a board; see the module docstring."""

    def __init__(self, skippable=True):
        super().__init__()
        self.show = None
        self.skippable = skippable      # a tap during a show skips to its end
        self.touch_enabled = False
        self.update_interval = 1 / 60.0

    def play(self, show):
        """Start show now, replacing any show still playing."""
        self.show = show
        self.touch_enabled = self.skippable
        self.set_needs_display()

    def finish(self):
        """Drop the current show at once (it ended, or a tap skipped it), and
        call its finished() if it has one, so its board can settle."""
        if self.show is None:
            return
        show, self.show = self.show, None
        self.touch_enabled = False
        ending = getattr(show, "finished", None)
        if ending is not None:
            ending()
        self.set_needs_display()

    def update(self):
        if self.superview is None or self.show is None:
            return
        if self.show.done(time.time()):
            self.finish()
            return
        self.set_needs_display()

    def draw(self):
        if self.show is not None:
            self.show.draw(time.time())

    def touch_began(self, touch):
        self.finish()