"""
Opens Pick & Mix inside Maths Games.

The launcher calls create_view() when the game is chosen and places the
returned view below the shared header. PickAndMixScreen uses the header
contract (gamecore/game.py): a gear for its settings and a subtitle
describing the match.

The theme editor calls create_preview() to show the real screen in colours
that are not saved yet, and offers the roles in THEME_ROLES
(notes/THEME_EDITOR_SPEC.txt). Player colours stay locked: they mean whose
tile and whose turn.
"""

from games.pick_and_mix.screen import PickAndMixScreen


# The colours the theme editor offers for Pick & Mix, in order:
# (role token in style/theme.py, name, what it colours).
THEME_ROLES = (
    ("background", "Background", "Behind the pool and zones"),
    ("surface", "Panels", "Player zones and results"),
    ("tile", "Tiles", "Number tiles in the pool"),
    ("button", "Buttons", "Undo"),
    ("text", "Text", "Labels, scores and button words"),
)


def create_view():
    """Build Pick & Mix with a new match for the saved settings."""
    return PickAndMixScreen()


def create_preview():
    """Build the real Pick & Mix screen as a preview.

    A seeded match with default settings: no settings read or written, and
    touches off.
    """
    return PickAndMixScreen(preview=True)