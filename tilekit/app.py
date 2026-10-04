"""
TileKit app contract.

A TileKit app owns app-specific setup: rules, initial objects, palettes,
actions, renderers, coordinate systems, and later persistence defaults.

The framework core should not know about calculator, chess, Forge tiles,
or desktop apps. It only knows how to run an app object that follows this
small contract.
"""


class TileKitApp:
    """Small app contract used by launchers and tests."""

    name = "Untitled"

    def register(self, board):
        """Register app-specific rules/actions/renderers on a board."""
        return board

    def build_board(self):
        """Build and return a board for this app."""
        raise NotImplementedError


def load_app(module):
    """
    Load a TileKit app from a plugin module.

    Supported plugin shapes:
    - module.APP is a TileKitApp-like object
    - module.create_app() returns a TileKitApp-like object
    - module.build_board() exists, with optional APP_NAME
    """
    app = getattr(module, "APP", None)
    if app is not None:
        return app

    create_app = getattr(module, "create_app", None)
    if callable(create_app):
        return create_app()

    build_board = getattr(module, "build_board", None)
    if callable(build_board):
        name = getattr(module, "APP_NAME", "Untitled")

        class FunctionApp(TileKitApp):
            pass

        FunctionApp.name = name
        FunctionApp.build_board = staticmethod(build_board)
        return FunctionApp()

    raise ValueError("module does not expose a TileKit app")