"""What a screen's mapper asks the module to do with the mouse: the one contract every
screen shares (app.py turns each into a hover, click, scroll, hold, drag or typed text in
the TTR window). Its own module so screens don't import battle.py to get it."""

from dataclasses import dataclass

from . import ui


@dataclass(frozen=True)
class PointerCommand:
    kind: str  # "hover" (park the cursor), "click", "scroll" (turn the wheel there), "hold", "release", "drag", "type"
    point: ui.UIPoint
    name: str
    notches: int = 0  # scroll: positive is up
    delay: float = 0.0  # click: seconds to wait after the previous command
    # hover: the item's width and height (units of the window's shorter side), for
    # the highlight frame drawn around it. None draws no frame.
    size: tuple[float, float] | None = None
    frame_at: ui.UIPoint | None = None  # hover: draw the frame here instead of around the point
    color: tuple[int, int, int] | None = None  # hover: the frame's color (None: the usual gold)
    pointer: bool = False  # hover: a pulsing pointer left of the item instead of a frame round it
    to: ui.UIPoint | None = None  # drag: press at point, move here, let go
