"""
Opens Multiple Merge inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. GameScreen uses the header contract
(gamecore/game.py): a gear for its settings and a subtitle naming the mode.

The theme editor calls create_preview() to show the real screen in colours
that are not saved yet, and offers the roles in THEME_ROLES
(notes/THEME_EDITOR_SPEC.txt).
"""

from games.multiple_merge import plugin
from games.multiple_merge.screen import GameScreen
from tilekit.app import load_app


# The colours the theme editor offers for Multiple Merge, in order:
# (role token in style/theme.py, name, what it colours).
THEME_ROLES = (
    ("background", "Background", "Behind the board and buttons"),
    ("tile", "Tiles", "Number tiles and the main button"),
    ("open_chip", "Open targets", "Targets you can still make"),
    ("button", "Buttons", "Reset board"),
    ("text", "Text", "Labels, targets and button words"),
)


def create_view():
    """Build Multiple Merge with a fresh board and return its screen."""
    app = load_app(plugin)
    return GameScreen(board=app.build_board())


def create_preview():
    """Build the real Multiple Merge screen as a preview.

    Classic with a seeded board and default settings: no settings or records
    read or written, and touches off.
    """
    app = load_app(plugin)
    return GameScreen(board=app.build_board(), preview=True)