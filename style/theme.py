"""
The Maths Games theme: every colour, font, radius and timing in one place.

Games and the launcher ask for tokens by name. They never define their own
hex values or durations, so changing a value here changes the whole app.
"""


# --- colours -----------------------------------------------------------------

COLORS = {
    # Surfaces and text
    "background": "#0E1422",
    "surface": "#1A2440",
    "text": "#F7F9FC",
    "muted": "#A9B8E8",
    "button": "#2A3554",       # round icon buttons and secondary buttons

    # Accents: one per game family, used by launcher cards and highlights
    "warm": "#F3B467",
    "coral": "#F28B82",
    "mint": "#7FD8BE",
    "sky": "#7CB7FF",
    "violet": "#B69CFF",

    # Tile games: number tiles and the four operations
    "tile": "#F3B467",
    "tile_text": "#172033",
    "op_add": "#EA718D",
    "op_subtract": "#6EA8FF",
    "op_multiply": "#5ED3A2",
    "op_divide": "#A98AF4",

    # Game feedback
    "success": "#5ED3A2",              # a found target or a solved board
    "chip_disabled": "#161D30",        # a target this board cannot make
    "chip_disabled_text": "#4A5470",

    # Two-player games: each player's buttons and found targets
    "player_one": "#7CB7FF",
    "player_two": "#F28B82",
}


# --- type --------------------------------------------------------------------

FONTS = {
    "title": ("AvenirNext-Bold", 30),
    "heading": ("AvenirNext-Bold", 20),
    "header": ("AvenirNext-Bold", 18),     # the shared header title
    "body": ("AvenirNext-Medium", 15),
    "caption": ("AvenirNext-Medium", 12),
    "icon": ("AvenirNext-Bold", 30),
}


# --- shape -------------------------------------------------------------------

RADII = {
    "card": 20,
    "badge": 16,
}


# --- layout ------------------------------------------------------------------

# Points. The app presents with the Pythonista title bar hidden, so safe_top
# keeps the shared header clear of the status bar and notch.
LAYOUT = {
    "safe_top": 50,
    "header_height": 44,
    "icon_button": 40,
}


# --- feel --------------------------------------------------------------------

# Seconds for touch feedback. Short press, slightly longer spring back.
TIMINGS = {
    "press": 0.07,
    "release": 0.16,
}

# How far a pressed card or button shrinks.
PRESS_SCALE = 0.96


def color(name):
    """Return the colour for a token name, failing clearly if it is unknown."""
    try:
        return COLORS[name]
    except KeyError:
        raise KeyError(
            "Unknown colour token %r; add it to style/theme.py COLORS" % name
        )


def font(name):
    """Return the (font name, size) pair for a token name."""
    try:
        return FONTS[name]
    except KeyError:
        raise KeyError(
            "Unknown font token %r; add it to style/theme.py FONTS" % name
        )