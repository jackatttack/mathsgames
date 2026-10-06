"""
The app shell: the one presented view.

It shows the home screen or one game, always beneath the shared header.
Opening a game resolves its catalogue entry at that moment; if that fails,
the traceback goes to the console and the home screen shows a message, so a
broken game never takes the app down.

Game views may opt in to header features (see gamecore/game.py):
open_settings() shows the gear, header_subtitle fills the subtitle line, and
the shell attaches on_header_changed so a game can report a new subtitle.
"""

import traceback

import ui

from feel import tactile
from gamecore.game import load_entry
from launcher.header import HeaderBar
from launcher.help_card import HelpCardOverlay
from gamecore import how_to_play
from launcher.home import HomeView
from style import theme


HOME_TITLE = "Maths Games"
HOME_SUBTITLE = "Pick a game"


class AppShell(ui.View):
    """Home screen or current game, under one shared header."""

    CONTENT_GAP = 8   # points between the header and the content below

    def __init__(self, games, **kwargs):
        super().__init__(**kwargs)
        self.background_color = theme.color("background")
        self.game_view = None
        self.help_card = None       # the open game's HelpCard, if it has one
        self.help_accent = theme.color("tile")

        self.home = HomeView(games, on_open=self.open_game)
        self.add_subview(self.home)

        self.header = HeaderBar(
            on_left=self.left_tapped,
            on_settings=self.settings_tapped,
            on_help=self.help_tapped,
        )
        self.add_subview(self.header)

        # Built once, shown over everything when the ? is tapped.
        self.help_overlay = HelpCardOverlay()
        self.add_subview(self.help_overlay)

        self.show_home_header()

    # --- header --------------------------------------------------------------

    def show_home_header(self):
        self.header.show(HOME_TITLE, HOME_SUBTITLE, back=False, settings=False)

    def game_header_changed(self):
        """Called by a game after it changes its header_subtitle."""
        if self.game_view is not None:
            self.header.set_subtitle(
                getattr(self.game_view, "header_subtitle", "")
            )

    def left_tapped(self, sender=None):
        if self.game_view is None:
            self.close()
        else:
            self.close_game()

    def settings_tapped(self, sender=None):
        open_settings = getattr(self.game_view, "open_settings", None)
        if callable(open_settings):
            open_settings()

    def help_tapped(self, sender=None):
        """Show the open game's how-to-play card."""
        if self.help_card is not None:
            self.help_overlay.show_card(self.help_card, self.help_accent)

    # --- games ---------------------------------------------------------------

    def open_game(self, game):
        """Build the chosen game's view and show it in place of the home screen."""
        tactile.haptic_tap()
        try:
            create_view = load_entry(game)
            view = create_view()
        except Exception:
            traceback.print_exc()
            self.home.show_message(
                "Couldn't open %s. The console has the details." % game.title
            )
            return

        self.show_game(
            view, game.title,
            help_card=how_to_play.load_card(game),
            accent=theme.color(game.accent),
        )

    def show_game(self, view, title, help_card=None, accent=None):
        """Place a built game view under the header.

        Separate from open_game so a smoke can supply its own view. With a
        help_card the header shows a ? that opens it, in the game's accent.
        """
        self.game_view = view
        self.help_card = help_card
        self.help_accent = accent or theme.color("tile")
        self.add_subview(view)

        try:
            view.on_header_changed = self.game_header_changed
        except AttributeError:
            pass   # a plain view that cannot take attributes; no subtitle updates

        self.header.show(
            title,
            getattr(view, "header_subtitle", ""),
            back=True,
            settings=callable(getattr(view, "open_settings", None)),
            help=help_card is not None,
        )
        self.home.hidden = True
        self.layout()

    def close_game(self, sender=None):
        """Leave the current game and return to the home screen."""
        tactile.haptic_tap()
        self.help_overlay.close_tapped()
        self.help_card = None
        if self.game_view is not None:
            self.remove_subview(self.game_view)
            self.game_view = None
        self.show_home_header()
        self.home.hidden = False

    # --- layout --------------------------------------------------------------

    def layout(self):
        width, height = self.width, self.height
        top = theme.LAYOUT["safe_top"]
        header_height = theme.LAYOUT["header_height"]

        self.header.frame = (0, top, width, header_height)
        self.help_overlay.frame = (0, 0, width, height)

        content_top = top + header_height + self.CONTENT_GAP
        content = (0, content_top, width, max(0, height - content_top))
        self.home.frame = content

        if self.game_view is not None:
            self.game_view.frame = content