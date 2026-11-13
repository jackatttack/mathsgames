"""Sudoku on editorkit.web: the native game, drawn as a web page.

Game mirrors games/sudoku/screen.py's SudokuScreen method for method, on
the same Maths Games code: rules, FillGrid, the settings file, the saved
game and the best times are the native game's own (imported, never
copied). A game started in one version carries on in the other, and both
keep one set of best times. Only the drawing is new:

    the board      givens, your numbers, notes in a box-shaped mini grid; the
                   focus cell's row, column, box and number highlighted (or
                   the armed number's copies); mistakes; completed numbers
    the picker     a tapped empty cell opens it under the board, over the
                   tray: its numbers, Notes and Clear
    the tray       each number with a stack of bars, one per copy still to
                   place; tap to arm, Notes while armed
    settings       ⚙️: size, difficulty, the four switches, New puzzle, Best
                   times, Done (a draft, as natively)
    best times     the RecordsPanel's leaderboards, by size and level
    motion         a new deal unfolds from a random corner, the givens pop in
                   and the board swells; a solve celebrates in a random style.
                   CSS stand-ins for board_build.py and flourish_overlay.py,
                   played once, on the page drawn after the deal or the solve.

No UI here: html() says what the page shows and go(payload) is a tap, so
smokes/webgames_sudoku_smoke.py plays it headless.
"""
import math
import random
import time

from games.sudoku import rules
from games.sudoku import screen as native
from tilegame import saved_game
from tilegame.fill_grid import FillGrid
from tilegame.records import RecordBook


# --- Settings -------------------------------------------------------------

# The theme roles the page uses, as --mg-<role> (shell.theme_css).
THEME_TOKENS = ('background', 'surface', 'text', 'muted', 'button', 'button_text', 'tile',
                'tile_text', 'success', 'mistake', 'sky', 'board', 'grid_line', 'box_wall',
                'given', 'player_number', 'note', 'selection_fill', 'selection',
                'assist_peer', 'assist_match')

# Motion, from games/sudoku/board_build.py and feel/flourish.py.
BUILD_FOLD_SECONDS = 0.45
BUILD_SPREAD_SECONDS = 2.0
NUMBER_POP_SECONDS = 0.36
NUMBER_STEP_SECONDS = 0.07
NUMBER_SPREAD_SECONDS = 1.0
CELEBRATION_STYLES = ('ripple', 'sweep', 'sparkle')
CELEBRATION_SPREAD_SECONDS = 1.5     # the last cell starts this long after the first
CORNERS = ('tl', 'tr', 'bl', 'br')

TRAY_PER_ROW = 5                     # NumberTray.MAX_PER_ROW
PICKER_COLUMNS = 5                   # CellPicker.MAX_COLUMNS
SWITCHES = (('show_mistakes', 'Show mistakes'),
            ('tidy_notes', 'Remove notes when a number is placed'),
            ('highlight', 'Highlight row, column, box and matching numbers'),
            ('highlight_complete', 'Highlight completed numbers'))
NO_RECORDS = 'No solves on this board yet'


def when_text(when):
    """A best time's date: stored as seconds since 1970 or as text."""
    if isinstance(when, (int, float)):
        return time.strftime('%d %b %Y', time.localtime(when))
    return str(when)[:10]


