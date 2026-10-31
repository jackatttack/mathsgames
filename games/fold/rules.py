"""
Fold rules: a board of coloured triangles, flood moves, regions and undo.

Pure Python, smoke-tested headless by smokes/fold_smoke.py. Colours are
small whole numbers (0, 1, 2, ...): which paint each number shows is the
level's palette, chosen by the screen, never by the rules.

A region is a connected group of cells sharing a colour. A move picks a
cell and a new colour: that cell's whole region takes the colour, and so
joins every touching region already that colour. The board is solved when
every cell is one colour.

The board only needs a grid with cells() and neighbours(cell), so the same
rules would play on squares or hexagons.
"""


class Move:
    """One flood, kept for undo and for the fold animation.

    cells lists the recoloured cells nearest first; steps gives each one's
    distance in triangles from the tapped cell, and parents the neighbour
    the flood reached it from (None for the tapped cell), so a view can
    ripple the fold outwards and hinge each triangle on its parent's edge.
    """

    def __init__(self, cell, old_colour, new_colour, cells, steps, parents=None):
        self.cell = cell
        self.old_colour = old_colour
        self.new_colour = new_colour
        self.cells = cells
        self.steps = steps
        self.parents = parents if parents is not None else [None] * len(cells)


class FoldBoard:
    """A playable board: colours, moves made and undo."""

    def __init__(self, grid, colours):
        """colours maps every cell of grid to its colour number."""
        missing = [cell for cell in grid.cells() if cell not in colours]
        if missing:
            raise ValueError("no colour for {} cell(s), first {}".format(len(missing), missing[0]))
        self.grid = grid
        self.colours = {cell: colours[cell] for cell in grid.cells()}
        self.history = []

    @property
    def moves_made(self):
        return len(self.history)

    def colour_at(self, cell):
        return self.colours[cell]

    def region_tree(self, cell):
        """cell's region as (cell, steps, parent) triples, nearest first.

        parent is the neighbour the search reached each cell from; None for
        cell itself.
        """
        colour = self.colours[cell]
        found = {cell: (0, None)}
        order = [cell]
        index = 0
        while index < len(order):
            current = order[index]
            index += 1
            for other in self.grid.neighbours(current):
                if other not in found and self.colours[other] == colour:
                    found[other] = (found[current][0] + 1, current)
                    order.append(other)
        return [(member, found[member][0], found[member][1]) for member in order]

    def region_of(self, cell):
        """cell's region as (cell, steps from cell) pairs, nearest first."""
        return [(member, steps) for member, steps, parent in self.region_tree(cell)]

    def regions(self):
        """Every region as a list of cells."""
        return region_graph(self.grid, self.colours).region_cells

    def colours_left(self):
        return sorted(set(self.colours.values()))

    def is_solved(self):
        return len(set(self.colours.values())) <= 1

    def can_flood(self, cell, colour):
        return cell in self.colours and colour != self.colours[cell]

    def flood(self, cell, colour):
        """Recolour cell's region. Returns the Move, or None when it would change nothing."""
        if not self.can_flood(cell, colour):
            return None
        tree = self.region_tree(cell)
        move = Move(cell, self.colours[cell], colour,
                    [member for member, steps, parent in tree],
                    [steps for member, steps, parent in tree],
                    [parent for member, steps, parent in tree])
        for member in move.cells:
            self.colours[member] = colour
        self.history.append(move)
        return move

    def undo(self):
        """Take back the last move. Returns it, or None with nothing to undo."""
        if not self.history:
            return None
        move = self.history.pop()
        for member in move.cells:
            self.colours[member] = move.old_colour
        return move

    def region_graph(self):
        return region_graph(self.grid, self.colours)


class RegionGraph:
    """The board seen as regions: what the solver and the generator search.

    region_cells[r]  the cells of region r
    colours[r]       its colour (a tuple over all regions)
    neighbours[r]    the regions touching it, as a frozenset
    region_at[cell]  which region a cell is in
    """

    def __init__(self, region_cells, colours, neighbours, region_at):
        self.region_cells = region_cells
        self.colours = colours
        self.neighbours = neighbours
        self.region_at = region_at

    def __len__(self):
        return len(self.region_cells)


def region_graph(grid, colours):
    """Group grid's cells into regions and record which regions touch."""
    region_at = {}
    region_cells = []
    region_colours = []
    for cell in grid.cells():
        if cell in region_at:
            continue
        region = len(region_cells)
        colour = colours[cell]
        members = [cell]
        region_at[cell] = region
        index = 0
        while index < len(members):
            current = members[index]
            index += 1
            for other in grid.neighbours(current):
                if other not in region_at and colours[other] == colour:
                    region_at[other] = region
                    members.append(other)
        region_cells.append(members)
        region_colours.append(colour)

    touching = [set() for _ in region_cells]
    for cell, region in region_at.items():
        for other in grid.neighbours(cell):
            other_region = region_at[other]
            if other_region != region:
                touching[region].add(other_region)
    return RegionGraph(region_cells, tuple(region_colours),
                       [frozenset(regions) for regions in touching], region_at)
