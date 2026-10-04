"""Small Pythonista view-lifecycle helpers shared by UI surfaces."""


def remove_view(view):
    """Detach through the owning parent (Pythonista has no child remove API)."""
    parent = getattr(view, "superview", None)
    if parent is not None:
        parent.remove_subview(view)

