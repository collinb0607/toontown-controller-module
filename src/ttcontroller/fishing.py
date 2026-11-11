"""Fishing on a pond's dock (M14).

TTR's fishing screen: a round Cast button over the toon (pure red; pure green while
it's being dragged), the jellybean jar and the bucket along the bottom, and a gold-ringed
red X in the bottom right that leaves the dock. Casting is TTR's slingshot: press the
Cast button, drag the mouse back (a yellow arrow points the other way, longer the
farther you pull), and let go. A catch shows a cream card hanging from the rod, with a
red X (throw it back) bottom left and a blue check (keep it) bottom right. The bucket
full and out of jellybeans popups have one red Exit button and are found by
dialog.find_cancel_alone like any such dialog (A or B clicks it).

With a controller: hold A to press Cast, and while A is held the left stick moves the
mouse's pull at a steady speed, like moving a cursor (the user's choice, Nov 9): it stays
where it is when the stick is let go, and stops at the longest pull. It's a slingshot:
pull back to cast forward, back-left to cast to the right. It can't go forward of the
Cast button (that would cast at the dock). Let go of A to cast. Each cast starts where
the last one was let go (the first straight back, a medium way), so A alone casts to the
same spot again. LS switches to the first way it worked (and back): the stick's tilt is
the pull itself, the shortest cast straight forward at rest (fishing_cast "stick"; the user
wanted both, Nov 9). B leaves the dock. On the catch card X keeps the fish and B throws it
back; A casts again straight away, card or not (TTR lets you, and the user prefers it,
Nov 9).

Measured at 1920x1009 (fishing_* captures, Nov 8, 2026). Everything is assumed to be on
TTR's aspect2d (centered, scaled with the shorter side), like the rest of its 2D UI.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass

from . import ui
from .battle import PointerCommand

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]
_U = 1009  # the captures' shorter side


def _px(x: float, y: float) -> ui.UIPoint:
    """A point measured in pixels at 1920x1009, kept from the window's middle."""
    return ui.UIPoint("center", (x - 960) / _U, (y - 504.5) / _U, "center")


CAST = _px(961, 741)  # the Cast button's middle
EXIT = _px(1551, 953)  # the red X leaving the dock
CARD_RELEASE = _px(821, 446)  # the catch card's red X: throw it back
CARD_KEEP = _px(1098, 446)  # its blue check: keep it

_CAST_PROBES = tuple(CAST.offset(dx / _U, dy / _U) for dx, dy in ((0, 0), (-12, 0), (12, 0), (0, -12), (0, 12)))
# The X's dark red middle, and its gold ring left, right and above.
_EXIT_MIDDLE = tuple(EXIT.offset(dx / _U, dy / _U) for dx, dy in ((0, 0), (-3, 0), (3, 0)))
_EXIT_RING = tuple(EXIT.offset(dx / _U, dy / _U) for dx, dy in ((-16, 0), (16, 0), (0, -16)))
# The catch card's buttons are rings: red or blue a few pixels either side of the middle.
_RING = ((-8, 0), (8, 0), (0, -8))
_CARD_CREAM = (_px(860, 300), _px(1060, 300), _px(960, 140))

# The longest pull from the Cast button, in units of the shorter side; the first cast's
# pull (straight back, this part of the longest); how fast a full tilt moves the pull
# (units a second); the stick's deadzone.
# 0.22 fell short of TTR's longest cast (Nov 9). Straight back, the window's bottom edge
# is only 0.2656 below the button (at a landscape window), so the pull stops at BOTTOM.
REACH = 0.30
REST_PULL = 0.45
SPEED = 0.30
BOTTOM = 0.26
MIN_PULL = 0.02  # the "stick" way at rest: the shortest cast, straight forward (the user, Nov 9)
STICK_DEADZONE = 0.2
MOVE_STEP = 0.004  # the pull is moved again once it's this far from the last spot
# Pulling straight after the press sometimes moved the mouse off the button before TTR
# took the press, so nothing was grabbed (Nov 9). The pull waits until the button turns
# green (grabbed), at least GRAB_SECONDS after the press; with no green by RETRY_SECONDS
# it presses again, up to PRESSES times, then pulls anyway.
GRAB_SECONDS = 0.08
RETRY_SECONDS = 0.5
PRESSES = 3


