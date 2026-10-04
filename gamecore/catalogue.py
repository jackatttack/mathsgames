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
)