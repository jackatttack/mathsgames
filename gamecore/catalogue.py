"""
The Maths Games catalogue: every game the launcher offers, in display order.

This list is the one place a game is added to the app. Nothing here imports
game code, so listing games stays fast and needs no UIKit.
"""

from gamecore.game import GameInfo


GAMES = (
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
        status="in development",
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
        game_id="number_detective",
        title="Number Detective",
        tagline="Crack four hidden numbers with arithmetic clues",
        icon="?",
        accent="sky",
        entry="games.number_detective.entry:create_view",
        status="in development",
    ),
)