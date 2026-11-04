"""Record the pixels the battle screen reader looks at in a capture, for tests.

Usage: python tools/record_pixels.py CAPTURE...

Writes tests/fixtures/battle/<capture name>.json holding the window size and
only the pixels read_screen(), read_shop() and read_npc() sampled, so tests can replay a real screen
without storing (or publishing) whole screenshots.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from ttcontroller.battle import read_screen  # noqa: E402
from ttcontroller.npc import read_npc  # noqa: E402
from ttcontroller.shop import read_shop  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "battle"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for capture in map(Path, sys.argv[1:]):
        img = pygame.image.load(str(capture))
        w, h = img.get_size()
        seen: dict[str, list[int]] = {}

        def get_pixel(x: int, y: int):
            c = tuple(img.get_at((x, y)))[:3] if 0 <= x < w and 0 <= y < h else (0, 0, 0)
            seen[f"{x},{y}"] = list(c)
            return c

        screen = read_screen(w, h, get_pixel)
        shop = read_shop(w, h, get_pixel)
        # The task choice panel (speech bubbles search the whole window, so they're
        # tested from cropped images instead; see tests/fixtures/npc).
        npc = read_npc(w, h, get_pixel)
        path = OUT / f"{capture.stem}.json"
        path.write_text(json.dumps({"size": [w, h], "pixels": seen}, separators=(",", ":")), encoding="utf-8")
        print(f"wrote {path.name}: {screen.kind or shop.kind or npc.kind}, {len(seen)} pixels")


if __name__ == "__main__":
    main()
