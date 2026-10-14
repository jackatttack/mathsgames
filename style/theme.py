"""
The Maths Games theme: every colour, font, radius and timing in one place.

Games and the launcher ask for tokens by name. They never define their own
hex values or durations, so changing a value here changes the whole app.

Colours come from the player's theme choices (notes/THEME_EDITOR_SPEC.txt
v2): a palette family, an app accent and a colour-blind-safe feedback
switch, and per game a family and role choices from curated swatches. Role
tokens (board, grid_line, note and so on) give each job on a game screen
its own colour; left at Default they follow the shared token they replaced.
The choices live in style/settings.json, which the installer keeps and the
release never ships. With no file the app looks exactly as it always has:
Midnight with the warm accent.

The shell calls set_game() before building a game and re-imports the game
packages, so module-level colour constants read that game's colours.
"""

import json
import os


# --- colours -----------------------------------------------------------------

# Midnight with the warm accent: the default look, and the base every
# palette starts from.
COLORS = {
    # Surfaces and text
    "background": "#0E1422",
    "surface": "#1A2440",
    "text": "#F7F9FC",
    "muted": "#A9B8E8",
    "button": "#2A3554",       # round icon buttons and secondary buttons

    # Accents: one per game family, used by launcher cards and highlights
    "warm": "#F3B467",
    "coral": "#F28B82",
    "mint": "#7FD8BE",
    "sky": "#7CB7FF",
    "violet": "#B69CFF",

    # Tile games: number tiles and the four operations
    "tile": "#F3B467",                 # the main accent; set by the accent choice
    "tile_text": "#172033",
    "op_add": "#EA718D",
    "op_subtract": "#6EA8FF",
    "op_multiply": "#5ED3A2",
    "op_divide": "#A98AF4",
    "op_text": "#FFFFFF",              # operation symbols on their quadrants
    "tile_border": "#FFFFFF36",        # a tile at rest
    "tile_border_armed": "#FFFFFF",    # the selected tile while a move is armed
    "tile_border_valid": "#F7F9FC",    # a tile that can take the move; follows text

    # Game feedback
    "success": "#5ED3A2",              # a found target or a solved board
    "mistake": "#F28B82",              # a clash or a wrong answer
    "chip_disabled": "#161D30",        # a target this board cannot make
    "chip_disabled_text": "#4A5470",

    # Grid assists: the tapped cell's row, column and box, and matching numbers
    "assist_peer": "#27355E",
    "assist_match": "#3F68AD",

    # Two-player games: each player's buttons and found targets
    "player_one": "#7CB7FF",
    "player_two": "#F28B82",
}


# --- palette families --------------------------------------------------------

# The only tokens a family may change. Everything else is fixed.
FAMILY_TOKENS = (
    "background", "surface", "text", "muted", "button",
    "assist_peer", "assist_match", "chip_disabled", "chip_disabled_text",
)

FAMILIES = {
    "midnight": {"label": "Midnight"},      # COLORS as they are
    "graphite": {
        "label": "Graphite",
        "background": "#121316",
        "surface": "#1E2026",
        "text": "#F5F6F8",
        "muted": "#AEB4C0",
        "button": "#2C2F37",
        "assist_peer": "#2A2E38",
        "assist_match": "#46536E",
        "chip_disabled": "#17191E",
        "chip_disabled_text": "#4D525E",
    },
    "forest": {
        "label": "Forest",
        "background": "#0D1714",
        "surface": "#18271F",
        "text": "#F3F8F4",
        "muted": "#A7C4B4",
        "button": "#253A2F",
        "assist_peer": "#22382C",
        "assist_match": "#3E6B55",
        "chip_disabled": "#132019",
        "chip_disabled_text": "#45594E",
    },
}
FAMILY_ORDER = ("midnight", "graphite", "forest")


# --- accents -----------------------------------------------------------------

