"""
Double Up rules for Maths Games: slide, merge, spawn, win and lose.

No UIKit lives here. The screen asks this module what a swipe does and
draws the answer, so every rule is smoke-tested headless
(smokes/twenty48_rules_smoke.py).

Variants, all played through one Game:

    board size       3×3 to 6×6
    doubling mode    equal tiles merge; tiles are the starting number times
                     a power of 2 (start 3: 3, 6, 12, 24, ...)
    fibonacci mode   two 1s, or two neighbouring Fibonacci numbers, merge
                     into the next one (1, 2, 3, 5, 8, 13, ...)

A merged tile is always the sum of the pair, in every mode. Each tile has a
step: how far along its mode's sequence it is (0 for the smallest). The
screen colours tiles by step, so one palette fits every mode and start.

A swipe slides every line toward that edge. Within a line, tiles pair up
from the leading edge and each tile merges at most once per swipe. A swipe
that changes nothing is not a move, and no tile spawns.
"""

import math
import random


# --- editable settings ------------------------------------------------------

BOARD_SIZES = (3, 4, 5, 6)
DEFAULT_SIZE = 4
STARTING_NUMBERS = (2, 3, 5)
DEFAULT_START = 2
MODES = ("doubling", "fibonacci")
DEFAULT_MODE = "doubling"

OPENING_TILES = 2           # tiles on a new board
HIGH_SPAWN_CHANCE = 0.1     # chance a new tile is the larger spawn value
GOAL_DOUBLINGS = 10         # doubling goal: the starting number × 2**10
FIBONACCI_GOAL = 2584

DIRECTIONS = ("left", "right", "up", "down")


# --- merge rules ------------------------------------------------------------

class DoublingRule:
    """Equal tiles merge: start, 2 × start, 4 × start, ..."""

    mode = "doubling"

    def __init__(self, start):
        self.start = start
        self.spawn_values = (start, 2 * start)
        self.goal = start * 2 ** GOAL_DOUBLINGS

    def can_merge(self, first, second):
        return first == second

    def step(self, value):
        """Doublings from the starting number: start is 0, 2 × start is 1."""
        return int(round(math.log2(value / self.start)))

    def is_tile(self, value):
        """True for the starting number times a power of 2."""
        if value % self.start:
            return False
        ratio = value // self.start
        return ratio >= 1 and ratio & (ratio - 1) == 0


def _fibonacci_numbers(limit=10 ** 12):
    numbers = [1, 2]
    while numbers[-1] < limit:
        numbers.append(numbers[-1] + numbers[-2])
    return tuple(numbers)


FIBONACCI = _fibonacci_numbers()     # 1, 2, 3, 5, 8, ... with a single 1
_FIBONACCI_INDEX = {value: index for index, value in enumerate(FIBONACCI)}


class FibonacciRule:
    """Two 1s, or neighbouring Fibonacci numbers, merge into the next one."""

    mode = "fibonacci"
    start = 1

    def __init__(self):
        self.spawn_values = (1, 2)
        self.goal = FIBONACCI_GOAL

    def can_merge(self, first, second):
        if first == second == 1:
            return True
        first_index = _FIBONACCI_INDEX.get(first)
        second_index = _FIBONACCI_INDEX.get(second)
        return (first_index is not None and second_index is not None
                and abs(first_index - second_index) == 1)

    def step(self, value):
        """Position in 1, 2, 3, 5, 8, ...: 1 is 0, 2 is 1, 3 is 2."""
        return _FIBONACCI_INDEX[value]

    def is_tile(self, value):
        return value in _FIBONACCI_INDEX


def make_rule(mode, start=DEFAULT_START):
    """The merge rule for a mode. Fibonacci ignores start."""
    if mode == "doubling":
        return DoublingRule(start)
    if mode == "fibonacci":
        return FibonacciRule()
    raise ValueError("mode must be one of %s" % ", ".join(MODES))


# --- one line ---------------------------------------------------------------

def slide_line(values, rule):
    """Slide one line toward its index-0 end, merging pairs.

    values lists the line from the edge tiles slide toward, None for empty.
    Returns (new_values, groups, gained). groups has one entry per tile in
    new_values: (source_indexes, merged), where its tile or pair came from.
    """
    tiles = [(index, value) for index, value in enumerate(values) if value is not None]
    new_values = []
    groups = []
    gained = 0

    position = 0
    while position < len(tiles):
        index, value = tiles[position]
        if position + 1 < len(tiles) and rule.can_merge(value, tiles[position + 1][1]):
            other_index, other_value = tiles[position + 1]
            merged = value + other_value
            new_values.append(merged)
            groups.append(((index, other_index), True))
            gained += merged
            position += 2
        else:
            new_values.append(value)
            groups.append(((index,), False))
            position += 1

    new_values += [None] * (len(values) - len(new_values))
    return new_values, groups, gained


# --- the game ---------------------------------------------------------------

class MoveResult:
    """What one swipe did, for the screen to draw and animate."""

    def __init__(self, direction, slides, merged_cells, spawned, gained,
                 reached_goal, over):
        self.direction = direction
        self.slides = slides              # [(from_cell, to_cell)] for every earlier tile
        self.merged_cells = merged_cells  # cells holding a freshly merged tile
        self.spawned = spawned            # (cell, value) or None
        self.gained = gained              # score added by this swipe
        self.reached_goal = reached_goal  # True only on the swipe that first reaches it
        self.over = over                  # no move is left


