"""
Fold solver: the fewest moves that turn a board one colour.

Works on the region graph (rules.RegionGraph), never on cells. A position
is a colour for every original region; touching regions that share a
colour count as one group. A move recolours a group, which merges it with
every touching group of its new colour.

solve() runs iterative deepening A* with two lower bounds, using the larger:
- colours left - 1: a move removes at most one colour from the board;
- half the group graph's spread, rounded up: a move contracts one group and
  its same-coloured neighbours into a single node, which shortens any path
  between two groups by at most 2. The spread is the eccentricity of a far
  group, found by two breadth-first sweeps, which never exceeds the
  diameter, so the bound stays safe. It is what makes ring and spiral
  boards provable.
Other speed-ups:
- only moves that merge something are tried: painting a group a colour
  none of its neighbours have joins nothing (smokes/fold_smoke.py checks
  this against a full search on small boards);
- moves that merge the most groups go first, so answers come early;
- a position already searched at the same or a shallower depth is skipped;
- the cheap colour bound is checked before the groups are worked out.

A node budget keeps callers responsive: past it, solve() returns the
shorter of the greedy plan and pivot_plan() (flood outwards from a central
region, a beam search), marked exact=False, so its length is only an
upper bound on par. Textured boards with 100+ regions rely on it.
"""


# --- editable effort ---------------------------------------------------------

SOLVE_BUDGET = 50000    # positions searched before solve() settles for a plan
PIVOT_CANDIDATES = 3    # pivot_plan: most central regions tried as the pivot
PIVOT_BEAM = 40         # pivot_plan: positions kept at each depth


# --- internal markers --------------------------------------------------------

FOUND = "found"
OUT_OF_BUDGET = "out of budget"
NO_LIMIT = float("inf")


class Solution:
    """moves: (cell, colour) taps in order. exact: True when no shorter
    solution exists. nodes: positions the search visited."""

    def __init__(self, moves, exact, nodes):
        self.moves = moves
        self.exact = exact
        self.nodes = nodes

    @property
    def length(self):
        return len(self.moves)


# --- positions ---------------------------------------------------------------

def merged_groups(graph, state):
    """(group_of, groups): touching regions sharing a colour, joined.

    group_of[region] is the region's group number; groups lists each
    group's regions.
    """
    group_of = [-1] * len(state)
    groups = []
    for first in range(len(state)):
        if group_of[first] != -1:
            continue
        group = len(groups)
        members = [first]
        group_of[first] = group
        index = 0
        while index < len(members):
            region = members[index]
            index += 1
            for other in graph.neighbours[region]:
                if group_of[other] == -1 and state[other] == state[first]:
                    group_of[other] = group
                    members.append(other)
        groups.append(members)
    return group_of, groups


def lower_bound(state):
    """The cheap bound: colours left - 1."""
    return len(set(state)) - 1


def group_links(graph, group_of, groups):
    """For each group, the set of groups touching it."""
    links = [set() for _ in groups]
    for group, members in enumerate(groups):
        for region in members:
            for other in graph.neighbours[region]:
                if group_of[other] != group:
                    links[group].add(group_of[other])
    return links


def _farthest(links, start):
    """(group, distance) of a group farthest from start."""
    distance = {start: 0}
    queue = [start]
    index = 0
    while index < len(queue):
        node = queue[index]
        index += 1
        for other in links[node]:
            if other not in distance:
                distance[other] = distance[node] + 1
                queue.append(other)
    node = queue[-1]
    return node, distance[node]


def spread_bound(links):
    """ceil(e / 2) for the eccentricity e of a far group (two sweeps)."""
    far, _ = _farthest(links, 0)
    _, eccentricity = _farthest(links, far)
    return (eccentricity + 1) // 2


def examine(graph, state):
    """(bound, moves, group count) for a position.

    Each move is (groups merged, group's regions, colour), best first; no
    moves once the board is one group.
    """
    group_of, groups = merged_groups(graph, state)
    if len(groups) <= 1:
        return 0, [], len(groups)
    links = group_links(graph, group_of, groups)
    moves = []
    for group, members in enumerate(groups):
        touching = {}
        for other in links[group]:
            touching.setdefault(state[groups[other][0]], set()).add(other)
        for colour, others in touching.items():
            moves.append((len(others), members, colour))
    moves.sort(key=lambda move: -move[0])
    bound = max(lower_bound(state), spread_bound(links))
    return bound, moves, len(groups)


def useful_moves(graph, state):
    """(moves, group count), as examine() finds them."""
    bound, moves, group_count = examine(graph, state)
    return moves, group_count


def recolour(state, members, colour):
    changed = list(state)
    for region in members:
        changed[region] = colour
    return tuple(changed)


def _as_taps(graph, path):
    """Search steps as taps a player could make: any cell of the group."""
    return [(graph.region_cells[members[0]][0], colour) for members, colour in path]


