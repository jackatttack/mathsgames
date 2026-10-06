"""
The how-to-play overlay: a rounded card with one game's rules, shown over
the whole app when the header's ? is tapped.

Built once by the shell and only shown, hidden or refilled (see the
Pythonista UI stability guide): no animations and no timers. The rules
scroll in a native ScrollView whose content is a single view that draws
every block in draw(), so a new card is one set_needs_display().
Got it, or a tap outside the card, closes it.
"""

import ui

from gamecore.how_to_play import BULLET, HEADING
from style import theme

# --- editable look ------------------------------------------------------------

BACKDROP = (0, 0, 0, 0.6)           # dims the app behind the card
CARD_COLOR = theme.color("surface")
TEXT_COLOR = theme.color("text")
BODY_FONT = theme.font("body")
HEADING_FONT = ("AvenirNext-Bold", 17)
TITLE_FONT = theme.font("heading")


class RulesView(ui.View):
    """Draws a card's blocks top to bottom at its own width."""

    PADDING = 20          # left and right
    GAP = 8               # between blocks
    HEADING_SPACE = 10    # extra space above a heading that follows text
    BULLET_INDENT = 18

    def __init__(self):
        super().__init__()
        self.blocks = ()
        self.accent = TEXT_COLOR

    def placed_blocks(self, width):
        """[(kind, text, font, color, x, y, w, h)] and the total height."""
        inner = max(1, width - 2 * self.PADDING)
        placed = []
        y = 0

        for index, (kind, text) in enumerate(self.blocks):
            x, text_width = self.PADDING, inner
            font, color = BODY_FONT, TEXT_COLOR
            if kind == HEADING:
                font, color = HEADING_FONT, self.accent
                if index > 0:
                    y += self.HEADING_SPACE
            elif kind == BULLET:
                x += self.BULLET_INDENT
                text_width -= self.BULLET_INDENT

            height = ui.measure_string(text, max_width=text_width, font=font)[1]
            placed.append((kind, text, font, color, x, y, text_width, height))
            y += height + self.GAP

        return placed, y

    def content_height(self, width):
        return self.placed_blocks(width)[1]

    def draw(self):
        for kind, text, font, color, x, y, width, height in self.placed_blocks(self.width)[0]:
            if kind == BULLET:
                ui.set_color(self.accent)
                ui.Path.oval(x - 13, y + font[1] * 0.7 - 3, 6, 6).fill()
            ui.draw_string(text, rect=(x, y, width, height), font=font, color=color)


class HelpCardOverlay(ui.View):
    """Full-screen backdrop holding the rules card. Hidden until shown."""

    MAX_WIDTH = 420
    MARGIN = 20
    TITLE_HEIGHT = 60
    BUTTON_HEIGHT = 48
    INNER = 16

    def __init__(self):
        super().__init__()
        self.background_color = BACKDROP
        self.hidden = True

        self.card_view = ui.View()
        self.card_view.background_color = CARD_COLOR
        self.card_view.corner_radius = theme.RADII["card"]

        self.title_label = ui.Label()
        self.title_label.font = TITLE_FONT
        self.title_label.text_color = TEXT_COLOR

        self.scroll = ui.ScrollView()
        self.scroll.shows_vertical_scroll_indicator = True
        self.rules = RulesView()
        self.scroll.add_subview(self.rules)

        self.done_button = ui.Button(title="Got it")
        self.done_button.action = self.close_tapped
        self.done_button.font = ("AvenirNext-DemiBold", 17)
        self.done_button.tint_color = theme.color("background")
        self.done_button.corner_radius = 14

        for view in (self.title_label, self.scroll, self.done_button):
            self.card_view.add_subview(view)
        self.add_subview(self.card_view)

    def show_card(self, card, accent):
        """Fill the card with this game's rules and show it, scrolled to the top."""
        self.title_label.text = "How to play %s" % card.title
        self.rules.blocks = card.blocks
        self.rules.accent = accent
        self.done_button.background_color = accent
        self.hidden = False
        self.bring_to_front()
        self.layout()
        self.scroll.content_offset = (0, 0)
        self.rules.set_needs_display()

    def close_tapped(self, sender=None):
        self.hidden = True

    def touch_ended(self, touch):
        """A tap on the backdrop, outside the card, closes it."""
        x, y = touch.location
        left, top, width, height = self.card_view.frame
        if not (left <= x <= left + width and top <= y <= top + height):
            self.close_tapped()

    def layout(self):
        width = max(1, min(self.MAX_WIDTH, self.width - 2 * self.MARGIN))
        top = theme.LAYOUT["safe_top"] + 10
        available = max(1, self.height - top - 34)

        rules_height = self.rules.content_height(width)
        chrome = self.TITLE_HEIGHT + self.BUTTON_HEIGHT + 2 * self.INNER
        card_height = min(available, chrome + rules_height)

        x = (self.width - width) / 2
        y = top + (available - card_height) / 2
        self.card_view.frame = (x, y, width, card_height)

        self.title_label.frame = (20, 14, width - 40, 34)
        scroll_height = max(1, card_height - chrome)
        self.scroll.frame = (0, self.TITLE_HEIGHT, width, scroll_height)
        self.rules.frame = (0, 0, width, rules_height)
        self.scroll.content_size = (width, rules_height)
        self.done_button.frame = (
            20, card_height - self.BUTTON_HEIGHT - self.INNER,
            width - 40, self.BUTTON_HEIGHT,
        )