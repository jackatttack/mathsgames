"""Countdown numbers rules: dealing, target building, solver and hints.

No UIKit lives here.

Rules, as on the show but without the clock:
    Six numbers are dealt: big_count from BIG_NUMBERS and the rest from
    SMALL_POOL, which holds two each of 1 to 10. Any two numbers may be
    combined with + - × ÷, and every result must be a positive whole number.
    Not every number has to be used. The target is in TARGET_RANGE.

Targets are built, not guessed: the dealer plays random legal merges, picks
a value made along the way, and keeps only the merges that value needed.
That route is stored on the round, so every target is makeable and hints
along it are instant. Off the route, a capped breadth-first search over
sorted number sets finds the shortest way from the current position.
"""

import random
from collections import deque

from tilegame.board_state import any_pair, positive_whole_numbers
from tilegame.targets import TargetRound


# --- editable settings ------------------------------------------------------

BIG_NUMBERS = (25, 50, 75, 100)
SMALL_POOL = tuple(number for number in range(1, 11) for _ in range(2))

BOARD_ROWS = 2
BOARD_COLS = 3
TILE_COUNT = BOARD_ROWS * BOARD_COLS

BIG_COUNT_CHOICES = (0, 1, 2, 3, 4)
DEFAULT_BIG_COUNT = 1

TARGET_RANGE = (101, 999)
MIN_ROUTE_MOVES = 3          # a dealt target needs at least this many merges
MAX_DEAL_ATTEMPTS = 300

# Positions the off-route hint search may explore before giving up, so a
# hint can never freeze the app.
SOLVER_NODE_LIMIT = 50000


# --- combining two numbers --------------------------------------------------

