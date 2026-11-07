"""Leave buttons in boss fights: the CEO's seltzer bottles and golf balls, and the
CFO's cranes. Each has an X button to leave it, bottom right, in the same place.

On a bottle or a golf ball, TTR shows a red button with a white X ("Leave Bottle",
"Leave Golf Ball" under it) instead of the usual controls; B clicks it. It's
read only when B is pressed.

Measured at 1920x1009, 1577x535, 1637x533 and tall 388x812 (ceo_golfing and
ceo_seltzer captures): its middle is 0.5248 right of the window's middle and 0.4054
below it, in units of the shorter side. In a tall window that's past the right edge,
and only a sliver of it shows, so the sliver is clicked.

The CFO's Leave Crane is the same button in the same place (the user, in game). The
buttons turn yellow while hovered (Leave Crane in a video still), so yellow counts too.
"""

from collections.abc import Callable

from . import ui
from .ui import RGB

PixelReader = Callable[[int, int], RGB]

LEAVE = ui.UIPoint("center", 0.5248, 0.4054, "center")
_RING = 0.02  # spots this far above, below and beside its middle: red, clear of the white X
_EDGE_DYS = (-0.008, 0.0, 0.008)  # down the sliver showing at the right edge
_LABEL_DY = 0.061  # its label's row, below its middle
_LABEL_DXS = tuple(-0.1 + 0.004 * i for i in range(51))
_LABEL_MIN = 4  # white letter pixels along that row


def is_leave_red(c: RGB) -> bool:
    r, g, b = c
    return r > 180 and g < 100 and b < 100


def is_leave_yellow(c: RGB) -> bool:
    """A leave button while hovered: (240, 200, 40) or so, as in the video still."""
    r, g, b = c
    return r > 200 and g > 160 and b < 100 and r - b > 120


def _is_leave(c: RGB) -> bool:
    return is_leave_red(c) or is_leave_yellow(c)


def read_leave(width: int, height: int, get_pixel: PixelReader) -> ui.UIPoint | None:
    """Where to click the leave button, if it's showing."""
    unit = min(width, height)
    cx, cy = LEAVE.to_client(width, height)
    ring = round(_RING * unit)
    if cx + ring < width:
        spots = ((cx - ring, cy), (cx + ring, cy), (cx, cy - ring), (cx, cy + ring))
        if sum(_is_leave(get_pixel(x, y)) for x, y in spots) < 3:
            return None
        x = cx
    else:
        x = width - 2  # cut off by the right edge: the sliver showing
        if not all(_is_leave(get_pixel(x, cy + round(dy * unit))) for dy in _EDGE_DYS):
            return None
    ly = cy + round(_LABEL_DY * unit)
    letters = sum(min(get_pixel(px, ly)) > 220 for dx in _LABEL_DXS if (px := cx + round(dx * unit)) < width)
    if letters < _LABEL_MIN:
        return None
    return ui.UIPoint("center", (x - width / 2) / unit, LEAVE.y, "center")
