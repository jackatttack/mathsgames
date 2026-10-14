"""
Opens Number Detective inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. DetectiveScreen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle naming
the pool.

The theme editor calls create_preview() to show the real screen in colours
that are not saved yet, and offers the roles in THEME_ROLES
(notes/THEME_EDITOR_SPEC.txt).
"""

from games.number_detective.screen import DetectiveScreen


# The colours the theme editor offers for Number Detective, in order:
# (role token in style/theme.py, name, what it colours).
THEME_ROLES = (
    ("background", "Background", "Behind the tiles and cards"),
    ("surface", "Panels", "The case log"),
    ("tile", "Chosen tiles", "Tiles picked for a question, and Ask"),
    ("open_outline", "Open tile outline", "The tile you are naming"),
    ("button", "Buttons", "Question cards and New case"),
    ("text", "Text", "Labels, the log and button words"),
)


def create_view():
    """Build Number Detective with a fresh case for the saved settings."""
    return DetectiveScreen()


def create_preview():
    """Build the real Number Detective screen as a preview.

    A seeded case with default settings: no settings read or written, and
    touches off.
    """
    return DetectiveScreen(preview=True)