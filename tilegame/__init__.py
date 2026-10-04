"""Shared tile-game layer for Maths Games.

board_state  values, pluggable merge and result rules, moves, undo
model        the pending-move state machine (select, arm, target)
ui           number tile view with operation quadrants, fixed board view

Games build on these and keep their own rules, dealing and scoring.
"""