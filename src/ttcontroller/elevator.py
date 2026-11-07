"""The Hop off button: sitting in an elevator (cog buildings, Cog HQ facilities, the
boss elevators) or a golf kart, TTR shows a "Hop off" button at the top middle; B
clicks it. It's read only when B is pressed, after speedchat is closed (an open
speedchat takes B first).

Measured in the elevator_* captures at 1920x1009, 1660x614 and tall 515x880: top
middle anchored, its middle 0.063 below the top, about 0.25 wide and 0.085 tall, in
units of the shorter side. Usually gray with white letters; the toon golf kart's is
red with cream letters (maybe how it looks hovered), so both count.
"""

from collections.abc import Callable

from . import ui
from .ui import RGB

PixelReader = Callable[[int, int], RGB]

HOP_OFF = ui.UIPoint("center", 0.0, 0.063, "top")
_FILL = ((-0.115, 0.05), (-0.115, 0.075), (0.115, 0.05), (0.115, 0.075), (0.0, 0.045), (0.0, 0.095))
_RIM = ((-0.115, 0.1), (0.115, 0.1))  # the dark edge along its bottom
_LETTERS_Y = 0.07
_LETTERS_DXS = tuple(-0.1 + 0.004 * i for i in range(51))
_LETTERS_MIN = 6  # letter pixels along that row
_FILL_MIN = 6  # and fill between them


def _is_gray(c: RGB) -> bool:
    return 120 < min(c) and max(c) < 180 and max(c) - min(c) < 12


def _is_red(c: RGB) -> bool:
    r, g, b = c
    return r > 190 and g < 110 and b < 110 and r - g > 120


def _is_letter(c: RGB, red: bool) -> bool:
    r, g, b = c
    if red:
        return r > 230 and g > 220 and b > 130  # cream
    return min(c) > 205 and max(c) - min(c) < 15  # white


def _is_rim(c: RGB, red: bool) -> bool:
    r, g, b = c
    if red:
        return r < 190 and g < 40 and b < 40
    return max(c) < 115 and max(c) - min(c) < 12


def read_hop_off(width: int, height: int, get_pixel: PixelReader) -> ui.UIPoint | None:
    """Where to click Hop off, if it's showing."""
    unit = min(width, height)
    cx = width / 2

    def at(dx: float, dy: float) -> RGB:
        return get_pixel(round(cx + dx * unit), round(dy * unit))

    fill = [at(dx, dy) for dx, dy in _FILL]
    for is_fill, red in ((_is_gray, False), (_is_red, True)):
        if not all(is_fill(c) for c in fill):
            continue
        if not all(_is_rim(at(dx, dy), red) for dx, dy in _RIM):
            return None
        row = [at(dx, _LETTERS_Y) for dx in _LETTERS_DXS]
        if (sum(_is_letter(c, red) for c in row) < _LETTERS_MIN
                or sum(is_fill(c) for c in row) < _FILL_MIN):
            return None
        return HOP_OFF
    return None
