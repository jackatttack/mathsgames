"""
The finishing wave for Gradient: when each tile pulses once a level is solved.

A ripple spreads from the last tile placed: each tile swells and settles
once, starting later the further it is from that tile. board_view.py asks
these functions on every frame-clock tick.

Pure Python: smokes/gradient_smoke.py checks it.
"""

import math


# --- editable feel -----------------------------------------------------------

WAVE_SECONDS = 1.1      # from the first pulse starting to the last one starting
PULSE_SECONDS = 0.35    # one tile's pulse
PULSE_GROW = 0.22       # how much a tile swells at the top of its pulse


def wave_starts(cols, rows, origin):
    """{cell: start seconds} for a ripple outwards from the origin cell."""
    origin_row, origin_col = divmod(origin, cols)
    distances = {}
    for cell in range(cols * rows):
        row, col = divmod(cell, cols)
        distances[cell] = math.hypot(row - origin_row, col - origin_col)
    farthest = max(distances.values()) or 1.0
    return {cell: WAVE_SECONDS * distance / farthest for cell, distance in distances.items()}


def wave_length(starts):
    """Seconds from the wave starting until its last pulse ends."""
    return max(starts.values()) + PULSE_SECONDS if starts else 0.0


def pulse_scale(since_start, seconds=PULSE_SECONDS, grow=PULSE_GROW):
    """1 before and after a pulse; swells smoothly to 1 + grow halfway through."""
    if since_start <= 0 or since_start >= seconds:
        return 1.0
    return 1.0 + grow * math.sin(math.pi * since_start / seconds)


def scaled(frame, factor):
    """A frame grown or shrunk by factor about its own centre."""
    x, y, width, height = frame
    new_width, new_height = width * factor, height * factor
    return (x + (width - new_width) / 2, y + (height - new_height) / 2, new_width, new_height)
