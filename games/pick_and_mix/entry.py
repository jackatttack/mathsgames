"""
Opens Pick & Mix inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. PickAndMixScreen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle
describing the match.
"""

from games.pick_and_mix.screen import PickAndMixScreen


def create_view():
    """Build Pick & Mix with a new match for the saved settings."""
    return PickAndMixScreen()