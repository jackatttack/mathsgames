"""
Easing and motion paths for boardkit: where a moving tile is part way
through its move. Pure Python, checked by smokes/boardkit_smoke.py.

Frames are (x, y, width, height); progress runs from 0 to 1. A path is any
function path(start, end, progress) -> frame. straight() and arc() make
them, ready to hand to a clock.Track.

The arc, its easing and the pulse come from Gradient
(games/gradient/swap_motion.py and wave.py), where Jack chose them in the
swap lab.
"""

import math


# --- editable feel -----------------------------------------------------------

ARC_BEND = 0.18      # how far an arc bows out, as a share of the distance travelled
OVERSHOOT = 0.8      # ease-out-back strength: 0 lands with no overshoot
PULSE_GROW = 0.22    # how much a pulsing tile swells at its peak


# --- easing ------------------------------------------------------------------

def clamp(t):
    return min(1.0, max(0.0, t))


def ease_out_cubic(t):
    """Fast start, gentle stop, never past 1."""
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_out_back(t, overshoot=OVERSHOOT):
    """0 at t = 0 and 1 at t = 1, rising a little past 1 near the end when overshoot > 0."""
    t = clamp(t)
    u = t - 1
    return 1 + (overshoot + 1) * u ** 3 + overshoot * u ** 2


# --- frame helpers -----------------------------------------------------------

def blend(a, b, t):
    return a + (b - a) * t


def centre(frame):
    x, y, width, height = frame
    return (x + width / 2, y + height / 2)


def frame_around(point, width, height):
    """A frame of this size centred on point."""
    return (point[0] - width / 2, point[1] - height / 2, width, height)


def scaled(frame, factor):
    """A frame grown or shrunk by factor about its own centre."""
    x, y, width, height = frame
    new_width, new_height = width * factor, height * factor
    return (x + (width - new_width) / 2, y + (height - new_height) / 2, new_width, new_height)


# --- paths -------------------------------------------------------------------

def straight_frame(start, end, progress, ease=ease_out_cubic):
    """The frame part way along a straight, eased move."""
    eased = ease(progress)
    return tuple(blend(a, b, eased) for a, b in zip(start, end))


def arc_frame(start, end, progress, side=1, bend=ARC_BEND, overshoot=OVERSHOOT):
    """The frame part way along a bowed move that overshoots a little and settles.

    The centre follows a quadratic curve whose middle is pushed sideways,
    perpendicular to the straight path, by bend times the distance. side
    (1 or -1) picks which way; give the two tiles of a swap opposite sides
    to have them pass beside each other. Width and height ease from start to
    end, so a lifted tile shrinks as it lands.
    """
    eased = ease_out_back(progress, overshoot)
    start_x, start_y = centre(start)
    end_x, end_y = centre(end)
    dx, dy = end_x - start_x, end_y - start_y

    # A quadratic curve reaches half its control point's offset at its
    # middle, so the control point sits twice as far out as the bow wanted.
    control_x = (start_x + end_x) / 2 - side * 2 * bend * dy
    control_y = (start_y + end_y) / 2 + side * 2 * bend * dx

    weight_start = (1 - eased) ** 2
    weight_control = 2 * (1 - eased) * eased
    weight_end = eased ** 2
    x = weight_start * start_x + weight_control * control_x + weight_end * end_x
    y = weight_start * start_y + weight_control * control_y + weight_end * end_y

    width = start[2] + (end[2] - start[2]) * eased
    height = start[3] + (end[3] - start[3]) * eased
    return frame_around((x, y), width, height)


def straight(ease=ease_out_cubic):
    """A path along the straight line, eased."""
    def path(start, end, progress):
        return straight_frame(start, end, progress, ease)
    return path


def arc(side=1, bend=ARC_BEND, overshoot=OVERSHOOT):
    """A bowed path with a soft landing (see arc_frame)."""
    def path(start, end, progress):
        return arc_frame(start, end, progress, side, bend, overshoot)
    return path


# --- pulses ------------------------------------------------------------------

def pulse_scale(since_start, seconds, grow=PULSE_GROW):
    """1 before and after a pulse; swells smoothly to 1 + grow halfway through."""
    if since_start <= 0 or since_start >= seconds:
        return 1.0
    return 1.0 + grow * math.sin(math.pi * since_start / seconds)
