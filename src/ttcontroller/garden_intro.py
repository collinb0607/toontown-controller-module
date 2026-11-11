"""The gardening introduction: five pages (Gardening, Flowers, Trees, How-To, Statues) on
a cream, green-bordered panel, shown the first time a toon gets gardening. Under the
text: Previous Page (a blue left triangle, faded on the first page) and Next Page (a
blue right triangle, faded on the last), and on the last page Done (a blue round check)
at the right.

With a controller: A turns to the next page (Done on the last), B and D-pad left go
back a page, D-pad right goes on.

Measured at 958x484 (gardening_intro captures, Nov 9, 2026), on TTR's aspect2d (centered,
scaled with the shorter side) like the rest of its 2D UI.
"""

from collections.abc import Callable
from dataclasses import dataclass

from . import ui
from .battle import PointerCommand

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]
_W, _H = 958, 484


def _px(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", (x - _W / 2) / _H, (y - _H / 2) / _H, "center")


PREVIOUS = _px(431.4, 301.2)
NEXT = _px(525.6, 301.2)
DONE = _px(612, 302)
_CREAM = tuple(_px(x, y) for x, y in ((320, 300), (640, 290), (479, 340), (320, 180), (380, 300), (580, 300)))
_DONE_RING = tuple(DONE.offset(dx / _H, dy / _H) for dx, dy in ((-7, 0), (7, 0), (0, -6)))


def is_cream(c: RGB) -> bool:
    r, g, b = c  # (255,255,191)
    return r > 235 and g > 235 and 165 < b < 215


def is_arrow_blue(c: RGB) -> bool:
    r, g, b = c  # (45,158,245) / (29,147,237)
    return b > 200 and b - r > 140


def is_arrow_faded(c: RGB) -> bool:
    r, g, b = c  # (156,209,218)
    return b > 195 and g > 190 and 120 < r < 200 and b - r > 30


def is_done_blue(c: RGB) -> bool:
    r, g, b = c  # (90,109,184), (86,102,175)
    return b > 140 and b - r > 60


@dataclass(frozen=True)
class GardenIntro:
    is_open: bool = False
    previous: bool = False  # Previous Page can be pressed (not the first page)
    next: bool = False  # Next Page can be pressed (not the last page)
    done: bool = False  # Done shows (the last page)


def read_garden_intro(width: int, height: int, get_pixel: PixelReader) -> GardenIntro:
    def at(p: ui.UIPoint) -> RGB:
        return get_pixel(*p.to_client(width, height))

    if sum(is_cream(at(p)) for p in _CREAM) < 5:
        return GardenIntro()
    prev, nxt = at(PREVIOUS), at(NEXT)
    if not all(is_arrow_blue(c) or is_arrow_faded(c) for c in (prev, nxt)):
        return GardenIntro()
    done = sum(is_done_blue(at(p)) for p in _DONE_RING) >= 2
    return GardenIntro(True, previous=is_arrow_blue(prev), next=is_arrow_blue(nxt), done=done)


class GardenIntroMapper:
    """A next (Done on the last page), B or D-pad left back, D-pad right on."""

    BUTTONS = frozenset({"a", "b", "dpad_left", "dpad_right"})

    def __init__(self):
        self._held: frozenset[str] = frozenset()

    def reset_buttons(self) -> None:
        self._held = self.BUTTONS

    def update(self, buttons: frozenset[str], now: float, screen: GardenIntro) -> list[PointerCommand]:
        pressed = buttons - self._held
        self._held = buttons & self.BUTTONS
        if not screen.is_open:
            return []
        if "a" in pressed:
            if screen.done:
                return [PointerCommand("click", DONE, "done")]
            if screen.next:
                return [PointerCommand("click", NEXT, "next page")]
        if pressed & {"b", "dpad_left"} and screen.previous:
            return [PointerCommand("click", PREVIOUS, "previous page")]
        if "dpad_right" in pressed and screen.next:
            return [PointerCommand("click", NEXT, "next page")]
        return []
