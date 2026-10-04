"""
TileKit actions.

Actions are renderer-neutral behaviours that can be offered for TileObjects.

They are intentionally separate from renderers and UI menus. A renderer or
Pythonista view may later present these actions as buttons, context menus,
keyboard shortcuts, command palettes, or gesture affordances, but the action
itself belongs to the object/board layer.
"""


class TileAction:
    """Base contract for an object action."""

    id = "action"
    label = "Action"
    icon = ""
    records_history = True
    restores_board = False

    def __init__(self, id=None, label=None, icon=None, records_history=None, restores_board=None):
        if id is not None:
            self.id = str(id)
        if label is not None:
            self.label = str(label)
        if icon is not None:
            self.icon = str(icon)
        if records_history is not None:
            self.records_history = bool(records_history)
        if restores_board is not None:
            self.restores_board = bool(restores_board)

    def applies_to(self, obj, board):
        """Return True if this action should be offered for obj."""
        return obj is not None

    def run(self, obj, board, context=None):
        """Perform the action.

        Subclasses may mutate the object/board directly or return a value for
        the caller. UI layers should not be required for actions to run.
        """
        return None

    def to_menu_item(self, obj=None, board=None):
        """Return a small serialisable menu item description."""
        return {
            "id": self.id,
            "label": self.label,
            "icon": self.icon,
            "enabled": bool(self.applies_to(obj, board)),
            "action": self,
        }


class UndoAction(TileAction):
    """Generic board undo action."""

    id = "undo"
    label = "Undo"
    icon = "↶"
    records_history = False
    restores_board = True

    def applies_to(self, obj, board):
        return bool(board is not None and board.can_undo())

    def run(self, obj, board, context=None):
        if board is None:
            return False
        return board.undo()


class RedoAction(TileAction):
    """Generic board redo action."""

    id = "redo"
    label = "Redo"
    icon = "↷"
    records_history = False
    restores_board = True

    def applies_to(self, obj, board):
        return bool(board is not None and board.can_redo())

    def run(self, obj, board, context=None):
        if board is None:
            return False
        return board.redo()


class DuplicateAction(TileAction):
    """Generic duplicate action for board objects."""

    id = "duplicate"
    label = "Duplicate"
    icon = "⧉"
    records_history = True

    def applies_to(self, obj, board):
        return bool(obj is not None and board is not None)

    def run(self, obj, board, context=None):
        if obj is None or board is None:
            return None

        import copy

        direction = "right"
        if isinstance(context, dict):
            direction = context.get("direction") or direction

        spec = {
            "kind": getattr(obj, "kind", "generic"),
            "label": getattr(obj, "label", ""),
            "payload": copy.deepcopy(getattr(obj, "payload", None)),
            "size": tuple(getattr(obj, "size", None) or (64, 64)),
            "renderer": getattr(obj, "renderer_id", "block"),
            "meta": copy.deepcopy(getattr(obj, "meta", {}) or {}),
        }

        spawned = board.spawn_object(spec, near=obj, direction=direction)
        try:
            board.select(spawned)
        except Exception:
            pass
        return spawned


class DeleteAction(TileAction):
    """Generic delete action for board objects."""

    id = "delete"
    label = "Delete"
    icon = "×"
    records_history = True

    def applies_to(self, obj, board):
        return bool(obj is not None and board is not None)

    def run(self, obj, board, context=None):
        if obj is None or board is None:
            return False
        board.remove_object(obj)
        return True


class DeleteSelectionAction(TileAction):
    """Generic delete action for the current board selection."""

    id = "delete-selection"
    label = "Delete selection"
    icon = "🗑"
    records_history = True

    def applies_to(self, obj, board):
        if board is None:
            return False
        try:
            selection = getattr(board, "selection", None)
            group = list(getattr(selection, "group", []) or [])
            return len(group) > 1
        except Exception:
            return False

    def run(self, obj, board, context=None):
        if board is None:
            return False

        try:
            selected = list(board.selected_objects())
        except Exception:
            selected = []

        if not selected:
            return False

        for item in selected:
            try:
                board.remove_object(item)
            except Exception:
                pass

        try:
            board.clear_selection()
        except Exception:
            pass

        return True


