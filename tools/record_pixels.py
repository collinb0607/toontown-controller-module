"""Record the pixels the battle screen reader looks at in a capture, for tests.

Usage: python tools/record_pixels.py CAPTURE...

Writes tests/fixtures/battle/<capture name>.json holding the window size and
only the pixels screen readers sampled, so tests can replay a real screen
without storing (or publishing) whole screenshots.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from ttcontroller.battle import read_screen  # noqa: E402
from ttcontroller.book import read_book, read_pages  # noqa: E402
from ttcontroller import ui  # noqa: E402
from ttcontroller.ceo import read_leave  # noqa: E402
from ttcontroller.elevator import read_hop_off  # noqa: E402
from ttcontroller.makeatoon import read_make_a_toon  # noqa: E402
from ttcontroller.boarding import read_boarding  # noqa: E402
from ttcontroller.silly import read_silly  # noqa: E402
from ttcontroller.dialog import find_cancel_alone  # noqa: E402
from ttcontroller.friends import read_friends  # noqa: E402
from ttcontroller.garden import read_garden  # noqa: E402
from ttcontroller.garden_intro import read_garden_intro  # noqa: E402
from ttcontroller.facility import read_facility  # noqa: E402
from ttcontroller.fishing import read_fishing  # noqa: E402
from ttcontroller.golf_green import read_golf_green  # noqa: E402
from ttcontroller.hud import read_hud  # noqa: E402
from ttcontroller.mail import read_mail  # noqa: E402
from ttcontroller.mailbox import read_mailbox  # noqa: E402
from ttcontroller.npc import read_npc  # noqa: E402
from ttcontroller.options import read_options  # noqa: E402
from ttcontroller.pregame import read_pregame  # noqa: E402
from ttcontroller.shop import read_shop  # noqa: E402
from ttcontroller.speedchat import read_speedchat  # noqa: E402
from ttcontroller.vp import read_pie_round  # noqa: E402

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
        speedchat = read_speedchat(w, h, get_pixel, look_for_unite=True)
        friends = read_friends(w, h, get_pixel)
        read_friends(w, h, get_pixel, dialogs=True)  # Ignore's and Report's dialogs too
        book = read_book(w, h, get_pixel)
        read_pages(w, h, get_pixel)
        pregame = read_pregame(w, h, get_pixel)
        options = read_options(w, h, get_pixel)
        read_mail(w, h, get_pixel)
        hud = read_hud(w, h, get_pixel)
        read_pie_round(w, h, get_pixel)
        read_garden(w, h, get_pixel)
        read_leave(w, h, get_pixel)
        ui.is_visible(ui.FRIENDS_BUTTON, w, h, get_pixel)
        ui.is_visible(ui.BOOK_BUTTON, w, h, get_pixel)
        read_hop_off(w, h, get_pixel)
        mat = read_make_a_toon(w, h, get_pixel)
        read_boarding(w, h, get_pixel)
        read_silly(w, h, get_pixel)
        find_cancel_alone(w, h, get_pixel)
        read_mailbox(w, h, get_pixel)
        read_golf_green(w, h, get_pixel)
        read_facility(w, h, get_pixel)
        fishing = read_fishing(w, h, get_pixel)
        intro = read_garden_intro(w, h, get_pixel)
        path = OUT / f"{capture.stem}.json"
        path.write_text(json.dumps({"size": [w, h], "pixels": seen}, separators=(",", ":")), encoding="utf-8")
        print(f"wrote {path.name}: {(options.kind and f'options {options.kind}') or (mat.kind and f'make-a-toon {mat.kind}') or pregame.kind or screen.kind or shop.kind or npc.kind or ('speedchat' if speedchat.is_open else friends.kind) or (book.page and f'book {book.page}') or (hud.kind and f'{hud.kind} HUD') or (fishing.kind and f'fishing {fishing.kind}') or ('gardening intro' if intro.is_open else None)}, {len(seen)} pixels")


if __name__ == "__main__":
    main()
