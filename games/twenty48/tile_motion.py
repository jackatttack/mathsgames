"""
Tile identity for animating Double Up: which tile view shows which tile, and
what one swipe asks of each view.

rules.Game knows values, not tiles. To slide a tile, the screen needs the
same view to travel from the old cell to the new one. TileMotion keeps a
map from cells to view numbers (0 to pool_size - 1) and turns each
MoveResult into a MotionPlan. No UIKit lives here;
smokes/twenty48_motion_smoke.py checks the bookkeeping.

A merge partner is retired: it slides into the merge cell and fades out,
and its view goes to the back of the free list, so it is the last to be
reused while it may still be fading.
"""


class MotionPlan:
    """What one swipe asks of the tile views."""

    def __init__(self):
        self.moves = []      # (view, from_cell, to_cell, value) for views that stay
        self.retired = []    # (view, from_cell, to_cell) for merge partners that fade
        self.spawn = None    # (view, cell, value) for the new tile, or None


class TileMotion:
    """Maps cells to tile views and plans each swipe."""

    def __init__(self, pool_size):
        self.pool_size = pool_size
        self.at = {}                          # cell -> view number
        self.free = list(range(pool_size))    # views showing no tile

    def reset(self, cells):
        """Start over: give every tile on cells a view. Returns [(view, cell, value)]."""
        self.at = {}
        self.free = list(range(self.pool_size))
        placed = []
        for row, values in enumerate(cells):
            for col, value in enumerate(values):
                if value is not None:
                    view = self._take()
                    self.at[(row, col)] = view
                    placed.append((view, (row, col), value))
        return placed

    def plan(self, result, cells):
        """The MotionPlan for one MoveResult. cells is the board after it."""
        plan = MotionPlan()
        new_at = {}
        for source, target in result.slides:
            view = self.at[source]
            if target in new_at:
                plan.retired.append((view, source, target))
            else:
                new_at[target] = view
                plan.moves.append((view, source, target, cells[target[0]][target[1]]))
        self.at = new_at

        if result.spawned is not None:
            cell, value = result.spawned
            view = self._take()
            self.at[cell] = view
            plan.spawn = (view, cell, value)

        self.free.extend(view for view, _, _ in plan.retired)
        return plan

    def matches(self, cells):
        """True when exactly the tiles on cells have views, each its own."""
        tiles = {
            (row, col)
            for row, values in enumerate(cells)
            for col, value in enumerate(values)
            if value is not None
        }
        views = list(self.at.values())
        return (set(self.at) == tiles and len(set(views)) == len(views)
                and not set(views) & set(self.free))

    def _take(self):
        if not self.free:
            raise RuntimeError("the tile view pool is empty")
        return self.free.pop(0)