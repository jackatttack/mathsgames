"""
How-to-play cards: the rules each game shows behind the header's ? button.

Each game keeps its rules in games/<game_id>/HOW_TO_PLAY.txt, in a tiny
plain-text format that can be edited without touching code:

    A paragraph is one or more lines; a blank line ends it.
    ## Heading      a section heading
    - item         a bullet point, one line each

Nothing here imports game code or UIKit, so the shell can load a card
cheaply when a game opens. A game without the file simply has no ? button.
"""

import os
from dataclasses import dataclass

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILE_NAME = "HOW_TO_PLAY.txt"

HEADING = "heading"
PARAGRAPH = "paragraph"
BULLET = "bullet"


@dataclass(frozen=True)
class HelpCard:
    """One game's rules: its title and (kind, text) blocks in reading order."""

    title: str
    blocks: tuple


def card_path(game_id):
    return os.path.join(PROJECT_DIR, "games", game_id, FILE_NAME)


def parse_card(title, text):
    """Turn the plain-text format into a HelpCard."""
    blocks = []
    paragraph = []

    def finish_paragraph():
        if paragraph:
            blocks.append((PARAGRAPH, " ".join(paragraph)))
            paragraph.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            finish_paragraph()
        elif line.startswith("## "):
            finish_paragraph()
            blocks.append((HEADING, line[3:].strip()))
        elif line.startswith("- "):
            finish_paragraph()
            blocks.append((BULLET, line[2:].strip()))
        else:
            paragraph.append(line)

    finish_paragraph()
    return HelpCard(title, tuple(blocks))


def load_card(game):
    """The game's HelpCard, or None when it has no readable rules file."""
    try:
        with open(card_path(game.game_id), encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return None
    card = parse_card(game.title, text)
    return card if card.blocks else None