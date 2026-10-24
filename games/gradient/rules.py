"""
Gradient rules: the board a player rearranges, with no UI.

Cells are numbered row by row: cell = row * cols + col. Tile t is the tile
whose solved home is cell t, so the board is solved when every cell holds
its own number. Anchored cells hold their own tile from the start and never
move. Any two free tiles may swap; each swap is one move.

Pure Python, no UI: safe in Pythonista, PythonIDE and Forge RUN.
"""

from games.gradient import levels


def minimum_swaps(arrangement):
    """The fewest swaps that solve an arrangement (cell -> tile).

    Follow each tile to the cell it belongs in: the misplaced tiles fall
    into cycles, and a cycle of k tiles needs k - 1 swaps. So the answer is
    (misplaced tiles) - (cycles among them). This is a level's par.
    """
    seen = set()
    swaps = 0
    for start in range(len(arrangement)):
        if start in seen or arrangement[start] == start:
            continue
        length = 0
        cell = start
        while cell not in seen:
            seen.add(cell)
            cell = arrangement[cell]
            length += 1
        swaps += length - 1
    return swaps


class GradientBoard:
    """A level being played: the current arrangement and the moves made."""

    def __init__(self, level, arrangement=None, moves=0):
        self.level = level
        self.arrangement = list(level.start if arrangement is None else arrangement)
        self.moves = moves
        self.par = minimum_swaps(level.start)

    # --- reading the board ---------------------------------------------------

    @property
    def cols(self):
        return self.level.cols

    @property
    def rows(self):
        return self.level.rows

    def cell_at(self, col, row):
        return row * self.level.cols + col

    def tile_in(self, cell):
        return self.arrangement[cell]

    def colour_in(self, cell):
        """The sRGB colour currently showing in a cell."""
        return self.level.colours[self.arrangement[cell]]

    def is_anchor(self, cell):
        return cell in self.level.anchors

    def is_home(self, cell):
        return self.arrangement[cell] == cell

    def is_solved(self):
        return all(tile == cell for cell, tile in enumerate(self.arrangement))

    def swaps_left(self):
        """The fewest swaps that would still solve the board."""
        return minimum_swaps(self.arrangement)

    # --- moves -------------------------------------------------------------------

    def can_swap(self, first, second):
        cell_count = len(self.arrangement)
        return (
            first != second
            and 0 <= first < cell_count
            and 0 <= second < cell_count
            and not self.is_anchor(first)
            and not self.is_anchor(second)
        )

    def swap(self, first, second):
        """Swap two free tiles and count a move. Returns False (and changes nothing) if not allowed."""
        if not self.can_swap(first, second):
            return False
        self.arrangement[first], self.arrangement[second] = (
            self.arrangement[second], self.arrangement[first])
        self.moves += 1
        return True

    def hint(self):
        """A swap that sends one tile home, as (cell, home); None when solved.

        The tile in cell belongs in home. Following hints alone solves the
        board in exactly par moves.
        """
        for cell, tile in enumerate(self.arrangement):
            if tile != cell:
                return (cell, tile)
        return None

    # --- saving --------------------------------------------------------------

    def to_dict(self):
        return {
            "seed": self.level.seed,
            "difficulty": self.level.difficulty,
            "arrangement": list(self.arrangement),
            "moves": self.moves,
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a saved board; the level is regenerated from its seed.

        Returns None if the save is damaged or no longer fits its level
        (for example after a generator change), so the caller deals afresh.
        """
        try:
            level = levels.generate_level(data["seed"], data["difficulty"])
            arrangement = [int(tile) for tile in data["arrangement"]]
            moves = int(data.get("moves", 0))
        except (KeyError, TypeError, ValueError):
            return None
        if sorted(arrangement) != list(range(len(level.start))):
            return None
        if any(arrangement[cell] != cell for cell in level.anchors):
            return None
        return cls(level, arrangement, moves)
