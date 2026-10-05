"""
Pick & Mix rules: number pools, targets, a small solver and margin scoring.
No UIKit.

A round deals a shared pool of POOL_SIZE tiles from one of the POOLS and a
target. Players take turns picking tiles into their own hand, up to
PICKS_PER_PLAYER each, and merge them with + − × ÷ (results must be
positive whole numbers) to get as close to the target as they can.

Every target is reachable: it is chosen from the values one random hand of
PICKS_PER_PLAYER pool tiles can make, preferring targets that need at least
MIN_TILES_FOR_TARGET of those tiles, and never a number already in the pool.

Scoring is by margin of victory: the closer player scores the loser's
distance minus their own, capped at MARGIN_CAP, plus EXACT_BONUS for hitting
the target exactly. A tie scores nothing for either player.

Solver steps are (left, operation, right, value) with the operation symbols
of tilegame.board_state: "+", "-", "×", "/".
"""

import random
from dataclasses import dataclass


# --- editable rules ----------------------------------------------------------

POOL_SIZE = 10
PICKS_PER_PLAYER = 4

MARGIN_CAP = 10       # most points a round can give for the margin alone
EXACT_BONUS = 3       # extra for hitting the target exactly

MIN_TILES_FOR_TARGET = 3    # preferred: targets need at least this many tiles
TARGET_ATTEMPTS = 200       # random hands tried when choosing a target
DEAL_ATTEMPTS = 20          # fresh pools tried if no target fits the range


# --- editable pools ----------------------------------------------------------

SMALL_NUMBERS = tuple(range(1, 11))
BIG_NUMBERS = (25, 50, 75, 100)
PRIMES = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47)
CUBES = (1, 8, 27, 64, 125, 216, 343, 512)
FACTOR_RICH = (6, 8, 12, 16, 18, 24, 30, 36, 48, 60, 72, 96, 120)
LARGE_NUMBERS = (15, 20, 25, 30, 40, 50, 60, 75, 80, 90, 100)


def _standard(rng):
    """Countdown style: two or three big numbers, the rest from 1 to 10."""
    big_count = rng.choice((2, 3))
    bigs = rng.sample(BIG_NUMBERS, big_count)
    smalls = rng.sample(SMALL_NUMBERS * 2, POOL_SIZE - big_count)
    return bigs + smalls


def _without_repeats(numbers):
    return lambda rng: rng.sample(numbers, POOL_SIZE)


def _with_repeats(numbers):
    return lambda rng: rng.choices(numbers, k=POOL_SIZE)


@dataclass(frozen=True)
class Pool:
    """One kind of tile pool: how to draw it and where its targets lie."""

    name: str            # stable id, saved in settings
    label: str           # shown in Settings
    description: str     # one line for Settings
    draw: object         # function(rng) -> POOL_SIZE ints
    target_range: tuple  # (lowest, highest) target


POOLS = (
    Pool("standard", "Standard",
         "2 or 3 of 25, 50, 75, 100; the rest 1 to 10",
         _standard, (100, 999)),
    Pool("primes", "Primes",
         "Ten different primes up to 47",
         _without_repeats(PRIMES), (100, 999)),
    Pool("cubes", "Cubes",
         "Cubes from 1 to 512, repeats allowed",
         _with_repeats(CUBES), (100, 999)),
    Pool("factor_rich", "Factor-rich",
         "Numbers with lots of factors, 6 to 120",
         _without_repeats(FACTOR_RICH), (100, 999)),
    Pool("all_large", "All large",
         "Big numbers only, 15 to 100",
         _without_repeats(LARGE_NUMBERS), (200, 999)),
    Pool("small", "Small",
         "The numbers 1 to 10, with targets from 20 to 99",
         lambda rng: list(SMALL_NUMBERS), (20, 99)),
)

POOL_NAMES = tuple(pool.name for pool in POOLS)


def find_pool(name):
    for pool in POOLS:
        if pool.name == name:
            return pool
    raise ValueError("Unknown pool %r; choose one of %s" % (name, POOL_NAMES))


# --- the solver --------------------------------------------------------------

