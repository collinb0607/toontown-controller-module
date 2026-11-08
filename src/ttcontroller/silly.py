"""The Silly Meter: a gauge icon (a cream face in a gold ring) in the top right, in the
slot left of the friends list's icon, where Clarabelle's icon also goes. Clicking it
opens a yellow Silly Meter card down the right edge, with a round back button (the
reward's details) and a red X at its bottom; the details open as a wider card to its
left, with its own red X.

Controls (the user, Nov 7, 2026): RT is Clarabelle's, so holding RT (0.5 s; a tap is
still Clarabelle) clicks the Silly Meter, or closes it (both cards) when it's open.
With the card open, D-pad left opens the details and B closes the top card.

Measured at 1920x1009 (silly_meter, silly_meter_popup, silly_meter_details), anchored to
the top right like the friends list. With Clarabelle's icon up too, the gauge may sit
in the next slot left (not seen yet), so that one is looked at as well.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from . import ui
from .battle import PointerCommand

PixelReader = Callable[[int, int], ui.RGB]

_U = 1009
_SLOT_STEP = 138  # px between the top-right icons (the gauge's slot to the friends list's)


def _pt(px: float, py: float) -> ui.UIPoint:
    """Measured in pixels at 1920x1009, from the top right."""
    return ui.UIPoint("right", (px - 1920) / _U, py / _U, "top")


_ICON = (1717, 62)

def _circle(radius: float) -> tuple[tuple[int, int], ...]:
    return tuple((round(radius * math.cos(k * math.pi / 8)), round(-radius * math.sin(k * math.pi / 8)))
                 for k in range(16))


# Its cream face, 16 spots round the middle: the needle swings across the face and covers
# a few at a time, and the dial's marks a few more, so most (not all) must be cream; 12 or
# 13 are in the captures. Then its gold ring: 8 of these 16 spots in the captures (the
# ring isn't centered on the face). Nothing else there has either (Clarabelle's icon: 0).
_FACE = _circle(22)
_FACE_HITS = 9
_RING = _circle(50)
_RING_HITS = 5
CARD_X = _pt(1878, 489)
DETAILS_BUTTON = _pt(1738, 495)
DETAILS_X = _pt(1273, 489)
_CARD_YELLOW = _pt(1815, 470)


@dataclass(frozen=True)
class SillyScreen:
    icon: ui.UIPoint | None = None  # the gauge, where to click it
    card: bool = False  # the Silly Meter card is open
    details: bool = False  # and its details beside it

    @property
    def is_open(self) -> bool:
        return self.card


def _is_cream(c: ui.RGB) -> bool:
    # The icon pulses: only its blue changes, the face from about (245,250,160), dark
    # yellow, to (245,250,235), light cream (measured live over a few pulses, Nov 8).
    r, g, b = c
    return r > 225 and g > 225 and 145 < b < 242


def _is_gold(c: ui.RGB) -> bool:
    # The ring pulses too, from about (235,238,99) to (235,238,141). Deeper than the
    # pale yellow wallpaper inside some buildings (234,234,163), which is cream enough
    # to pass for the face (task_turn_in).
    r, g, b = c
    return r > 180 and g > 180 and b < 156 and r - b > 78


def _is_card_yellow(c: ui.RGB) -> bool:
    r, g, b = c
    return r > 180 and g > 170 and b < 110


def _is_red(c: ui.RGB) -> bool:
    r, g, b = c
    return r > 190 and g < 110 and b < 110


def _round_x(at: Callable[[ui.UIPoint], ui.RGB], x: ui.UIPoint) -> bool:
    """A red X button: white strokes in its middle, red just left of them."""
    return min(at(x)) > 225 and _is_red(at(x.offset(-12 / _U, 0)))


def read_silly(width: int, height: int, get_pixel: PixelReader) -> SillyScreen:
    def at(p: ui.UIPoint) -> ui.RGB:
        x, y = p.to_client(width, height)
        return get_pixel(min(max(x, 0), width - 1), min(max(y, 0), height - 1))

    card = _is_card_yellow(at(_CARD_YELLOW)) and _round_x(at, CARD_X)
    if card:
        return SillyScreen(card=True, details=_round_x(at, DETAILS_X))
    for slot in range(2):
        x, y = _ICON[0] - slot * _SLOT_STEP, _ICON[1]
        if (sum(_is_cream(at(_pt(x + dx, y + dy))) for dx, dy in _FACE) >= _FACE_HITS
                and sum(_is_gold(at(_pt(x + dx, y + dy))) for dx, dy in _RING) >= _RING_HITS):
            return SillyScreen(icon=_pt(x, y))
    return SillyScreen()


def toggle(screen: SillyScreen) -> list[PointerCommand]:
    """Holding RT: open the Silly Meter, or close it (the details first) if it's open."""
    if screen.card:
        commands = [PointerCommand("click", DETAILS_X, "close silly meter details")] if screen.details else []
        return commands + [PointerCommand("click", CARD_X, "close silly meter", delay=0.15 if screen.details else 0.0)]
    if screen.icon is not None:
        return [PointerCommand("click", screen.icon, "silly meter")]
    return []


class SillyMapper:
    """With the card open: D-pad left opens the details, B closes the top card."""

    BUTTONS = frozenset({"b", "dpad_left"})

    def __init__(self):
        self._held: frozenset[str] = frozenset()

    def reset_buttons(self) -> None:
        self._held = frozenset()

    def update(self, buttons: frozenset[str], now: float, screen: SillyScreen) -> list[PointerCommand]:
        buttons = buttons & self.BUTTONS
        pressed, self._held = buttons - self._held, buttons
        if not screen.card:
            return []
        if "b" in pressed:
            if screen.details:
                return [PointerCommand("click", DETAILS_X, "close silly meter details")]
            return [PointerCommand("click", CARD_X, "close silly meter")]
        if "dpad_left" in pressed and not screen.details:
            return [PointerCommand("click", DETAILS_BUTTON, "silly meter details")]
        return []
