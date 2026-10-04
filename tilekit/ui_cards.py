"""Reusable floating editor surface for Pythonista.

Bodies provide commit_pending() -> bool and optionally discard_pending().
The source object stays in the board throughout editing.
"""
import ui

from .cards import CardEditSession


def _workspace_card(definition, obj=None):
    """Return whether this card should use dense tool-workspace chrome.

    Plot/Stats opt in by object kind as a compatibility bridge for candidate
    branches whose CardDefinition was created before ``chrome=workspace`` was
    added. Explicit definition chrome remains authoritative for all other kinds.
    """
    return (
        getattr(definition, "chrome", "standard") == "workspace"
        or getattr(obj, "kind", None) in ("plot", "stats")
    )


class ObjectCard(ui.View):
    """Screen-space overlay containing one profile-owned editor."""

    def __init__(self, board_view, obj, definition):
        super().__init__(frame=board_view.bounds)
        self.flex = "WH"
        self.board_view = board_view
        self.definition = definition
        self.session = CardEditSession(board_view.board, obj)
        self._closing = False
        self.background_color = (0, 0, 0, 0.28)

        workspace = _workspace_card(definition, obj)
        self.panel = ui.View()
        self.panel.background_color = "#1C1C1E" if workspace else "#202630"
        self.panel.corner_radius = 20
        self.panel.border_width = 1
        self.panel.border_color = "#465363" if not workspace else "#48484A"
        self.add_subview(self.panel)

        self.accent = ui.View()
        self.accent.background_color = definition.accent
        self.accent.corner_radius = 2
        self.accent.touch_enabled = False
        self.panel.add_subview(self.accent)

        self.title_label = ui.Label()
        self.title_label.text = definition.title
        self.title_label.font = ("<System-Bold>", 17 if workspace else 22)
        self.title_label.text_color = "#F4F7FB"
        self.title_label.alignment = ui.ALIGN_CENTER if workspace else ui.ALIGN_LEFT
        self.title_label.touch_enabled = False
        self.panel.add_subview(self.title_label)

        self.subtitle = ui.Label()
        self.subtitle.text = getattr(definition, "subtitle", "Explore • edit • create")
        self.subtitle.font = ("<System>", 11)
        self.subtitle.text_color = "#A9B7C8"
        self.subtitle.touch_enabled = False
        self.panel.add_subview(self.subtitle)

        self.scroll = ui.ScrollView()
        self.scroll.background_color = "clear"
        self.panel.add_subview(self.scroll)

        self.done_button = ui.Button(title="Done")
        self.done_button.background_color = "clear" if workspace else definition.accent
        self.done_button.tint_color = definition.accent if workspace else "#14202A"
        self.done_button.font = ("<System-Bold>", 15)
        self.done_button.corner_radius = 12
        self.done_button.action = lambda sender: self.close()
        self.panel.add_subview(self.done_button)

        self.cancel_button = ui.Button(title="Cancel")
        self.cancel_button.tint_color = "#CBD5E1"
        self.cancel_button.font = ("<System>", 14)
        self.cancel_button.action = lambda sender: self.close(commit=False)
        self.panel.add_subview(self.cancel_button)

        self.body_view = None
        self.layout()
        self.body_view = definition.build_body(self)
        if self.body_view is None:
            raise ValueError("Card factory must return a body view")
        self.scroll.add_subview(self.body_view)
        self.layout()

    @property
    def obj(self):
        return self.session.obj

    def layout(self):
        if not hasattr(self, "panel"):
            return
        width = max(1, min(self.definition.width, self.width - 24))
        height = max(1, min(self.definition.height, self.height - 24))
        self.panel.frame = ((self.width - width) / 2, 12, width, height)
        workspace = _workspace_card(self.definition, self.obj)

        if workspace:
            self.accent.hidden = True
            self.subtitle.hidden = True
            self.cancel_button.frame = (10, 10, 72, 38)
            self.done_button.frame = (width - 82, 10, 72, 38)
            self.title_label.frame = (82, 13, max(1, width - 164), 32)
            self.scroll.frame = (12, 54, width - 24, max(1, height - 66))
        else:
            self.accent.hidden = False
            self.subtitle.hidden = False
            self.accent.frame = (18, 16, 32, 4)
            self.title_label.frame = (18, 28, width - 36, 30)
            self.subtitle.frame = (18, 61, width - 36, 18)
            self.scroll.frame = (12, 90, width - 24, max(1, height - 156))
            self.cancel_button.frame = (16, height - 56, 90, 44)
            self.done_button.frame = (width - 118, height - 56, 100, 44)

        body = getattr(self, "body_view", None)
        if body is not None:
            body.frame = (
                0, 0, self.scroll.width,
                max(self.scroll.height, getattr(body, "content_height", 330)),
            )
            layout_body = getattr(body, "layout", None)
            if callable(layout_body):
                layout_body()
            self.scroll.content_size = (body.width, body.height)

    def commit_pending(self):
        if not self.session.active:
            self.close(commit=False)
            return False
        commit = getattr(self.body_view, "commit_pending", None)
        return True if commit is None else bool(commit())

    def close(self, commit=True):
        """Done/outside saves a valid draft; Cancel discards pending input.

        Closing returns the board to a neutral selection state. This is
        intentional: a card is a modal inspection/edit interaction, and the
        next tile tap should always begin a fresh select -> open-card cycle.
        """
        if self._closing:
            return True
        if commit and self.session.active and not self.commit_pending():
            return False
        self._closing = True
        source_obj = self.obj
        if not commit:
            discard = getattr(self.body_view, "discard_pending", None)
            if discard is not None:
                discard()
        try:
            end_editing = getattr(self.body_view, "end_editing", None)
            if callable(end_editing):
                end_editing()
        except Exception:
            pass
        self.session.close()
        if self.superview is not None:
            self.superview.remove_subview(self)
        if getattr(self.board_view, "_object_card", None) is self:
            self.board_view._object_card = None
            hook = getattr(self.board_view, "card_visibility_changed", None)
            if callable(hook):
                hook(False)

        board = self.board_view.board
        if getattr(board, "selected", None) is source_obj:
            board.select(None)
            try:
                self.board_view.sync_object(source_obj)
            except Exception:
                pass
        return True

    def run_action(self, action_id):
        """Commit input, dispatch normally, then honour card-dismiss intent."""
        if not self.commit_pending():
            return None

        board = self.board_view.board
        action = board.action_registry.get(action_id)
        result = board.run_action(
            action_id, self.obj, {"view": self.board_view}
        )

        self.board_view._unmount_removed_objects()
        self.board_view.sync_all()

        should_dismiss = bool(
            result is not None
            and action is not None
            and getattr(action, "dismisses_card", False)
        )

        if not self.session.active or should_dismiss:
            self.close(commit=False)

        return result

    def touch_ended(self, touch):
        x, y = touch.location
        px, py, width, height = self.panel.frame
        if not (px <= x <= px + width and py <= y <= py + height):
            self.close()


def open_object_card(board_view, obj):
    """Open the registered editor, returning None if no editor applies."""
    definition = board_view.board.card_for(obj)
    if definition is None:
        return None

    previous = getattr(board_view, "_object_card", None)
    if previous is not None:
        if previous.session.active and previous.obj is obj:
            previous.bring_to_front()
            return previous
        if not previous.close():
            return None

    card = ObjectCard(board_view, obj, definition)
    board_view.transient.hide_action_dock()
    board_view._object_card = card
    board_view.add_subview(card)
    hook = getattr(board_view, "card_visibility_changed", None)
    if callable(hook):
        hook(True)
    card.bring_to_front()
    return card