# (label, accent colour, text on the accent). Chosen to stay clear of the
# success and mistake colours so a tile never reads as feedback.
ACCENTS = {
    "warm": ("Warm", "#F3B467", "#172033"),
    "gold": ("Gold", "#F2D16B", "#172033"),
    "sand": ("Sand", "#E8D5B0", "#172033"),
    "rose": ("Rose", "#F49AC1", "#172033"),
    "violet": ("Violet", "#B69CFF", "#172033"),
    "sky": ("Sky", "#7CB7FF", "#172033"),
    "teal": ("Teal", "#4FC3C7", "#172033"),
    "silver": ("Silver", "#C9D2E3", "#172033"),
}
ACCENT_ORDER = ("warm", "gold", "sand", "rose", "violet", "sky", "teal", "silver")

# Colour-blind-safe feedback: blue for right, orange for wrong.
SAFE_FEEDBACK = {"success": "#4EA1FF", "mistake": "#FF9F43"}


# --- roles -------------------------------------------------------------------

# One token per job on a game screen, each derived from the shared token it
# replaced. Derivation runs after a game's own choices, so a role left at
# Default follows its source even when the game changed that source: pick
# new Tiles and the target chip follows, unless it has its own choice.
# With no choices every game looks exactly as it did before roles existed.
# (role, derived from), in resolving order.
DERIVED_ROLES = (
    ("board", "surface"),               # grid board cells
    ("grid_line", "button"),            # thin lines between cells
    ("box_wall", "muted"),              # Sudoku box walls, KenKen cage walls
    ("given", "text"),                  # Sudoku givens, KenKen numbers
    ("player_number", "sky"),           # numbers the player writes
    ("note", "muted"),                  # pencil marks
    ("selection_fill", "button"),       # the selected cell
    ("selection", "tile"),              # the selected cell's outline
    ("target_chip", "tile"),            # the target in a banner
    ("target_chip_text", "background"), # text on the target chip, as it always was
    ("open_chip", "button"),            # a target you can still make (Multiple Merge)
    ("open_outline", "sky"),            # the tile being named (Number Detective)
)


# --- swatches ----------------------------------------------------------------

# The player picks from short curated rows, never a free colour. Each
# choosable role has a kind, and the kind decides its row of swatches.
ROLE_KINDS = {
    "background": "surface",
    "surface": "surface",
    "board": "surface",
    "button": "surface",
    "selection_fill": "surface",
    "open_chip": "surface",
    "text": "ink",
    "given": "ink",
    "player_number": "ink",
    "note": "ink",
    "grid_line": "line",
    "box_wall": "line",
    "assist_peer": "highlight",
    "assist_match": "highlight",
    "tile": "accent",
    "selection": "accent",
    "target_chip": "accent",
    "open_outline": "accent",
}

# Accent roles that carry text: choosing the accent also sets its text.
ACCENT_TEXT = {"tile": "tile_text", "target_chip": "target_chip_text"}

# (id, label, colour) in offer order. The accent kind is ACCENTS itself.
SWATCHES = {
    "surface": (
        ("night", "Night", "#0E1422"),
        ("navy", "Navy", "#1A2440"),
        ("dusk", "Dusk", "#2A3554"),
        ("charcoal", "Charcoal", "#1E2026"),
        ("pine", "Pine", "#18271F"),
        ("plum", "Plum", "#2A1E33"),
        ("cocoa", "Cocoa", "#2B211C"),
        ("black", "Black", "#08090B"),
    ),
    "ink": (
        ("white", "White", "#F7F9FC"),
        ("mist", "Mist", "#A9B8E8"),
        ("sky", "Sky", "#7CB7FF"),
        ("mint", "Mint", "#7FD8BE"),
        ("butter", "Butter", "#F2D16B"),
        ("blush", "Blush", "#F49AC1"),
    ),
    "line": (
        ("shadow", "Shadow", "#2A3554"),
        ("steel", "Steel", "#4A5470"),
        ("fog", "Fog", "#7A86A6"),
        ("mist", "Mist", "#A9B8E8"),
        ("pale", "Pale", "#DDE3F0"),
    ),
    "highlight": (
        ("dusk", "Dusk", "#27355E"),
        ("denim", "Denim", "#3F68AD"),
        ("iron", "Iron", "#46536E"),
        ("moss", "Moss", "#3E6B55"),
        ("plum", "Plum", "#5A3F7A"),
        ("teal", "Teal", "#2F6670"),
    ),
}