class DuplicateSelectionAction(TileAction):
    """Generic duplicate action for the current board selection."""

    id = "duplicate-selection"
    label = "Duplicate selection"
    icon = "⧉"
    records_history = True

    def applies_to(self, obj, board):
        if board is None:
            return False
        try:
            selection = getattr(board, "selection", None)
            group = list(getattr(selection, "group", []) or [])
            return len(group) > 1
        except Exception:
            return False

    def run(self, obj, board, context=None):
        if board is None:
            return []

        try:
            selected = list(board.selected_objects())
        except Exception:
            selected = []

        if not selected:
            return []

        import copy

        specs = []
        for item in selected:
            specs.append({
                "kind": getattr(item, "kind", "generic"),
                "label": getattr(item, "label", ""),
                "payload": copy.deepcopy(getattr(item, "payload", None)),
                "size": tuple(getattr(item, "size", None) or (64, 64)),
                "renderer": getattr(item, "renderer_id", "block"),
                "meta": copy.deepcopy(getattr(item, "meta", {}) or {}),
            })

        created = []
        origin = getattr(selected[0], "position", None) if selected else None
        objects = [board.create_object(spec) for spec in specs]

        try:
            positions = board.placer.place_sequence(
                board,
                objects,
                origin=origin,
                exclude=selected,
            )
        except Exception:
            positions = []

        for index, new_obj in enumerate(objects):
            if index < len(positions):
                new_obj.position = positions[index]
            else:
                new_obj.position = None

            board.add_object(new_obj, position=new_obj.position)
            created.append(new_obj)

        try:
            board.set_group_selection(created)
            if created:
                # Keep the duplicated objects as a group, while still giving the
                # group a primary selected object for positioning/menu anchoring.
                board.selected = created[0]
                created[0].set_selected(True)
        except Exception:
            pass

        return created


class CreateTextAction(TileAction):
    """Global action: create a new text object."""

    id = "create-text"
    label = "New text"
    icon = "T"
    records_history = True

    def applies_to(self, obj, board):
        return bool(obj is None and board is not None)

    def run(self, obj, board, context=None):
        if board is None:
            return None

        origin = None
        if isinstance(context, dict):
            origin = context.get("origin")

        created = board.spawn_object({
            "kind": "text",
            "label": "text",
            "size": (64, 64),
            "renderer": "block",
            "meta": {"color": "#FFD60A"},
        }, origin=origin)

        try:
            board.select(created)
        except Exception:
            pass

        return created


class CreateFileAction(TileAction):
    """Global action: create a new file-like object."""

    id = "create-file"
    label = "New file"
    icon = "F"
    records_history = True

    def applies_to(self, obj, board):
        return bool(obj is None and board is not None)

    def run(self, obj, board, context=None):
        if board is None:
            return None

        origin = None
        if isinstance(context, dict):
            origin = context.get("origin")

        created = board.spawn_object({
            "kind": "file",
            "label": "file",
            "size": (76, 56),
            "renderer": "block",
            "meta": {"color": "#30D158"},
        }, origin=origin)

        try:
            board.select(created)
        except Exception:
            pass

        return created


class ActionRegistry:
    """Registry of available TileActions."""

    def __init__(self, actions=None):
        self._actions = []
        for action in actions or []:
            self.register(action)

    def register(self, action):
        """Register an action object."""
        if action is None:
            return action

        action_id = getattr(action, "id", "")
        if not action_id:
            raise ValueError("TileAction requires an id")

        existing = [
            item for item in self._actions
            if getattr(item, "id", None) == action_id
        ]
        for item in existing:
            self._actions.remove(item)

        self._actions.append(action)
        return action

    def get(self, action_id):
        """Return an action by id, or None."""
        action_id = str(action_id or "")
        for action in self._actions:
            if getattr(action, "id", None) == action_id:
                return action
        return None

    def all(self):
        """Return all registered actions in registration order."""
        return list(self._actions)

    def actions_for(self, obj, board):
        """Return actions that apply to obj."""
        out = []
        for action in self._actions:
            try:
                if action.applies_to(obj, board):
                    out.append(action)
            except Exception:
                continue
        return out

    def menu_for(self, obj, board):
        """Return a MenuModel for obj."""
        return MenuModel([
            action.to_menu_item(obj, board)
            for action in self.actions_for(obj, board)
        ])


class MenuModel:
    """Small renderer-neutral menu model."""

    def __init__(self, items=None):
        self.items = list(items or [])

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def ids(self):
        return [item.get("id") for item in self.items]

    def labels(self):
        return [item.get("label") for item in self.items]

    def get(self, action_id):
        action_id = str(action_id or "")
        for item in self.items:
            if item.get("id") == action_id:
                return item
        return None