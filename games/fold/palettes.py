"""
Fold palettes: the paint for colour numbers 0, 1, 2, ...

Paper colours are built in OKLCh (games/gradient/colour.py) so they read as
clearly different: hues spread round the wheel, lightness stepped so
neighbours differ in value as well as hue, and chroma kept modest for a
printed-paper look, fitted into what a screen can show.

Named palettes are hand-picked sets in the spirit of KAMI's quilts.
"""

import itertools
import random

from games.gradient import colour


# --- editable feel -----------------------------------------------------------

PAPER_LIGHTNESS = (0.58, 0.72, 0.84)    # used in turn round the hue wheel
PAPER_CHROMA = 0.13
HUE_JITTER = 12                          # degrees either way
MIN_DISTANCE = 0.08                      # closest two paper colours may be, in OKLab
ATTEMPTS = 40

NAMED = {
    "quilt":   ("#c8323c", "#e8b23a", "#3f7f9e", "#f1e6d0", "#2b2a4a"),
    "rainbow": ("#d9433a", "#ef8a2f", "#f2c938", "#79b543", "#3f8fc4", "#6d4fa1"),
    "slate":   ("#e9e1cf", "#7f8c96", "#2e3a45", "#d98c5f", "#f3efe7"),
    # Scene colour numbers: 0 background, 1-3 stone, 4-6 brick, 7 ribbon.
    "scene":   ("#26292e", "#efe3c8", "#a7a39a", "#6b6a66",
                "#d9483b", "#a3342b", "#6c2420", "#2f9c7c"),
}


def paper(count, rng=None):
    """count paper colours as '#rrggbb', the most separated of a few tries."""
    rng = rng or random.Random()
    best, best_gap = None, -1.0
    for _ in range(ATTEMPTS):
        start = rng.uniform(0, 360)
        labs = []
        for index in range(count):
            hue = (start + 360.0 * index / count + rng.uniform(-HUE_JITTER, HUE_JITTER)) % 360
            lightness = PAPER_LIGHTNESS[index % len(PAPER_LIGHTNESS)]
            labs.append(colour.oklab_from_oklch(colour.fit_chroma(lightness, PAPER_CHROMA, hue)))
        gap = min((colour.distance(a, b) for a, b in itertools.combinations(labs, 2)), default=1.0)
        if gap > best_gap:
            best, best_gap = labs, gap
        if gap >= MIN_DISTANCE:
            break
    return [colour.hex_from_srgb(colour.srgb_from_oklab(lab)) for lab in best]


def named(name, count):
    """The first count colours of a named palette."""
    if name not in NAMED:
        raise ValueError("palette must be one of {}, not {!r}".format(sorted(NAMED), name))
    if count > len(NAMED[name]):
        raise ValueError("{} has only {} colours".format(name, len(NAMED[name])))
    return list(NAMED[name][:count])
