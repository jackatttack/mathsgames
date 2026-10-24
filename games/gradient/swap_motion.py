"""
Swap motion for Gradient: where a swapping tile is at each moment, with no UI.

The Arc technique in labs/gradient_swap_lab.py asks frame_at() for each moving
tile about 60 times a second. The path bows out to one side, so the two
tiles of a swap pass beside each other rather than through each other, and
it overshoots a little before settling, which reads as a soft landing.

Frames are (x, y, width, height). Pure Python; smokes/gradient_smoke.py
checks it.
"""


# --- editable feel -----------------------------------------------------------

ARC_BEND = 0.18     # how far the path bows out, as a share of the distance travelled
OVERSHOOT = 0.8     # ease-out-back strength: 0 lands with no overshoot


def ease_out_back(t, overshoot=OVERSHOOT):
    """0 at t = 0 and 1 at t = 1, rising a little past 1 near the end when overshoot > 0."""
    t = min(1.0, max(0.0, t))
    u = t - 1
    return 1 + (overshoot + 1) * u ** 3 + overshoot * u ** 2


def frame_at(start, end, progress, side=1, bend=ARC_BEND, overshoot=OVERSHOOT):
    """The frame part way (progress 0..1) along a swap from start to end.

    The centre follows a quadratic curve whose middle is pushed sideways,
    perpendicular to the straight path, by bend times the distance. side
    (1 or -1) picks which way; give the two tiles of a swap opposite sides.
    Width and height ease from start to end, so a lifted tile shrinks as it
    lands.
    """
    eased = ease_out_back(progress, overshoot)
    start_x, start_y = _centre(start)
    end_x, end_y = _centre(end)
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
    return (x - width / 2, y - height / 2, width, height)


def _centre(frame):
    x, y, width, height = frame
    return (x + width / 2, y + height / 2)
