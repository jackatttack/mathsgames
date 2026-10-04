"""
What every Maths Games game declares, and how the app finds it.

A game is described by one GameInfo record in gamecore/catalogue.py. The
record is plain data: no UIKit and no game code is imported to list games.
Opening a game resolves its entry string, "package.module:function", to a
function at that moment.

The entry function takes no arguments and returns one ui.View, which the
shell places below the shared header. The view may opt in to header
features; all are optional, and a view without them still works:

    open_settings()      define it and the header shows a gear that calls it
    header_subtitle      a short string shown under the game's title
    on_header_changed    attached by the shell; call it after changing
                         header_subtitle so the header updates
"""

from dataclasses import dataclass
import importlib


# Where a game stands. The launcher can show this beside the title.
STATUSES = ("playable", "in development", "prototype")


@dataclass(frozen=True)
class GameInfo:
    """One game as the launcher sees it."""

    game_id: str      # stable identifier, also the games/ folder name
    title: str        # display name
    tagline: str      # one line shown under the title
    icon: str         # a short glyph or emoji for the launcher card
    accent: str       # a style token name, resolved by style/, never a hex
    entry: str        # "package.module:function" returning the game's view
    status: str = "in development"

    def entry_parts(self):
        """Return (module_name, function_name) from the entry string."""
        module_name, _, function_name = self.entry.partition(":")
        return module_name.strip(), function_name.strip()


def check_catalogue(games):
    """Return a list of problems with a catalogue; an empty list means valid."""
    problems = []
    seen = set()

    for game in games:
        label = game.game_id or "(missing id)"

        if not game.game_id.isidentifier():
            problems.append("%s: game_id must be a Python identifier" % label)
        if game.game_id in seen:
            problems.append("%s: duplicate game_id" % label)
        seen.add(game.game_id)

        module_name, function_name = game.entry_parts()
        if not module_name or not function_name:
            problems.append("%s: entry must be 'package.module:function'" % label)

        if game.status not in STATUSES:
            problems.append(
                "%s: status must be one of %s" % (label, ", ".join(STATUSES))
            )

    return problems


def find_game(games, game_id):
    """Return the GameInfo with this id, or None."""
    for game in games:
        if game.game_id == game_id:
            return game
    return None


def load_entry(game):
    """Import the game's module now and return its open function."""
    module_name, function_name = game.entry_parts()
    module = importlib.import_module(module_name)
    return getattr(module, function_name)