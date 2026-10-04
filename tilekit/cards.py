"""Renderer-neutral card definitions and explicit object-edit commits.

Apps provide a Pythonista body factory and optional applicability predicate.
The factory is stored here but invoked only by the UI layer.
"""
from copy import deepcopy


class CardDefinition:
    """Presentation supplied by a profile for one object kind.

    build_body(card) returns an app-owned body view. The card supplies its
    edit session and board view. accepts(obj, board) optionally narrows a kind.

    ``chrome='workspace'`` keeps the same session/history contract but asks the
    Pythonista surface for a compact tool-style top bar. It is intended for rich
    objects such as plots and spreadsheets whose body is the application, not
    merely a few fields inside a generic inspector.
    """

    def __init__(self, title, build_body, accepts=None,
                 width=360, height=480, accent="#64D2FF",
                 subtitle=None, chrome="standard"):
        if not callable(build_body):
            raise TypeError("Card body factory must be callable")
        if accepts is not None and not callable(accepts):
            raise TypeError("Card predicate must be callable")
        chrome = str(chrome or "standard")
        if chrome not in ("standard", "workspace"):
            raise ValueError("Unknown card chrome: {}".format(chrome))
        self.title = str(title)
        self.build_body = build_body
        self.accepts = accepts
        self.width = max(240, float(width))
        self.height = max(240, float(height))
        self.accent = accent
        self.subtitle = (
            "Explore • edit • create" if subtitle is None else str(subtitle)
        )
        self.chrome = chrome

    def applies_to(self, obj, board):
        return obj is not None and (
            self.accepts is None or bool(self.accepts(obj, board))
        )


class CardEditSession:
    """Commit validated model edits without storing views in object metadata.

    Text under active editing remains an app-owned draft. Apps validate and
    compute a complete mutation before commit; invalid drafts never reach
    the board. Closing a session adds no history entry by itself.
    """

    def __init__(self, board, obj):
        if obj not in board.objects:
            raise ValueError("Cannot edit an object outside this board")
        self.board = board
        self.obj = obj
        self.closed = False

    @property
    def active(self):
        # Identity matters: undo can recreate the same ID as a different object.
        return not self.closed and self.obj in self.board.objects

    def commit(self, mutation, label="Edit tile"):
        """Apply one prepared mutation; return whether model state changed."""
        if not self.active:
            raise RuntimeError("This editor is stale; reopen the tile")
        if not isinstance(mutation, dict):
            raise TypeError("An edit must be a mutation dictionary")
        unknown = set(mutation) - {"kind", "label", "payload", "meta"}
        if unknown:
            raise ValueError("Unsupported edit fields: " + ", ".join(sorted(unknown)))
        if "meta" in mutation and not isinstance(mutation["meta"], dict):
            raise TypeError("Edit metadata must be a dictionary")
        for key in ("kind", "label"):
            if key in mutation and not isinstance(mutation[key], str):
                raise TypeError("Edit {} must be text".format(key))

        prepared = deepcopy(mutation)
        history = self.board.history
        before = history.snapshot()
        self.board._apply_mutation(self.obj, prepared)
        return history.record_change(before, label=label)

    def close(self):
        """Invalidate this session without committing an unfinished draft."""
        self.closed = True
