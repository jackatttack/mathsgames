"""Multiple Merge-specific TileKit presentation and fixed-board input."""

import time

import ui

from style import theme
from tilekit.input import PointerEvent
from tilekit.renderers import (
    TileRenderer,
    default_renderer_registry,
)
from tilekit.ui_board import UIBoardView

from .board_state import BoardState, format_value
from .model import (
    NUMBER_SELECTED,
    OPERATION_ARMED,
    PendingMove,
)


# Colours come from the shared Maths Games theme.
TILE_COLOR = theme.color("tile")
TEXT_COLOR = theme.color("tile_text")

OP_COLORS = {
    "+": theme.color("op_add"),
    "-": theme.color("op_subtract"),
    "×": theme.color("op_multiply"),
    "/": theme.color("op_divide"),
}

OP_SYMBOLS = {
    "+": "+",
    "-": "−",
    "×": "×",
    "/": "÷",
}


# --- editable look of the operation quadrants ---------------------------
QUADRANT_ALPHA = 0.88      # 1.0 is the solid operation colour
QUADRANT_GAP = 3           # points of tile colour between quadrants
CENTRE_DISC_RATIO = 0.32   # disc radius as a fraction of the tile side;
                           # tapping the disc deselects the tile


def _hex_rgba(value, alpha=1.0):
    text = str(value or "#000000").lstrip("#")

    if len(text) != 6:
        return (0, 0, 0, alpha)

    return (
        int(text[0:2], 16) / 255.0,
        int(text[2:4], 16) / 255.0,
        int(text[4:6], 16) / 255.0,
        alpha,
    )


