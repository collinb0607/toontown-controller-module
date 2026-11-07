"""Talking to NPCs: their speech bubbles, and Toon HQ's task choice panel.

A speech bubble floats over the NPC in the 3D scene, so it can be anywhere on
screen. The ones you click through have a small blue "next" arrow (cyan while
hovered), or a red close circle on the last one (gold while hovered), in the
bubble's bottom-right corner; other toons' chat bubbles have neither. So the whole window is searched
for that arrow or circle with white bubble around it, using numpy.

The task choice panel is anchored to the left edge and centered vertically, in
units of the window's shorter side (see ui.py). It holds one to three tasks, each
with a Choose button down its right side, and a Cancel button at the bottom. It's
only as tall as its tasks, so Cancel moves: choosing a new task can offer three,
handing one in shows only the tasks that are done.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from . import ui
from .battle import PointerCommand
from .bindings import Bindings, ButtonActions

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]


def _left(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("left", x, y, "center")


TASK_CANCEL = _left(0.325, 0.3964)  # with three tasks
_CANCEL_XS = (0.265, 0.39)  # either end of the Cancel button
_CANCEL_BOTTOM = 0.48  # the lowest the panel goes
_CHOOSE_X = 0.423  # right of the "Choose" lettering
_CHOOSE_TOP, _CHOOSE_BOTTOM = -0.49, 0.25


def _is_border_olive(c: RGB) -> bool:
    return 60 < c[0] < 100 and 75 < c[1] < 105 and 35 < c[2] < 65


def _is_button_yellow(c: RGB) -> bool:
    return c[0] > 200 and c[1] > 190 and c[2] < 120


def _is_hover_blue(c: RGB) -> bool:
    return c[2] > 200 and c[0] < 120 and c[1] > 150


# The panel's right border, where even a one-task panel (handing one in) has it.
TASK_BORDER = ui.Button("task choice", TASK_CANCEL, tuple(_left(0.474, 0.05 * i) for i in range(-3, 4)),
                        _is_border_olive, min_hits=7)


@dataclass(frozen=True)
class NpcScreen:
    kind: str | None = None  # "dialogue", "tasks", or None
    button: ui.UIPoint | None = None  # dialogue: the next arrow, or the close circle on the last bubble
    last: bool = False
    choices: tuple[ui.UIPoint, ...] = ()  # tasks: Choose buttons, top to bottom
    cancel: ui.UIPoint | None = None


def _scan_choose(width: int, height: int, get_pixel: PixelReader) -> list[ui.UIPoint]:
    unit = min(width, height)
    px = _left(_CHOOSE_X, 0).to_client(width, height)[0]
    top, bottom = (round(height / 2 + y * unit) for y in (_CHOOSE_TOP, _CHOOSE_BOTTOM))
    runs: list[list[int]] = []
    for py in range(max(0, top), min(height - 1, bottom) + 1):
        c = get_pixel(px, py)
        if _is_button_yellow(c) or _is_hover_blue(c):
            if runs and py - runs[-1][1] <= 2:
                runs[-1][1] = py
            else:
                runs.append([py, py])
    return [_left(_CHOOSE_X - 0.035, ((a + b) / 2 - height / 2) / unit) for a, b in runs if b - a >= 0.01 * unit]


def _find_cancel(width: int, height: int, get_pixel: PixelReader, below: ui.UIPoint) -> ui.UIPoint | None:
    """The Cancel button below the last Choose button: yellow at both its ends."""
    unit = min(width, height)
    xs = [_left(x, 0).to_client(width, height)[0] for x in _CANCEL_XS]
    top = below.to_client(width, height)[1] + round(0.05 * unit)
    bottom = min(height - 1, round(height / 2 + _CANCEL_BOTTOM * unit))
    run = None
    for py in range(top, bottom + 1, 2):
        if all(_is_button_yellow(get_pixel(px, py)) for px in xs):
            run = (run[0], py) if run else (py, py)
        elif run:
            break
    if run is None or run[1] - run[0] < 0.015 * unit:
        return None
    return _left(TASK_CANCEL.x, ((run[0] + run[1]) / 2 - height / 2) / unit)


def _is_bubble_corner(rgb: np.ndarray, x: int, y: int, unit: int) -> bool:
    """A button in a speech bubble's bottom-right corner: white bubble to its left,
    and the bubble's black outline just to its right and just below it."""
    height, width, _ = rgb.shape

    def dark(px: int, py: int) -> bool:
        return 0 <= px < width and 0 <= py < height and int(rgb[py, px].sum()) < 150

    def white(px: int, py: int) -> bool:
        return 0 <= px < width and 0 <= py < height and bool((rgb[py, px] > 240).all())

    left = [white(x - round(f * unit), y) for f in (0.02, 0.03, 0.04, 0.05)]
    right = any(dark(x + i, y) for i in range(round(0.012 * unit), round(0.04 * unit)))
    below = any(dark(x, y + i) for i in range(round(0.008 * unit), round(0.03 * unit)))
    return sum(left) >= 3 and right and below


