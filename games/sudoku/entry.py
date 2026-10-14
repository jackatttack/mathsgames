"""
Opens Sudoku inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. SudokuScreen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle
describing the puzzle.

The theme editor calls create_preview() to show the real screen in colours
that are not saved yet (notes/THEME_EDITOR_SPEC.txt).
"""

from games.sudoku.screen import SudokuScreen


# The colours the theme editor offers for Sudoku, in order:
# (role token in style/theme.py, name, what it colours).
THEME_ROLES = (
    ("background", "Background", "Behind the board and buttons"),
    ("board", "Board", "The cells"),
    ("grid_line", "Grid lines", "Thin lines between cells"),
    ("box_wall", "Box walls", "Thick lines round each box"),
    ("given", "Given numbers", "Numbers the puzzle starts with"),
    ("player_number", "Your numbers", "Numbers you write in"),
    ("note", "Notes", "Pencil marks"),
    ("selection_fill", "Selected cell", "The cell you tapped"),
    ("selection", "Selection outline", "The ring round the cell you tapped"),
    ("assist_peer", "Row, column and box", "Highlight round the selected cell"),
    ("assist_match", "Matching numbers", "Cells holding the selected number"),
)


def create_view():
    """Build Sudoku with a fresh puzzle for the saved settings."""
    return SudokuScreen()


def create_preview():
    """Build the real Sudoku screen as a preview.

    A fixed sample with default settings: no settings read, no saved game
    resumed or written, and touches off.
    """
    return SudokuScreen(preview=True)