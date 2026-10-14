"""
Opens KenKen inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. KenKenScreen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle
describing the puzzle.

The theme editor calls create_preview() to show the real screen in colours
that are not saved yet, and offers the roles in THEME_ROLES
(notes/THEME_EDITOR_SPEC.txt).
"""

from games.kenken.screen import KenKenScreen


# The colours the theme editor offers for KenKen, in order:
# (role token in style/theme.py, name, what it colours).
THEME_ROLES = (
    ("background", "Background", "Behind the board and buttons"),
    ("board", "Board", "The cells"),
    ("grid_line", "Grid lines", "Thin lines between cells"),
    ("box_wall", "Cage walls", "Thick lines round each cage"),
    ("given", "Numbers and labels", "Your numbers and the cage clues"),
    ("note", "Notes", "Pencil marks"),
    ("selection_fill", "Selected cell", "The cell you tapped"),
    ("selection", "Selection outline", "The ring round the cell you tapped"),
)


def create_view():
    """Build KenKen with a fresh puzzle for the saved settings."""
    return KenKenScreen()


def create_preview():
    """Build the real KenKen screen as a preview.

    A fixed sample with default settings: no settings read, no saved game
    resumed or written, and touches off.
    """
    return KenKenScreen(preview=True)