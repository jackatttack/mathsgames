# Maths Games

Quick, tactile maths games for iPhone and iPad, built in Pythonista.
Big number tiles, four operations, and puzzles from a spare minute to a
proper challenge.

## Install

Paste this into a new script in Pythonista and run it:

    import urllib.request
    url = ('https://raw.githubusercontent.com/'
           'jackatttack/mathsgames/main/install.py')
    source = urllib.request.urlopen(url).read()
    exec(compile(source, 'install.py', 'exec'), {'__name__': '__main__'})

It installs everything into `Documents/Maths Games/` and opens the launcher.

## Play

Run `Maths Games/launch_mathsgames.py`. Pick a game from the home screen; the
back arrow returns to it and the cross closes the app.

## The games

### Multiple Merge

Tap a number and it splits into four operation quadrants (+ − × ÷). Choose
one, then tap a neighbouring tile: the numbers merge into the result.

- Classic: make as many multiples of a chosen number as you can from one
  board (10, 20 … 100 by default).
- Target: make one number. Exact solves score 10 and build a streak; skip
  and your closest value scores Countdown-style points. Easy, medium and
  hard targets, on mixed boards, four-of-a-kind boards or three-plus-one.

### Countdown

Six numbers, one three-digit target, any two tiles at a time. Results must
be positive whole numbers. Choose how many big numbers (25, 50, 75, 100) in
Settings. No clock: your solve time is shown instead.

Both games have optional hints (in Settings): tap the target to see the
next step, tap again to play it. Double-tap empty board to undo.

## Updating

Run the install snippet again. The games are replaced with the latest
version; your settings are kept.

## Making your own game

Every game is a folder in `games/` plus one line in
`gamecore/catalogue.py`. See `docs/ADDING_A_GAME.md`.

## Project layout

    launch_mathsgames.py   run this to play
    install.py             install or update
    launcher/              home screen, shared header, app shell
    gamecore/              game contract and catalogue
    games/                 one folder per game
    tilegame/              shared tile board, rules, widgets and scoring
    tilekit/               the TileKit board engine
    style/                 colours, fonts, layout tokens
    feel/                  touch feedback and haptics
    docs/                  guides

## Requirements

Pythonista 3 on iPhone or iPad.

## Licence

See LICENSE.