class MultipleMergeNumberView(ui.View):
    """Large number tile that splits into operation quadrants when selected."""

    def __init__(self, obj, renderer, frame=(0, 0, 120, 120)):
        super().__init__(frame=frame)

        self.obj = obj
        self.renderer = renderer
        self.touch_enabled = False
        self.background_color = "clear"

        self.number_label = ui.Label()
        self.number_label.alignment = ui.ALIGN_CENTER
        self.number_label.font = (
            "AvenirNext-Bold",
            38,
        )
        self.number_label.text_color = TEXT_COLOR
        self.number_label.background_color = "clear"

        try:
            self.number_label.touch_enabled = False
        except Exception:
            pass

        self.add_subview(self.number_label)

        self.op_labels = {}

        for operation in ("+", "-", "×", "/"):
            label = ui.Label()
            label.text = OP_SYMBOLS[operation]
            label.alignment = ui.ALIGN_CENTER
            label.font = (
                "AvenirNext-Bold",
                18,
            )
            label.text_color = "#FFFFFF"
            label.background_color = "clear"
            label.hidden = True

            try:
                label.touch_enabled = False
            except Exception:
                pass

            self.add_subview(label)
            self.op_labels[operation] = label

    def layout(self):
        self.number_label.frame = self.bounds

        side = min(
            self.width,
            self.height,
        )

        label_size = max(
            24,
            min(34, side * 0.24),
        )

        inset = max(
            8,
            side * 0.055,
        )

        self.op_labels["+"].frame = (
            inset + 5,
            inset + 5,
            label_size,
            label_size,
        )

        self.op_labels["-"].frame = (
            self.width - inset - label_size - 5,
            inset + 5,
            label_size,
            label_size,
        )

        self.op_labels["×"].frame = (
            inset + 5,
            self.height - inset - label_size - 5,
            label_size,
            label_size,
        )

        self.op_labels["/"].frame = (
            self.width - inset - label_size - 5,
            self.height - inset - label_size - 5,
            label_size,
            label_size,
        )

        # Operation symbols scale with the tile so they read on the quadrants.
        for label in self.op_labels.values():
            label.font = ("AvenirNext-Bold", label_size * 0.8)

        # Shrink longer text such as "21/2×" so it stays inside the tile.
        characters = max(1, len(self.number_label.text or ""))
        font_size = max(
            18,
            min(80, side * 0.42, side * 1.3 / characters),
        )

        self.number_label.font = (
            "AvenirNext-Bold",
            font_size,
        )

    def _draw_operation_quadrants(self, tile_path, tile_color):
        """Fill the four quadrants with operation colours around a centre disc.

        Quadrant positions must match operation_at_screen_point:
        + top-left, - top-right, × bottom-left, ÷ bottom-right.
        """
        w = self.width
        h = self.height
        half_w = w / 2
        half_h = h / 2

        quadrant_origins = {
            "+": (0, 0),
            "-": (half_w, 0),
            "×": (0, half_h),
            "/": (half_w, half_h),
        }

        with ui.GState():
            tile_path.add_clip()

            for operation, (x, y) in quadrant_origins.items():
                ui.set_color(_hex_rgba(OP_COLORS[operation], QUADRANT_ALPHA))
                ui.Path.rect(x, y, half_w, half_h).fill()

            # Thin tile-coloured seams keep the four choices distinct.
            seams = ui.Path()
            seams.move_to(half_w, 0)
            seams.line_to(half_w, h)
            seams.move_to(0, half_h)
            seams.line_to(w, half_h)
            seams.line_width = QUADRANT_GAP
            ui.set_color(_hex_rgba(tile_color))
            seams.stroke()

        radius = self._centre_disc_radius()
        disc = ui.Path.oval(
            half_w - radius,
            half_h - radius,
            radius * 2,
            radius * 2,
        )
        ui.set_color(_hex_rgba(tile_color))
        disc.fill()

    def _centre_disc_radius(self):
        """Radius of the number disc, shared by drawing and hit-testing."""
        return min(self.width, self.height) * CENTRE_DISC_RATIO

    def draw(self):
        meta = getattr(self.obj, "meta", {}) or {}

        w = self.width
        h = self.height

        if w <= 1 or h <= 1:
            return

        corner = max(18, min(28, min(w, h) * 0.15))

        armed = meta.get("mm_armed_op")
        valid = bool(meta.get("mm_valid_target"))
        selected = bool(meta.get("mm_selected"))
        show_all = bool(meta.get("mm_show_ops"))

        tile_color = meta.get("color") or TILE_COLOR
        base = OP_COLORS.get(armed) if armed else tile_color

        tile = ui.Path.rounded_rect(0, 0, w, h, corner)
        ui.set_color(_hex_rgba(base))
        tile.fill()

        # Four-choice state: the tile splits into operation quadrants.
        # An armed tile is already filled with its operation colour.
        if show_all and not armed:
            self._draw_operation_quadrants(tile, tile_color)

        # Soft glossy sweep: enough depth to feel tactile without bringing
        # back the heavier TileCalc chrome.
        with ui.GState():
            tile.add_clip()

            gloss = ui.Path()
            gloss.move_to(0, 0)
            gloss.line_to(w, 0)
            gloss.line_to(w, h * 0.33)
            gloss.add_curve(
                w * 0.58,
                h * 0.43,
                w * 0.18,
                h * 0.38,
                0,
                h * 0.29,
            )
            gloss.close()

            ui.set_color((1, 1, 1, 0.18))
            gloss.fill()

        border_width = 4 if valid else 2

        if valid:
            border_color = "#F7F9FC"
        elif selected and armed:
            border_color = "#FFFFFF"
        else:
            border_color = "#FFFFFF36"

        border = ui.Path.rounded_rect(
            border_width / 2,
            border_width / 2,
            max(1, w - border_width),
            max(1, h - border_width),
            max(0, corner - border_width / 2),
        )

        border.line_width = border_width
        ui.set_color(_hex_rgba(border_color))
        border.stroke()

    def operation_at_screen_point(self, point):
        """Return the operation whose quadrant contains point, otherwise None.

        The centre disc is not an operation: a tap there falls through to
        the normal number tap, which deselects the tile.
        """
        meta = getattr(self.obj, "meta", {}) or {}

        show_all = bool(meta.get("mm_show_ops"))
        active = meta.get("mm_armed_op")

        if not show_all and not active:
            return None

        local_x = point[0] - self.x
        local_y = point[1] - self.y

        centre_x = self.width / 2
        centre_y = self.height / 2

        dx = local_x - centre_x
        dy = local_y - centre_y

        if dx * dx + dy * dy <= self._centre_disc_radius() ** 2:
            return None

        top = local_y < centre_y
        left = local_x < centre_x

        if top and left:
            operation = "+"
        elif top:
            operation = "-"
        elif left:
            operation = "×"
        else:
            operation = "/"

        if show_all:
            return operation

        if operation == active:
            return operation

        return None


