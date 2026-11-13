"""
The Maths Games catalogue: every game the launcher offers, in display order.

This list is the one place a game is added to the app. Nothing here imports
game code, so listing games stays fast and needs no UIKit.

RELEASED games ship in the public build. IN_DEVELOPMENT games are offered
only in a development copy: one with a DEV_BUILD file at the project root.
tools/stage_release.py never ships that file or those games' folders.
GAMES is what this copy offers; the launcher, Appearance and the smokes
all read it.
"""

import importlib.util
import os

from gamecore.game import GameInfo


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEV_MARKER = "DEV_BUILD"


RELEASED = (
    GameInfo(
        game_id="multiple_merge",
        title="Multiple Merge",
        tagline="Merge numbers to hit multiples and targets",
        icon="×10",
        accent="warm",
        entry="games.multiple_merge.entry:create_view",
        status="playable",
    ),
    GameInfo(
        game_id="countdown",
        title="Countdown",
        tagline="Make the target from six numbers, any pair at a time",
        icon="952",
        accent="sky",
        entry="games.countdown.entry:create_view",
        status="playable",
    ),
    GameInfo(
        game_id="kenken",
        title="KenKen",
        tagline="Fill the grid so every cage makes its target",
        icon="12×",
        accent="mint",
        entry="games.kenken.entry:create_view",
        status="playable",
    ),
    GameInfo(
        game_id="sudoku",
        title="Sudoku",
        tagline="Every row, column and box holds each number once",
        icon="9",
        accent="violet",
        entry="games.sudoku.entry:create_view",
        status="playable",
    ),
    GameInfo(
        game_id="pick_and_mix",
        title="Pick & Mix",
        tagline="Two players draft tiles, then merge to get closest to the target",
        icon="1v1",
        accent="coral",
        entry="games.pick_and_mix.entry:create_view",
        status="playable",
    ),
    GameInfo(
        game_id="gradient",
        title="Gradient",
        tagline="Swap tiles to restore the colour gradient",
        icon="∇",
        accent="violet",
        entry="games.gradient.entry:create_view",
        status="playable",
    ),
    GameInfo(
        game_id="fold",
        title="Fold",
        tagline="Fold the paper until the board is one colour",
        icon="△",
        accent="mint",
        entry="games.fold.entry:create_view",
        status="playable",
    ),
    GameInfo(
        game_id="twenty48",
        title="Double Up",
        tagline="Swipe to merge tiles: doubling or Fibonacci",
        icon="×2",
        accent="warm",
        entry="games.twenty48.entry:create_view",
        status="playable",
    ),
)

# Not ready to ship yet. Listed after the released games in a dev copy.
IN_DEVELOPMENT = (
    GameInfo(
        game_id="number_detective",
        title="Number Detective",
        tagline="Crack four hidden numbers with arithmetic clues",
        icon="?",
        accent="sky",
        entry="games.number_detective.entry:create_view",
        status="in development",
    ),

    GameInfo(
        game_id="times_tables",
        title="Times Tables",
        tagline="Tap the answer: practise, or beat the clock",
        icon="7×",
        accent="coral",
        entry="games.times_tables.entry:create_view",
        status="in development",
    ),
)


# Web versions (webgames/, on the editorkit web frame work), each listed
# right after its native game. Offered only when editorkit is installed
# (Toolbox for Pythonista). They open in their own full-screen window and
# share the native game's settings, saved game and best times.
WEB_VERSIONS = (
    GameInfo(
        game_id="sudoku_web",
        title="Sudoku (web)",
        tagline="The web version: same puzzle, same best times",
        icon="9",
        accent="violet",
        entry="webgames:open_game",
        status="playable",
        web_game="sudoku",
    ),
)


def is_dev_copy():
    """True when this copy has the DEV_BUILD marker at its root."""
    return os.path.exists(os.path.join(PROJECT_DIR, DEV_MARKER))


def editorkit_installed():
    """True when the editorkit package is importable (found, not imported)."""
    try:
        return importlib.util.find_spec("editorkit") is not None
    except (ImportError, ValueError):
        return False


def with_web_versions(games):
    """games with each web version placed right after its native game."""
    listed = []
    for game in games:
        listed.append(game)
        listed.extend(web for web in WEB_VERSIONS if web.web_game == game.game_id)
    return tuple(listed)


GAMES = (RELEASED + IN_DEVELOPMENT) if is_dev_copy() else RELEASED
if editorkit_installed():
    GAMES = with_web_versions(GAMES)