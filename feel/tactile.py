"""
Touch feel shared by the launcher and every game.

press() and release() give views the same quick shrink and spring back.
haptic_tap() fires a real iOS impact. Haptics are optional: if objc_util is
unavailable or anything fails, the tap silently does nothing, because touch
feedback must never break a game.
"""

import ui

from style import theme


def press(view):
    """Shrink a view slightly while a finger is on it."""
    def shrink():
        view.transform = ui.Transform.scale(theme.PRESS_SCALE, theme.PRESS_SCALE)
    ui.animate(shrink, duration=theme.TIMINGS["press"])


def release(view):
    """Spring a pressed view back to full size."""
    def restore():
        view.transform = ui.Transform()
    ui.animate(restore, duration=theme.TIMINGS["release"])


# One generator is reused; UIKit objects must be created on the main thread.
_impact_generator = None


def haptic_tap():
    """Fire one medium impact haptic, or do nothing if unavailable."""
    try:
        from objc_util import on_main_thread
    except ImportError:
        return
    try:
        on_main_thread(_fire_impact)()
    except Exception:
        pass


def _fire_impact():
    global _impact_generator
    from objc_util import ObjCClass

    if _impact_generator is None:
        medium = 1  # UIImpactFeedbackStyleMedium
        _impact_generator = (
            ObjCClass("UIImpactFeedbackGenerator").alloc().initWithStyle_(medium)
        )
    _impact_generator.impactOccurred()