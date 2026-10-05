"""Shared widgets for tile games: labels, buttons, choice rows, target banner.

All colours come from style/theme.py. Plain views and buttons only, in line
with the UI stability rules: no timers, no layer tricks.
"""

import ui

from style import theme


BACKGROUND = theme.color("background")
TEXT = theme.color("text")
MUTED = theme.color("muted")
BUTTON_COLOR = theme.color("button")
ACCENT = theme.color("tile")       # the main action and the target chip
SUCCESS = theme.color("success")   # a solved target


def make_label(text, font, color, alignment=ui.ALIGN_CENTER):
    label = ui.Label()
    label.text = text
    label.font = font
    label.text_color = color
    label.alignment = alignment
    return label


def make_button(title, action, background=BUTTON_COLOR, title_color=TEXT,
                font_size=17):
    button = ui.Button(title=title)
    button.action = action
    button.background_color = background
    button.tint_color = title_color
    button.font = ("AvenirNext-DemiBold", font_size)
    button.corner_radius = 12
    return button


def draw_centred_text(text, font, color, x, y, width, height):
    """Draw one line of text centred inside a rectangle (inside draw())."""
    _, text_height = ui.measure_string(
        text, font=font, alignment=ui.ALIGN_CENTER
    )
    ui.draw_string(
        text,
        rect=(x, y + (height - text_height) / 2, width, text_height),
        font=font,
        color=color,
        alignment=ui.ALIGN_CENTER,
    )


class ChoiceRow(ui.View):
    """A row of buttons where exactly one is chosen.

    Used instead of ui.SegmentedControl, whose unselected labels render dark
    on the dark theme. Interface: selected_index, and action(sender) called
    when the choice changes.
    """

    GAP = 6

    def __init__(self, labels, action, selected_colors=None):
        super().__init__()
        self.action = action
        # One colour per button for the chosen state, or None for ACCENT.
        self.selected_colors = selected_colors
        self._selected_index = 0
        self.buttons = []

        for label in labels:
            button = make_button(label, self._button_tapped, font_size=15)
            button.corner_radius = 9
            self.buttons.append(button)
            self.add_subview(button)

        self._show_selection()

    def set_labels(self, labels):
        """Retitle the buttons in place, e.g. to show scores."""
        for button, label in zip(self.buttons, labels):
            if button.title != label:
                button.title = label

    def set_enabled(self, flags):
        """Enable or disable buttons in place; disabled ones fade and ignore taps."""
        for button, enabled in zip(self.buttons, flags):
            button.enabled = bool(enabled)
            button.alpha = 1.0 if enabled else 0.35

    @property
    def selected_index(self):
        return self._selected_index

    @selected_index.setter
    def selected_index(self, index):
        self._selected_index = index
        self._show_selection()

    def layout(self):
        count = len(self.buttons)
        width = (self.width - self.GAP * (count - 1)) / count

        for index, button in enumerate(self.buttons):
            button.frame = (index * (width + self.GAP), 0, width, self.height)

    def _show_selection(self):
        for index, button in enumerate(self.buttons):
            chosen = index == self._selected_index
            if self.selected_colors:
                chosen_color = self.selected_colors[index]
            else:
                chosen_color = ACCENT
            button.background_color = chosen_color if chosen else BUTTON_COLOR
            button.tint_color = BACKGROUND if chosen else TEXT

    def _button_tapped(self, sender):
        index = self.buttons.index(sender)

        if index == self._selected_index:
            return

        self.selected_index = index

        if self.action is not None:
            self.action(self)


