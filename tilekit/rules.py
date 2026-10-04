"""
TileKit interaction rules.

Rules are renderer-neutral. They receive source object, target object,
and context, then return an InteractionResult. They should describe
intent rather than directly mutating ui.Views.
"""


class InteractionResult:
    """Intent returned by a rule and applied by the board/controller."""

    def __init__(self, mutate_source=None, mutate_target=None,
                 delete_source=False, delete_target=False,
                 delete_objects=None, spawn=None, keep_both=False,
                 move_source=None, animation_hint=None, undo_label=None):
        self.mutate_source = mutate_source
        self.mutate_target = mutate_target
        self.delete_source = bool(delete_source)
        self.delete_target = bool(delete_target)
        self.delete_objects = list(delete_objects or [])
        self.spawn = list(spawn or [])
        self.keep_both = bool(keep_both)
        self.move_source = move_source
        self.animation_hint = animation_hint
        self.undo_label = undo_label


class InteractionPreview:
    """
    Renderer-neutral preview/hint for a potential interaction.

    This deliberately carries data only. UI layers may render it as a label,
    ghost tile, outline, arrow, card, status row, or nothing at all.
    """

    def __init__(self, source=None, target=None, relation=None, label=None,
                 kind=None, payload=None, meta=None, rule=None, valid=True,
                 message=None):
        self.source = source
        self.target = target
        self.relation = relation
        self.label = label
        self.kind = kind
        self.payload = payload
        self.meta = dict(meta or {})
        self.rule = rule
        self.valid = bool(valid)
        self.message = message

    def to_dict(self):
        relation = self.relation
        if hasattr(relation, "to_dict"):
            relation = relation.to_dict()

        return {
            "source_id": getattr(self.source, "id", None),
            "source_kind": getattr(self.source, "kind", None),
            "source_label": getattr(self.source, "label", None),
            "target_id": getattr(self.target, "id", None),
            "target_kind": getattr(self.target, "kind", None),
            "target_label": getattr(self.target, "label", None),
            "relation": relation,
            "label": self.label,
            "kind": self.kind,
            "payload": self.payload,
            "meta": dict(self.meta),
            "valid": self.valid,
            "message": self.message,
            "rule": self.rule,
        }


class InteractionRule:
    """Base rule contract."""

    priority = 100

    def can_apply(self, source, target, context):
        return False

    def preview(self, source, target, context):
        return None

    def apply(self, source, target, context):
        return None


class InteractionProfile:
    """Interaction map for one object kind."""

    def __init__(self, kind, accepts=None, relation_rules=None,
                 fallback_rule=None, actions=None):
        self.kind = kind
        self.accepts = tuple(accepts or ())
        self.relation_rules = dict(relation_rules or {})
        self.fallback_rule = fallback_rule
        self.actions = list(actions or [])

    def resolve(self, source, target, context):
        if self.accepts and source.kind not in self.accepts:
            return None

        relation_obj = context.get("drop_relation")
        relation_names = []

        for name in (
            getattr(relation_obj, "profile_position", None),
            getattr(relation_obj, "relation", None),
            getattr(relation_obj, "target_zone", None),
            getattr(relation_obj, "started_zone", None),
            getattr(relation_obj, "drag_direction", None),
            getattr(relation_obj, "spawn_direction", None),
        ):
            if name and name not in relation_names:
                relation_names.append(name)

        for relation in relation_names:
            rule = self.relation_rules.get(relation)
            if rule is None:
                continue
            if hasattr(rule, "can_apply") and not rule.can_apply(source, target, context):
                continue
            return rule

        rule = self.fallback_rule
        if rule is None:
            return None
        if hasattr(rule, "can_apply") and not rule.can_apply(source, target, context):
            return None
        return rule


class ProfileRegistry:
    """Registry mapping object kind to InteractionProfile."""

    def __init__(self):
        self._profiles = {}

    def register(self, profile):
        self._profiles[profile.kind] = profile

    def get(self, kind):
        return self._profiles.get(kind)

    def has(self, kind):
        return kind in self._profiles

    def all_kinds(self):
        return list(self._profiles.keys())


class RuleEngine:
    """Resolve and apply interaction profiles."""

    def __init__(self, registry=None):
        self.registry = registry or ProfileRegistry()

    def _resolve_rule(self, source, target, context=None):
        context = dict(context or {})
        if source is None or target is None:
            return None

        profile = self.registry.get(target.kind)
        if profile is None:
            return None

        return profile.resolve(source, target, context)

    def _normalise_preview(self, preview, source, target, context, rule):
        if preview is None:
            return None

        relation = context.get("drop_relation")

        if isinstance(preview, InteractionPreview):
            if preview.source is None:
                preview.source = source
            if preview.target is None:
                preview.target = target
            if preview.relation is None:
                preview.relation = relation
            if preview.rule is None:
                preview.rule = rule.__class__.__name__
            return preview

        if isinstance(preview, dict):
            return InteractionPreview(
                source=source,
                target=target,
                relation=preview.get("relation", relation),
                label=preview.get("label"),
                kind=preview.get("kind"),
                payload=preview.get("payload"),
                meta=preview.get("meta"),
                rule=preview.get("rule") or rule.__class__.__name__,
                valid=preview.get("valid", True),
                message=preview.get("message"),
            )

        if isinstance(preview, tuple):
            label = preview[0] if len(preview) > 0 else None
            kind = preview[1] if len(preview) > 1 else None
            meta = preview[2] if len(preview) > 2 else None
            return InteractionPreview(
                source=source,
                target=target,
                relation=relation,
                label=label,
                kind=kind,
                meta=meta,
                rule=rule.__class__.__name__,
            )

        return InteractionPreview(
            source=source,
            target=target,
            relation=relation,
            label=str(preview),
            rule=rule.__class__.__name__,
        )

    def preview_interaction(self, source, target, context=None):
        """Return renderer-neutral preview data for a potential interaction."""
        context = dict(context or {})
        rule = self._resolve_rule(source, target, context)
        if rule is None:
            return None

        try:
            preview = rule.preview(source, target, context)
        except Exception:
            return None

        return self._normalise_preview(preview, source, target, context, rule)

    def try_interaction(self, source, target, context=None):
        context = dict(context or {})
        rule = self._resolve_rule(source, target, context)
        if rule is None:
            return None

        return rule.apply(source, target, context)