class Game:
    """Sudoku's play, as games/sudoku/screen.py's SudokuScreen. store=False
    (smokes) reads and writes no files."""

    celebration_count = 0            # set by the shell: the theme's celebration colours

    def __init__(self, store=True, settings=None):
        self.store = store
        if settings is not None:
            self.settings = dict(native.DEFAULT_SETTINGS, **settings)
        elif store:
            self.settings = native.load_settings()
        else:
            self.settings = dict(native.DEFAULT_SETTINGS)
        self.records = RecordBook(native.RECORDS_PATH) if store else None
        self.page = 'game'           # 'game', 'settings' or 'records'
        self.draft = None            # the settings page's draft
        self.records_choice = (0, 0)  # (size index, level index) on Best times
        self.notes_mode = False      # the picker's Notes, kept as the player left it
        self.subtitle_text = ''
        self.motion = None           # played on the next game page only
        self.puzzle = None
        self.grid = None
        self.selected_cell = None    # the cell the picker is open for
        self.focus_cell = None       # highlighted with its row, column, box and number
        self.armed_value = None      # the tray number that cell taps place
        self.notes_armed = False     # with a number armed, cell taps toggle its note
        self.started = None
        self.solve_seconds = None
        self.run_result = None
        if not self.resume_saved_game():
            self.new_puzzle()

    # --- the shell's contract ------------------------------------------------

    def subtitle(self):
        return self.subtitle_text

    def toggle_settings(self):
        """⚙️: open Settings on a draft, or close it (and Best times) unsaved."""
        if self.page == 'game':
            self.selected_cell = None
            self.draft = dict(self.settings)
            self.sync_difficulty()
            self.page = 'settings'
        else:
            self.page = 'game'
            self.draft = None

    def go(self, payload):
        parts = payload.split('/')
        kind = parts[0]
        if kind == 'cell':
            self.cell_tapped((int(parts[1]), int(parts[2])))
        elif kind == 'bg':
            self.background_tapped()
        elif kind == 'pick':
            self.picker_tapped(parts[1])
        elif kind == 'tray':
            if parts[1] == 'notes':
                self.tray_notes_tapped()
            else:
                self.tray_tapped(int(parts[1]))
        elif kind == 'undo':
            self.undo_tapped()
        elif kind == 'new':
            self.new_puzzle()
        elif kind == 'set':
            self.settings_tapped(parts[1:])
        elif kind == 'rec':
            self.records_tapped(parts[1:])
        self.settle()

    def html(self):
        if self.page == 'settings':
            return self.settings_html()
        if self.page == 'records':
            return self.records_html()
        return self.game_html()

    # --- game flow (SudokuScreen) ---------------------------------------------

    @property
    def solved(self):
        return self.solve_seconds is not None

    def new_puzzle(self):
        puzzle = rules.generate_puzzle(self.settings['size'], self.settings['difficulty'])
        self.show_puzzle(puzzle, self.fresh_grid(puzzle), seconds_played=0)
        self.save_game()
        self.motion = ('build', random.choice(CORNERS))

    def fresh_grid(self, puzzle):
        return FillGrid(puzzle.size, givens=puzzle.givens_by_cell(),
                        units=rules.cell_units(puzzle.size))

    def show_puzzle(self, puzzle, grid, seconds_played):
        size = puzzle.size
        self.puzzle = puzzle
        self.grid = grid
        self.selected_cell = None
        self.focus_cell = None
        self.armed_value = None
        self.notes_armed = False
        self.run_result = None
        self.started = time.time() - seconds_played
        self.solve_seconds = None
        self.motion = None
        self.subtitle_text = '%d×%d · %s' % (size, size, native.LEVEL_LABELS.get(puzzle.level, 'Easy'))

    def save_game(self):
        if not self.store:
            return
        if self.solved:
            saved_game.discard_game(native.SAVE_PATH)
            return
        saved_game.save_game(native.SAVE_PATH, rules.puzzle_to_data(self.puzzle), self.grid,
                             time.time() - self.started, self.subtitle_text)

    def resume_saved_game(self):
        if not self.store:
            return False
        data = saved_game.load_game(native.SAVE_PATH)
        if data is None:
            return False
        try:
            puzzle = rules.puzzle_from_data(data['puzzle'])
            grid = self.fresh_grid(puzzle)
            saved_game.restore_marks(grid, data['marks'])
            seconds_played = float(data['seconds_played'])
        except (KeyError, IndexError, TypeError, ValueError) as error:
            print('Sudoku: ignoring saved game: {}'.format(error))
            return False
        if rules.is_solved(puzzle, grid.rows()):
            saved_game.discard_game(native.SAVE_PATH)
            return False
        self.show_puzzle(puzzle, grid, seconds_played)
        return True

    def settle(self):
        """SudokuScreen.refresh's rule: an armed number whose copies are all
        placed (or a solved puzzle) disarms, and Notes goes with it."""
        if self.grid is None:
            return
        remaining = self.remaining_by_value(self.grid.rows())
        if self.armed_value is not None and (
                self.solved or remaining.get(self.armed_value, 0) == 0):
            self.armed_value = None
        if self.armed_value is None:
            self.notes_armed = False

    def remaining_by_value(self, values):
        """How many more copies of each number the board needs. Wrong numbers
        count as placed, so the tray never hints at mistakes."""
        placed = {value: 0 for value in self.grid.allowed_values}
        for row in values:
            for value in row:
                if value in placed:
                    placed[value] += 1
        return {value: max(0, self.puzzle.size - count) for value, count in placed.items()}

    def solved_text(self):
        text = 'Solved in %s' % native.format_time(self.solve_seconds)
        result = self.run_result
        if result is None:
            return text
        if result.previous_best is None:
            return text + ' · first best time'
        if result.is_best:
            return text + ' · new best!'
        return text + ' · best %s' % native.format_time(result.previous_best)

    def puzzle_level(self):
        level = self.puzzle.level
        return level if level in (1, 2, 3) else 1

    def record_solve(self):
        if self.records is None:
            return
        key = native.best_times_key(self.puzzle.size, self.puzzle_level())
        try:
            self.run_result = self.records.add(key, self.solve_seconds)
        except OSError as error:
            print('Sudoku: best time not saved: {}'.format(error))

    # --- taps (SudokuScreen) ----------------------------------------------------

    def cell_tapped(self, cell):
        """A given highlights (again: lets go); an empty cell opens the picker
        (again: closes it); with a tray number armed, the tap places it."""
        if self.solved or cell is None:
            self.background_tapped()
            return
        if self.armed_value is not None:
            self.cell_tapped_while_armed(cell)
            return
        if self.grid.is_given(cell):
            self.focus_cell = None if cell == self.focus_cell else cell
            self.selected_cell = None
            return
        if cell == self.selected_cell:
            self.focus_cell = None
            self.selected_cell = None
            return
        self.selected_cell = cell
        self.focus_cell = cell

    def cell_tapped_while_armed(self, cell):
        if self.grid.is_given(cell):
            return
        if self.notes_armed:
            if self.grid.value_at(cell) is None:
                self.grid.toggle_note(cell, self.armed_value)
                self.save_game()
            return
        if self.grid.value_at(cell) == self.armed_value:
            self.grid.clear(cell)
            self.save_game()
            return
        self.place_value(cell, self.armed_value)

    def tray_tapped(self, value):
        """Arm a number (while copies remain), or disarm the armed one."""
        if self.solved:
            return
        remaining = self.remaining_by_value(self.grid.rows())
        if value != self.armed_value and remaining.get(value, 0) <= 0:
            return
        self.selected_cell = None
        self.focus_cell = None
        self.armed_value = None if value == self.armed_value else value

    def tray_notes_tapped(self):
        if self.solved or self.armed_value is None:
            return
        self.notes_armed = not self.notes_armed

    def background_tapped(self):
        """Beside the board: let go of the highlight, disarm, close the picker."""
        self.focus_cell = None
        self.armed_value = None
        self.selected_cell = None

    def picker_tapped(self, what):
        if what == 'notes':
            self.notes_mode = not self.notes_mode
        elif what == 'clear':
            self.value_picked(None)
        else:
            self.value_picked(int(what))

    def value_picked(self, value):
        cell = self.selected_cell
        if cell is None:
            return
        if value is None:
            self.grid.clear(cell)
            self.selected_cell = None
            self.save_game()
            return
        if self.notes_mode:
            self.grid.toggle_note(cell, value)       # the picker stays open
            self.save_game()
            return
        self.selected_cell = None
        self.place_value(cell, value)

    def place_value(self, cell, value):
        changed = self.grid.set_value(cell, value, clean_peer_notes=self.settings['tidy_notes'])
        just_solved = changed and rules.is_solved(self.puzzle, self.grid.rows())
        if just_solved:
            self.solve_seconds = time.time() - self.started
            self.record_solve()
        self.save_game()
        if just_solved:
            self.motion = ('celebrate', random.choice(CELEBRATION_STYLES), cell)

    def undo_tapped(self):
        self.selected_cell = None
        if not self.solved:
            self.grid.undo()
        self.save_game()

    # --- settings and best times ------------------------------------------------

    def sync_difficulty(self):
        offered = rules.DIFFICULTIES_BY_SIZE[self.draft['size']]
        if self.draft['difficulty'] not in offered:
            self.draft['difficulty'] = native.hardest_offered(self.draft['size'])

    def settings_tapped(self, parts):
        what = parts[0]
        if what == 'size':
            self.draft['size'] = rules.BOARD_SIZES[int(parts[1])]
            self.sync_difficulty()
        elif what == 'diff':
            difficulty = rules.DIFFICULTIES[int(parts[1])]
            if difficulty in rules.DIFFICULTIES_BY_SIZE[self.draft['size']]:
                self.draft['difficulty'] = difficulty
        elif what == 'toggle':
            self.draft[parts[1]] = not self.draft[parts[1]]
        elif what in ('new', 'done'):
            if self.apply_settings(self.draft, force_new_puzzle=what == 'new'):
                self.page = 'game'
                self.draft = None
        elif what == 'best':
            self.records_choice = native.records_selection(self.puzzle.size, self.puzzle_level())
            self.settle_records()
            self.page = 'records'

    def apply_settings(self, draft, force_new_puzzle=False):
        if draft['difficulty'] not in rules.DIFFICULTIES_BY_SIZE.get(draft['size'], ()):
            return False
        previous = self.settings
        self.settings = dict(draft)
        if (force_new_puzzle or self.settings['size'] != previous['size']
                or self.settings['difficulty'] != previous['difficulty']):
            self.new_puzzle()
        if self.settings != previous and self.store:
            native.save_settings(self.settings)
        return True

    def settle_records(self):
        """RecordsPanel's rule: a faded level moves to the last level offered."""
        size_index, level_index = self.records_choice
        enabled = native.records_enabled_for(self.records_choice)[1]
        if not enabled[level_index]:
            level_index = max(index for index, on in enumerate(enabled) if on)
        self.records_choice = (size_index, level_index)

    def records_tapped(self, parts):
        what = parts[0]
        size_index, level_index = self.records_choice
        if what == 'size':
            self.records_choice = (int(parts[1]), level_index)
            self.settle_records()
        elif what == 'level':
            if native.records_enabled_for(self.records_choice)[1][int(parts[1])]:
                self.records_choice = (size_index, int(parts[1]))
        elif what == 'back':
            self.page = 'settings'

    # --- pages -------------------------------------------------------------------

    def game_html(self):
        motion, self.motion = self.motion, None
        puzzle, grid = self.puzzle, self.grid
        size = puzzle.size
        box_rows, box_cols = rules.BOX_SHAPES[size]
        values = grid.rows()
        solved = self.solved
        show = self.settings
        conflicts = grid.conflicts() if show['show_mistakes'] and not solved else set()
        focus = self.focus_cell if show['highlight'] and not solved else None
        completed = set(grid.completed_values()) if show['highlight_complete'] and not solved else set()
        if self.armed_value is not None:
            match = self.armed_value
        elif focus is not None:
            match = values[focus[0]][focus[1]]
        else:
            match = None
        givens = set(puzzle.givens_by_cell())

        board_style = '--n:%d;--br:%d;--bc:%d;' % (size, box_rows, box_cols)
        building = motion is not None and motion[0] == 'build'
        celebrating = motion if motion is not None and motion[0] == 'celebrate' else None
        build = self.build_timing(motion[1], size, givens) if building else None
        if building:
            corner = motion[1]
            board_style += '--ax:%d;--ay:%d;' % (1 if corner[0] == 't' else -1,
                                                 1 if corner[1] == 'l' else -1)

        cells = []
        for row in range(size):
            for col in range(size):
                cell = (row, col)
                value = values[row][col]
                given = cell in givens
                classes = ['sd-cell']
                classes.append('cl' if col == size - 1 else 'wr' if (col + 1) % box_cols == 0 else '')
                classes.append('rl' if row == size - 1 else 'wb' if (row + 1) % box_rows == 0 else '')
                if match is not None and value == match:
                    classes.append('match')
                elif focus is not None and (
                        row == focus[0] or col == focus[1]
                        or (row // box_rows, col // box_cols) == (focus[0] // box_rows, focus[1] // box_cols)):
                    classes.append('peer')
                if cell == self.selected_cell:
                    classes.append('sel')
                style = ''
                if solved and value is not None:
                    classes.append('cel')
                    style += '--cc:var(--mg-cel-%d, var(--mg-tile));' % (
                        (value - 1) % max(1, self.celebration_count))
                    if celebrating is not None:
                        classes.append('anim')
                        style += '--d:%.2fs;' % self.celebration_delay(celebrating, cell, size)
                if build is not None:
                    fold, pop = build.get(cell, (0, 0))
                    style += '--d:%.2fs;--p:%.2fs;' % (fold, pop)
                if value is not None:
                    if solved:
                        ink = 'ok'
                    elif cell in conflicts and not given:
                        ink = 'bad'
                    elif value in completed:
                        ink = 'done'
                    else:
                        ink = 'given' if given else 'mine'
                    inner = '<span class="sd-v %s%s">%d</span>' % (ink, ' g' if given else '', value)
                else:
                    noted = grid.notes_at(cell)
                    inner = ''
                    if noted:
                        marks = []
                        for note in range(1, size + 1):
                            if note in noted:
                                marks.append('<span%s>%d</span>' % (' class="m"' if note == match else '', note))
                            else:
                                marks.append('<span></span>')
                        inner = '<div class="sd-notes">%s</div>' % ''.join(marks)
                cells.append('<div class="%s" style="%s" data-go="cell/%d/%d">%s</div>'
                             % (' '.join(name for name in classes if name), style, row, col, inner))

        if solved:
            status = '<div class="sd-status ok">%s</div>' % self.solved_text()
        else:
            status = ('<div class="sd-status">Each row, column and box holds 1 to %d · %d to fill</div>'
                      % (size, len(grid.empty_cells())))
        if self.selected_cell is not None and not solved:
            lower = self.picker_html()
        else:
            lower = self.tray_html(values)
        undo_on = grid.can_undo() and not solved
        wrap_style = ''
        if build is not None:
            wrap_style = '--sw:%.2fs;' % build['swell']
        return ('<div class="sd-screen" data-go="bg">%s'
                '<div class="sd-wrap%s" style="%s"><div class="sd-board%s" style="%s">%s</div></div>'
                '%s<div class="sd-buttons">'
                '<div class="mg-button%s"%s>Undo</div>'
                '<div class="mg-button" data-go="new">New puzzle</div></div></div>'
                % (status, ' bld' if building else '', wrap_style, ' bld' if building else '',
                   board_style, ''.join(cells), lower,
                   '' if undo_on else ' off', ' data-go="undo"' if undo_on else ''))

    def build_timing(self, corner, size, givens):
        """{cell: (fold delay, pop delay)} and 'swell': squares unfold out
        from corner across BUILD_SPREAD_SECONDS; then the givens pop in from
        the finishing corner (the one nearest the last square), a step apart
        within NUMBER_SPREAD_SECONDS; then the board swells."""
        start_row = 0 if corner[0] == 't' else size - 1
        start_col = 0 if corner[1] == 'l' else size - 1
        reach = max(1, 2 * (size - 1))
        timing = {}
        for row in range(size):
            for col in range(size):
                distance = abs(row - start_row) + abs(col - start_col)
                timing[(row, col)] = (BUILD_SPREAD_SECONDS * distance / reach, 0)
        unfolded = BUILD_SPREAD_SECONDS + BUILD_FOLD_SECONDS
        end_row, end_col = size - 1 - start_row, size - 1 - start_col
        order = sorted(givens, key=lambda cell: (abs(cell[0] - end_row) + abs(cell[1] - end_col),
                                                 random.random()))
        step = min(NUMBER_STEP_SECONDS, NUMBER_SPREAD_SECONDS / max(1, len(order)))
        for index, cell in enumerate(order):
            timing[cell] = (timing[cell][0], unfolded + index * step)
        timing['swell'] = unfolded + len(order) * step + NUMBER_POP_SECONDS
        return timing

    def celebration_delay(self, celebration, cell, size):
        _, style, origin = celebration
        reach = max(1, size - 1)
        if style == 'ripple':
            share = max(abs(cell[0] - origin[0]), abs(cell[1] - origin[1])) / float(reach)
        elif style == 'sweep':
            share = (cell[0] + cell[1]) / float(2 * reach)
        else:
            share = random.random()
        return CELEBRATION_SPREAD_SECONDS * share

    def picker_html(self):
        """CellPicker.show_below: the numbers, then Notes and Clear."""
        cell = self.selected_cell
        grid = self.grid
        values = tuple(grid.allowed_values)
        count = max(1, len(values))
        columns = count if count <= PICKER_COLUMNS else int(math.ceil(count / 2.0))
        current = grid.value_at(cell)
        notes = set(grid.notes_at(cell))
        completed = set(grid.completed_values())
        buttons = []
        for value in values:
            if self.notes_mode:
                look = 'noted' if value in notes else 'done' if value in completed else ''
            else:
                look = 'cur' if value == current else 'done' if value in completed else ''
            buttons.append('<div class="sd-pk %s" data-go="pick/%d">%d</div>' % (look, value, value))
        return ('<div class="sd-picker" data-go="none" style="--cols:%d">'
                '<div class="sd-pick-grid">%s</div><div class="sd-pick-row">'
                '<div class="%s" data-go="pick/notes">Notes</div>'
                '<div data-go="pick/clear">Clear</div></div></div>'
                % (columns, ''.join(buttons), 'on' if self.notes_mode else ''))

    def tray_html(self, values):
        """NumberTray: a slot per number (bars for what is left) and the Notes
        slot, always reserved, drawn while a number is armed."""
        remaining = self.remaining_by_value(values)
        numbers = tuple(self.grid.allowed_values)
        count = len(numbers) + 1
        rows = int(math.ceil(count / float(TRAY_PER_ROW)))
        per_row = int(math.ceil(count / float(rows)))
        slots = []
        for value in numbers:
            left = remaining.get(value, 0)
            armed = value == self.armed_value
            tappable = armed or left > 0
            tile = 'sd-tile' + (' armed' if armed else '') + (' done' if left == 0 and not armed else '')
            slots.append('<div class="sd-slot%s"%s><div class="sd-stack">%s</div>'
                         '<div class="%s">%d</div></div>'
                         % (' armed' if armed else '',
                            ' data-go="tray/%d"' % value if tappable else ' data-go="none"',
                            '<i></i>' * left, tile, value))
        if self.armed_value is not None:
            slots.append('<div class="sd-slot" data-go="tray/notes"><div class="sd-chip%s">Notes</div></div>'
                         % (' on' if self.notes_armed else ''))
        else:
            slots.append('<div class="sd-slot" data-go="none"></div>')
        return '<div class="sd-tray" data-go="none" style="--per:%d">%s</div>' % (per_row, ''.join(slots))

    def settings_html(self):
        draft = self.draft
        size = draft['size']
        offered = rules.DIFFICULTIES_BY_SIZE[size]
        sizes = ''.join('<div class="mg-chip%s" data-go="set/size/%d">%s</div>'
                        % (' on' if rules.BOARD_SIZES[index] == size else '', index, label)
                        for index, label in enumerate(native.SIZE_LABELS))
        levels = []
        for index, difficulty in enumerate(rules.DIFFICULTIES):
            label = native.DIFFICULTY_LABELS[index]
            if difficulty not in offered:
                levels.append('<div class="mg-chip off">%s</div>' % label)
            else:
                levels.append('<div class="mg-chip%s" data-go="set/diff/%d">%s</div>'
                              % (' on' if difficulty == draft['difficulty'] else '', index, label))
        if len(offered) == len(rules.DIFFICULTIES):
            note = ''
        else:
            note = '%d×%d goes up to %s' % (size, size, native.DIFFICULTY_LABELS[
                rules.DIFFICULTIES.index(offered[-1])])
        switches = ''.join('<div class="sd-setting" data-go="set/toggle/%s"><span>%s</span>'
                           '<div class="sd-switch%s"><b></b></div></div>'
                           % (key, label, ' on' if draft[key] else '') for key, label in SWITCHES)
        return ('<div class="sd-settings"><div class="mg-title">Settings</div>'
                '<div class="mg-caption">Board size</div><div class="mg-chips">%s</div>'
                '<div class="mg-caption">Difficulty: the hardest technique needed</div>'
                '<div class="mg-chips">%s</div><div class="mg-note">%s</div>%s'
                '<div class="mg-button primary sd-gap" data-go="set/new">New puzzle</div>'
                '<div class="mg-row sd-gap-small"><div class="mg-button" data-go="set/best">Best times</div>'
                '<div class="mg-button" data-go="set/done">Done</div></div></div>'
                % (sizes, ''.join(levels), note, switches))

    def records_html(self):
        size_index, level_index = self.records_choice
        enabled = native.records_enabled_for(self.records_choice)[1]
        sizes = ''.join('<div class="mg-chip%s" data-go="rec/size/%d">%s</div>'
                        % (' on' if index == size_index else '', index, label)
                        for index, label in enumerate(native.SIZE_LABELS))
        levels = ''.join(
            '<div class="mg-chip off">%s</div>' % label if not enabled[index] else
            '<div class="mg-chip%s" data-go="rec/level/%d">%s</div>'
            % (' on' if index == level_index else '', index, label)
            for index, label in enumerate(native.DIFFICULTY_LABELS))
        runs = []
        if self.records is not None:
            runs = self.records.top(native.records_key_for(self.records_choice))
        if runs:
            rows = ''.join('<div class="sd-run"><span>%d</span><b>%s</b><em>%s</em></div>'
                           % (index, native.format_time(run['seconds']), when_text(run.get('when')))
                           for index, run in enumerate(runs, 1))
        else:
            rows = '<div class="mg-note">%s</div>' % NO_RECORDS
        return ('<div class="sd-settings"><div class="mg-title">Best times</div>'
                '<div class="mg-caption">Board size</div><div class="mg-chips">%s</div>'
                '<div class="mg-caption">Level</div><div class="mg-chips">%s</div>'
                '<div class="sd-runs">%s</div>'
                '<div class="mg-button sd-gap" data-go="rec/back">Back to settings</div></div>'
                % (sizes, levels, rows))


CSS = """
.sd-screen { --bw: min(calc(100vw - 28px), 444px); padding-bottom: 12px;
    font-family: "Avenir Next", -apple-system, sans-serif;
    -webkit-user-select: none; -webkit-touch-callout: none;
    -webkit-tap-highlight-color: transparent; }
.sd-status { color: var(--mg-muted); font-size: 15px; font-weight: 500; text-align: center;
    min-height: 22px; margin: 4px 0 8px 0; }
.sd-status.ok { color: var(--mg-success); }
.sd-wrap { width: var(--bw); margin: 0 auto; }
.sd-board { display: grid; grid-template-columns: repeat(var(--n), 1fr); width: 100%;
    background: var(--mg-board); border: 3px solid var(--mg-box_wall); box-sizing: border-box; }
.sd-cell { position: relative; aspect-ratio: 1 / 1; display: flex; align-items: center;
    justify-content: center; box-sizing: border-box; cursor: pointer;
    border-right: 1px solid var(--mg-grid_line); border-bottom: 1px solid var(--mg-grid_line); }
.sd-cell.cl { border-right: none; }
.sd-cell.rl { border-bottom: none; }
.sd-cell.wr { border-right: 3px solid var(--mg-box_wall); }
.sd-cell.wb { border-bottom: 3px solid var(--mg-box_wall); }
.sd-cell.peer { background: var(--mg-assist_peer); }
.sd-cell.match { background: var(--mg-assist_match); }
.sd-cell.sel { background: var(--mg-selection_fill); box-shadow: inset 0 0 0 3px var(--mg-selection); }
.sd-v { position: relative; font-size: calc(var(--bw) / var(--n) * 0.6); font-weight: 500; line-height: 1; }
.sd-v.g { font-weight: 700; }
.sd-v.given { color: var(--mg-given); }
.sd-v.mine { color: var(--mg-player_number); }
.sd-v.done, .sd-v.ok { color: var(--mg-success); }
.sd-v.bad { color: var(--mg-mistake); }
.sd-notes { position: absolute; inset: 0; display: grid;
    grid-template-columns: repeat(var(--bc), 1fr); grid-template-rows: repeat(var(--br), 1fr); }
.sd-notes span { display: flex; align-items: center; justify-content: center;
    font-size: max(8px, calc(var(--bw) / var(--n) * 0.26)); font-weight: 500; color: var(--mg-note); }
.sd-notes span.m { color: var(--mg-sky); }

.sd-cell.cel::before { content: ''; position: absolute; inset: 1.5px; border-radius: 4px;
    background: var(--cc); opacity: 0.55; }
.sd-cell.cel .sd-v { color: var(--mg-given); }
.sd-cell.cel.anim::before { animation: sd-cel-fill 0.5s ease-out both; animation-delay: var(--d); }
.sd-cell.cel.anim .sd-v { animation: sd-cel-ink 0.5s ease-out both; animation-delay: var(--d); }
@keyframes sd-cel-fill { 0% { opacity: 0; transform: scale(0.2); }
    60% { opacity: 0.7; transform: scale(1.08); } 100% { opacity: 0.55; transform: scale(1); } }
@keyframes sd-cel-ink { 0% { color: var(--mg-success); } 100% { color: var(--mg-given); } }

.sd-board.bld .sd-cell { animation: sd-unfold 0.45s ease-out both; animation-delay: var(--d); }
.sd-board.bld .sd-v.given { animation: sd-pop 0.36s cubic-bezier(0.34, 1.7, 0.5, 1) both;
    animation-delay: var(--p); }
.sd-wrap.bld { animation: sd-swell 0.45s ease-in-out both; animation-delay: var(--sw); }
@keyframes sd-unfold { 0% { opacity: 0; transform: perspective(400px) rotate3d(var(--ax), var(--ay), 0, 90deg); }
    100% { opacity: 1; transform: none; } }
@keyframes sd-pop { 0% { transform: scale(0); } 100% { transform: scale(1); } }
@keyframes sd-swell { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.04); } }

.sd-picker { width: fit-content; min-width: 200px; margin: 10px auto 0 auto; padding: 8px;
    border-radius: 14px; background: var(--mg-surface); border: 1px solid var(--mg-muted);
    box-sizing: border-box; }
.sd-pick-grid { display: grid; grid-template-columns: repeat(var(--cols), 48px); gap: 6px;
    justify-content: center; }
.sd-pk { height: 48px; border-radius: 10px; background: var(--mg-button); color: var(--mg-text);
    display: flex; align-items: center; justify-content: center; font-size: 22px;
    font-weight: 500; cursor: pointer; }
.sd-pk.cur { background: var(--mg-tile); color: var(--mg-background); }
.sd-pk.noted { background: var(--mg-sky); color: var(--mg-background); }
.sd-pk.done { color: var(--mg-success); }
.sd-pick-row { display: flex; gap: 6px; margin-top: 6px; }
.sd-pick-row div { flex: 1; height: 36px; border-radius: 10px; background: var(--mg-button);
    color: var(--mg-text); display: flex; align-items: center; justify-content: center;
    font-size: 15px; font-weight: 500; cursor: pointer; }
.sd-pick-row div.on { background: var(--mg-sky); color: var(--mg-background); }

.sd-tray { width: var(--bw); margin: 10px auto 0 auto; display: flex; flex-wrap: wrap;
    justify-content: center; gap: 8px 6px; }
.sd-slot { width: min(72px, calc((var(--bw) - (var(--per) - 1) * 6px) / var(--per)));
    height: 52px; display: flex; align-items: center; justify-content: center; cursor: pointer; }
.sd-stack { width: 16px; height: 46px; margin-right: -5px; display: flex;
    flex-direction: column-reverse; gap: 1.5px; padding-bottom: 2px; box-sizing: border-box; }
.sd-stack i { display: block; height: 3px; border-radius: 1.5px; background: var(--mg-grid_line); }
.sd-slot.armed .sd-stack i { background: var(--mg-selection); }
.sd-tile { position: relative; width: 46px; height: 46px; border-radius: 9px; box-sizing: border-box;
    background: var(--mg-board); border: 1px solid var(--mg-grid_line); color: var(--mg-player_number);
    display: flex; align-items: center; justify-content: center; font-size: 26px; font-weight: 600; }
.sd-tile.armed { background: var(--mg-selection_fill); border: 2px solid var(--mg-selection); }
.sd-tile.done { color: var(--mg-success); }
.sd-chip { width: 64px; height: 46px; border-radius: 9px; box-sizing: border-box;
    background: var(--mg-board); border: 1px solid var(--mg-grid_line); color: var(--mg-note);
    display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; }
.sd-chip.on { background: var(--mg-selection_fill); border: 2px solid var(--mg-selection);
    color: var(--mg-player_number); }

.sd-buttons { display: flex; gap: 12px; justify-content: center; margin-top: 16px; }
.sd-buttons .mg-button { width: min(160px, calc((var(--bw) - 12px) / 2)); }

.sd-settings { max-width: 320px; margin: 0 auto; padding-top: 8px; }
.sd-setting { display: flex; align-items: center; gap: 12px; min-height: 44px; margin-top: 12px;
    font-size: 15px; font-weight: 500; cursor: pointer; }
.sd-setting span { flex: 1; }
.sd-switch { position: relative; width: 51px; height: 31px; border-radius: 16px; flex: 0 0 auto;
    background: var(--mg-button); transition: background 0.2s; }
.sd-switch b { position: absolute; top: 2px; left: 2px; width: 27px; height: 27px; border-radius: 14px;
    background: #FFFFFF; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3); transition: left 0.2s; }
.sd-switch.on { background: #34C759; }
.sd-switch.on b { left: 22px; }
.sd-gap { margin-top: 24px; }
.sd-gap-small { margin-top: 12px; }
.sd-runs { margin-top: 18px; }
.sd-run { display: flex; align-items: baseline; gap: 12px; height: 30px; font-size: 16px; }
.sd-run span { width: 24px; color: var(--mg-muted); }
.sd-run b { width: 70px; }
.sd-run em { font-style: normal; color: var(--mg-muted); font-size: 14px; }
"""

# The shell reads these from the game it hosts.
Game.CSS = CSS
Game.THEME_TOKENS = THEME_TOKENS