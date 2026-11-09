"""Clarabelle's mail popup in the playground, and her icon beside the friends button.

When a delivery or a new catalog arrives, TTR shows Clarabelle's icon (a lavender
circle left of the friends button) with a pale yellow popup beside it, closed by a
red X button centered along its bottom. The popup's size follows its message, so
both are searched for near where they were measured (1920x1009) instead of being
read at fixed spots. Only read on a button press, never every frame.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from . import ui
from .ui import RGB

PixelReader = Callable[[int, int], RGB]

# Where the popup can be: the top right, in units of the shorter side.
_POPUP_LEFT = -0.95  # from the right edge
_POPUP_RIGHT = -0.08
_POPUP_BOTTOM = 0.35
_POPUP_STEP = 0.02
_POPUP_MIN_HITS = 20
# The X sits this far up from the popup's bottommost fill, at most.
_BORDER = 0.012  # the green border just outside the fill, at most this far
_X_SEARCH = 0.06
_X_COLUMNS = (-0.01, 0.01)  # either side of the X's white strokes

ICON = ui.UIPoint("right", -0.2061, 0.0595)  # Clarabelle's icon, measured at 1920x1009
# With the Silly Meter's gauge up too, the gauge takes that slot and Clarabelle moves one
# slot left (clarabelle_bug, 1920x1009: about 1575, 60), so that slot is searched next.
_SLOT_STEP = 138 / 1009
_ICON_SEARCH = 0.02  # how far from ICON its center is looked for
_ICON_STEP = 2  # pixels


def _ring(radius: float, sixteenths: tuple[int, ...]) -> tuple[tuple[float, float], ...]:
    """Offsets around a center, at the given 16ths of a turn counterclockwise from the right."""
    return tuple((radius * math.cos(k * math.pi / 8), -radius * math.sin(k * math.pi / 8)) for k in sixteenths)


# Inside the circle: lavender where Clarabelle doesn't cover it (her hair, face and
# the handle cover the rest). Just outside it: no lavender, which a sky would have.
_ICON_INNER = _ring(0.042, (1, 2, 3, 7, 8, 10, 12))
_ICON_INNER_HITS = 6
_ICON_OUTER = _ring(0.066, tuple(range(16)))
_ICON_OUTER_HITS = 2  # at most
# Or its dark slate rim, when what's behind the icon is lavender too (TTR's purple hills,
# clarabelle_hills, 1921x1080): (95..117, 104..124, 128..138) in every capture, pulse or not.
_ICON_RIM = tuple(_ring(r, tuple(range(16))) for r in (0.0505, 0.0525, 0.0545))
_ICON_RIM_HITS = 12  # of 16 directions


def is_popup_yellow(c: RGB) -> bool:
    r, g, b = c
    return r > 245 and g > 245 and 175 < b < 205


def is_border_green(c: RGB) -> bool:
    r, g, b = c
    return g > 110 and g - r > 60 and g - b > 40


def is_x_red(c: RGB) -> bool:
    r, g, b = c
    return r > 170 and r - g > 80 and r - b > 80


def is_icon_rim(c: RGB) -> bool:
    r, g, b = c
    return 85 <= r <= 130 and 0 <= g - r <= 20 and 12 <= b - r <= 45


def is_icon_lavender(c: RGB) -> bool:
    r, g, b = c
    # Sky blue is bluer and greener: (128,177,238) against the icon's (144,158,196).
    # The icon pulses: its pale background goes from about (138,151,187), lavender, to
    # neutral gray (204,204,204) and back (measured live, Nov 8). So this only asks for
    # pale, gray to bluish; the search's ring just outside the icon (at most 2 matches
    # there) keeps clouds and walls, which spill past it, from counting.
    return min(r, g) > 120 and b > 150 and -3 <= b - r < 80 and b >= g - 3 and g - r < 30


@dataclass(frozen=True)
class MailScreen:
    close: ui.UIPoint | None = None  # the popup's X
    icon: ui.UIPoint | None = None  # Clarabelle's icon


def _to_ui(width: int, height: int, x: float, y: float) -> ui.UIPoint:
    unit = min(width, height)
    return ui.UIPoint("right", (x - width) / unit, y / unit)


def _find_close(width: int, height: int, get_pixel: PixelReader) -> ui.UIPoint | None:
    unit = min(width, height)
    step = max(1, round(_POPUP_STEP * unit))
    hits = [(x, y)
            for y in range(step // 2, min(height, round(_POPUP_BOTTOM * unit)), step)
            for x in range(max(0, round(width + _POPUP_LEFT * unit)), round(width + _POPUP_RIGHT * unit), step)
            if is_popup_yellow(get_pixel(x, y))]
    if len(hits) < _POPUP_MIN_HITS:
        return None
    # The fill's left and right edges, along the row with the most fill.
    rows: dict[int, list[int]] = {}
    for x, y in hits:
        rows.setdefault(y, []).append(x)
    y = max(rows, key=lambda r: len(rows[r]))
    left, right = min(rows[y]), max(rows[y])
    while left > 0 and is_popup_yellow(get_pixel(left - 1, y)):
        left -= 1
    while right < width - 1 and is_popup_yellow(get_pixel(right + 1, y)):
        right += 1
    # The popup's green border either side (speech bubbles and book pages have none).
    border = round(_BORDER * unit) + 1
    if not all(any(is_border_green(get_pixel(x0 + side * d, y)) for d in range(1, border + 1))
               for x0, side in ((left, -1), (right, 1))):
        return None
    middle = (left + right) / 2
    bottom = max(y for _, y in hits)
    reds = [py
            for dx in _X_COLUMNS
            for py in range(max(0, bottom - round(_X_SEARCH * unit)), min(height, bottom + step + 1))
            if is_x_red(get_pixel(round(middle + dx * unit), py))]
    if len(reds) < 0.01 * unit:
        return None
    return _to_ui(width, height, middle, (min(reds) + max(reds)) / 2)


def _find_icon(width: int, height: int, get_pixel: PixelReader) -> ui.UIPoint | None:
    for slot in range(2):
        found = _find_icon_near(width, height, get_pixel, ICON.offset(-slot * _SLOT_STEP, 0))
        if found is not None:
            return found
    return None


def _find_icon_near(width: int, height: int, get_pixel: PixelReader, where: ui.UIPoint) -> ui.UIPoint | None:
    unit = min(width, height)
    cx, cy = where.to_client(width, height)
    reach = round(_ICON_SEARCH * unit)

    def count(x: int, y: int, ring) -> int:
        return sum(is_icon_lavender(get_pixel(round(x + dx * unit), round(y + dy * unit))) for dx, dy in ring)

    def rim(x: int, y: int) -> int:
        # Directions where any of the three radii is rim (the center is found to 2 px).
        return sum(any(is_icon_rim(get_pixel(round(x + ring[k][0] * unit), round(y + ring[k][1] * unit)))
                       for ring in _ICON_RIM) for k in range(16))

    best = None  # (inner hits, -distance, x, y)
    for y in range(cy - reach, cy + reach + 1, _ICON_STEP):
        for x in range(cx - reach, cx + reach + 1, _ICON_STEP):
            inner = count(x, y, _ICON_INNER)
            if inner < _ICON_INNER_HITS:
                continue
            key = (inner, -math.hypot(x - cx, y - cy), x, y)
            if (best is None or key > best) and (count(x, y, _ICON_OUTER) <= _ICON_OUTER_HITS
                                                 or rim(x, y) >= _ICON_RIM_HITS):
                best = key
    return None if best is None else _to_ui(width, height, best[2], best[3])


def read_mail(width: int, height: int, get_pixel: PixelReader) -> MailScreen:
    return MailScreen(close=_find_close(width, height, get_pixel), icon=_find_icon(width, height, get_pixel))