# --- solving -----------------------------------------------------------------

def solve(graph, budget=SOLVE_BUDGET):
    """The fewest-moves Solution for graph, or the greedy plan if the budget runs out."""
    search = _Search(graph, budget)
    start = tuple(graph.colours)
    bound = examine(graph, start)[0]
    while True:
        search.seen = {}
        outcome = search.visit(start, 0, bound)
        if outcome is FOUND:
            return Solution(_as_taps(graph, search.path), True, search.nodes)
        if outcome is OUT_OF_BUDGET or outcome == NO_LIMIT:
            break
        bound = outcome
    return Solution(best_effort_plan(graph), False, search.nodes)


def best_effort_plan(graph, candidates=PIVOT_CANDIDATES, beam=PIVOT_BEAM):
    """The shorter of the greedy plan and the pivot plan: par's upper bound
    when the search runs out of budget. Smaller beams are quicker."""
    greedy = greedy_plan(graph)
    pivot = pivot_plan(graph, candidates, beam)
    return pivot if pivot and len(pivot) < len(greedy) else greedy


def greedy_plan(graph, limit=500):
    """Taps that always make the biggest merge available. Quick, rarely optimal."""
    state = tuple(graph.colours)
    path = []
    while len(path) < limit:
        moves, group_count = useful_moves(graph, state)
        if group_count <= 1:
            break
        merged, members, colour = moves[0]
        path.append((members, colour))
        state = recolour(state, members, colour)
    return _as_taps(graph, path)


class _Search:
    """One iterative-deepening search: the path so far, positions seen, nodes spent."""

    def __init__(self, graph, budget):
        self.graph = graph
        self.budget = budget
        self.nodes = 0
        self.path = []
        self.seen = {}

    def visit(self, state, depth, bound):
        """FOUND, OUT_OF_BUDGET, or the smallest estimate past bound (the next bound)."""
        quick = depth + lower_bound(state)
        if quick > bound:
            return quick
        estimate, moves, group_count = examine(self.graph, state)
        if group_count == 1:
            return FOUND
        if depth + estimate > bound:
            return depth + estimate
        previous = self.seen.get(state)
        if previous is not None and previous <= depth:
            return NO_LIMIT
        self.seen[state] = depth
        self.nodes += 1
        if self.nodes > self.budget:
            return OUT_OF_BUDGET
        smallest = NO_LIMIT
        for merged, members, colour in moves:
            self.path.append((members, colour))
            outcome = self.visit(recolour(state, members, colour), depth + 1, bound)
            if outcome is FOUND or outcome is OUT_OF_BUDGET:
                return outcome
            self.path.pop()
            smallest = min(smallest, outcome)
        return smallest


# --- big boards: flooding outwards from one region -------------------------------------



def _eccentricity(links, start):
    return _farthest(links, start)[1]


def pivot_plan(graph, candidates=PIVOT_CANDIDATES, beam=PIVOT_BEAM):
    """Taps that flood outwards from one central region, as KAMI players do
    on busy boards. A beam search over colour choices for the pivot's group,
    tried from the few most central regions; the shortest plan wins. Never
    proves anything, but on textured boards it beats greedy by a lot."""
    start = tuple(graph.colours)
    group_of, groups = merged_groups(graph, start)
    if len(groups) <= 1:
        return []
    links = group_links(graph, group_of, groups)
    central = sorted(range(len(groups)), key=lambda group: _eccentricity(links, group))[:candidates]
    best = None
    for group in central:
        pivot = groups[group][0]
        plan = _pivot_beam(graph, start, pivot, beam)
        if plan is not None and (best is None or len(plan) < len(best)):
            best = plan
    return best or []


def _pivot_beam(graph, start, pivot, beam):
    frontier = [(start, [])]
    seen = {start}
    for depth in range(200):
        following = []
        for state, path in frontier:
            group_of, groups = merged_groups(graph, state)
            if len(groups) == 1:
                return _as_taps(graph, path)
            links = group_links(graph, group_of, groups)
            own = group_of[pivot]
            members = groups[own]
            for colour in {state[groups[other][0]] for other in links[own]}:
                child = recolour(state, members, colour)
                if child in seen:
                    continue
                seen.add(child)
                child_of, child_groups = merged_groups(graph, child)
                if len(child_groups) == 1:
                    return _as_taps(graph, path + [(members, colour)])
                child_links = group_links(graph, child_of, child_groups)
                reach = _eccentricity(child_links, child_of[pivot])
                score = (max(reach, len(set(child)) - 1), len(child_groups))
                following.append((score, child, path + [(members, colour)]))
        following.sort(key=lambda item: item[0])
        frontier = [(state, path) for score, state, path in following[:beam]]
        if not frontier:
            return None
    return None