# Minimum WCAG contrast for each (foreground, background) token pair. A
# swatch is offered only if every rule it changes still passes, and the
# defaults pass them all on every family (smokes/theme_smoke.py). Numbers
# on highlighted cells are large digits, so they use the 3:1 large-text rule.
CONTRAST_RULES = (
    ("text", "background", 4.5),
    ("text", "surface", 4.5),
    ("text", "button", 4.5),
    ("text", "open_chip", 4.5),
    ("muted", "background", 3.0),
    ("tile_text", "tile", 4.5),
    ("target_chip_text", "target_chip", 4.5),
    ("given", "board", 4.5),
    ("player_number", "board", 4.5),
    ("note", "board", 3.0),
    ("grid_line", "board", 1.15),
    ("box_wall", "board", 1.5),
    ("selection", "board", 3.0),
    ("open_outline", "background", 3.0),
    ("given", "selection_fill", 4.5),
    ("player_number", "selection_fill", 4.5),
    ("given", "assist_peer", 3.0),
    ("given", "assist_match", 3.0),
)


# --- type --------------------------------------------------------------------

FONTS = {
    "title": ("AvenirNext-Bold", 30),
    "heading": ("AvenirNext-Bold", 20),
    "header": ("AvenirNext-Bold", 18),     # the shared header title
    "body": ("AvenirNext-Medium", 15),
    "caption": ("AvenirNext-Medium", 12),
    "icon": ("AvenirNext-Bold", 30),
}


# --- shape -------------------------------------------------------------------

RADII = {
    "card": 20,
    "badge": 16,
}


# --- layout ------------------------------------------------------------------

# Points. The app presents with the Pythonista title bar hidden, so safe_top
# keeps the shared header clear of the status bar and notch.
LAYOUT = {
    "safe_top": 50,
    "header_height": 44,
    "icon_button": 40,
}


# --- feel --------------------------------------------------------------------

# Seconds for touch feedback. Short press, slightly longer spring back.
TIMINGS = {
    "press": 0.07,
    "release": 0.16,
}

# How far a pressed card or button shrinks.
PRESS_SCALE = 0.96


# --- the player's choices ----------------------------------------------------

CHOICES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")

DEFAULT_CHOICES = {
    "family": "midnight",
    "accent": "warm",
    "safe_feedback": False,
    # game_id -> {"family": name, "roles": {role: swatch_id}}, only where a
    # game differs. An absent family means "Same as All games".
    "games": {},
}


def clean_choices(raw):
    """Valid choices from anything: unknown or missing values become defaults.

    Also migrates v1 choices: "game_accents" (one accent per game) becomes
    that game's tile role, unless the game already chose its tiles.
    """
    choices = dict(DEFAULT_CHOICES, games={})
    if not isinstance(raw, dict):
        return choices
    if raw.get("family") in FAMILIES:
        choices["family"] = raw["family"]
    if raw.get("accent") in ACCENTS:
        choices["accent"] = raw["accent"]
    if isinstance(raw.get("safe_feedback"), bool):
        choices["safe_feedback"] = raw["safe_feedback"]

    games = raw.get("games")
    if isinstance(games, dict):
        for game_id, entry in games.items():
            cleaned = _clean_game(entry)
            if cleaned:
                choices["games"][str(game_id)] = cleaned

    v1_accents = raw.get("game_accents")
    if isinstance(v1_accents, dict):
        for game_id, accent in v1_accents.items():
            if accent in ACCENTS:
                entry = choices["games"].setdefault(str(game_id), {})
                entry.setdefault("roles", {}).setdefault("tile", accent)
    return choices


