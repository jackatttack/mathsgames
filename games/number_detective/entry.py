"""
Opens Number Detective inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. DetectiveScreen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle naming
the pool.
"""

from games.number_detective.screen import DetectiveScreen


def create_view():
    """Build Number Detective with a fresh case for the saved settings."""
    return DetectiveScreen()