"""
The shared header: a round left button, title, subtitle and optional gear.

The shell owns one header for the whole app. On the home screen the left
button is a close cross that closes the app; inside a game it is a back
chevron that returns to the home screen. The gear shows only for games
whose view supports settings (see gamecore/game.py).
"""

import ui

from style import theme


def make_icon_button(image_name, fallback_title, action):
    """Round button showing a built-in icon, or text if the icon is missing."""
    button = ui.Button()
    image = ui.Image.named(image_name)

    if image is not None:
        button.image = image
    else:
        button.title = fallback_title
        button.font = theme.font("heading")

    button.action = action
    button.background_color = theme.color("button")
    button.tint_color = theme.color("text")
    button.corner_radius = theme.LAYOUT["icon_button"] / 2
    return button


class HeaderBar(ui.View):
    """Left button, centred title with a subtitle line, optional gear."""

    MARGIN = 16

    def __init__(self, on_left, on_settings):
        super().__init__()
        self.background_color = theme.color("background")

        self.close_button = make_icon_button(
            "iob:close_round_24", "✕", on_left
        )
        self.back_button = make_icon_button(
            "iob:chevron_left_24", "‹", on_left
        )
        self.settings_button = make_icon_button(
            "iob:gear_a_24", "⚙", on_settings
        )

        self.title_label = ui.Label()
        self.title_label.font = theme.font("header")
        self.title_label.text_color = theme.color("text")
        self.title_label.alignment = ui.ALIGN_CENTER

        self.subtitle_label = ui.Label()
        self.subtitle_label.font = theme.font("caption")
        self.subtitle_label.text_color = theme.color("muted")
        self.subtitle_label.alignment = ui.ALIGN_CENTER

        for view in (
            self.close_button,
            self.back_button,
            self.settings_button,
            self.title_label,
            self.subtitle_label,
        ):
            self.add_subview(view)

    def show(self, title, subtitle, back, settings):
        """Set the whole header: back chevron or close cross, gear or not."""
        self.title_label.text = title.upper()
        self.subtitle_label.text = subtitle or ""
        self.close_button.hidden = back
        self.back_button.hidden = not back
        self.settings_button.hidden = not settings

    def set_subtitle(self, text):
        self.subtitle_label.text = text or ""

    def layout(self):
        width = self.width
        middle = self.height / 2
        margin = self.MARGIN
        icon = theme.LAYOUT["icon_button"]

        left = (margin, middle - icon / 2, icon, icon)
        self.close_button.frame = left
        self.back_button.frame = left
        self.settings_button.frame = (
            width - margin - icon, middle - icon / 2, icon, icon
        )

        title_left = margin + icon + 8
        title_width = max(0, width - 2 * title_left)
        self.title_label.frame = (title_left, 0, title_width, 26)
        self.subtitle_label.frame = (title_left, 24, title_width, 18)