class Game:
    """One board: cells[row][col] hold tile values or None."""

    def __init__(self, size=DEFAULT_SIZE, rule=None, rng=None):
        if size not in BOARD_SIZES:
            raise ValueError("size must be one of %s" % (BOARD_SIZES,))
        self.size = size
        self.rule = rule or make_rule(DEFAULT_MODE)
        self.rng = rng or random.Random()
        self.cells = [[None] * size for _ in range(size)]
        self.score = 0
        self.won = False      # the goal has been reached; play can go on
        self.moves = 0

    @classmethod
    def new(cls, size=DEFAULT_SIZE, rule=None, rng=None):
        """A fresh board with its opening tiles."""
        game = cls(size, rule, rng)
        for _ in range(OPENING_TILES):
            game.spawn()
        return game

    # Reading.

    def value_at(self, cell):
        return self.cells[cell[0]][cell[1]]

    def empty_cells(self):
        return [
            (row, col)
            for row in range(self.size) for col in range(self.size)
            if self.cells[row][col] is None
        ]

    def highest(self):
        values = [value for row in self.cells for value in row if value is not None]
        return max(values) if values else 0

    def can_move(self):
        """True while a swipe could change the board."""
        if self.empty_cells():
            return True
        for row in range(self.size):
            for col in range(self.size):
                value = self.cells[row][col]
                if col + 1 < self.size and self.rule.can_merge(value, self.cells[row][col + 1]):
                    return True
                if row + 1 < self.size and self.rule.can_merge(value, self.cells[row + 1][col]):
                    return True
        return False

    def is_over(self):
        return not self.can_move()

    def lines(self, direction):
        """Each line's cells, starting from the edge tiles slide toward."""
        indexes = range(self.size)
        if direction == "left":
            return [[(row, col) for col in indexes] for row in indexes]
        if direction == "right":
            return [[(row, col) for col in reversed(indexes)] for row in indexes]
        if direction == "up":
            return [[(row, col) for row in indexes] for col in indexes]
        if direction == "down":
            return [[(row, col) for row in reversed(indexes)] for col in indexes]
        raise ValueError("direction must be one of %s" % ", ".join(DIRECTIONS))

    # Changing.

    def spawn(self):
        """Put a new tile on a random empty cell. Returns (cell, value) or None."""
        empty = self.empty_cells()
        if not empty:
            return None
        cell = self.rng.choice(empty)
        low, high = self.rule.spawn_values
        value = high if self.rng.random() < HIGH_SPAWN_CHANCE else low
        self.cells[cell[0]][cell[1]] = value
        return cell, value

    def move(self, direction):
        """Swipe: slide and merge, spawn, then check the goal and game over.

        Returns a MoveResult, or None when the swipe would change nothing
        (the board is left untouched and nothing spawns).
        """
        new_cells = [[None] * self.size for _ in range(self.size)]
        slides = []
        merged_cells = []
        gained = 0
        changed = False

        for line in self.lines(direction):
            values = [self.value_at(cell) for cell in line]
            new_values, groups, line_gain = slide_line(values, self.rule)
            gained += line_gain
            for position, (sources, merged) in enumerate(groups):
                target = line[position]
                for source in sources:
                    slides.append((line[source], target))
                    if line[source] != target:
                        changed = True
                if merged:
                    merged_cells.append(target)
                    changed = True
            for cell, value in zip(line, new_values):
                new_cells[cell[0]][cell[1]] = value

        if not changed:
            return None

        self.cells = new_cells
        self.score += gained
        self.moves += 1
        spawned = self.spawn()

        reached_goal = False
        if not self.won and self.highest() >= self.rule.goal:
            self.won = True
            reached_goal = True

        return MoveResult(direction, slides, merged_cells, spawned, gained,
                          reached_goal, self.is_over())

    # Saving.

    def to_data(self):
        return {
            "size": self.size,
            "mode": self.rule.mode,
            "start": self.rule.start,
            "cells": [list(row) for row in self.cells],
            "score": self.score,
            "won": self.won,
            "moves": self.moves,
        }

    @classmethod
    def from_data(cls, data, rng=None):
        """Rebuild a saved game. Raises ValueError for anything that does not fit."""
        try:
            size = int(data["size"])
            mode = data["mode"]
            start = int(data["start"])
            cells = data["cells"]
            score = int(data.get("score", 0))
            won = bool(data.get("won", False))
            moves = int(data.get("moves", 0))
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("saved game is incomplete: %s" % error)

        if size not in BOARD_SIZES:
            raise ValueError("saved size %r is not offered" % size)
        if mode == "doubling" and start not in STARTING_NUMBERS:
            raise ValueError("saved starting number %r is not offered" % start)
        rule = make_rule(mode, start)
        if (not isinstance(cells, list) or len(cells) != size
                or any(not isinstance(row, list) or len(row) != size for row in cells)):
            raise ValueError("saved cells do not make a %d×%d board" % (size, size))
        for row in cells:
            for value in row:
                if value is not None and not (isinstance(value, int) and rule.is_tile(value)):
                    raise ValueError("saved tile %r is not a %s tile" % (value, mode))

        game = cls(size, rule, rng)
        game.cells = [list(row) for row in cells]
        game.score = score
        game.won = won
        game.moves = moves
        return game