def pair_results(a, b):
    """Every legal merge of two numbers, larger first, as solver steps."""
    larger, smaller = max(a, b), min(a, b)
    steps = [
        (larger, "+", smaller, larger + smaller),
        (larger, "×", smaller, larger * smaller),
    ]
    if larger > smaller:
        steps.append((larger, "-", smaller, larger - smaller))
    if smaller > 1 and larger % smaller == 0:
        steps.append((larger, "/", smaller, larger // smaller))
    return steps


def _tile_count(mask):
    return bin(mask).count("1")


def made_by(numbers):
    """{subset mask: {value: recipe}} for every non-empty subset of numbers.

    Each value is made using every tile in its subset. A recipe is None for
    a single tile, or (part, a, other, b, step): value a from subset part
    and value b from subset other, combined by step.
    """
    numbers = list(numbers)
    made = {}
    masks = sorted(range(1, 1 << len(numbers)), key=_tile_count)

    for mask in masks:
        if mask & (mask - 1) == 0:
            made[mask] = {numbers[mask.bit_length() - 1]: None}
            continue

        values = {}
        part = (mask - 1) & mask
        while part:
            other = mask ^ part
            if part < other:       # each unordered split once
                for a in made[part]:
                    for b in made[other]:
                        for step in pair_results(a, b):
                            if step[3] not in values:
                                values[step[3]] = (part, a, other, b, step)
            part = (part - 1) & mask
        made[mask] = values

    return made


def route(made, mask, value):
    """The steps that make value from subset mask, in playing order."""
    recipe = made[mask][value]
    if recipe is None:
        return []
    part, a, other, b, step = recipe
    return route(made, part, a) + route(made, other, b) + [step]


def closest(numbers, target):
    """(value, distance, steps) for the closest value these numbers can make.

    Ties go to fewer tiles, then to the smaller value. None if no numbers.
    """
    numbers = list(numbers)
    if not numbers:
        return None
    made = made_by(numbers)
    best = None
    for mask, values in made.items():
        tiles = _tile_count(mask)
        for value in values:
            key = (abs(value - target), tiles, value)
            if best is None or key < best[0]:
                best = (key, mask, value)
    key, mask, value = best
    return value, key[0], route(made, mask, value)


# --- dealing -----------------------------------------------------------------

@dataclass(frozen=True)
class Deal:
    """One round's shared pool and target."""

    pool_name: str
    numbers: tuple        # the pool, smallest first
    target: int
    example_hand: tuple   # a hand of pool tiles that makes the target exactly


def choose_target(numbers, target_range, rng):
    """(target, example hand): a value one random hand can make exactly.

    Prefers targets needing at least MIN_TILES_FOR_TARGET tiles; falls back
    to any reachable target in range. Raises ValueError if none is found.
    """
    low, high = target_range
    in_pool = set(numbers)
    fallback = None

    for _ in range(TARGET_ATTEMPTS):
        hand = rng.sample(list(numbers), PICKS_PER_PLAYER)
        fewest = {}
        for mask, values in made_by(hand).items():
            tiles = _tile_count(mask)
            for value in values:
                if low <= value <= high and value not in in_pool:
                    if value not in fewest or tiles < fewest[value]:
                        fewest[value] = tiles

        preferred = sorted(
            value for value, tiles in fewest.items() if tiles >= MIN_TILES_FOR_TARGET
        )
        if preferred:
            return rng.choice(preferred), tuple(hand)
        if fallback is None and fewest:
            fallback = (rng.choice(sorted(fewest)), tuple(hand))

    if fallback is not None:
        return fallback
    raise ValueError("No reachable target in range for this pool")


def deal(pool_name, rng=None):
    """Deal a pool of POOL_SIZE tiles and a reachable target."""
    pool = find_pool(pool_name)
    rng = rng or random.Random()
    for _ in range(DEAL_ATTEMPTS):
        numbers = sorted(pool.draw(rng))
        try:
            target, hand = choose_target(numbers, pool.target_range, rng)
        except ValueError:
            continue
        return Deal(pool_name, tuple(numbers), target, hand)
    raise ValueError("Could not deal a %s round" % pool_name)


# --- scoring -----------------------------------------------------------------

@dataclass(frozen=True)
class RoundScore:
    """How far each player was from the target and what they scored."""

    distances: tuple   # per player
    points: tuple      # per player
    winner: object     # 0 or 1, or None for a tie


def score_round(target, values):
    """Score two counted values against the target by margin of victory."""
    distances = tuple(abs(target - value) for value in values)
    if distances[0] == distances[1]:
        return RoundScore(distances, (0, 0), None)

    winner = 0 if distances[0] < distances[1] else 1
    loser = 1 - winner
    margin = min(MARGIN_CAP, distances[loser] - distances[winner])
    bonus = EXACT_BONUS if distances[winner] == 0 else 0

    points = [0, 0]
    points[winner] = margin + bonus
    return RoundScore(distances, tuple(points), winner)