class MultipleMergeNumberRenderer(TileRenderer):
    """Mounts one MultipleMergeNumberView and keeps it in step with its tile.

    Frames come from obj.position (the tile centre) and obj.size, which
    MultipleMergeBoardView sets during layout. TileKit's cell-span sizing is
    deliberately not used: the game owns its responsive grid.
    """

    renderer_id = "multiple_merge_number"

    def __init__(self):
        self.view = None

    def mount(self, board_view, obj):
        self.view = MultipleMergeNumberView(obj, self)
        board_view.add_subview(self.view)
        self.update(obj)
        return self.view

    def update(self, obj):
        view = self.view

        if view is None or obj is None or getattr(view, "obj", None) is None:
            return

        meta = getattr(obj, "meta", {}) or {}

        x, y = obj.position or (0, 0)
        width, height = obj.size or (120, 120)

        coords = getattr(getattr(view.superview, "board", None), "coords", None)
        if coords is not None:
            x, y = coords.to_screen((x, y))
            width = coords.screen_length(width)
            height = coords.screen_length(height)

        view.frame = (x - width / 2, y - height / 2, width, height)
        view.hidden = bool(meta.get("mm_empty"))

        display = meta.get("display")
        if display is None:
            display = obj.label or ""
        armed = meta.get("mm_armed_op")
        if armed:
            display = "{}{}".format(display, OP_SYMBOLS.get(armed, armed))
        view.number_label.text = str(display)

        show_all = bool(meta.get("mm_show_ops"))
        armed = meta.get("mm_armed_op")
        for label in view.op_labels.values():
            label.hidden = not show_all

        view.alpha = 0.34 if meta.get("mm_dimmed") else 1.0

        view.layout()
        view.set_needs_display()


def multiple_merge_renderer_registry():
    registry = default_renderer_registry()

    registry.register(
        "multiple_merge_number",
        MultipleMergeNumberRenderer,
    )

    return registry


def board_state_from_tiles(tiles):
    """Build a BoardState from number tiles carrying row, col and value meta.

    Tile meta "value" is only the starting value. Once play begins the
    BoardState owns live values and tiles show meta "display".
    """
    placed = {}

    for tile in tiles:
        if getattr(tile, "kind", None) != "number":
            continue
        meta = getattr(tile, "meta", {}) or {}
        placed[(int(meta["row"]), int(meta["col"]))] = meta["value"]

    rows = 1 + max(row for row, _ in placed)
    cols = 1 + max(col for _, col in placed)

    return BoardState(
        [[placed.get((row, col)) for col in range(cols)] for row in range(rows)]
    )


