"""
A fill-in grid: the shared model for games where the player writes values
into fixed cells. KenKen and Sudoku use it. No UIKit.

The grid knows which values may be written, which cells are fixed givens,
and which groups of cells ("units") must not repeat a value. Rows and
columns are the default units; Sudoku adds its boxes. Two cells are peers
when they share a unit.

Empty cells may carry notes (pencil marks): a set of values the player
thinks are possible. Writing a value clears that cell's notes and can
optionally clear the value from its peers' notes.

Every player action is one undo step, even when it changes several cells
(a value plus the peer notes it cleaned). Cells are (row, col) tuples and
empty cells hold None.
"""


def rows_and_columns(size):
    """The default units: every row and every column."""
    rows = [tuple((row, col) for col in range(size)) for row in range(size)]
    cols = [tuple((row, col) for row in range(size)) for col in range(size)]
    return tuple(rows + cols)


class FillGrid:
    """The source of truth for values and notes written into a square grid."""

    def __init__(self, size, allowed_values=None, givens=None, units=None):
        self.size = size
        if allowed_values is None:
            allowed_values = range(1, size + 1)
        self.allowed_values = tuple(allowed_values)
        self.givens = dict(givens or {})
        self.units = tuple(units) if units is not None else rows_and_columns(size)

        self._units_by_cell = {}
        self._peers = {}
        for unit in self.units:
            for cell in unit:
                self._units_by_cell.setdefault(cell, []).append(unit)
                self._peers.setdefault(cell, set()).update(
                    other for other in unit if other != cell
                )

        self._values = [[None] * size for _ in range(size)]
        for (row, col), value in self.givens.items():
            self._values[row][col] = value
        self._notes = {}       # cell -> frozenset of noted values
        self._history = []     # each step: list of (cell, old value, old notes)

    # --- reading -------------------------------------------------------------

    def in_bounds(self, cell):
        row, col = cell
        return 0 <= row < self.size and 0 <= col < self.size

    def value_at(self, cell):
        row, col = cell
        return self._values[row][col]

    def notes_at(self, cell):
        return self._notes.get(cell, frozenset())

    def is_given(self, cell):
        return cell in self.givens

    def peers_of(self, cell):
        return set(self._peers.get(cell, ()))

    def rows(self):
        """A copy of the grid's values as a list of row lists."""
        return [list(row) for row in self._values]

    def is_full(self):
        return all(value is not None for row in self._values for value in row)

    def empty_cells(self):
        return [
            (row, col)
            for row in range(self.size)
            for col in range(self.size)
            if self._values[row][col] is None
        ]

    def conflicts(self):
        """Cells whose value repeats somewhere in one of their units."""
        clashing = set()
        for unit in self.units:
            cells_by_value = {}
            for cell in unit:
                value = self.value_at(cell)
                if value is not None:
                    cells_by_value.setdefault(value, []).append(cell)
            for cells in cells_by_value.values():
                if len(cells) > 1:
                    clashing.update(cells)
        return clashing

    def values_seen_from(self, cell):
        """Values already in this cell's peers. A picker can dim these."""
        seen = set()
        for peer in self._peers.get(cell, ()):
            value = self.value_at(peer)
            if value is not None:
                seen.add(value)
        return seen

    # --- writing values ------------------------------------------------------

    def can_set(self, cell, value):
        """True when value (or None, to clear) may be written into cell."""
        if not self.in_bounds(cell) or self.is_given(cell):
            return False
        return value is None or value in self.allowed_values

    def set_value(self, cell, value, clean_peer_notes=False):
        """Write value into cell (None clears it) as one undo step.

        The cell's notes are cleared. With clean_peer_notes, value is also
        removed from the notes of every peer, in the same undo step.
        Returns True when the grid changed; refused or unchanged writes
        return False and add no history.
        """
        if not self.can_set(cell, value):
            return False
        old_value = self.value_at(cell)
        if old_value == value:
            return False

        changes = [(cell, old_value, self.notes_at(cell))]
        self._write(cell, value, frozenset())

        if clean_peer_notes and value is not None:
            for peer in sorted(self._peers.get(cell, ())):
                notes = self.notes_at(peer)
                if value in notes:
                    changes.append((peer, self.value_at(peer), notes))
                    self._write(peer, self.value_at(peer), notes - {value})

        self._history.append(changes)
        return True

    def clear(self, cell):
        """Empty the cell's value, or its notes if it has no value. One undo step."""
        if self.value_at(cell) is not None:
            return self.set_value(cell, None)
        if not self.in_bounds(cell) or self.is_given(cell):
            return False
        notes = self.notes_at(cell)
        if not notes:
            return False
        self._history.append([(cell, None, notes)])
        self._write(cell, None, frozenset())
        return True

    # --- writing notes -------------------------------------------------------

    def toggle_note(self, cell, value):
        """Add or remove one note in an empty cell, as one undo step.

        Refused (False) for givens, filled cells and values not allowed.
        """
        if not self.in_bounds(cell) or self.is_given(cell):
            return False
        if self.value_at(cell) is not None or value not in self.allowed_values:
            return False
        notes = self.notes_at(cell)
        new_notes = notes - {value} if value in notes else notes | {value}
        self._history.append([(cell, None, notes)])
        self._write(cell, None, new_notes)
        return True

    # --- history -------------------------------------------------------------

    def can_undo(self):
        return bool(self._history)

    def undo(self):
        """Undo the last step. Returns the cell the player acted on, or None."""
        if not self._history:
            return None
        changes = self._history.pop()
        for cell, value, notes in reversed(changes):
            self._write(cell, value, notes)
        return changes[0][0]

    def reset(self):
        """Empty every non-given cell, drop all notes and forget history."""
        for row in range(self.size):
            for col in range(self.size):
                if (row, col) not in self.givens:
                    self._values[row][col] = None
        self._notes = {}
        self._history = []

    # --- internal ------------------------------------------------------------

    def _write(self, cell, value, notes):
        row, col = cell
        self._values[row][col] = value
        if notes:
            self._notes[cell] = frozenset(notes)
        else:
            self._notes.pop(cell, None)