def combinations_for(a, b):
    """Every legal result of combining a and b, as (left, op, right, value).

    The larger number is the left operand, so subtraction stays positive.
    Moves that change nothing (× 1, ÷ 1) are left out of searches; the
    board itself still allows them.
    """
    big, small = max(a, b), min(a, b)
    results = [(big, "+", small, big + small)]

    if small != 1:
        results.append((big, "×", small, big * small))
    if big > small:
        results.append((big, "-", small, big - small))
    if small != 1 and big % small == 0:
        results.append((big, "/", small, big // small))

    return results


def one_move_makes(numbers, target):
    """True when a single merge of two of these numbers makes target."""
    for i in range(len(numbers)):
        for j in range(i + 1, len(numbers)):
            for step in combinations_for(numbers[i], numbers[j]):
                if step[3] == target:
                    return True
    return False


# --- solver -----------------------------------------------------------------

def solve(numbers, target, node_limit=SOLVER_NODE_LIMIT):
    """Shortest route from numbers to target, or None.

    A route is a list of (left, op, right, value) steps. Returns [] when the
    target is already one of the numbers, and None when no route is found
    within node_limit positions.
    """
    start = tuple(sorted(numbers))

    if target in start:
        return []

    explored = {start}
    queue = deque([(start, [])])

    while queue:
        state, route = queue.popleft()
        tried_pairs = set()

        for i in range(len(state)):
            for j in range(i + 1, len(state)):
                pair = (state[i], state[j])
                if pair in tried_pairs:
                    continue
                tried_pairs.add(pair)

                rest = state[:i] + state[i + 1:j] + state[j + 1:]

                for step in combinations_for(*pair):
                    if step[3] == target:
                        return route + [step]

                    child = tuple(sorted(rest + (step[3],)))
                    if child in explored:
                        continue

                    explored.add(child)
                    if len(explored) > node_limit:
                        return None
                    queue.append((child, route + [step]))

    return None


# --- dealing ----------------------------------------------------------------

def deal_numbers(big_count, rng):
    """Six numbers: big_count big ones, the rest from the small pool."""
    if big_count not in BIG_COUNT_CHOICES:
        raise ValueError("big_count must be one of {}".format(BIG_COUNT_CHOICES))

    numbers = (
        rng.sample(BIG_NUMBERS, big_count)
        + rng.sample(SMALL_POOL, TILE_COUNT - big_count)
    )
    rng.shuffle(numbers)
    return numbers


def _random_walk(numbers, rng):
    """Play random legal merges until one number is left.

    Returns steps (left, op, right, value, left_id, right_id, value_id);
    the ids say which earlier number each operand was, for route pruning.
    """
    pool = [(value, index) for index, value in enumerate(numbers)]
    next_id = len(numbers)
    steps = []

    while len(pool) > 1:
        i, j = rng.sample(range(len(pool)), 2)
        (a, a_id), (b, b_id) = pool[i], pool[j]

        left, op, right, value = rng.choice(combinations_for(a, b))

        if left == a and right == b:
            left_id, right_id = a_id, b_id
        else:
            left_id, right_id = b_id, a_id

        pool = [item for k, item in enumerate(pool) if k not in (i, j)]
        pool.append((value, next_id))
        steps.append((left, op, right, value, left_id, right_id, next_id))
        next_id += 1

    return steps


def _route_to(steps, value_id):
    """Only the steps the value with value_id actually depends on, in order."""
    needed = {value_id}
    route = []

    for step in reversed(steps):
        if step[6] in needed:
            route.append(step[:4])
            needed.add(step[4])
            needed.add(step[5])

    route.reverse()
    return route


class CountdownRound(TargetRound):
    """A Countdown board: the shared target round plus its stored route."""

    def __init__(self, starting_rows, target, route, big_count, attempts=1):
        super().__init__(
            starting_rows,
            target,
            merge_rule=any_pair,
            result_rule=positive_whole_numbers,
        )
        self.route = list(route)
        self.big_count = big_count
        self.attempts = attempts

        # The sorted numbers on the board before each route step.
        current = sorted(value for row in starting_rows for value in row)
        self.route_states = [tuple(current)]

        for left, op, right, value in self.route:
            current.remove(left)
            current.remove(right)
            current.append(value)
            current.sort()
            self.route_states.append(tuple(current))

    def next_route_step(self, numbers):
        """The stored route's next step if the board is on the route."""
        state = tuple(sorted(numbers))

        for index, route_state in enumerate(self.route_states[:-1]):
            if route_state == state:
                return self.route[index]

        return None


def deal_round(big_count=DEFAULT_BIG_COUNT, rng=None):
    """Deal six numbers and a target needing at least MIN_ROUTE_MOVES merges."""
    rng = rng or random.Random()
    low, high = TARGET_RANGE
    fallback = None

    for attempts in range(1, MAX_DEAL_ATTEMPTS + 1):
        numbers = deal_numbers(big_count, rng)
        steps = _random_walk(numbers, rng)

        candidates = []
        for step in steps:
            value = step[3]
            if not low <= value <= high or value in numbers:
                continue
            if one_move_makes(numbers, value):
                continue
            route = _route_to(steps, step[6])
            candidates.append((value, route))

        rich = [c for c in candidates if len(c[1]) >= MIN_ROUTE_MOVES]

        if rich:
            target, route = rng.choice(rich)
            rows = [numbers[:BOARD_COLS], numbers[BOARD_COLS:]]
            return CountdownRound(rows, target, route, big_count, attempts)

        if fallback is None and candidates:
            fallback = (numbers, candidates)

    if fallback is None:
        raise RuntimeError("Could not deal a Countdown target")

    numbers, candidates = fallback
    target, route = rng.choice(candidates)
    rows = [numbers[:BOARD_COLS], numbers[BOARD_COLS:]]
    return CountdownRound(rows, target, route, big_count, MAX_DEAL_ATTEMPTS)


# --- hints ------------------------------------------------------------------

def board_numbers(board):
    """The whole numbers currently on a board, as ints."""
    return [
        int(value)
        for row in board.cells
        for value in row
        if value is not None
    ]


def next_hint_step(round_, board):
    """The next (left, op, right, value) towards the target, or None.

    None also means the target is already on the board. The capped search
    gives the shortest route from the current position; the stored route
    is the fallback if the search hits its cap. Searches from a full board
    take about 0.01s, so shortest-first costs nothing.
    """
    numbers = board_numbers(board)
    route = solve(numbers, round_.target)

    if route is not None:
        return route[0] if route else None

    return round_.next_route_step(numbers)


# --- factors ----------------------------------------------------------------

SUPERSCRIPTS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def prime_factors(n):
    """[(prime, power), ...] for n >= 2, smallest prime first."""
    factors = []
    prime = 2

    while prime * prime <= n:
        power = 0
        while n % prime == 0:
            n //= prime
            power += 1
        if power:
            factors.append((prime, power))
        prime += 1

    if n > 1:
        factors.append((n, 1))

    return factors


def factor_pairs(n):
    """Every (a, b) with a × b = n and a <= b, smallest a first."""
    return [
        (a, n // a)
        for a in range(1, int(n ** 0.5) + 1)
        if n % a == 0
    ]


def describe_factors(n):
    """Two lines for the factors panel.

    '352 = 2⁵ × 11' (or '797 is prime'), then every factor pair.
    """
    primes = prime_factors(n)

    if primes == [(n, 1)]:
        first = "{} is prime".format(n)
    else:
        first = "{} = {}".format(n, " × ".join(
            str(prime) + (str(power).translate(SUPERSCRIPTS) if power > 1 else "")
            for prime, power in primes
        ))

    pairs = "  ·  ".join("{}×{}".format(a, b) for a, b in factor_pairs(n))
    return first + "\n" + pairs


def cells_for_step(board, step):
    """The (source, destination) cells holding a step's left and right values."""
    left, _, right, _ = step
    cells = [
        (row, col)
        for row in range(board.rows)
        for col in range(board.cols)
        if board.value_at((row, col)) is not None
    ]

    for source in cells:
        if board.value_at(source) != left:
            continue
        for destination in cells:
            if destination != source and board.value_at(destination) == right:
                return source, destination

    return None