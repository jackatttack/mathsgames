"""
Opens Countdown inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. CountdownScreen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle
describing the deal.

The theme editor calls create_preview() to show the real screen in colours
that are not saved yet, and offers the roles in THEME_ROLES
(notes/THEME_EDITOR_SPEC.txt).
"""

from games.countdown import plugin
from games.countdown.screen import CountdownScreen
from tilekit.app import load_app


# The colours the theme editor offers for Countdown, in order:
# (role token in style/theme.py, name, what it colours).
THEME_ROLES = (
    ("background", "Background", "Behind the board and buttons"),
    ("surface", "Panels", "The factors card"),
    ("tile", "Tiles", "Number tiles and the main button"),
    ("target_chip", "Target chip", "The number to make"),
    ("button", "Buttons", "Reset and Skip"),
    ("text", "Text", "Labels, times and button words"),
)


def create_view():
    """Build Countdown with a fresh 2 × 3 board and return its screen."""
    app = load_app(plugin)
    return CountdownScreen(board=app.build_board())


def create_preview():
    """Build the real Countdown screen as a preview.

    A seeded board with default settings: no settings or records read or
    written, and touches off.
    """
    app = load_app(plugin)
    return CountdownScreen(board=app.build_board(), preview=True)