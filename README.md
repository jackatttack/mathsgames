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
  board (10, 20 … 100 by default). Each board is timed, and your best time
  is kept for that multiple and number of targets.
- Classic for two: choose 2 players in Settings. Tap your name before you
  merge; the targets you make light up in your colour, and the player with
  the most targets wins.
- Target: make one number. Exact solves score 10 and build a streak; skip
  and your closest value scores Countdown-style points. Easy, medium, hard
  and tricky targets (tricky ones need a negative or a fraction along the
  way), on mixed boards, four-of-a-kind boards or three-plus-one.

### Countdown

Six numbers, one three-digit target, any two tiles at a time. Results must
be positive whole numbers. In Settings, choose how many big numbers (25, 50,
75, 100), or Mix for a random number each board, and a difficulty: how many
numbers the answer needs. Normal varies from three to all six; or choose
exactly five, or all six.

Play is a timed run of five boards. Skipping adds a penalty you set in
Settings, and your best time for each set of rules is kept and shown at the
start of every run.

Both games have optional hints (in Settings): tap the target to see the
next step, tap again to play it. Double-tap empty board to undo.

## Updating

Run the install snippet again. The games are replaced with the latest
version; your settings and best times are kept.

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