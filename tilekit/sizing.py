"""
TileKit object sizing.

An object's size is a span of grid cells, not a pixel measurement. A kind
declares how it wants to be sized; the framework searches for the smallest
span whose content fits.

Old Tile Calc sized this way and it is why its tiles read well at any zoom:
ensure_legible searched 1..4 cells for a span the label fitted, and only
then did _fit_label shrink the font. TileKit previously had the font step
alone, so long labels such as "d/dx(x^2)" shrank until unreadable inside a
one-cell tile.

Measurement is injected. tilekit core stays headless so it can be tested
without Pythonista's ui module; pass a real measure function from the UI
layer when one is available.
"""


# --- Editable defaults ------------------------------------------------------
# These are the framework's starting policy. Apps override per kind.

DEFAULT_MAX_CELLS = 4
DEFAULT_FONT_SIZE = 20.0

# Mean glyph width as a fraction of font size, for the headless estimate.
ESTIMATED_CHAR_RATIO = 0.6

# Space lost to border and padding on each axis, in points.
CELL_PADDING = 12.0


def estimate_text_width(text, font_size=DEFAULT_FONT_SIZE):
    """Return an approximate rendered width for text.

    A crude average-character estimate. Good enough to choose a cell span,
    and it lets sizing run headlessly. The UI layer should pass a real
    measure function when accuracy matters.
    """
    return len(str(text or "")) * float(font_size) * ESTIMATED_CHAR_RATIO


class SizePolicy:
    """How one kind of object chooses its cell span.

    Args:
        w_cells/h_cells: a fixed span. Set these for kinds that always
            occupy the same shape, such as a 2x2 image tile.
        fit_label:  when True, search 1..max_cells for the smallest width
            the object's label fits.
        max_cells:  widest span the search may return.
        font_size:  size the label is measured at before any font shrinking.
        min_w_cells/min_h_cells: floor for the search result.
    """

    def __init__(self, w_cells=None, h_cells=None, fit_label=False,
                 max_cells=DEFAULT_MAX_CELLS, font_size=DEFAULT_FONT_SIZE,
                 min_w_cells=1, min_h_cells=1):
        self.w_cells = w_cells
        self.h_cells = h_cells
        self.fit_label = bool(fit_label)
        self.max_cells = max(1, int(max_cells))
        self.font_size = float(font_size)
        self.min_w_cells = max(1, int(min_w_cells))
        self.min_h_cells = max(1, int(min_h_cells))

    def span_for(self, obj, grid=60.0, measure=None):
        """Return the (w_cells, h_cells) span this policy wants for obj.

        grid is the board's cell size in points. measure is an optional
        callable taking (text, font_size) and returning a width; the
        headless estimate is used when it is None.
        """
        height = self.h_cells if self.h_cells is not None else self.min_h_cells

        if self.w_cells is not None:
            return (max(self.min_w_cells, int(self.w_cells)),
                    max(self.min_h_cells, int(height)))

        if not self.fit_label:
            return (self.min_w_cells, max(self.min_h_cells, int(height)))

        width = self._fit_width(getattr(obj, "label", ""), grid, measure)
        return (width, max(self.min_h_cells, int(height)))

    def _fit_width(self, label, grid, measure):
        """Return the smallest cell width whose usable space fits label."""
        text = str(label or "")
        if not text.strip():
            return self.min_w_cells

        measure_fn = measure or estimate_text_width
        try:
            text_width = float(measure_fn(text, self.font_size))
        except Exception:
            text_width = estimate_text_width(text, self.font_size)

        for cells in range(self.min_w_cells, self.max_cells + 1):
            usable = cells * float(grid) - CELL_PADDING
            # The 1.06 margin matches old Tile Calc's ensure_legible: text
            # that only just fits looks cramped against the border.
            if text_width * 1.06 <= usable:
                return cells

        return self.max_cells


def apply_size_policy(obj, policy, grid=60.0, measure=None):
    """Set obj's cell span from policy, unless obj sized itself.

    Returns the span the object ended up with. Objects flagged fixed_size
    keep the span they have: that flag means a manual resize or a kind that
    sizes itself, and automatic sizing must not fight it.
    """
    if obj is None or policy is None:
        return None

    if getattr(obj, "fixed_size", False):
        return getattr(obj, "cell_span", None)

    span = policy.span_for(obj, grid=grid, measure=measure)
    setter = getattr(obj, "set_cell_span", None)
    if setter is not None:
        setter(span[0], span[1])
    return span