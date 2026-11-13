"""Sudoku (web): Maths Games' Sudoku on the web frame work, full screen.

Run it, or point a Shortcut at it to open Sudoku like an app. It plays the
same game as the native Sudoku: settings, the puzzle in progress and best
times are shared. Needs Toolbox for Pythonista (its editorkit package).
"""
import os
import sys


HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for name in [name for name in sys.modules if name.split('.')[0] == 'webgames']:
    del sys.modules[name]

import webgames


webgames.open_game('sudoku')