class ChoiceGrid(ChoiceRow):
    """Like ChoiceRow, but the buttons wrap into rows of `columns`.

    Same interface: selected_index, action(sender), set_labels and
    set_enabled. Use it when there are too many choices for one row.
    """

    def __init__(self, labels, action, columns=3, selected_colors=None):
        super().__init__(labels, action, selected_colors)
        self.columns = columns

    def row_count(self):
        return max(1, -(-len(self.buttons) // self.columns))

    def preferred_height(self, row_height=44):
        """Height for every row at row_height points, gaps included."""
        rows = self.row_count()
        return rows * row_height + (rows - 1) * self.GAP

    def layout(self):
        rows = self.row_count()
        width = (self.width - self.GAP * (self.columns - 1)) / self.columns
        height = (self.height - self.GAP * (rows - 1)) / rows

        for index, button in enumerate(self.buttons):
            row, col = divmod(index, self.columns)
            button.frame = (
                col * (width + self.GAP), row * (height + self.GAP), width, height
            )


class ToggleRow(ui.View):
    """A row of buttons where any number can be on.

    Interface: selected_indices (a set), action(sender) called after each
    change, and an optional allow(new_indices) that may refuse a change,
    for example to keep at least one option on.
    """

    GAP = 6

    def __init__(self, labels, action, allow=None):
        super().__init__()
        self.action = action
        self.allow = allow
        self._selected = set()
        self.buttons = []

        for label in labels:
            button = make_button(label, self._button_tapped, font_size=17)
            button.corner_radius = 9
            self.buttons.append(button)
            self.add_subview(button)

        self._show_selection()

    @property
    def selected_indices(self):
        return set(self._selected)

    @selected_indices.setter
    def selected_indices(self, indices):
        self._selected = set(indices)
        self._show_selection()

    def layout(self):
        count = len(self.buttons)
        width = (self.width - self.GAP * (count - 1)) / count

        for index, button in enumerate(self.buttons):
            button.frame = (index * (width + self.GAP), 0, width, self.height)

    def _show_selection(self):
        for index, button in enumerate(self.buttons):
            on = index in self._selected
            button.background_color = ACCENT if on else BUTTON_COLOR
            button.tint_color = BACKGROUND if on else TEXT

    def _button_tapped(self, sender):
        index = self.buttons.index(sender)
        new_indices = self._selected ^ {index}

        if self.allow is not None and not self.allow(set(new_indices)):
            return

        self.selected_indices = new_indices

        if self.action is not None:
            self.action(self)


class TargetBanner(ui.View):
    """A big target chip with two stats either side (score and streak, or
    board and time).

    A tap on the chip calls on_target_tapped(target), set by the screen.
    """

    CHIP_RADIUS = 16

    def __init__(self):
        super().__init__()
        self.background_color = BACKGROUND
        self.target = None
        self.score = 0
        self.streak = 0
        self.left = ("SCORE", 0)     # (caption, value) drawn left of the chip
        self.right = ("STREAK", 0)   # and right of it
        self.solved = False
        self.on_target_tapped = None

    def show(self, target, score, streak, solved):
        """Target with score and streak either side."""
        self.score = score
        self.streak = streak
        self.show_stats(target, ("SCORE", score), ("STREAK", streak), solved)

    def show_stats(self, target, left, right, solved):
        """Target with any two (caption, value) stats either side."""
        self.target = target
        self.left = left
        self.right = right
        self.solved = solved
        self.set_needs_display()

    def layout(self):
        self.set_needs_display()

    def chip_frame(self):
        width = min(170, self.width * 0.44)
        return ((self.width - width) / 2, 0, width, self.height)

    def _draw_stat(self, caption, value, x, width):
        text = str(value)
        size = max(16, min(30, width * 1.6 / max(1, len(text))))
        draw_centred_text(caption, ("AvenirNext-DemiBold", 12), MUTED,
                          x, 14, width, 18)
        draw_centred_text(text, ("AvenirNext-Bold", size), TEXT,
                          x, 34, width, self.height - 44)

    def draw(self):
        if self.target is None or self.width <= 1:
            return

        x, y, w, h = self.chip_frame()

        ui.set_color(SUCCESS if self.solved else ACCENT)
        ui.Path.rounded_rect(x, y, w, h, self.CHIP_RADIUS).fill()

        draw_centred_text("MAKE", ("AvenirNext-DemiBold", 12), BACKGROUND,
                          x, y + 8, w, 16)

        digits = max(2, len(str(self.target)))
        size = max(20, min(52, h * 0.55, w * 1.3 / digits))
        draw_centred_text(str(self.target), ("AvenirNext-Bold", size),
                          BACKGROUND, x, y + 20, w, h - 24)

        self._draw_stat(self.left[0], self.left[1], 0, x)
        self._draw_stat(self.right[0], self.right[1], x + w,
                        self.width - (x + w))

    def touch_ended(self, touch):
        if self.target is None or self.on_target_tapped is None:
            return

        px, py = touch.location
        x, y, w, h = self.chip_frame()

        if x <= px <= x + w and y <= py <= y + h:
            self.on_target_tapped(self.target)