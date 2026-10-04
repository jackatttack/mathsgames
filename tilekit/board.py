"""
TileKit board.

Board is the object surface. It owns TileObjects, a coordinate system,
selection state, and a rule engine. Rendering/input layers can be added
on top without changing the object model.
"""

from .coords import FreeformSquareGrid
from .data import TileData, TileSpec
from .object import TileObject
from .rules import RuleEngine
from .actions import ActionRegistry
from .selection import SelectionModel
from .palette import PaletteRegistry
from .input_session import InputSession


class Board:
    """Renderer-neutral TileKit board core."""

    def __init__(self, coords=None, rule_engine=None, action_registry=None, palette=None, placer=None, history=None):
        self.coords = coords or FreeformSquareGrid()
        self.rule_engine = rule_engine or RuleEngine()
        self.action_registry = action_registry or ActionRegistry()
        self.palette = palette or PaletteRegistry()

        if placer is None:
            from .placement import GridPlacer
            placer = GridPlacer(self.coords)
        self.placer = placer

        self.objects = []
        self.selected = None
        self.selection = SelectionModel(self)
        self.input_session = InputSession(self)

        if history is None:
            from .history import HistoryStack
            history = HistoryStack(self)
        self.history = history
        self.history.board = self

        # Size policy per kind, installed by profile sets. Kinds with no
        # policy keep whatever size their spec gave them.
        self.size_policies = {}
        self.card_definitions = {}

        # Set from the UI layer when real text measurement is available.
        # None means sizing uses tilekit.sizing's headless estimate.
        self.measure_text = None

    def set_card(self, kind, definition):
        """Register a profile-owned editor definition for an object kind."""
        self.card_definitions[str(kind)] = definition

    def card_for(self, obj):
        """Return an applicable editor definition, or None."""
        if obj is None or obj not in self.objects:
            return None
        definition = self.card_definitions.get(obj.kind)
        if definition is not None and definition.applies_to(obj, self):
            return definition
        return None

    def set_size_policy(self, kind, policy):
        """Register how objects of one kind choose their cell span."""
        if kind and policy is not None:
            self.size_policies[str(kind)] = policy
        return policy

    def size_policy_for(self, kind):
        """Return the size policy for kind, or None."""
        return self.size_policies.get(str(kind or ""))

    def apply_size_policy(self, obj):
        """Give obj the cell span its kind's policy wants.

        Called when an object is created and whenever a rule changes its
        label, since an armed tool tile such as sin(30) needs more room than
        the bare sin tile it replaced.
        """
        if obj is None:
            return None
        policy = self.size_policy_for(getattr(obj, "kind", None))
        if policy is None:
            return None

        from .sizing import apply_size_policy

        return apply_size_policy(
            obj,
            policy,
            grid=self.placer.grid_size(self),
            measure=self.measure_text,
        )

    def create_object(self, spec):
        """Create a TileObject from a TileSpec or dictionary."""
        if isinstance(spec, dict):
            spec = TileSpec.from_dict(spec)

        data = TileData(
            kind=spec.kind,
            label=spec.label,
            payload=spec.payload,
            meta=spec.meta,
        )

        obj = TileObject(
            data=data,
            position=spec.position,
            size=spec.size,
            renderer_id=spec.renderer or "block",
        )
        obj.board = self
        self.apply_size_policy(obj)
        return obj

    def add_object(self, obj, position=None, snap=True):
        """Add an object to the board."""
        obj.board = self
        if position is not None:
            obj.position = position
        if obj.position is None:
            obj.position = (0, 0)
        if snap:
            obj.position = self.coords.snap(obj.position, obj)
        self.objects.append(obj)
        return obj

    def spawn_object(self, spec, near=None, direction="right", origin=None, snap=True):
        """Create, place, add, and return an object.

        This is the app-facing helper for actions/palettes that create tiles.
        Placement is delegated to board.placer so UI code does not need to know
        how to find free board positions.
        """
        obj = self.create_object(spec)

        if near is not None:
            obj.position = self.placer.find_adjacent(
                self,
                near,
                obj=obj,
                direction=direction,
            )
        elif obj.position is None:
            obj.position = self.placer.find_free_position(
                self,
                obj,
                origin=origin,
            )

        return self.add_object(obj, position=obj.position, snap=snap)

    def remove_object(self, obj):
        """Remove an object if present."""
        if obj in self.objects:
            self.objects.remove(obj)

        if self.selected is obj:
            self.selected = None

        input_session = getattr(self, "input_session", None)
        if input_session is not None and getattr(input_session, "target", None) is obj:
            input_session.clear_target()

        selection = getattr(self, "selection", None)
        if selection is not None:
            try:
                selection.remove_from_group(obj)
                selection.prune_missing()
            except Exception:
                pass

    def select(self, obj):
        """Select one object and make it the default input target."""
        selection = getattr(self, "selection", None)
        if selection is not None:
            result = selection.select_one(obj)
        else:
            if self.selected is not None and self.selected is not obj:
                self.selected.set_selected(False)
            self.selected = obj
            if obj is not None:
                obj.set_selected(True)
            result = obj

        input_session = getattr(self, "input_session", None)
        if input_session is not None:
            if result is None:
                input_session.clear_target()
            else:
                input_session.set_target(result)

        return result

    def clear_selection(self):
        """Clear primary/group selection and the default input target."""
        selection = getattr(self, "selection", None)
        if selection is not None:
            selection.clear_all()
        else:
            self.selected = None

        input_session = getattr(self, "input_session", None)
        if input_session is not None:
            input_session.clear_target()

    def set_group_selection(self, objects):
        """Set the current group selection."""
        selection = getattr(self, "selection", None)
        if selection is None:
            return []
        return selection.set_group(objects)

    def clear_group_selection(self):
        """Clear the current group selection."""
        selection = getattr(self, "selection", None)
        if selection is not None:
            selection.clear_group()

    def selected_objects(self):
        """Return selected objects, preferring group selection."""
        selection = getattr(self, "selection", None)
        if selection is not None:
            return selection.selected_objects()
        return [self.selected] if self.selected is not None else []

    def object_at_position(self, position, excluding=None, radius=None):
        """Find nearest object to a logical position."""
        radius = radius if radius is not None else self.coords.grid * 0.5
        best = None
        best_dist = None

        for obj in self.objects:
            if obj is excluding:
                continue
            if obj.position is None:
                continue
            dist = self.coords.distance(position, obj.position)
            if dist <= radius and (best_dist is None or dist < best_dist):
                best = obj
                best_dist = dist

        return best

    def apply_result(self, result, source=None, target=None, context=None):
        """Apply an InteractionResult to board objects."""
        if result is None:
            return False

        context = dict(context or {})
        # A drag controller can own history for the whole move-and-merge.
        before = (
            self.history.snapshot()
            if getattr(self, "history", None) is not None
            and context.get("record_history", True)
            else None
        )

        self._apply_mutation(source, result.mutate_source)
        self._apply_mutation(target, result.mutate_target)

        relation = context.get("drop_relation")
        spawn_direction = (
            getattr(relation, "spawn_direction", None)
            or getattr(relation, "direction", None)
            or "right"
        )

        for spec in result.spawn:
            # If an interaction/app rule provides an explicit result position,
            # honour it. Directional TileCalc merges use direction to choose the
            # operation, not to push the result into an adjacent free cell.
            if isinstance(spec, dict) and spec.get("position") is not None:
                self.spawn_object(spec)
            elif target is not None:
                # Interaction results usually make most sense near the merge
                # target. This keeps calculated/result tiles from appearing in
                # confusing free-board positions or overlapping stale objects.
                self.spawn_object(spec, near=target, direction=spawn_direction)
            else:
                self.spawn_object(spec)

        if result.move_source is not None and source is not None:
            source.position = result.move_source

        if result.delete_source and source is not None:
            self.remove_object(source)

        if result.delete_target and target is not None:
            self.remove_object(target)

        for item in list(getattr(result, "delete_objects", []) or []):
            if item is not None:
                self.remove_object(item)

        if before is not None:
            label = getattr(result, "undo_label", "") or "interaction"
            self.history.record_change(before, label=label)

        return True

    def actions_for(self, obj):
        """Return actions currently available for obj."""
        return self.action_registry.actions_for(obj, self)

    def menu_for(self, obj):
        """Return a renderer-neutral MenuModel for obj."""
        return self.action_registry.menu_for(obj, self)

    def run_action(self, action_id, obj, context=None):
        """Run a registered action by id."""
        action = self.action_registry.get(action_id)
        if action is None:
            return None
        if not action.applies_to(obj, self):
            return None

        should_record = bool(getattr(action, "records_history", True))
        before = None
        if should_record and getattr(self, "history", None) is not None:
            before = self.history.snapshot()

        result = action.run(obj, self, context or {})

        if before is not None and result is not None:
            label = getattr(action, "label", "") or getattr(action, "id", "") or "action"
            self.history.record_change(before, label=label)

        return result

    def capture_history(self, label=""):
        """Manually capture the current board state for undo."""
        if getattr(self, "history", None) is None:
            return False
        return self.history.capture(label=label)

    def undo(self):
        """Undo the most recent recorded board change."""
        if getattr(self, "history", None) is None:
            return False
        return self.history.undo()

    def redo(self):
        """Redo the most recently undone board change."""
        if getattr(self, "history", None) is None:
            return False
        return self.history.redo()

    def can_undo(self):
        """Return True if undo is available."""
        history = getattr(self, "history", None)
        return bool(history is not None and history.can_undo())

    def can_redo(self):
        """Return True if redo is available."""
        history = getattr(self, "history", None)
        return bool(history is not None and history.can_redo())

    def _apply_mutation(self, obj, mutation):
        if obj is None or not mutation:
            return

        if "kind" in mutation:
            obj.kind = mutation["kind"]
        if "label" in mutation:
            obj.label = mutation["label"]
        if "payload" in mutation:
            obj.payload = mutation["payload"]
        if "meta" in mutation:
            obj.meta.update(mutation["meta"])

        if "kind" in mutation or "label" in mutation:
            self.apply_size_policy(obj)

        obj._notify_renderer()