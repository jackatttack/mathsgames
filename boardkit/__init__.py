"""
boardkit: board geometry, motion and touch for Maths Games boards.

The pieces every grid game in Maths Games kept rebuilding, taken out once
and checked by smokes/boardkit_smoke.py. One of the kit family: TileKit
(the TileCalc workspace), boardkit, and a planned cardkit.

Modules:
    grid    where each cell's tile sits in a board view; which cell a touch hits
    paths   easing and motion paths: straight, arc, pulse
    clock   tracks for one frame clock: which views move, and where they are now
    folds   paper sheets turning over onto pieces: scatter chains, hinged
            turns, tiny squares (Fold's animation, shared; Double Up uses it)
    fold_layer  ui adapter: a see-through FoldLayer that plays fold shows
            over a board on its own frame clock (Sudoku's unfold uses it)

House rules:
    - Pure Python unless a module says otherwise (a ui adapter gets its own
      module), so everything smokes headless and runs the same in
      Pythonista and PythonIDE.
    - No game rules, levels or colours: games own those.
    - A piece earns a place here once two games need it.
    - Animation follows library/guides/pythonista-ui-stability.md: one frame
      clock with update_interval set once, or ui.animate with no completion.

Lives inside Maths Games until it is worth its own project.
"""
