"""
One player's hand in Pick & Mix: up to SLOTS tiles they picked and merged.
No UIKit.

Picks fill the first empty slot and are never undone: a pick can block the
other player, so it is final. A merge combines two tiles: the source is the
left operand, the result lands in the destination's slot and the source
slot empties. Results must be positive whole numbers, as in Countdown.

Undo reverses merges one at a time, newest first, and is unaffected by
picks made in between: the unmerged source tile goes back to its old slot,
or to the first free slot if a pick has filled it since.
"""

from tilegame.board_state import evaluate, positive_whole_numbers


class Tile:
    """A tile in a hand. The id lets undo tell tiles with equal values apart."""

    __slots__ = ("tile_id", "value")

    def __init__(self, tile_id, value):
        self.tile_id = tile_id
        self.value = value


class Hand:
    """Slots of tiles for one player, with merge-only undo."""

    SLOTS = 4

    def __init__(self):
        self.slots = [None] * self.SLOTS
        self.picked = []       # values picked this round, in order
        self._next_id = 0
        self._history = []     # (source, source tile, destination, destination tile)

    # --- reading -------------------------------------------------------------

    def values(self):
        """Value per slot, None for an empty slot."""
        return [None if tile is None else tile.value for tile in self.slots]

    def tile_values(self):
        return [tile.value for tile in self.slots if tile is not None]

    def free_slot(self):
        for index, tile in enumerate(self.slots):
            if tile is None:
                return index
        return None

    def closest_to(self, target):
        """The tile value nearest target (smaller wins a tie), or None if empty."""
        values = self.tile_values()
        if not values:
            return None
        return min(values, key=lambda value: (abs(value - target), value))

    # --- picking -------------------------------------------------------------

    def add_tile(self, value):
        """Put a picked value in the first free slot and return that slot."""
        slot = self.free_slot()
        if slot is None:
            raise ValueError("This hand is full")
        self.slots[slot] = self._new_tile(value)
        self.picked.append(value)
        return slot

    # --- merging -------------------------------------------------------------

    def result_of(self, source, destination, operation):
        """The value source <operation> destination would make, or None."""
        if source == destination:
            return None
        if not (0 <= source < self.SLOTS and 0 <= destination < self.SLOTS):
            return None
        left_tile = self.slots[source]
        right_tile = self.slots[destination]
        if left_tile is None or right_tile is None:
            return None
        value = evaluate(left_tile.value, operation, right_tile.value)
        if value is None or not positive_whole_numbers(
            left_tile.value, operation, right_tile.value, value
        ):
            return None
        return int(value)

    def merge(self, source, destination, operation):
        """Merge source into destination as one undo step. Returns the value or None."""
        value = self.result_of(source, destination, operation)
        if value is None:
            return None
        self._history.append(
            (source, self.slots[source], destination, self.slots[destination])
        )
        self.slots[destination] = self._new_tile(value)
        self.slots[source] = None
        return value

    def can_undo(self):
        return bool(self._history)

    def undo(self):
        """Reverse the newest merge. Returns False if there is none."""
        if not self._history:
            return False
        source, source_tile, destination, destination_tile = self._history.pop()
        # Merges undo newest first and picks only fill empty slots, so the
        # merge's result is still in the destination slot.
        self.slots[destination] = destination_tile
        if self.slots[source] is None:
            self.slots[source] = source_tile
        else:
            self.slots[self.free_slot()] = source_tile
        return True

    # --- internal ------------------------------------------------------------

    def _new_tile(self, value):
        self._next_id += 1
        return Tile(self._next_id, value)