def _clean_game(entry):
    """One game's valid choices; empty when nothing differs from All games."""
    if not isinstance(entry, dict):
        return {}
    cleaned = {}
    if entry.get("family") in FAMILIES:
        cleaned["family"] = entry["family"]
    roles = entry.get("roles")
    if isinstance(roles, dict):
        kept = {
            role: swatch_id
            for role, swatch_id in roles.items()
            if role in ROLE_KINDS and swatch_id in swatch_ids(ROLE_KINDS[role])
        }
        if kept:
            cleaned["roles"] = kept
    return cleaned


def load_choices(path=CHOICES_PATH):
    """Read saved choices. A missing or broken file gives the defaults."""
    try:
        with open(path) as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        return clean_choices(None)
    except (OSError, ValueError) as error:
        print("Maths Games: ignoring theme file: {}".format(error))
        return clean_choices(None)
    return clean_choices(raw)


def save_choices(choices, path=CHOICES_PATH, use_now=True):
    """Save choices synchronously. With use_now, colours follow them at once."""
    global _choices, _cache
    cleaned = clean_choices(choices)
    temporary = path + ".tmp"
    with open(temporary, "w") as handle:
        json.dump(cleaned, handle, indent=2)
    os.replace(temporary, path)
    if use_now:
        _choices = cleaned
        _cache = {}
    return cleaned


# --- resolving colours -------------------------------------------------------

_choices = None     # loaded on first use
_game_id = None     # the open game, or None for the launcher
_cache = {}         # game_id -> palette for the current choices
_override = None    # a whole palette, used while a preview board is built


def current_choices():
    global _choices
    if _choices is None:
        _choices = load_choices()
    return _choices


def palette(choices=None, game_id=None):
    """Every colour token for these choices, as seen inside game_id.

    Pure apart from reading the current choices when none are given, so the
    theme editor can preview choices before saving them.
    """
    if choices is None:
        choices = current_choices()
    game = choices["games"].get(game_id, {}) if game_id is not None else {}

    # 1. Family: the game's own, else the app's.
    colors = dict(COLORS)
    family = FAMILIES[game.get("family", choices["family"])]
    colors.update({name: family[name] for name in FAMILY_TOKENS if name in family})

    # 2. App accent.
    _, colors["tile"], colors["tile_text"] = ACCENTS[choices["accent"]]

    # 3. The game's role choices.
    chosen = {}
    for role, swatch_id in game.get("roles", {}).items():
        chosen.update(role_colors(role, swatch_id))
    colors.update(chosen)

    # 4. Roles left at Default follow their source.
    for role, source in DERIVED_ROLES:
        if role not in chosen:
            colors[role] = colors[source]
    colors["tile_border_valid"] = colors["text"]

    # 5. Feedback is never a role; only the safe switch changes it.
    if choices["safe_feedback"]:
        colors.update(SAFE_FEEDBACK)
    return colors


def set_game(game_id):
    """Resolve colours as seen inside this game from now on (None: launcher)."""
    global _game_id
    _game_id = game_id


def preview_palette(colors):
    """Answer color() from colors until preview_palette(None).

    Only for building a preview board in colours that are not saved yet
    (launcher/appearance.py). Always clear it in a finally block.
    """
    global _override
    _override = colors


def color(name):
    """Return the colour for a token name, failing clearly if it is unknown."""
    colors = _override if _override is not None else _cache.get(_game_id)
    if colors is None:
        colors = _cache[_game_id] = palette(current_choices(), _game_id)
    try:
        return colors[name]
    except KeyError:
        raise KeyError(
            "Unknown colour token %r; add it to style/theme.py COLORS" % name
        )


def font(name):
    """Return the (font name, size) pair for a token name."""
    try:
        return FONTS[name]
    except KeyError:
        raise KeyError(
            "Unknown font token %r; add it to style/theme.py FONTS" % name
        )


# --- contrast ----------------------------------------------------------------

