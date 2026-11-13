"""The Maths Games shell on editorkit.web: one window per game.

From webports' shell (projects/webports, 2026-11-12), made to ship with
Maths Games: it finds Maths Games from its own folder (this package sits
inside it), so it needs nothing from Toolbox but the editorkit package.

What the native shell's header contract becomes on the web:

    the title and subtitle   the window title, "Sudoku (web) · 9×9 · Medium"
    settings                 ⚙️ in the header swaps the page to the game's
                             settings page; ⚙️ again closes it, discarding the
                             draft (as Back does natively)
    HOW_TO_PLAY.txt          ❓ opens it as a themed web page

The game's own Maths Games theme (style/theme.py) becomes CSS variables,
--mg-<role>, and its celebration colours --mg-cel-<n>.

A game module's Game class offers:

    html()            the page to show now (the game, or its settings)
    go(payload)       a tap on an element with data-go="payload"
    subtitle()        the header subtitle
    toggle_settings() open or close its settings page
    CSS, THEME_TOKENS (optional) its own styles and the theme roles it uses
    celebration_count set by the shell: how many --mg-cel-<n> there are

Every tap redraws the whole page.
"""
import html
import os
import sys
import traceback

import editorkit as ek
from editorkit.web import tiles as web_tiles


# --- Settings -------------------------------------------------------------

MATHS_GAMES_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WINDOW_EMOJI = '🌐'
WINDOW_KEY = 'webgames-%s'
HELP_KEY = 'webgames-help-%s'
TITLE_SUFFIX = ' (web)'
CELEBRATION_COLOURS = 9         # one per number on the biggest board
SETTINGS_ICON = '⚙️'
HELP_ICON = '❓'

# Maths Games theme roles offered to pages as --mg-<role>, unless the game
# names its own. Roles a game's theme does not know are skipped.
THEME_TOKENS = ('background', 'surface', 'tile', 'tile_text', 'target_chip',
                'target_chip_text', 'button', 'button_text', 'text', 'muted')

BASE_CSS = """
html, body { background: var(--mg-background) !important; color: var(--mg-text); }
#results { font: 16px "Avenir Next", -apple-system, sans-serif; white-space: normal;
    padding: 8px 6px 24px 6px; }
.mg-page { max-width: 460px; margin: 0 auto; }
.mg-button { display: flex; align-items: center; justify-content: center;
    min-height: 48px; padding: 0 12px; border-radius: 12px;
    background: var(--mg-button); color: var(--mg-button_text, var(--mg-text));
    font-weight: 600; cursor: pointer; }
.mg-button.primary { background: var(--mg-tile); color: var(--mg-tile_text, var(--mg-background)); }
.mg-button.off { opacity: 0.35; }
.mg-row { display: flex; gap: 12px; }
.mg-row > .mg-button { flex: 1; }
.mg-chips { display: flex; flex-wrap: wrap; gap: 8px; }
.mg-chip { padding: 9px 15px; border-radius: 18px; background: var(--mg-button);
    color: var(--mg-button_text, var(--mg-text)); font-weight: 600; cursor: pointer; }
.mg-chip.on { background: var(--mg-tile); color: var(--mg-tile_text, var(--mg-background)); }
.mg-chip.off { opacity: 0.35; cursor: default; }
.mg-caption { color: var(--mg-muted); font-size: 15px; margin: 18px 0 8px 0; }
.mg-note { color: var(--mg-muted); font-size: 13px; margin: 6px 0 0 0; min-height: 18px; }
.mg-title { font-size: 24px; font-weight: 700; margin: 6px 0 2px 0; }
"""


# --- Maths Games ------------------------------------------------------------

def use_maths_games():
    """Make Maths Games importable (Pythonista resets sys.path on every run)."""
    if MATHS_GAMES_DIR not in sys.path:
        sys.path.insert(0, MATHS_GAMES_DIR)
    return MATHS_GAMES_DIR


def find_game(game_id):
    """The catalogue's GameInfo for game_id, or None."""
    use_maths_games()
    from gamecore.catalogue import GAMES
    for info in GAMES:
        if info.game_id == game_id:
            return info
    return None


def css_colour(value):
    """A theme colour as CSS: '#RRGGBB' (alpha cut: the old web view ignores
    #RRGGBBAA) or rgb() from a (r, g, b) tuple; None when unreadable."""
    if isinstance(value, str):
        return value[:7] if value.startswith('#') and len(value) > 7 else value
    if isinstance(value, (tuple, list)) and len(value) >= 3:
        parts = [float(part) for part in value[:3]]
        if max(parts) <= 1.0:
            parts = [part * 255 for part in parts]
        return 'rgb(%d, %d, %d)' % tuple(int(round(part)) for part in parts)
    return None


