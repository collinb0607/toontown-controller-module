"""The VP's pie round: a blue pie icon shows at the top center of the screen.

While it's up, pies are thrown with TTR's performAction key (Delete by default),
pressed for one or held to wind up. Measured at 1920x1009.
"""

from collections.abc import Callable

from . import ui
from .ui import RGB

PixelReader = Callable[[int, int], RGB]


def _top(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "top")


def is_icon_blue(c: RGB) -> bool:
    r, g, b = c
    return b > 200 and b - r > 120 and 120 < g < 200


def is_cream(c: RGB) -> bool:
    r, g, b = c
    return r > 220 and g > 220 and 160 < b < 215


# The icon's blue on its left, right, top and bottom, and the cream pie in its middle.
_BLUE = tuple(_top(x, y) for x, y in ((-0.0377, 0.0476), (0.0297, 0.0476), (0.0, 0.0248), (0.0, 0.0704)))
_CREAM = (_top(-0.0149, 0.0436), _top(-0.0050, 0.0436))
PIE_ICON = _top(-0.0010, 0.0481)


def read_pie_round(width: int, height: int, get_pixel: PixelReader) -> bool:
    def hits(points, test) -> int:
        return sum(test(get_pixel(*p.to_client(width, height))) for p in points)

    return hits(_BLUE, is_icon_blue) >= 4 and hits(_CREAM, is_cream) >= 1
