"""
Opens Sudoku inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. SudokuScreen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle
describing the puzzle.
"""

from games.sudoku.screen import SudokuScreen


def create_view():
    """Build Sudoku with a fresh puzzle for the saved settings."""
    return SudokuScreen()