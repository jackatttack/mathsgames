"""
Opens Countdown inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. CountdownScreen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle
describing the deal.
"""

from games.countdown import plugin
from games.countdown.screen import CountdownScreen
from tilekit.app import load_app


def create_view():
    """Build Countdown with a fresh 2 × 3 board and return its screen."""
    app = load_app(plugin)
    return CountdownScreen(board=app.build_board())