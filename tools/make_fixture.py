"""Crop the probe area of a detectable button from a capture into tests/fixtures.

Usage: python tools/make_fixture.py BUTTON LABEL CAPTURE...
  e.g. python tools/make_fixture.py SPEEDCHAT_MENU speedchat_open captures/speedchat_1920x1009.png

Crops are small so they hold no names or chat. File names record the full
window size and the crop origin: <label>_<W>x<H>_at_<x0>_<y0>.png
"""

import argparse
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from ttcontroller import ui  # noqa: E402

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
MARGIN = 4  # pixels around the probe points


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("button", help="name of a Button in ttcontroller.ui, e.g. FRIENDS_CLOSE")
    parser.add_argument("label", help="fixture name prefix, e.g. friends_open or friends_closed")
    parser.add_argument("captures", nargs="+", type=Path)
    args = parser.parse_args()

    button = getattr(ui, args.button)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for capture in args.captures:
        img = pygame.image.load(str(capture))
        w, h = img.get_size()
        points = [p.to_client(w, h) for p in button.probes]
        x0 = max(0, min(x for x, _ in points) - MARGIN)
        y0 = max(0, min(y for _, y in points) - MARGIN)
        x1 = min(w, max(x for x, _ in points) + MARGIN + 1)
        y1 = min(h, max(y for _, y in points) + MARGIN + 1)
        crop = img.subsurface(pygame.Rect(x0, y0, x1 - x0, y1 - y0)).copy()
        name = f"{args.label}_{w}x{h}_at_{x0}_{y0}.png"
        pygame.image.save(crop, str(FIXTURES / name))
        print("wrote", name)


if __name__ == "__main__":
    main()
