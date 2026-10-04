#<games:maths-games>

"""
Maths Games — run directly in Pythonista.

Opens the home screen listing every game in gamecore/catalogue.py.
"""

import os
import sys


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)


from gamecore.catalogue import GAMES
from launcher.shell import AppShell


def main():
    shell = AppShell(GAMES)
    shell.name = "Maths Games"
    # The shell draws its own header, with a close button on the home screen.
    shell.present("fullscreen", hide_title_bar=True)


if __name__ == "__main__":
    main()