def rgb(hex_color):
    """(r, g, b) from 0 to 1 for '#RRGGBB' (any alpha digits are ignored)."""
    text = str(hex_color).lstrip("#")[:6]
    return tuple(int(text[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def luminance(hex_color):
    """WCAG relative luminance."""
    def channel(value):
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(value) for value in rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(first, second):
    """WCAG contrast ratio between two colours, from 1 to 21."""
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def accents_for_family(family):
    """Accents offered on this family: readable text on them, visible on it."""
    background = FAMILIES[family].get("background", COLORS["background"])
    return [
        name for name in ACCENT_ORDER
        if contrast(ACCENTS[name][1], background) >= 3
        and contrast(ACCENTS[name][2], ACCENTS[name][1]) >= 4.5
    ]


# --- per-game roles ----------------------------------------------------------

def swatch_ids(kind):
    """Swatch ids for a kind, in offer order."""
    if kind == "accent":
        return ACCENT_ORDER
    return tuple(swatch_id for swatch_id, _, _ in SWATCHES[kind])


def swatch_label(kind, swatch_id):
    """The name shown under a swatch."""
    if kind == "accent":
        return ACCENTS[swatch_id][0]
    return _swatch_entry(kind, swatch_id)[1]


def _swatch_entry(kind, swatch_id):
    for entry in SWATCHES[kind]:
        if entry[0] == swatch_id:
            return entry
    raise KeyError("Unknown %s swatch %r" % (kind, swatch_id))


def role_colors(role, swatch_id):
    """The tokens one role choice sets: the role, and for accents its text."""
    kind = ROLE_KINDS[role]
    if kind != "accent":
        return {role: _swatch_entry(kind, swatch_id)[2]}
    _, accent, text = ACCENTS[swatch_id]
    colors = {role: accent}
    if role in ACCENT_TEXT:
        colors[ACCENT_TEXT[role]] = text
    return colors


def game_family(choices, game_id):
    """The family this game chose, or None for "Same as All games"."""
    return choices["games"].get(game_id, {}).get("family")


def game_role(choices, game_id, role):
    """The swatch this game chose for role, or None for Default."""
    return choices["games"].get(game_id, {}).get("roles", {}).get(role)


def with_game_family(choices, game_id, family):
    """A cleaned copy of choices with this game's family set; None follows All games."""
    if game_id is None:
        raise ValueError("a game family needs a game id")
    raw = _copy(choices)
    entry = raw["games"].setdefault(game_id, {})
    if family is None:
        entry.pop("family", None)
    else:
        entry["family"] = family
    return clean_choices(raw)


def with_game_role(choices, game_id, role, swatch_id):
    """A cleaned copy of choices with one game's role set; None means Default."""
    if game_id is None:
        raise ValueError("roles are chosen per game, not for the launcher")
    if role not in ROLE_KINDS:
        raise KeyError("Role %r cannot be chosen; see ROLE_KINDS" % role)
    raw = _copy(choices)
    roles = raw["games"].setdefault(game_id, {}).setdefault("roles", {})
    if swatch_id is None:
        roles.pop(role, None)
    else:
        roles[role] = swatch_id
    return clean_choices(raw)


def swatches_for(choices, game_id, role):
    """Swatch ids offered for role in this game, in offer order.

    A swatch is offered only if every contrast rule touching a colour it
    changes still passes. Default is always offered too and is not listed.
    """
    current = palette(choices, game_id)
    offered = []
    for swatch_id in swatch_ids(ROLE_KINDS[role]):
        trial = palette(with_game_role(choices, game_id, role, swatch_id), game_id)
        changed = {name for name in trial if trial[name] != current[name]}
        if all(
            contrast(trial[foreground], trial[background]) >= minimum
            for foreground, background, minimum in CONTRAST_RULES
            if foreground in changed or background in changed
        ):
            offered.append(swatch_id)
    return offered


def _copy(choices):
    """A deep copy of plain JSON choices, so callers' drafts never alias."""
    return json.loads(json.dumps(choices))