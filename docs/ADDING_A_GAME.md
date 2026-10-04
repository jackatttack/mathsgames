# Adding a game

A game is a folder in `games/` plus one record in `gamecore/catalogue.py`.
Nothing else needs to change: the home screen draws a card for it and the
shell opens it under the shared header.

## 1. Make the folder

    games/my_game/
        __init__.py
        entry.py       create_view() returns one ui.View
        rules.py       the game's maths, no UIKit
        screen.py      the view

`entry.py` is the only file the app imports when your game opens:

    def create_view():
        return MyGameScreen()

## 2. Add it to the catalogue

    GameInfo(
        game_id="my_game",              # also the folder name
        title="My Game",
        tagline="One line for the card",
        icon="42",                      # a short glyph for the badge
        accent="mint",                  # a colour name from style/theme.py
        entry="games.my_game.entry:create_view",
        status="in development",        # "playable" hides the status line
    )

## 3. Optional: use the header

The shell's header shows your title. Your view can opt in to more:

    open_settings()      define it and a gear appears that calls it
    header_subtitle      a short line under the title
    on_header_changed    attached by the shell; call it after changing
                         header_subtitle so the header updates

## Shared pieces you can build on

- `tilegame/board_state.py`: a grid of exact values with pluggable rules.
  `merge_rule` decides which cells may merge (`orthogonal_neighbours`,
  `any_pair`); `result_rule` decides which results are allowed
  (`any_exact_value`, `positive_whole_numbers`). Undo and reset included.
- `tilegame/model.py`: the select, arm an operation, tap a target state
  machine.
- `tilegame/ui.py`: number tiles with operation quadrants and a fixed board
  view that animates merges and highlights legal moves.
- `tilegame/targets.py`: one target round, Countdown-style scoring and a
  session with score and streak.
- `tilegame/widgets.py`: buttons, labels, choice rows and the target banner.

Multiple Merge and Countdown are complete examples of all of this.

## House rules

- Keep rules headless: no `ui` import in `rules.py`, so they can be tested
  anywhere.
- Take colours from `style/theme.py`; add a token there rather than a hex
  value in your game.
- Change the UI only inside the tap that caused it; no timers that touch
  views. Pythonista crashes hard and without a traceback otherwise.
- Save settings next to your game (`games/my_game/settings.json`); the
  installer keeps every `settings.json` when it updates.