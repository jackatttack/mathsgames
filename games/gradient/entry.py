"""
Opens Gradient inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. GradientScreen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle naming
the level.

The theme editor calls create_preview() to show the real screen in colours
that are not saved yet. Tile colours are the level itself, so like the
operation colours they never follow the theme.
"""

from games.gradient.screen import GradientScreen


# The colours the theme editor offers for Gradient, in order:
# (role token in style/theme.py, name, what it colours).
THEME_ROLES = (
    ("background", "Background", "Behind the board and buttons"),
    ("text", "Text", "Moves, par and the drop outline"),
)


def create_view():
    """Build Gradient, resuming a saved level that fits the saved mode."""
    return GradientScreen()


def create_preview():
    """Build the real Gradient screen as a preview: a fixed level, no files, touches off."""
    return GradientScreen(preview=True)
