"""
TileKit object model.

TileObject is the behaviour-facing wrapper around TileData. It is not
itself a Pythonista ui.View. A TileObject can be rendered as a block,
card, sprite, icon, chess piece, file tile, command tile, or anything
else a renderer supports.
"""

from .data import TileData, TileState


class TileObject:
    """Renderer-neutral interactive object."""

    def __init__(self, data=None, position=None, size=None, renderer_id=None,
                 w_cells=None, h_cells=None, fixed_size=False):
        self.data = data if data is not None else TileData()
        self.state = TileState()
        self.position = position
        self.size = size
        self.renderer_id = renderer_id or "block"
        self.renderer = None

        # Set when the object joins a board. Content-driven sizing needs the
        # board's policies and grid.
        self.board = None

        # Size in grid cells, as model state rather than a pixel measurement.
        # Old Tile Calc stored a cell span and derived pixels from the board
        # grid, so a tile kept its shape at any zoom. None means no span has
        # been declared and callers fall back to measuring pixel size.
        self.w_cells = w_cells
        self.h_cells = h_cells

        # True when this object's size was chosen deliberately: a manual
        # resize, or a kind that sizes itself. Automatic sizing must leave
        # these objects alone.
        self.fixed_size = bool(fixed_size)

    @property
    def cell_span(self):
        """Return (w_cells, h_cells), or None when no span is declared."""
        if self.w_cells is None or self.h_cells is None:
            return None
        return (self.w_cells, self.h_cells)

    def set_cell_span(self, w_cells, h_cells, fixed=None):
        """Resize a board object while keeping its first grid cell anchored."""
        new_span = (max(1, int(w_cells)), max(1, int(h_cells)))
        old_span = self.cell_span or (1, 1)
        board = self.board
        coords = getattr(board, "coords", None)
        anchored = (
            board is not None
            and self in board.objects
            and self.position is not None
            and getattr(coords, "name", "") == "freeform_square_grid"
        )
        self.w_cells, self.h_cells = new_span
        if fixed is not None:
            self.fixed_size = bool(fixed)
        if anchored and old_span != new_span:
            grid = float(coords.grid)
            x, y = self.position
            self.position = (
                x + (new_span[0] - old_span[0]) * grid / 2,
                y + (new_span[1] - old_span[1]) * grid / 2,
            )
            if not self.state.dragging:
                self.position = coords.snap(self.position, self)
        self._notify_renderer()

    @property
    def id(self):
        return self.data.id

    @property
    def kind(self):
        return self.data.kind

    @kind.setter
    def kind(self, value):
        self.data.kind = str(value or "generic")
        self._resize_for_content()

    @property
    def label(self):
        return self.data.label

    @label.setter
    def label(self, value):
        self.data.label = str(value or "")
        self._resize_for_content()

    @property
    def payload(self):
        return self.data.payload

    @payload.setter
    def payload(self, value):
        self.data.payload = value

    @property
    def meta(self):
        return self.data.meta

    def set_selected(self, on):
        self.state.selected = bool(on)
        self._notify_renderer()

    def set_dragging(self, on):
        self.state.dragging = bool(on)
        self._notify_renderer()

    def set_sticky(self, on):
        self.state.sticky = bool(on)
        self._notify_renderer()

    def _resize_for_content(self):
        """Re-apply this object's size policy after its content changed.

        Sizing lives here rather than at each call site because a label can
        be set from anywhere: a rule mutation, keyboard digit entry, an app
        action. TileCalc's multi-digit entry set obj.label directly and its
        tile never grew, which is the defect this prevents recurring.

        Objects not on a board, or on a board with no policy for their kind,
        are left alone.
        """
        board = getattr(self, "board", None)
        if board is None:
            return
        resize = getattr(board, "apply_size_policy", None)
        if resize is None:
            return
        try:
            resize(self)
        except Exception:
            pass

    def _notify_renderer(self):
        if self.renderer is not None:
            try:
                self.renderer.update(self)
            except Exception:
                pass

    def to_dict(self):
        """Return a JSON-friendly object snapshot."""
        return {
            "data": self.data.to_dict(),
            "state": self.state.to_dict(),
            "position": self.position,
            "size": self.size,
            "w_cells": self.w_cells,
            "h_cells": self.h_cells,
            "fixed_size": self.fixed_size,
            "renderer": self.renderer_id,
        }