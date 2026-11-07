"""The golf green puzzle in the Bossbot Cog Golf courses: a gray board of holes with
colored balls at its top and a launcher at its bottom middle. The gold arrow on the
launcher points where the next ball goes, toward the mouse, anywhere within 150
degrees (75 either side of straight up). EXIT FOR NOW and HOW TO PLAY are yellow
buttons in the bottom right.

With a controller, the left stick sets the aim directly: the module puts the (hidden)
cursor on a circle around the launcher at the angle the stick points, and draws an aim
line and crosshair there (overlay.Highlighter.show_image), since the cursor isn't
visible. The aim stays put when the stick is let go; the D-pad's left and right nudge
it a little at a time. A shoots (a click), Y opens How to Play, and holding B exits for
now. It starts aimed straight up.

Measured from a 1280x720 video still with the game in 1280x677 of it (no in-game
capture yet, golf_green_video_still): the launcher's middle is 0.3966 below the
window's middle; the buttons are 0.5258 right of it and 0.3767 (Exit) and 0.4483 (How
to Play) below. Whether those buttons are anchored to the middle or the bottom right
isn't known yet, so both are tried.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from . import ui
from .battle import PointerCommand
from .bindings import Bindings, ButtonActions

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]


def _center(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "center")


PIVOT = _center(0.0, 0.3966)  # the launcher's middle
AIM_RADIUS = 0.45  # the cursor is put this far from the launcher (farther: finer aim)
MAX_ANGLE = 75.0  # degrees either side of straight up
NUDGE = 1.5  # degrees per D-pad press (repeating while held)
STICK_AIM = 0.5  # how far the stick must be pushed to set the aim

# The buttons, tried anchored to the middle and to the bottom right.
_BUTTONS = {
    "exit": (_center(0.5258, 0.3767), ui.UIPoint("right", -0.4195, -0.1233, "bottom")),
    "how to play": (_center(0.5251, 0.4483), ui.UIPoint("right", -0.4202, -0.0517, "bottom")),
}
_PILL_DXS = tuple(-0.08 + 0.02 * i for i in range(9))
_PILL_DYS = (-0.012, 0.012)  # above and below its lettering
_PILL_MIN = 12  # of 18
_BOARD = tuple(_center(x, y) for x in (-0.25, -0.1, 0.1, 0.25) for y in (0.05, 0.15, 0.25))
_BOARD_MIN = 10  # of 12 (a ball can cover some)


def _is_pill_yellow(c: RGB) -> bool:
    r, g, b = c
    return r > 200 and g > 200 and b < 90


def _is_board_gray(c: RGB) -> bool:
    return max(c) - min(c) < 25 and 40 < c[0] < 200


@dataclass(frozen=True)
class GolfGreenScreen:
    exit: ui.UIPoint | None = None  # EXIT FOR NOW, when the game is up
    how_to_play: ui.UIPoint | None = None

    @property
    def is_open(self) -> bool:
        return self.exit is not None


def _pill(width: int, height: int, get_pixel: PixelReader, point: ui.UIPoint) -> bool:
    hits = 0
    for dy in _PILL_DYS:
        for dx in _PILL_DXS:
            x, y = point.offset(dx, dy).to_client(width, height)
            if not (0 <= x < width and 0 <= y < height):
                return False
            hits += _is_pill_yellow(get_pixel(x, y))
    return hits >= _PILL_MIN


def read_golf_green(width: int, height: int, get_pixel: PixelReader) -> GolfGreenScreen:
    found = {}
    for name, candidates in _BUTTONS.items():
        found[name] = next((p for p in candidates if _pill(width, height, get_pixel, p)), None)
        if found[name] is None:
            return GolfGreenScreen()
    if sum(_is_board_gray(get_pixel(*p.to_client(width, height))) for p in _BOARD) < _BOARD_MIN:
        return GolfGreenScreen()
    return GolfGreenScreen(found["exit"], found["how to play"])


def aim_point(angle: float, radius: float = AIM_RADIUS) -> ui.UIPoint:
    """Where the cursor goes for an aim angle (degrees, 0 straight up, right positive)."""
    a = math.radians(angle)
    return PIVOT.offset(radius * math.sin(a), -radius * math.cos(a))


def stick_angle(x: float, y: float) -> float | None:
    """The aim a stick position asks for (y is down-positive, like pygame's), or None if
    it's barely pushed. Pulled down, it aims at the nearer side's limit."""
    if math.hypot(x, y) < STICK_AIM:
        return None
    angle = math.degrees(math.atan2(x, -y))
    return max(-MAX_ANGLE, min(MAX_ANGLE, angle))


def aim_image(length: int, angle: float, unit: int) -> tuple[np.ndarray, tuple[int, int]]:
    """An aim line from the launcher out to a crosshair, as premultiplied BGRA, and where
    the launcher is in it (to place it on screen). length: launcher to crosshair, in
    pixels. Gold with a dark outline, readable on the gray board and the green."""
    a = math.radians(angle)
    dx, dy = math.sin(a) * length, -math.cos(a) * length
    ring = max(6, round(0.016 * unit))
    pad = ring + 6
    left, top = min(0.0, dx) - pad, min(0.0, dy) - pad
    w, h = int(math.ceil(abs(dx) + 2 * pad)), int(math.ceil(abs(dy) + 2 * pad))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    px, py = xs + left, ys + top  # relative to the launcher
    tx, ty = px - dx, py - dy  # relative to the crosshair
    along = np.clip((px * dx + py * dy) / (length * length), 0, 1)
    off = np.hypot(px - along * dx, py - along * dy)
    dist = np.hypot(tx, ty)
    dash = max(4.0, 0.012 * unit)
    dashed = (np.floor(along * length / dash) % 2 == 0) & (along * length < length - ring)
    fade = 0.35 + 0.65 * along  # fainter near the launcher

    def shape(half: float) -> np.ndarray:
        line = np.clip(half + 0.5 - off, 0, 1) * dashed * fade
        circle = np.clip(half + 0.5 - np.abs(dist - ring * 0.6), 0, 1)
        ticks = (np.clip(half + 0.5 - np.minimum(np.abs(tx), np.abs(ty)), 0, 1)
                 * ((dist < ring) & (dist > ring * 0.25)))
        return np.maximum(np.maximum(line, circle), ticks)

    half = max(0.75, 0.00125 * unit)
    core = shape(half)
    outline = shape(half + 1.5)
    image = np.zeros((h, w, 4), np.uint8)
    for channel, value in zip((2, 1, 0), (255, 214, 64)):  # BGR, premultiplied (the outline is black)
        image[..., channel] = np.round(core * value)
    image[..., 3] = np.round(np.maximum(core, 0.6 * outline) * 255)
    return image, (int(round(-left)), int(round(-top)))


def default_golf_green_bindings() -> Bindings:
    return Bindings(press={"a": "shoot", "y": "how to play", "dpad_left": "left", "dpad_right": "right"},
                    hold={"b": "exit"})


class GolfGreenMapper:
    def __init__(self, bindings: Bindings | None = None, hold_seconds: float = 0.5):
        self.bindings = bindings or default_golf_green_bindings()
        self._actions = ButtonActions(self.bindings, hold_seconds, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in ("left", "right"))
        self.angle: float | None = None  # None: not aimed yet (the game just opened)

    @property
    def buttons(self) -> frozenset[str]:
        return frozenset(self.bindings.press) | frozenset(self.bindings.hold)

    def reset(self) -> None:
        self._actions.reset(ignore_held=True)
        self.angle = None

    def update(self, buttons: frozenset[str], stick: tuple[float, float], now: float,
               screen: GolfGreenScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons, now)
        if not screen.is_open:
            self.angle = None
            return []
        commands = []
        before = self.angle
        wanted = stick_angle(*stick)
        if wanted is not None:
            self.angle = wanted
        elif self.angle is None:
            self.angle = 0.0  # straight up to start
        for action in fired:
            if action in ("left", "right"):
                step = NUDGE if action == "right" else -NUDGE
                self.angle = max(-MAX_ANGLE, min(MAX_ANGLE, self.angle + step))
        if self.angle != before:
            commands.append(PointerCommand("hover", aim_point(self.angle), f"aim {self.angle:.0f}"))
        for action in fired:
            if action == "shoot":
                commands.append(PointerCommand("click", aim_point(self.angle), "shoot"))
            elif action == "how to play":
                commands.append(PointerCommand("click", screen.how_to_play, "how to play"))
            elif action == "exit":
                commands.append(PointerCommand("click", screen.exit, "exit for now"))
        return commands
