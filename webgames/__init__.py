"""webgames: Maths Games drawn on editorkit.web, the web frame work.

Each game's rules, settings, saved game and best times are the native
game's own (imported, never copied), so a game carries on between the two
versions and both keep one set of best times. Only the screen is a web
page. Needs the editorkit package, which Toolbox for Pythonista installs.

    import webgames
    webgames.open_game('sudoku')                       # full screen
    webgames.open_game('sudoku', full_screen=False)    # in a window
"""
import importlib
import traceback


# Games ported so far: the module name is the Maths Games game id.
PORTED = ('sudoku',)

ERROR_KEY = 'webgames-error'
NEEDS_EDITORKIT = ('The web games need editorkit: install Toolbox for Pythonista '
                   '(github.com/jackatttack/editorkit), then run this again.')


def open_game(game_id, full_screen=True):
    """Open one web game. Returns its WebGameHost, or None when it could not
    be opened (a window or the console says why)."""
    try:
        import editorkit as ek
    except ImportError:
        print(NEEDS_EDITORKIT)
        return None
    try:
        from . import shell
        info = shell.find_game(game_id)
        if info is None:
            raise RuntimeError('Maths Games has no game %r' % game_id)
        if game_id not in PORTED:
            raise RuntimeError('%s has no web version yet' % info.title)
        module = importlib.import_module('%s.%s' % (__name__, game_id))
        host = shell.WebGameHost(module.Game(), info)
    except Exception:
        details = traceback.format_exc()
        print(details)
        ek.show("Couldn't open the web %s.\n\n%s" % (game_id, details),
                title='Maths Games (web)', key=ERROR_KEY)
        return None
    host.window.show()
    if full_screen:
        host.window.when_still(lambda window: window.to_full())
    return host