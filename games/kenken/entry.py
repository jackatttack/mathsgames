"""
Opens KenKen inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. KenKenScreen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle
describing the puzzle.
"""

from games.kenken.screen import KenKenScreen


def create_view():
    """Build KenKen with a fresh puzzle for the saved settings."""
    return KenKenScreen()