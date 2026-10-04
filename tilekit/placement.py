"""
TileKit placement helpers.

Placement is renderer-neutral. It decides where new TileObjects should appear
on a Board without knowing about Pythonista views.

This is inspired by projects/tile_calc/placer.py, but rebuilt around TileKit's
Board/Object/CoordinateSystem model.
"""

import math


class PlacementResult:
    """Result from a placement operation."""

    def __init__(self, position=None, positions=None, fallback=False):
        self.position = position
        self.positions = list(positions or ([] if position is None else [position]))
        self.fallback = bool(fallback)

    def first(self):
        return self.position or (self.positions[0] if self.positions else None)


class GridPlacer:
    """Simple grid-aware placement helper for TileKit boards."""

    def __init__(self, coords=None):
        self.coords = coords

    def grid_size(self, board):
        coords = getattr(board, "coords", None) or self.coords
        return float(getattr(coords, "grid", 60) or 60)

    def object_cells(self, board, obj):
        """Return the occupied cell size for obj.

        A declared cell span is authoritative. Objects that have not declared
        one fall back to measuring pixel size against the grid, which is
        approximate and cannot distinguish a deliberately wide tile from a
        tile that merely renders wide.
        """
        declared = getattr(obj, "cell_span", None)
        if declared is not None:
            return (max(1, int(declared[0])), max(1, int(declared[1])))

        g = self.grid_size(board)
        size = getattr(obj, "size", None) or (g, g)
        try:
            w, h = size
        except Exception:
            w, h = g, g

        # Tile Calc's 64px tiles on a 60px grid are logically one cell.
        # round() keeps that behaviour while still allowing wider cards later.
        return (
            max(1, int(round(float(w) / g))),
            max(1, int(round(float(h) / g))),
        )

    def position_to_cell(self, board, position, obj=None):
        """Convert a centre to its first occupied cell when span is declared."""
        g = self.grid_size(board)
        ox, oy = getattr(board.coords, "origin", (0, 0))
        x, y = position or (0, 0)
        span = getattr(obj, "cell_span", None)
        if span is None:
            return (int(round((x - ox) / g)), int(round((y - oy) / g)))
        return (
            int(((x - ox) / g - (span[0] - 1) / 2 + 0.5) // 1),
            int(((y - oy) / g - (span[1] - 1) / 2 + 0.5) // 1),
        )

    def cell_to_position(self, board, cell, obj=None):
        """Convert a first occupied cell to an object's centre."""
        g = self.grid_size(board)
        ox, oy = getattr(board.coords, "origin", (0, 0))
        col, row = cell
        span = getattr(obj, "cell_span", None) or (1, 1)
        return (
            ox + (col + (span[0] - 1) / 2) * g,
            oy + (row + (span[1] - 1) / 2) * g,
        )

    def occupied_cells(self, board, exclude=None):
        """Return occupied grid cells for current board objects."""
        exclude_ids = set()
        if exclude is not None:
            if isinstance(exclude, (list, tuple, set)):
                exclude_ids = set(id(item) for item in exclude)
            else:
                exclude_ids = set([id(exclude)])

        occupied = set()
        for obj in getattr(board, "objects", []):
            if id(obj) in exclude_ids:
                continue
            if getattr(obj, "position", None) is None:
                continue

            col, row = self.position_to_cell(board, obj.position, obj)
            w, h = self.object_cells(board, obj)
            for dc in range(w):
                for dr in range(h):
                    occupied.add((col + dc, row + dr))

        return occupied

    def cells_for(self, board, obj, cell):
        w, h = self.object_cells(board, obj)
        col, row = cell
        return set(
            (col + dc, row + dr)
            for dc in range(w)
            for dr in range(h)
        )

    def is_clear(self, board, obj, cell, occupied=None, bounds=None):
        occupied = occupied if occupied is not None else self.occupied_cells(board)
        cells = self.cells_for(board, obj, cell)
        if cells & occupied:
            return False

        if bounds is not None:
            max_cols, max_rows = bounds
            for col, row in cells:
                if col < 0 or row < 0:
                    return False
                if max_cols is not None and col >= max_cols:
                    return False
                if max_rows is not None and row >= max_rows:
                    return False

        return True

    def find_free_cell(self, board, obj, origin_cell=(0, 0), occupied=None, bounds=None):
        """Find a nearby free cell, spiralling out from origin_cell."""
        occupied = occupied if occupied is not None else self.occupied_cells(board)
        ox, oy = origin_cell

        if self.is_clear(board, obj, origin_cell, occupied=occupied, bounds=bounds):
            return origin_cell

        # Square spiral. Small and deterministic; good enough for early TileKit.
        for radius in range(1, 24):
            candidates = []

            for dx in range(-radius, radius + 1):
                candidates.append((ox + dx, oy - radius))
                candidates.append((ox + dx, oy + radius))

            for dy in range(-radius + 1, radius):
                candidates.append((ox - radius, oy + dy))
                candidates.append((ox + radius, oy + dy))

            for cell in candidates:
                if self.is_clear(board, obj, cell, occupied=occupied, bounds=bounds):
                    return cell

        return origin_cell

    def find_free_position(self, board, obj, origin=None, exclude=None, bounds=None):
        """Return a free logical position near origin."""
        occupied = self.occupied_cells(board, exclude=exclude)
        origin = origin if origin is not None else getattr(obj, "position", None)
        origin = origin if origin is not None else (0, 0)
        origin_cell = self.position_to_cell(board, origin, obj)
        cell = self.find_free_cell(board, obj, origin_cell, occupied=occupied, bounds=bounds)
        return self.cell_to_position(board, cell, obj)

    def find_adjacent(self, board, anchor, obj=None, direction="right", bounds=None):
        """Place beside an anchor using both objects' occupied spans."""
        if anchor is None:
            return self.find_free_position(board, obj, bounds=bounds)
        col, row = self.position_to_cell(board, anchor.position, anchor)
        aw, ah = self.object_cells(board, anchor)
        w, h = self.object_cells(board, obj)
        offsets = {
            "right": (aw, 0),
            "left": (-w, 0),
            "above": (0, -h),
            "below": (0, ah),
        }
        dx, dy = offsets.get(direction, offsets["right"])
        found = self.find_free_cell(
            board, obj, (col + dx, row + dy),
            occupied=self.occupied_cells(board), bounds=bounds,
        )
        return self.cell_to_position(board, found, obj)

    def place_sequence(self, board, objects, origin=None, exclude=None, bounds=None):
        """Return positions for a sequence of objects, filling right then around."""
        positions = []
        occupied = self.occupied_cells(board, exclude=exclude)
        origin = origin if origin is not None else (0, 0)
        cell = self.position_to_cell(board, origin)

        for obj in objects or []:
            found = self.find_free_cell(board, obj, cell, occupied=occupied, bounds=bounds)
            positions.append(self.cell_to_position(board, found, obj))
            occupied |= self.cells_for(board, obj, found)
            cell = (found[0] + self.object_cells(board, obj)[0], found[1])

        return positions