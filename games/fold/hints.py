"""
Fold hints: the best next move from wherever the player has got to.

The solver runs on the current position. On boards small enough to prove
(HINT_EXACT_REGIONS), the hint is the first move of a shortest solution,
so following hints all the way finishes in the fewest moves still
possible. Busier boards get the first move of the pivot plan, a strong
move but not a proven one. Using a hint caps the puzzle at ★★ (stars.py).
"""

from games.fold import rules, solver


HINT_EXACT_REGIONS = 34     # above this, the pivot plan's first move
HINT_BUDGET = 20000         # solver positions before settling for a plan
HINT_PIVOTS = 2             # pivot plan effort on busy boards, kept small
HINT_BEAM = 12              # so a hint arrives in about a second


class Hint:
    """cell: any triangle of the region to tap; colour: what to paint it;
    region: every triangle of that region (for the highlight); moves_left:
    how many moves the plan needs from here; exact: whether that is proven."""

    def __init__(self, cell, colour, region, moves_left, exact):
        self.cell = cell
        self.colour = colour
        self.region = region
        self.moves_left = moves_left
        self.exact = exact


def best_move(board):
    """A Hint for board, or None when it is already solved."""
    if board.is_solved():
        return None
    graph = rules.region_graph(board.grid, board.colours)
    if len(graph) > HINT_EXACT_REGIONS:
        moves, exact = solver.best_effort_plan(graph, HINT_PIVOTS, HINT_BEAM), False
    else:
        found = solver.solve(graph, HINT_BUDGET)
        moves, exact = found.moves, found.exact
    cell, colour = moves[0]
    region = [member for member, steps in board.region_of(cell)]
    return Hint(cell, colour, region, len(moves), exact)