def find_bubble_button(rgb: np.ndarray) -> tuple[bool, float, float] | None:
    """Find a speech bubble's next arrow or close circle in an RGB image (rows, columns, 3).
    Returns (whether it's the close circle, x, y) in pixels, or None."""
    height, width, _ = rgb.shape
    unit = min(width, height)
    # The arrow is still several pixels across at half size in big windows.
    stride = 2 if unit >= 600 else 1
    small = rgb[::stride, ::stride]
    r, g, b = (small[..., i].astype(np.int16) for i in range(3))
    white = (r > 245) & (g > 245) & (b > 245)
    # The bubble's white is left of the button (its outline is right and below). Not
    # necessarily above: the last line of text can end right over it.
    d = max(2, round(0.02 * unit / stride))
    around = np.zeros_like(white)
    around[:, 2 * d:] = white[:, d:-d] & white[:, :-2 * d]
    arrow = ((b > 200) & (r < 90) & (g > 110) & (g < 180)) | ((b > 220) & (g > 190) & (r < 110))
    # Red, or gold while hovered.
    close = ((r > 190) & (g < 110) & (b < 110) & (r - g > 100)) | ((r > 220) & (g > 170) & (b < 100))
    for is_close, mask in ((False, arrow), (True, close)):
        ys, xs = np.nonzero(mask & around)
        if len(ys) == 0:
            continue
        # Group candidates into clumps and check each clump's middle.
        cell = max(1, round(0.03 * unit / stride))
        clumps: dict[tuple[int, int], list[int]] = {}
        for i, key in enumerate(zip((ys // cell).tolist(), (xs // cell).tolist())):
            clumps.setdefault(key, []).append(i)
        for members in clumps.values():
            if len(members) < 2:
                continue
            cx = float(xs[members].mean()) * stride
            cy = float(ys[members].mean()) * stride
            if _is_bubble_corner(rgb, round(cx), round(cy), unit):
                return is_close, cx, cy
    return None


def read_npc(width: int, height: int, get_pixel: PixelReader, rgb: np.ndarray | None = None) -> NpcScreen:
    if ui.is_visible(TASK_BORDER, width, height, get_pixel):
        choices = _scan_choose(width, height, get_pixel)[:3]
        cancel = _find_cancel(width, height, get_pixel, choices[-1]) if choices else None
        if cancel is not None:
            return NpcScreen("tasks", choices=tuple(choices), cancel=cancel)
    if rgb is not None:
        found = find_bubble_button(rgb)
        if found is not None:
            last, x, y = found
            unit = min(width, height)
            point = ui.UIPoint("center", (x - width / 2) / unit, (y - height / 2) / unit, "center")
            return NpcScreen("dialogue", button=point, last=last)
    return NpcScreen()


NPC_ACTIONS = {
    "up": "move the task highlight up", "down": "move the task highlight down",
    "select": "continue the conversation, or choose the highlighted task",
    "back": "cancel choosing a task",
}


def default_npc_bindings() -> Bindings:
    press = {"a": "select", "b": "back"}
    for direction in ("up", "down"):
        press[f"dpad_{direction}"] = direction
        press[f"ls_{direction}"] = direction
    return Bindings(press=press)


@dataclass
class NpcMapper:
    bindings: Bindings = field(default_factory=default_npc_bindings)
    settle_seconds: float = 0.25

    def __post_init__(self):
        self.set_bindings(self.bindings)
        self.choice = 0
        self._kind: str | None = None
        self._settle_until = 0.0
        self._rehover = False

    def set_bindings(self, bindings: Bindings) -> None:
        self.bindings = bindings
        self._actions = ButtonActions(bindings, 0.5, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in ("up", "down"))

    def buttons(self, screen: NpcScreen) -> set[str]:
        """Buttons this screen takes over. In a conversation that's only the continue
        button, so you can still walk away or open speedchat."""
        if screen.kind == "dialogue":
            return {b for b, a in self.bindings.press.items() if a == "select"}
        if screen.kind == "tasks":
            return self.bindings.buttons()
        return set()

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)

    @property
    def choosing(self) -> bool:
        """Whether the task panel was showing when this last ran."""
        return self._kind == "tasks"

    def forget(self) -> None:
        """The NPC screen has gone: whatever shows next is set up fresh."""
        self._kind = None
        self._rehover = False

    def rehover(self) -> None:
        """Put the hover back on the same task, e.g. after speedchat moved the cursor."""
        self._kind = None
        self._rehover = True

    def update(self, buttons: frozenset[str], now: float, screen: NpcScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons & self.buttons(screen), now)
        if now < self._settle_until:
            return []
        commands: list[PointerCommand] = []
        if screen.kind != self._kind:
            self._kind = screen.kind
            if screen.kind == "tasks":
                if not self._rehover:
                    self.choice = 0
                commands.append(self._hover_choice(screen))
            self._rehover = False
        for action in fired:
            commands += self._run(action, screen, now)
        return commands

    def _hover_choice(self, screen: NpcScreen) -> PointerCommand:
        self.choice = min(self.choice, len(screen.choices) - 1)
        return PointerCommand("hover", screen.choices[self.choice], f"task {self.choice + 1}")

    def _click(self, point: ui.UIPoint, name: str, now: float) -> list[PointerCommand]:
        self._settle_until = now + self.settle_seconds
        self._kind = None
        return [PointerCommand("click", point, name)]

    def _run(self, action: str, screen: NpcScreen, now: float) -> list[PointerCommand]:
        if screen.kind == "dialogue" and action == "select":
            return self._click(screen.button, "close" if screen.last else "continue", now)
        if screen.kind == "tasks":
            if action in ("up", "down"):
                step = -1 if action == "up" else 1
                self.choice = max(0, min(len(screen.choices) - 1, self.choice + step))
                return [self._hover_choice(screen)]
            if action == "select":
                return self._click(screen.choices[self.choice], f"choose task {self.choice + 1}", now)
            if action == "back":
                return self._click(screen.cancel, "cancel", now)
        return []
