"""
Saving a fill-in puzzle in progress (KenKen, Sudoku), so leaving a game or
closing the app loses nothing. No UIKit.

A game describes its puzzle as plain JSON data (its rules module knows how).
This module adds the player's marks from a FillGrid, the time played so
far and the header subtitle, and writes the file atomically: a temp file,
then a rename, so a crash mid-save never leaves half a file.

Games save synchronously inside the tap that changed the grid (see the
Pythonista UI stability guide). Every failure is printed and otherwise
ignored: a lost save must never break play.
"""

import json
import os

FORMAT_VERSION = 1


def marks_to_data(grid):
    """The player's values and notes from a FillGrid, as JSON-ready data."""
    return {
        "values": grid.rows(),
        "notes": [
            [row, col, sorted(noted)]
            for (row, col), noted in sorted(grid.all_notes().items())
        ],
    }


def restore_marks(grid, marks):
    """Put saved values and notes back into a freshly built FillGrid."""
    notes = {(row, col): set(noted) for row, col, noted in marks["notes"]}
    grid.load_marks(marks["values"], notes)


def save_game(path, puzzle_data, grid, seconds_played, subtitle):
    """Write the game in progress to path now."""
    data = {
        "version": FORMAT_VERSION,
        "puzzle": puzzle_data,
        "marks": marks_to_data(grid),
        "seconds_played": round(seconds_played, 1),
        "subtitle": subtitle,
    }
    temp_path = path + ".tmp"
    try:
        with open(temp_path, "w") as handle:
            json.dump(data, handle)
        os.replace(temp_path, path)
    except (OSError, TypeError, ValueError) as error:
        print("Could not save game to {}: {}".format(path, error))


def load_game(path):
    """The saved data as a dict, or None when there is no usable save."""
    try:
        with open(path) as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        print("Ignoring unreadable saved game {}: {}".format(path, error))
        return None
    if not isinstance(data, dict) or data.get("version") != FORMAT_VERSION:
        return None
    return data


def discard_game(path):
    """Remove the save, for example once the puzzle is solved."""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError as error:
        print("Could not remove saved game {}: {}".format(path, error))