# tilekit/

Core framework package for TileKit.

TileKit is an interactive object-surface framework. It provides boards, tile objects, renderers, coordinate systems, input models, action models, rule engines, and scene persistence.

This package should stay app-neutral.

Calculator rules belong in apps/calculator.
Chess rules belong in apps/chess.
Forge/file-manager rules belong in apps/forge_tiles.

Core rule:
Tile identity and behaviour must remain separate from visual representation.## App contract

TileKit apps should expose one of these plugin shapes:

    APP = SomeTileKitApp()

or:

    def create_app():
        return SomeTileKitApp()

Compatibility helpers like build_board() are allowed for tiny demos, but the preferred long-term shape is a TileKitApp object.

Apps own app-specific rules, actions, palettes, coordinate systems, renderers, and initial scenes. Core TileKit remains app-neutral.
