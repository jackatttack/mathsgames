"""
The home screen: one card per catalogue game, under the shell's header.

Cards are drawn from GameInfo records only, so the home screen never
imports game code. Choosing a card calls on_open(game).
"""

import ui

from feel import tactile
from style import theme


class GameCard(ui.View):
    """One tappable game card: accent badge, icon, title, tagline, status."""

    BADGE_SIZE = 64

    def __init__(self, game, on_open, **kwargs):
        super().__init__(**kwargs)
        self.game = game
        self.on_open = on_open
        self.background_color = (0, 0, 0, 0)

    def layout(self):
        self.set_needs_display()

    def draw(self):
        width, height = self.width, self.height
        badge = self.BADGE_SIZE
        badge_x = 16
        badge_y = (height - badge) / 2
        text_x = badge_x + badge + 16
        text_width = max(0, width - text_x - 16)

        ui.set_color(theme.color("surface"))
        ui.Path.rounded_rect(0, 0, width, height, theme.RADII["card"]).fill()

        # The badge looks like a game tile: accent fill, soft gloss, dark glyph.
        badge_path = ui.Path.rounded_rect(
            badge_x, badge_y, badge, badge, theme.RADII["badge"],
        )
        ui.set_color(theme.color(self.game.accent))
        badge_path.fill()

        with ui.GState():
            badge_path.add_clip()
            ui.set_color((1, 1, 1, 0.18))
            ui.Path.rect(badge_x, badge_y, badge, badge * 0.42).fill()

        icon = self.game.icon
        icon_size = min(theme.font("icon")[1], badge * 1.25 / max(2, len(icon)))
        icon_font = (theme.font("icon")[0], icon_size)
        _, icon_height = ui.measure_string(
            icon, font=icon_font, alignment=ui.ALIGN_CENTER
        )
        ui.draw_string(
            icon,
            rect=(badge_x, badge_y + (badge - icon_height) / 2, badge, icon_height),
            font=icon_font,
            color=theme.color("background"),
            alignment=ui.ALIGN_CENTER,
        )

        # Title and tagline sit centred; a status line shows only for games
        # that are not yet playable.
        show_status = self.game.status != "playable"
        block = 26 + 4 + 44 + (20 if show_status else 0)
        top = (height - block) / 2

        ui.draw_string(
            self.game.title,
            rect=(text_x, top, text_width, 26),
            font=theme.font("heading"),
            color=theme.color("text"),
        )
        ui.draw_string(
            self.game.tagline,
            rect=(text_x, top + 30, text_width, 44),
            font=theme.font("body"),
            color=theme.color("muted"),
        )

        if show_status:
            ui.draw_string(
                self.game.status.upper(),
                rect=(text_x, top + 76, text_width, 16),
                font=theme.font("caption"),
                color=theme.color(self.game.accent),
            )

    # --- touch ---------------------------------------------------------------

    def touch_began(self, touch):
        tactile.press(self)

    def touch_cancelled(self, touch):
        tactile.release(self)

    def touch_ended(self, touch):
        tactile.release(self)
        x, y = touch.location
        if 0 <= x <= self.width and 0 <= y <= self.height:
            self.on_open(self.game)


class HomeView(ui.View):
    """The game list with a header and a scrolling column of cards."""

    MARGIN = 16
    HEADER_HEIGHT = 8   # gap above the cards; the shared header is in the shell
    CARD_HEIGHT = 108
    CARD_GAP = 12

    def __init__(self, games, on_open, **kwargs):
        super().__init__(**kwargs)
        self.background_color = theme.color("background")

        # The app title lives in the shell's shared header above this view.

        self.scroll = ui.ScrollView()
        self.scroll.background_color = theme.color("background")
        self.scroll.shows_vertical_scroll_indicator = False
        self.add_subview(self.scroll)

        self.cards = []
        for game in games:
            card = GameCard(game, on_open)
            self.scroll.add_subview(card)
            self.cards.append(card)

        # Added last so it sits above the cards when shown.
        self.message_label = ui.Label()
        self.message_label.font = theme.font("body")
        self.message_label.text_color = theme.color("coral")
        self.message_label.number_of_lines = 2
        self.message_label.hidden = True
        self.add_subview(self.message_label)

    def layout(self):
        margin = self.MARGIN
        width, height = self.width, self.height
        inner = width - 2 * margin

        self.message_label.frame = (margin, height - 60, inner, 44)

        top = self.HEADER_HEIGHT
        self.scroll.frame = (0, top, width, max(0, height - top))

        y = 0
        for card in self.cards:
            card.frame = (margin, y, inner, self.CARD_HEIGHT)
            y += self.CARD_HEIGHT + self.CARD_GAP
        self.scroll.content_size = (width, y + margin)

    def show_message(self, text):
        """Show a short problem message at the bottom of the home screen."""
        self.message_label.text = text
        self.message_label.hidden = False