def is_cast_red(c: RGB) -> bool:
    r, g, b = c
    return r > 170 and g < 45 and b < 45


def is_cast_green(c: RGB) -> bool:
    r, g, b = c
    return g > 170 and r < 70 and b < 45


def is_exit_red(c: RGB) -> bool:
    r, g, b = c  # (133,38,15) in the middle
    return 100 < r < 210 and r - g > 60 and r - b > 80


def is_ring_gold(c: RGB) -> bool:
    r, g, b = c  # (223,184,65), (242,222,155) at the top
    return r > 180 and g > 140 and r - b > 70


def is_card_cream(c: RGB) -> bool:
    r, g, b = c  # (255,255,191)
    return r > 235 and g > 235 and 160 < b < 215


def is_release_red(c: RGB) -> bool:
    r, g, b = c  # (207,57,57), (202,60,55), (246,141,146)
    return r > 170 and r - g > 90 and r - b > 90


def is_keep_blue(c: RGB) -> bool:
    r, g, b = c  # (78,94,172), (85,101,179), (151,168,236)
    return b > 150 and b - r > 70


@dataclass(frozen=True)
class FishingScreen:
    kind: str | None = None  # "dock" (fishing), "card" (a catch to keep or throw back), or None
    can_cast: bool = False  # the Cast button is showing
    casting: bool = False  # it's green: being dragged


def read_fishing(width: int, height: int, get_pixel: PixelReader) -> FishingScreen:
    def look(points, test) -> int:
        return sum(test(get_pixel(*p.to_client(width, height))) for p in points)

    if look(_EXIT_MIDDLE, is_exit_red) < 2 or look(_EXIT_RING, is_ring_gold) < 2:
        return FishingScreen()
    red, green = look(_CAST_PROBES, is_cast_red), look(_CAST_PROBES, is_cast_green)
    card = (look(_CARD_CREAM, is_card_cream) >= 2
            and look([CARD_RELEASE.offset(dx / _U, dy / _U) for dx, dy in _RING], is_release_red) >= 2
            and look([CARD_KEEP.offset(dx / _U, dy / _U) for dx, dy in _RING], is_keep_blue) >= 2)
    return FishingScreen("card" if card else "dock", can_cast=red >= 4 or green >= 4, casting=green >= 4)


FIRST_PULL = (0.0, REST_PULL * REACH)


def move_pull(pull: tuple[float, float], stick: tuple[float, float], seconds: float) -> tuple[float, float]:
    """The pull (an offset from the Cast button, screen down being back) after the stick
    has moved it for `seconds`: its speed grows with the tilt past the deadzone; it stops
    at the longest pull and at the Cast button's level."""
    sx, sy = stick
    tilt = math.hypot(sx, sy)
    if tilt < STICK_DEADZONE:
        return pull
    speed = SPEED * min(1.0, (tilt - STICK_DEADZONE) / (1 - STICK_DEADZONE)) / tilt
    x, y = pull[0] + sx * speed * seconds, pull[1] + sy * speed * seconds
    y = max(0.0, y)
    length = math.hypot(x, y)
    if length > REACH:
        x, y = x * REACH / length, y * REACH / length
    return x, min(y, BOTTOM)


def stick_pull(stick: tuple[float, float]) -> tuple[float, float]:
    """The "stick" way: the pull is where the stick points, scaled to the longest pull,
    with the same limits; at rest, the shortest cast straight forward."""
    x, y = stick
    if math.hypot(x, y) < STICK_DEADZONE:
        return 0.0, MIN_PULL
    x, y = x * REACH, max(0.0, y * REACH)
    length = math.hypot(x, y)
    if length > REACH:
        x, y = x * REACH / length, y * REACH / length
    return x, min(y, BOTTOM)


def pull_point(pull: tuple[float, float]) -> ui.UIPoint:
    return CAST.offset(*pull)


