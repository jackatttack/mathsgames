"""Pure Multiple Merge interaction state.

No UIKit lives here.  The state machine only knows about tile ids,
row/column metadata and arithmetic-operation selection.
"""

ALLOWED_OPERATIONS = ("+", "-", "×", "/")

IDLE = "idle"
NUMBER_SELECTED = "number_selected"
OPERATION_ARMED = "operation_armed"


class PendingMove:
    """State for the move currently being composed by the player."""

    def __init__(self):
        self.mode = IDLE
        self.selected_id = None
        self.operation = None

    def clear(self):
        self.mode = IDLE
        self.selected_id = None
        self.operation = None

    def select(self, tile_id):
        self.mode = NUMBER_SELECTED
        self.selected_id = tile_id
        self.operation = None

    def choose_operation(self, operation):
        if operation not in ALLOWED_OPERATIONS:
            raise ValueError(
                "Unknown operation: {}".format(operation)
            )

        if self.selected_id is None:
            return False

        # Tapping the active operation again returns to the four-choice state.
        if (
            self.mode == OPERATION_ARMED
            and self.operation == operation
        ):
            self.mode = NUMBER_SELECTED
            self.operation = None
            return True

        self.mode = OPERATION_ARMED
        self.operation = operation
        return True

    def tap_number(self, tile_id):
        """Handle a number tap that is not an operation-corner tap."""

        if self.selected_id is None:
            self.select(tile_id)
            return "selected"

        if tile_id == self.selected_id:
            self.clear()
            return "cleared"

        if self.mode == NUMBER_SELECTED:
            self.select(tile_id)
            return "moved_selection"

        if self.mode == OPERATION_ARMED:
            return "target_candidate"

        return "ignored"

    @staticmethod
    def adjacent(a, b):
        if a is None or b is None:
            return False

        ar = int(a.get("row", -999))
        ac = int(a.get("col", -999))
        br = int(b.get("row", -999))
        bc = int(b.get("col", -999))

        return abs(ar - br) + abs(ac - bc) == 1

    def valid_target_ids(self, objects, can_target=None):
        """Ids of number tiles the armed move may land on.

        can_target(source_obj, target_obj) decides each candidate. The board
        view passes one that asks BoardState, so the board's merge and result
        rules decide. Without it, orthogonal neighbours by row/col meta.
        """
        if (
            self.mode != OPERATION_ARMED
            or self.selected_id is None
        ):
            return set()

        selected = None

        for obj in objects:
            if getattr(obj, "id", None) == self.selected_id:
                selected = obj
                break

        if selected is None:
            return set()

        if can_target is None:
            source_meta = getattr(selected, "meta", {}) or {}

            def can_target(source, target):
                target_meta = getattr(target, "meta", {}) or {}
                return self.adjacent(source_meta, target_meta)

        valid = set()

        for obj in objects:
            if obj is selected:
                continue

            if getattr(obj, "kind", None) != "number":
                continue

            if can_target(selected, obj):
                valid.add(obj.id)

        return valid