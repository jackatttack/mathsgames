"""
Colour maths for Gradient: sRGB, OKLab and OKLCh.

OKLab (Bjorn Ottosson, 2020) is a perceptual colour space: equal distances
in it look like roughly equal colour differences. The game builds every gradient
in OKLab so neighbouring tiles step by even-looking amounts, and measures
difficulty there too.

Conventions:
    sRGB  (r, g, b)  floats 0..1, as ui wants them (PIL wants them * 255)
    OKLab (L, a, b)  L is lightness 0..1; a and b run roughly -0.4..0.4
    OKLCh (L, C, h)  C is chroma (colourfulness), h is hue in degrees

A distance of about 0.02 in OKLab is a small but visible difference.

Pure Python, no UI: safe in Pythonista, PythonIDE and Forge RUN.
"""

import math


# --- sRGB transfer curve ---------------------------------------------------

def _linear_from_gamma(channel):
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def _gamma_from_linear(channel):
    # Negative (out of gamut) values take the straight branch, which keeps
    # Python from producing a complex number.
    if channel <= 0.0031308:
        return 12.92 * channel
    return 1.055 * channel ** (1 / 2.4) - 0.055


def _cube_root(x):
    return math.copysign(abs(x) ** (1 / 3), x)


# --- conversions -------------------------------------------------------------

def oklab_from_srgb(rgb):
    """OKLab for an sRGB colour."""
    r, g, b = (_linear_from_gamma(c) for c in rgb)
    l = _cube_root(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
    m = _cube_root(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
    s = _cube_root(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
    return (
        0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
        1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
        0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s,
    )


def srgb_from_oklab_unclipped(lab):
    """sRGB for an OKLab colour; channels fall outside 0..1 when out of gamut."""
    L, a, b = lab
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    linear = (
        4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
        -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
        -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s,
    )
    return tuple(_gamma_from_linear(c) for c in linear)


def srgb_from_oklab(lab):
    """sRGB for an OKLab colour, clipped into 0..1."""
    return tuple(min(1.0, max(0.0, c)) for c in srgb_from_oklab_unclipped(lab))


def in_gamut(rgb, tolerance=1e-4):
    """True when every sRGB channel lies in 0..1 (within tolerance)."""
    return all(-tolerance <= c <= 1 + tolerance for c in rgb)


def oklab_from_oklch(lch):
    L, C, h = lch
    angle = math.radians(h)
    return (L, C * math.cos(angle), C * math.sin(angle))


def oklch_from_oklab(lab):
    L, a, b = lab
    return (L, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360)


def fit_chroma(L, C, h, steps=20):
    """The OKLCh colour nearest (L, C, h) that a screen can show.

    Keeps lightness and hue and lowers chroma by bisection until the colour
    fits in sRGB. Returns (L, C, h).
    """
    if in_gamut(srgb_from_oklab_unclipped(oklab_from_oklch((L, C, h)))):
        return (L, C, h)
    low, high = 0.0, C
    for _ in range(steps):
        middle = (low + high) / 2
        if in_gamut(srgb_from_oklab_unclipped(oklab_from_oklch((L, middle, h)))):
            low = middle
        else:
            high = middle
    return (L, low, h)


def distance(lab_a, lab_b):
    """Perceptual difference between two OKLab colours (about 0.02 is just visible)."""
    return math.sqrt(
        (lab_a[0] - lab_b[0]) ** 2
        + (lab_a[1] - lab_b[1]) ** 2
        + (lab_a[2] - lab_b[2]) ** 2
    )


def hex_from_srgb(rgb):
    """'#rrggbb' for an sRGB colour."""
    return "#" + "".join("%02x" % round(min(1.0, max(0.0, c)) * 255) for c in rgb)