class FishingMapper:
    """A held casts (the stick pulls), B leaves; on the catch card X keeps the fish, B throws
    it back, and A still casts."""

    BUTTONS = frozenset({"a", "b", "x", "ls"})
    METHODS = ("move", "stick")

    @staticmethod
    def buttons(screen: FishingScreen) -> frozenset[str]:
        """The buttons fishing takes from the rest (X only while the card shows; LS, which
        is auto-sprint's elsewhere, switches the casting)."""
        return frozenset({"a", "b", "ls"}) | ({"x"} if screen.kind == "card" else set())

    def __init__(self):
        self._held: frozenset[str] = frozenset()
        self.holding = False  # Cast is pressed (A held)
        self.grabbed = False  # TTR took the press (its button turned green): the stick pulls
        self.pull = FIRST_PULL  # where the pull is (kept between casts)
        self._pulled: tuple[float, float] | None = None  # where the mouse was last put
        self._last = 0.0  # the last update's time
        self._wanted = False  # A went down on the dock and is still held: grab when Cast shows
        self._pressed_at = 0.0  # when Cast was last pressed
        self._presses = 0  # presses on Cast this hold
        self.method = "move"  # how the stick casts: "move" or "stick" (fishing_cast)
        self._switched = False  # LS switched it since take_switch()

    def take_switch(self) -> bool:
        """Whether LS switched the casting since the last call (for the log and the config)."""
        switched, self._switched = self._switched, False
        return switched

    def reset(self) -> None:
        """Forget the buttons (anything held is ignored until let go)."""
        self._held = self.BUTTONS
        self.holding = self.grabbed = self._wanted = False
        self._pulled = None

    def _press(self, now: float) -> list[PointerCommand]:
        self.holding, self.grabbed = True, False
        self._pressed_at = now
        self._presses += 1
        return [PointerCommand("hold", CAST, "press cast")]

    def update(self, buttons: frozenset[str], stick: tuple[float, float], now: float,
               screen: FishingScreen) -> list[PointerCommand]:
        pressed = buttons - self._held
        self._held = buttons & self.BUTTONS
        seconds, self._last = max(0.0, min(0.1, now - self._last)), now
        commands: list[PointerCommand] = []
        if "a" not in buttons:
            self._wanted = False
        if "ls" in pressed and screen.kind in ("dock", "card"):
            self.method = "stick" if self.method == "move" else "move"
            self._switched = True
        if self.holding and ("a" not in buttons or screen.kind not in ("dock", "card")):
            self.holding = self.grabbed = False
            self._pulled = None
            commands.append(PointerCommand("release", CAST, "cast"))
            return commands
        if screen.kind == "card":
            if "x" in pressed:
                commands.append(PointerCommand("click", CARD_KEEP, "keep the fish"))
            elif "b" in pressed:
                commands.append(PointerCommand("click", CARD_RELEASE, "throw the fish back"))
            pressed -= {"b"}  # B is the card's, not leaving the dock
        elif screen.kind != "dock":
            return commands
        if "a" in pressed:
            self._wanted = True
        if self.holding and not self.grabbed:
            waited = now - self._pressed_at
            if waited >= GRAB_SECONDS and (screen.casting or self._presses >= PRESSES and waited >= RETRY_SECONDS):
                self.grabbed = True  # green: TTR has it (or it never reads green: pull anyway)
                if self.method == "stick":
                    self.pull = stick_pull(stick)
                self._pulled = self.pull
                commands.append(PointerCommand("hover", pull_point(self.pull), "pull"))
            elif waited >= RETRY_SECONDS:
                commands.append(PointerCommand("release", CAST, "press cast again"))
                commands += self._press(now)
        elif self.holding:
            self.pull = move_pull(self.pull, stick, seconds) if self.method == "move" else stick_pull(stick)
            if max(abs(self.pull[0] - self._pulled[0]), abs(self.pull[1] - self._pulled[1])) >= MOVE_STEP:
                self._pulled = self.pull
                commands.append(PointerCommand("hover", pull_point(self.pull), "pull"))
        elif self._wanted and screen.can_cast:
            self._wanted = False
            self._presses = 0
            commands += self._press(now)
        elif "b" in pressed:
            commands.append(PointerCommand("click", EXIT, "leave the dock"))
        return commands