class MultipleMergeBoardView(UIBoardView):
    """Fixed board whose layout, taps and merges belong to Multiple Merge.

    BoardState is the source of truth for values. Each cell keeps one
    persistent TileKit object; an emptied cell hides its tile.

    Every move follows the same order:
        decide in the model -> animate -> sync visuals from the model.
    """

    # --- editable layout, in points -----------------------------------
    BOARD_MARGIN = 16
    TILE_GAP = 12

    # --- editable feel, in seconds ------------------------------------
    SLIDE_SECONDS = 0.30
    POP_SECONDS = 0.10
    SETTLE_SECONDS = 0.16
    POP_SCALE = 1.12
    DOUBLE_TAP_SECONDS = 0.35

    def __init__(self, *args, **kwargs):
        # Set before TileKit's constructor, which calls layout().
        self.pending_move = PendingMove()
        self.board_state = None
        self.resolving = False
        self._empty_tap_time = None

        # Set by the screen: called with each committed MoveResult.
        self.on_move_committed = None

        kwargs["interaction_mode"] = "fixed"
        kwargs["renderer_registry"] = (
            kwargs.get("renderer_registry")
            or multiple_merge_renderer_registry()
        )

        super().__init__(*args, **kwargs)

        self.board_state = board_state_from_tiles(self.board.objects)
        self.board.show_grid = False

        # Multiple Merge supplies its own chrome.
        for name in ("_status", "_action_dock", "_palette_dock", "_spawn_cursor"):
            view = getattr(self, name, None)
            if view is not None:
                view.hidden = True

        self.sync_from_state()
        self.layout()

    # --- tiles ---------------------------------------------------------

    def _all_number_tiles(self):
        return [
            tile for tile in self.board.objects
            if getattr(tile, "kind", None) == "number"
        ]

    def _number_objects(self):
        """Number tiles whose cells currently hold a value."""
        return [
            tile for tile in self._all_number_tiles()
            if not tile.meta.get("mm_empty")
        ]

    def _tile_by_id(self, tile_id):
        for tile in self._all_number_tiles():
            if tile.id == tile_id:
                return tile
        return None

    @staticmethod
    def _cell_of(tile):
        return (int(tile.meta["row"]), int(tile.meta["col"]))

    @staticmethod
    def _view_of(tile):
        return getattr(getattr(tile, "renderer", None), "view", None)

    def tile_at_point(self, point):
        """Return the visible number tile whose drawn frame contains point."""
        px, py = point
        for tile in self._number_objects():
            view = self._view_of(tile)
            if view is None:
                continue
            if view.x <= px <= view.x + view.width and view.y <= py <= view.y + view.height:
                return tile
        return None

    # --- layout --------------------------------------------------------

    def layout(self):
        """Size and place tiles from the view's own width and height."""
        super().layout()

        if self.board_state is None or self.width <= 1 or self.height <= 1:
            return

        # Repositioning mid-merge would snap the sliding tile back to its cell.
        if self.resolving:
            return

        rows = self.board_state.rows
        cols = self.board_state.cols
        margin = self.BOARD_MARGIN
        gap = self.TILE_GAP

        side = min(
            (self.width - 2 * margin - (cols - 1) * gap) / cols,
            (self.height - 2 * margin - (rows - 1) * gap) / rows,
        )
        side = max(1, side)

        board_width = cols * side + (cols - 1) * gap
        left = (self.width - board_width) / 2
        top = margin

        coords = self.board.coords
        world_side = coords.world_length(side)

        for tile in self._all_number_tiles():
            row, col = self._cell_of(tile)
            centre = (
                left + col * (side + gap) + side / 2,
                top + row * (side + gap) + side / 2,
            )
            tile.position = coords.from_screen(centre)
            tile.size = (world_side, world_side)
            tile._notify_renderer()

    # --- visuals -------------------------------------------------------

    def sync_from_state(self):
        """Refresh every tile from BoardState, then reapply move visuals."""
        for tile in self._all_number_tiles():
            value = self.board_state.value_at(self._cell_of(tile))
            tile.meta["mm_empty"] = value is None
            if value is not None:
                tile.meta["display"] = format_value(value)
            tile._notify_renderer()

        self.apply_move_visuals()

    def _tile_at_cell(self, cell):
        for tile in self._all_number_tiles():
            if self._cell_of(tile) == tuple(cell):
                return tile
        return None

    def hint_step(self, source_cell, operation, destination_cell):
        """Show or play one hinted move.

        If the source is not yet armed with this operation, arm it so the
        player sees which tile and operation come next ("shown"). If it is
        already armed, play the move onto the destination ("played").
        Returns "busy" while a merge is animating.
        """
        if self.resolving:
            return "busy"

        source = self._tile_at_cell(source_cell)
        destination = self._tile_at_cell(destination_cell)

        if source is None or destination is None:
            return "busy"

        self._empty_tap_time = None
        move = self.pending_move

        already_armed = (
            move.mode == OPERATION_ARMED
            and move.selected_id == source.id
            and move.operation == operation
        )

        if already_armed:
            self.resolve_move(destination)
            return "played"

        move.select(source.id)
        move.choose_operation(operation)
        self.apply_move_visuals()
        return "shown"

    def load_board_state(self, board_state):
        """Show a different BoardState on the existing tiles.

        Used for a new deal and for resetting to the starting numbers.
        Refused (returns False) while a merge is animating. The new board
        must have the same shape as the tiles.
        """
        if self.resolving:
            return False

        shape = (board_state.rows, board_state.cols)

        if shape != (self.board_state.rows, self.board_state.cols):
            raise ValueError(
                "Board shape {}x{} does not match the tiles".format(*shape)
            )

        self.pending_move.clear()
        self._empty_tap_time = None
        self.board_state = board_state
        self.sync_from_state()
        return True

    def apply_move_visuals(self):
        """Write selection, arming and valid-target flags onto visible tiles."""
        numbers = self._number_objects()
        move = self.pending_move
        valid_ids = move.valid_target_ids(numbers, can_target=self._can_target)
        armed = move.operation if move.mode == OPERATION_ARMED else None

        for tile in numbers:
            meta = tile.meta
            is_selected = tile.id == move.selected_id

            meta["mm_selected"] = is_selected
            meta["mm_show_ops"] = bool(is_selected and move.mode == NUMBER_SELECTED)
            meta["mm_armed_op"] = armed if is_selected else None
            meta["mm_valid_target"] = tile.id in valid_ids
            meta["mm_dimmed"] = bool(
                armed and not is_selected and tile.id not in valid_ids
            )

            tile._notify_renderer()

    def clear_pending_move(self):
        self.pending_move.clear()
        self.apply_move_visuals()

    # --- input ---------------------------------------------------------

    def _operation_hit(self, tile, point):
        if tile is None or tile.id != self.pending_move.selected_id:
            return None

        hit_test = getattr(self._view_of(tile), "operation_at_screen_point", None)
        if not callable(hit_test):
            return None

        return hit_test(point)

    def touch_began(self, touch):
        # Deliberately bypass TileKit's drag/action interaction controller.
        pass

    def touch_moved(self, touch):
        pass

    def touch_cancelled(self, touch):
        pass

    def touch_ended(self, touch):
        if self.resolving:
            return

        point = PointerEvent.from_touch("ended", touch, board_view=self).point
        tile = self.tile_at_point(point)

        if tile is None:
            self._handle_empty_board_tap()
            return

        self._empty_tap_time = None

        move = self.pending_move
        if move.mode == OPERATION_ARMED and tile.id == move.selected_id:
            # Tapping the armed tile anywhere returns to the four choices.
            move.choose_operation(move.operation)
            self.apply_move_visuals()
            return

        operation = self._operation_hit(tile, point)
        if operation is not None:
            self.pending_move.choose_operation(operation)
            self.apply_move_visuals()
            return

        result = self.pending_move.tap_number(tile.id)

        if result == "target_candidate":
            valid_ids = self.pending_move.valid_target_ids(
                self._number_objects(), can_target=self._can_target
            )
            if tile.id in valid_ids:
                self.resolve_move(tile)
            else:
                self.reject_tap(tile)
            return

        self.apply_move_visuals()

    def _can_target(self, source, target):
        """Ask the board's rules whether the armed move may land on target."""
        return self.board_state.move_allowed(
            self._cell_of(source),
            self.pending_move.operation,
            self._cell_of(target),
        )

    def _handle_empty_board_tap(self):
        """One empty tap clears the pending move; a quick second tap undoes."""
        now = time.monotonic()
        last = self._empty_tap_time

        if last is not None and now - last <= self.DOUBLE_TAP_SECONDS:
            self._empty_tap_time = None
            self.undo_last_move()
            return

        self._empty_tap_time = now
        self.clear_pending_move()

    # --- moves ---------------------------------------------------------

    def resolve_move(self, destination):
        """Commit the armed move in the model, then animate the merge."""
        source = self._tile_by_id(self.pending_move.selected_id)
        operation = self.pending_move.operation

        if source is None or operation is None:
            self.clear_pending_move()
            return

        result = self.board_state.apply_move(
            self._cell_of(source),
            operation,
            self._cell_of(destination),
        )

        if result is None:
            # For example division by zero: nothing changed.
            self.reject_tap(destination)
            return

        # Visuals stay armed during the slide so "7+" travels with the tile.
        self.pending_move.clear()

        if self.on_move_committed is not None:
            self.on_move_committed(result)

        self.resolving = True
        self._animate_merge(source, destination)

    def _animate_merge(self, source, destination):
        """Slide the source tile onto its neighbour, then pop the result.

        The model has already committed the move. layout() skips tile
        positioning while resolving, so nothing snaps the sliding tile back.
        """
        source_view = self._view_of(source)
        destination_view = self._view_of(destination)

        if source_view is None or destination_view is None:
            self.sync_from_state()
            self.resolving = False
            return

        source_view.bring_to_front()
        target_centre = destination_view.center

        def slide():
            source_view.center = target_centre

        def pop():
            destination_view.transform = ui.Transform.scale(self.POP_SCALE, self.POP_SCALE)

        def settle():
            destination_view.transform = ui.Transform.scale(1.0, 1.0)

        def finish():
            self.resolving = False
            # Catch up on any layout skipped while the move was resolving.
            self.layout()

        def reveal_result():
            # Hides the emptied source cell and shows the new value.
            self.sync_from_state()
            ui.animate(
                pop,
                duration=self.POP_SECONDS,
                completion=lambda: ui.animate(
                    settle,
                    duration=self.SETTLE_SECONDS,
                    completion=finish,
                ),
            )

        ui.animate(slide, duration=self.SLIDE_SECONDS, completion=reveal_result)

    def reject_tap(self, tile):
        """Brief shrink-and-return when a tap cannot complete the move."""
        view = self._view_of(tile)
        if view is None:
            return

        def shrink():
            view.transform = ui.Transform.scale(0.92, 0.92)

        def restore():
            view.transform = ui.Transform.scale(1.0, 1.0)

        ui.animate(
            shrink,
            duration=0.06,
            completion=lambda: ui.animate(restore, duration=0.10),
        )

    def undo_last_move(self):
        """Undo one whole committed move and clear any pending selection."""
        if self.resolving:
            return

        self.pending_move.clear()

        if self.board_state.undo():
            self.sync_from_state()
        else:
            self.apply_move_visuals()