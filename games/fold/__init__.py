"""
Fold: a KAMI-style flood puzzle on a board of paper triangles.

Tap a triangle and choose a colour: its whole region folds over to that
colour and joins every touching region of the same colour. Make the board
one colour in as few moves as possible; par is the fewest possible.

Modules:
    triangles    triangle board geometry (moves to boardkit once a second game needs it)
    rules        the board, flood moves, regions and undo
    solver       fewest moves to solve a board (par)
    patterns     lattice measures (and the first wallpaper patterns)
    scenes       isometric block pictures: pillars, beams, stairs, blocks
    compose      designed geometric motifs: stars, rosettes, spirals, hives...
    collection   the curated Journey (as data) and Random puzzles by difficulty
    fold_motion  the scatter fold animation, forwards and for undo
    levels       the first blob generator (labs only now)
    palettes     paper colours (labs only now)
    screen       the library and the board (ui)
    entry        create_view() for the Maths Games launcher

Everything but screen and entry is pure Python, smoke-tested by
smokes/fold_smoke.py.
"""
