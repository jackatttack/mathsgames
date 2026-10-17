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
)

# Not good enough to ship yet. Listed after the released games in a dev copy.
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
)


def is_dev_copy():
    """True when this copy has the DEV_BUILD marker at its root."""
    return os.path.exists(os.path.join(PROJECT_DIR, DEV_MARKER))


GAMES = (RELEASED + IN_DEVELOPMENT) if is_dev_copy() else RELEASED