def theme_css(game_id, tokens=THEME_TOKENS):
    """(css, celebration count): the game's own theme roles as --mg-<role>,
    and its celebration colours as --mg-cel-0, --mg-cel-1 ..."""
    from style import theme
    theme.set_game(game_id)
    lines = []
    count = 0
    try:
        for token in tokens:
            try:
                value = css_colour(theme.color(token))
            except Exception:
                value = None
            if value:
                lines.append('--mg-%s: %s;' % (token, value))
        try:
            for colour in theme.celebration_colors(CELEBRATION_COLOURS):
                value = css_colour(colour)
                if value:
                    lines.append('--mg-cel-%d: %s;' % (count, value))
                    count += 1
        except Exception:
            traceback.print_exc()
    finally:
        theme.set_game(None)            # leave the native games as they were
    return ':root { %s }\n' % ' '.join(lines), count


def ui_colour(value):
    """A theme colour for a ui view: '#RRGGBB' (alpha cut), or the value as given."""
    if isinstance(value, str) and value.startswith('#') and len(value) > 7:
        return value[:7]
    return value


def header_colours(game_id):
    """The game's own background, button, text and tile colours, for the
    full-screen header (editorkit's Window.set_full_look)."""
    from style import theme
    theme.set_game(game_id)
    try:
        return {'background': ui_colour(theme.color('background')),
                'button': ui_colour(theme.color('button')),
                'text': ui_colour(theme.color('text')),
                'accent': ui_colour(theme.color('tile'))}
    finally:
        theme.set_game(None)


def load_help_card(info):
    try:
        from gamecore import how_to_play
        return how_to_play.load_card(info)
    except Exception:
        traceback.print_exc()
        return None


def help_html(card):
    """A HelpCard as an HTML fragment: headings, paragraphs and bullet lists."""
    from gamecore import how_to_play
    out = []
    in_list = False
    for kind, text in card.blocks:
        text = html.escape(text)
        if kind == how_to_play.BULLET:
            if not in_list:
                out.append('<ul>')
                in_list = True
            out.append('<li>%s</li>' % text)
            continue
        if in_list:
            out.append('</ul>')
            in_list = False
        if kind == how_to_play.HEADING:
            out.append('<h3>%s</h3>' % text)
        else:
            out.append('<p>%s</p>' % text)
    if in_list:
        out.append('</ul>')
    return '\n'.join(out)


# --- The window ---------------------------------------------------------------

class WebGameHost:
    """One web game in an editorkit window: the page, ⚙️ and ❓."""

    def __init__(self, game, info):
        self.game = game
        self.info = info
        self.window = ek.Window(info.title + TITLE_SUFFIX, emoji=WINDOW_EMOJI,
                                key=WINDOW_KEY % info.game_id)
        css, count = theme_css(info.game_id, getattr(game, 'THEME_TOKENS', THEME_TOKENS))
        game.celebration_count = count
        self.page = web_tiles.Cards(self.window, on_go=self.tapped,
                                    extra_css=css + BASE_CSS + getattr(game, 'CSS', ''))
        self.match_header(info.game_id)
        self.page.every(self.keep_importable)
        self.window.add_page(info.title, self.page)
        self.window.add_button(SETTINGS_ICON, self.settings_tapped, name='settings')
        self.help_card = load_help_card(info)
        if self.help_card is not None:
            self.window.add_button(HELP_ICON, self.help_tapped, name='help')
        self.draw()

    def match_header(self, game_id):
        """Full screen in the game's own colours, header included, so the
        screen is one surface. Older editorkit has no set_full_look: skipped."""
        set_full_look = getattr(self.window, 'set_full_look', None)
        if set_full_look is None:
            return
        try:
            set_full_look(**header_colours(game_id))
        except Exception:
            traceback.print_exc()

    def keep_importable(self, now=None):
        use_maths_games()

    def draw(self):
        self.page.set_html('<div class="mg-page">%s</div>' % self.game.html())
        title = self.info.title + TITLE_SUFFIX
        subtitle = self.game.subtitle()
        self.window.set_title('%s · %s' % (title, subtitle) if subtitle else title)

    def tapped(self, payload):
        try:
            self.game.go(payload)
        except Exception:
            traceback.print_exc()
        self.draw()

    def settings_tapped(self, *sender):
        self.game.toggle_settings()
        self.draw()

    def help_tapped(self, *sender):
        ek.show(help_html(self.help_card), title='How to play %s' % self.info.title,
                key=HELP_KEY % self.info.game_id)