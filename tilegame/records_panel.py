"""
A records overlay any game can use: the best runs on one leaderboard,
chosen by rows of choices.

A game describes its leaderboards with rows of choice labels (for example
the mode, then Time or Moves) and functions of a selection, which is a
tuple holding the chosen index in each row:

    key_for(selection)      the RecordBook key for that leaderboard
    format_for(selection)   a function turning a stored value into text
    enabled_for(selection)  optional: for each row, a list of on/off flags,
                            or None to leave that row alone. A row whose
                            choice is switched off moves to its last
                            enabled choice. Rows are settled in order, so a
                            later row may depend on an earlier one (Sudoku
                            fades the levels a board size never reaches).

choose(row, choice) picks a choice as a tap would; smokes drive the panel
through it.

The panel reads the game's RecordBook (tilegame/records.py) and never
writes to it, so a game moving onto it keeps every old result. RecordBook
ranks lower values first, so a game stores what it wants smallest: seconds,
or moves over par. (RecordBook names every stored value "seconds" for its
older files; here it is just the value.) A higher-is-better score needs
RecordBook support first.

Used by Gradient (mode, then Time or Moves) and Sudoku (size, then level).

UI stability (see the pythonista-ui-stability guide): every label is made
once and only re-labelled when the choice changes.
"""

import time

import ui

from style import theme
from tilegame.records import TOP_LENGTH
from tilegame.widgets import ChoiceRow, make_button, make_label


BACKGROUND = theme.color("background")
TEXT = theme.color("text")
MUTED = theme.color("muted")


class RecordsPanel(ui.View):
    """Overlay listing the TOP_LENGTH best runs for the chosen leaderboard."""

    TOP = 16
    ROW_HEIGHT = 30
    EMPTY_TEXT = "No results here yet"

    def __init__(self, title, rows, key_for, format_for, book=None,
                 enabled_for=None, empty_text=EMPTY_TEXT,
                 back_title="Back to settings"):
        super().__init__()
        self.background_color = BACKGROUND
        self.hidden = True
        self.book = book                  # a RecordBook, or None for a preview
        self.key_for = key_for
        self.format_for = format_for
        self.enabled_for = enabled_for
        self.selection = [0] * len(rows)

        self.title_label = make_label(title, ("AvenirNext-Bold", 24), TEXT)
        self.choice_rows = [
            ChoiceRow(labels, self._row_changed(index)) for index, labels in enumerate(rows)
        ]
        self.empty_label = make_label(empty_text, ("AvenirNext-Medium", 15), MUTED)

        self.value_labels = []
        self.date_labels = []
        for _ in range(TOP_LENGTH):
            self.value_labels.append(make_label(
                "", ("AvenirNext-DemiBold", 17), TEXT, alignment=ui.ALIGN_LEFT))
            self.date_labels.append(make_label(
                "", ("AvenirNext-Medium", 15), MUTED, alignment=ui.ALIGN_RIGHT))

        self.back_button = make_button(back_title, self.back_tapped)

        for view in ([self.title_label] + self.choice_rows + [self.empty_label]
                     + self.value_labels + self.date_labels + [self.back_button]):
            self.add_subview(view)

    def _row_changed(self, index):
        def changed(sender):
            self.choose(index, sender.selected_index)
        return changed

    def layout(self):
        column = min(320, self.width - 48)
        left = (self.width - column) / 2

        y = self.TOP
        self.title_label.frame = (left, y, column, 36)
        y += 52
        for row in self.choice_rows:
            row.frame = (left, y, column, 40)
            y += 52
        y += 4
        self.empty_label.frame = (left, y, column, 24)
        for index, (value_label, date_label) in enumerate(
                zip(self.value_labels, self.date_labels)):
            row_y = y + index * self.ROW_HEIGHT
            value_label.frame = (left, row_y, column / 2, self.ROW_HEIGHT)
            date_label.frame = (left + column / 2, row_y, column / 2, self.ROW_HEIGHT)
        y += TOP_LENGTH * self.ROW_HEIGHT + 20
        self.back_button.frame = (left, y, column, 52)

    def open(self, selection):
        """Show the panel on this selection (one index per row)."""
        self.selection = list(selection)
        for row, index in zip(self.choice_rows, self.selection):
            row.selected_index = index
        self.show_board()
        self.hidden = False
        self.bring_to_front()

    def choose(self, row_index, choice_index):
        """Pick a choice in one row as a tap would, then show that board."""
        self.selection[row_index] = choice_index
        self.choice_rows[row_index].selected_index = choice_index
        self.show_board()

    def settle_rows(self):
        """Apply enabled_for: fade switched-off choices, moving off any that was chosen."""
        if self.enabled_for is None:
            return
        for index, row in enumerate(self.choice_rows):
            flags = self.enabled_for(tuple(self.selection))[index]
            if flags is None:
                continue
            row.set_enabled(flags)
            if not flags[self.selection[index]]:
                self.selection[index] = max(
                    choice for choice, enabled in enumerate(flags) if enabled)
            row.selected_index = self.selection[index]

    def show_board(self):
        """List the best runs for the current selection, best first."""
        self.settle_rows()
        selection = tuple(self.selection)
        runs = self.book.top(self.key_for(selection)) if self.book else []
        format_value = self.format_for(selection)
        self.empty_label.hidden = bool(runs)
        for index, (value_label, date_label) in enumerate(
                zip(self.value_labels, self.date_labels)):
            if index < len(runs):
                run = runs[index]
                value_label.text = "%d.   %s" % (index + 1, format_value(run["seconds"]))
                date_label.text = time.strftime("%d %b %Y", time.localtime(run["when"]))
            else:
                value_label.text = ""
                date_label.text = ""

    def back_tapped(self, sender):
        self.hidden = True
