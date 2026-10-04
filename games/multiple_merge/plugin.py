"""
Multiple Merge — fresh TileKit game plugin.

This is intentionally a clean implementation.

The historical Multiple Merge prototype is a behavioural and design
reference only. Its source is not the implementation base for this app.
"""

from style import theme
from tilekit.app import TileKitApp
from tilekit.board import Board


APP_NAME = "Multiple Merge"

TILE_COLOR = theme.color("tile")

STARTING_NUMBERS = (
    (7, 4),
    (3, 6),
)


class MultipleMergeApp(TileKitApp):
    """Initial TileKit foundation for the Multiple Merge reboot."""

    name = APP_NAME

    def register(self, board):
        """
        Register game-specific rules and actions.

        Phase 1 deliberately starts with no inherited interaction rules.
        The arithmetic interaction will be implemented explicitly once
        its state machine is defined.
        """
        return board

    def build_board(self):
        """Build the first clean 2x2 Multiple Merge board."""
        board = Board()
        self.register(board)

        size = 124
        gap = 18
        origin_x = 74
        origin_y = 126

        for row, values in enumerate(STARTING_NUMBERS):
            for col, value in enumerate(values):
                x = origin_x + col * (size + gap)
                y = origin_y + row * (size + gap)

                board.add_object(
                    board.create_object(
                        {
                            "kind": "number",
                            "label": str(value),
                            "position": (x, y),
                            "size": (size, size),
                            "renderer": "multiple_merge_number",
                            "meta": {
                                "value": value,
                                "row": row,
                                "col": col,
                                "color": TILE_COLOR,
                                "multiple_merge": True,
                            },
                        }
                    )
                )

        return board


APP = MultipleMergeApp()


def register(board):
    return APP.register(board)


def build_board():
    return APP.build_board()


def create_app():
    return APP