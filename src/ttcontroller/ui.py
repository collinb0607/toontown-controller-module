"""Where TTR draws its on-screen buttons, and how to tell if one is showing.

TTR's 2D UI scales with the shorter side of the window (the height in a normal
wide window, the width in a tall one) and each element is pinned to an edge or
the center. So a position is stored as an offset from its anchor measured in
units of the shorter side, which stays correct at any window size.
"""

from collections.abc import Callable
from dataclasses import dataclass

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class UIPoint:
    anchor: str  # horizontal anchor: "left", "center" or "right"
    x: float  # horizontal offset from the anchor, in units of the shorter side
    y: float  # vertical offset from the vertical anchor, in units of the shorter side
    v_anchor: str = "top"  # vertical anchor: "top", "center" or "bottom"

    def to_client(self, width: int, height: int) -> tuple[int, int]:
        unit = min(width, height)
        base_x = {"left": 0.0, "center": width / 2, "right": float(width)}[self.anchor]
        base_y = {"top": 0.0, "center": height / 2, "bottom": float(height)}[self.v_anchor]
        return round(base_x + self.x * unit), round(base_y + self.y * unit)

    def offset(self, dx: float, dy: float) -> "UIPoint":
        return UIPoint(self.anchor, self.x + dx, self.y + dy, self.v_anchor)


def is_red(c: RGB) -> bool:
    return c[0] > 150 and c[1] < 100 and c[2] < 100


def is_menu_gray(c: RGB) -> bool:
    """A speedchat panel: light and barely tinted (beige, lavender and so on, depending
    on the speedchat color chosen in TTR's options)."""
    return min(c) > 150 and max(c) > 185 and max(c) - min(c) < 40


@dataclass(frozen=True)
class Button:
    name: str
    center: UIPoint  # where to click
    # For things the module needs to detect: points where a known color shows
    # when it's on screen, and how many of them must match.
    probes: tuple[UIPoint, ...] = ()
    is_fill: Callable[[RGB], bool] | None = None
    min_hits: int = 0


def around(center: UIPoint, distance: float) -> tuple[UIPoint, ...]:
    """Points above, below and beside a center, e.g. between the strokes of an X icon."""
    return tuple(center.offset(dx, dy) for dx, dy in ((0, -distance), (0, distance), (-distance, 0), (distance, 0)))


def is_visible(button: Button, width: int, height: int, get_pixel: Callable[[int, int], RGB]) -> bool:
    hits = sum(button.is_fill(get_pixel(*p.to_client(width, height))) for p in button.probes)
    return hits >= button.min_hits


# Measured at 1920x1009 and 1533x711; both agree to within a pixel.
_FRIENDS_X = UIPoint("right", -0.112, 0.421)
FRIENDS_CLOSE = Button("friends list close", _FRIENDS_X, around(_FRIENDS_X, 0.009), is_red, min_hits=3)

# The green button in the top-left. Clicking it opens speedchat, and clicking again closes it.
SPEEDCHAT = Button("speedchat", UIPoint("left", 0.1015, 0.035))


def _is_whisper_x(c: RGB) -> bool:
    return is_red(c) or (c[0] > 220 and c[1] > 170 and c[2] < 100)  # gold while hovered


def _is_whisper_yellow(c: RGB) -> bool:
    return c[0] > 240 and c[1] > 240 and 160 < c[2] < 215


# Whispering to a toon: a pale yellow "Whisper To: <name>" bar next to the speedchat
# buttons, with a red X right of them that ends the whisper (friends_whisper_popup,
# 1920x1009; left-anchored like the speedchat buttons). Its fill is checked near its
# left end, which every name length has.
_WHISPER_X = UIPoint("left", 0.1695, 0.0332)
WHISPER_CLOSE = Button("whisper close", _WHISPER_X, around(_WHISPER_X, 0.011), _is_whisper_x, min_hits=3)
WHISPER_BAR = Button("whisper bar", _WHISPER_X,
                     tuple(UIPoint("left", x, y) for x, y in ((0.21, 0.013), (0.25, 0.013), (0.21, 0.09), (0.25, 0.09))),
                     _is_whisper_yellow, min_hits=4)

# The open speedchat menu, detected by a column of points down its light left
# margin (no text ever reaches it). The menu's top sits about 0.49 above the
# window's center; measured at 1920x1009, 1552x611 and 539x786.
_SPEEDCHAT_MARGIN = tuple(UIPoint("left", 0.138, -0.43 + 0.05 * i, "center") for i in range(11))
SPEEDCHAT_MENU = Button("speedchat menu", _SPEEDCHAT_MARGIN[0], _SPEEDCHAT_MARGIN, is_menu_gray, min_hits=8)
