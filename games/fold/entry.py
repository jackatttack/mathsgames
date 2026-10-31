"""
Opens Fold inside Maths Games.

The launcher calls create_view() when the game is chosen; create_preview()
builds the same screen for the theme editor with no files touched. Not in
gamecore/catalogue.py yet: until it is, play it from labs/fold_game_lab.py.
Board colours are each puzzle's own palette, so they never follow the theme.
"""

from games.fold.screen import FoldScreen


# The colours the theme editor offers for Fold, in order:
# (role token in style/theme.py, name, what it colours). Not wired to the
# theme yet: screen.py still uses its own constants.
THEME_ROLES = (
    ("background", "Background", "Behind the library and the board"),
    ("text", "Text", "Titles, moves and par"),
)


def create_view():
    """Build Fold: the puzzle library, ready to play."""
    return FoldScreen()


def create_preview():
    """The real Fold screen as a preview: no files read or written, touches off."""
    return FoldScreen(preview=True)
