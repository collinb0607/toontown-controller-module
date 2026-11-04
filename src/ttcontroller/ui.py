"""Where TTR draws its on-screen buttons, and how to tell if one is showing.

TTR's 2D UI scales with the window height and each panel is pinned to the
left edge, center or right edge. So a button's position is stored as an
offset from its anchor measured in window heights, which stays correct at
any window size.
"""

from collections.abc import Callable
from dataclasses import dataclass

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class UIPoint:
    anchor: str  # "left", "center" or "right"
    x: float  # horizontal offset from the anchor, in window heights
    y: float  # distance from the top, in window heights

    def to_client(self, width: int, height: int) -> tuple[int, int]:
        base = {"left": 0.0, "center": width / 2, "right": float(width)}[self.anchor]
        return round(base + self.x * height), round(self.y * height)

    def offset(self, dx: float, dy: float) -> "UIPoint":
        return UIPoint(self.anchor, self.x + dx, self.y + dy)


def is_red(c: RGB) -> bool:
    return c[0] > 150 and c[1] < 100 and c[2] < 100


@dataclass(frozen=True)
class Button:
    name: str
    center: UIPoint
    # The fill color shows above, below and beside the center, between the
    # strokes of the X icon. These points are checked to see if it's on screen.
    probe_distance: float
    is_fill: Callable[[RGB], bool]

    def probes(self) -> list[UIPoint]:
        d = self.probe_distance
        return [self.center.offset(dx, dy) for dx, dy in ((0, -d), (0, d), (-d, 0), (d, 0))]


# Measured at 1920x1009 and 1533x711; both agree to within half a pixel.
FRIENDS_CLOSE = Button("friends list close", UIPoint("right", -0.112, 0.421), 0.009, is_red)


def is_visible(button: Button, width: int, height: int, get_pixel: Callable[[int, int], RGB]) -> bool:
    """True if the button's fill color is at its probe points (all but one must match)."""
    hits = sum(button.is_fill(get_pixel(*p.to_client(width, height))) for p in button.probes())
    return hits >= len(button.probes()) - 1
