"""
Countdown — TileKit plugin that builds the fixed 2 × 3 board of number tiles.

Each cell gets one persistent tile using the shared quadrant renderer from
tilegame/ui.py. The values shown come from the round's BoardState, so the
starting values here are only placeholders.
"""

from style import theme
from tilekit.app import TileKitApp
from tilekit.board import Board

from games.countdown import rules


APP_NAME = "Countdown"
TILE_COLOR = theme.color("tile")
TILE_SIZE = 110   # world units; the board view resizes tiles to fit


class CountdownApp(TileKitApp):
    """Builds Countdown's board; the rules live in rules.py."""

    name = APP_NAME

    def register(self, board):
        return board

    def build_board(self):
        board = Board()
        self.register(board)

        for row in range(rules.BOARD_ROWS):
            for col in range(rules.BOARD_COLS):
                board.add_object(
                    board.create_object(
                        {
                            "kind": "number",
                            "label": "1",
                            "position": (col * TILE_SIZE, row * TILE_SIZE),
                            "size": (TILE_SIZE, TILE_SIZE),
                            "renderer": "multiple_merge_number",
                            "meta": {
                                "value": 1,
                                "row": row,
                                "col": col,
                                "color": TILE_COLOR,
                                "multiple_merge": True,
                            },
                        }
                    )
                )

        return board


APP = CountdownApp()


def register(board):
    return APP.register(board)


def build_board():
    return APP.build_board()


def create_app():
    return APP