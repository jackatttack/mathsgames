"""
Opens Double Up inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. Twenty48Screen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle naming
the rules.

The theme editor calls create_preview() to show the real screen in colours
that are not saved yet. The tile ramp is fixed, like the operation colours.
"""

from games.twenty48.screen import Twenty48Screen


# The colours the theme editor offers for Double Up, in order:
# (role token in style/theme.py, name, what it colours).
THEME_ROLES = (
    ("background", "Background", "Behind the board and buttons"),
    ("board", "Board", "The frame behind the tiles"),
    ("grid_line", "Empty cells", "Cells with no tile in them"),
    ("text", "Text", "The score"),
)


def create_view():
    """Build Double Up, resuming a saved game that fits the saved settings."""
    return Twenty48Screen()


def create_preview():
    """Build the real Double Up screen as a preview: a fixed board, no files, touches off."""
    return Twenty48Screen(preview=True)