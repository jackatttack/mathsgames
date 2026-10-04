"""
Opens Multiple Merge inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. GameScreen uses the header contract
(gamecore/game.py): a gear for its settings and a subtitle naming the mode.
"""

from games.multiple_merge import plugin
from games.multiple_merge.screen import GameScreen
from tilekit.app import load_app


def create_view():
    """Build Multiple Merge with a fresh board and return its screen."""
    app = load_app(plugin)
    return GameScreen(board=app.build_board())