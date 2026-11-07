"""The gags, trunk and tasks HUDs, moved through like the book's pages.

With toggle_hud on, the gags (Y) and tasks (X) HUDs stay up between presses, so
they can be hovered with the D-pad. Each is the book's page of the same name
(Gags, its Trunk tab, ToonTasks) drawn lower down: 0.050 of the shorter side
below it, at the same size (measured at 1920x1009 by matching the captures). So
the book's readers read them through shifted pixels, and the book's mapper moves
around them with its points shifted back.

The gags HUD has a small yellow arrow on its right edge that turns it into the
trunk, and the trunk one on its left edge back; the right stick clicks them.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from . import ui
from .battle import BattleScreen, PointerCommand
from .bindings import Bindings
from .book import TASK_CENTERS, BookMapper, BookScreen, _read_book_trunk, _read_gags, _read_tasks, gag_point
from .ui import RGB

PixelReader = Callable[[int, int], RGB]

SHIFT = 0.050  # how far below the book's page each HUD is


def _center(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "center")


# The arrows that switch between gags and trunk, measured at 1920x1009.
TO_TRUNK = _center(0.4063, -0.0580)  # on the gags HUD's right edge
TO_GAGS = _center(-0.3999, -0.0783)  # on the trunk HUD's left edge


# The book's readers expect their page to be showing, so each HUD is first told by
# its own look (measured at 1920x1009, in the HUD's places).
# Gags: each track's band color, left of its first gag (above and below its middle)
# and right of its last, Toon-Up to Drop.
_TRACK_COLORS = ((211, 148, 255), (249, 255, 93), (79, 190, 76), (93, 108, 239), (255, 145, 66), (255, 65, 199),
                 (67, 243, 255))
_TRACK_PROBES = tuple((color, _center(x, gag_point(r, 0).y + SHIFT + dy))
                      for r, color in enumerate(_TRACK_COLORS)
                      for x, dy in ((-0.2359, -0.016), (-0.2359, 0.012), (0.3816, 0.0)))
_TRACK_MIN = 18  # of 21
# Trunk: its dark blue frame and blue panel.
_TRUNK_PROBES = (((36, 71, 91), _center(-0.3568, -0.2869)), ((36, 71, 91), _center(-0.3667, 0.1145)),
                 ((60, 118, 156), _center(0.3667, -0.2027)), ((60, 118, 156), _center(-0.2378, -0.2423)),
                 ((70, 128, 162), _center(-0.2577, 0.1293)), ((70, 128, 162), _center(0.0396, 0.1293)))
_TRUNK_MIN = 5
_COLOR_TOLERANCE = 35  # per channel
# Tasks: parchment around each scroll's middle, clear of its writing.
_SCROLL_DOTS = ((-0.1685, -0.0595), (0.1685, -0.0595), (-0.1685, 0.0892), (0.1685, 0.0892), (-0.1189, 0.109),
                (0.1189, 0.109))


def _is_parchment(c: RGB) -> bool:
    r, g, b = c
    return r > 205 and g > 195 and 150 < b < 190 and r - b > 40


def _near(c: RGB, color: RGB) -> bool:
    return all(abs(a - b) <= _COLOR_TOLERANCE for a, b in zip(c, color))


@dataclass(frozen=True)
class HudScreen:
    kind: str | None = None  # "gags", "trunk" or "tasks"
    gags: tuple[tuple[bool, ...], ...] | None = None
    trunk: BattleScreen | None = None  # as the battle trunk, like the book's Trunk tab
    tasks: tuple[ui.UIPoint | bool | None, ...] = ()


def read_hud(width: int, height: int, get_pixel: PixelReader, gags: bool = True, tasks: bool = True) -> HudScreen:
    """gags, tasks: which HUDs are up (toggled on), so only they are looked for."""
    shift = round(SHIFT * min(width, height))

    def book_pixel(x: int, y: int) -> RGB:
        # Where the book's page has a pixel, read from where the HUD has it.
        return get_pixel(x, y + shift)

    def hits(probes) -> int:
        return sum(_near(get_pixel(*p.to_client(width, height)), color) for color, p in probes)

    if gags:
        if hits(_TRUNK_PROBES) >= _TRUNK_MIN:
            trunk = _read_book_trunk(width, height, book_pixel)
            if trunk is not None:
                return HudScreen("trunk", trunk=trunk)
        if hits(_TRACK_PROBES) >= _TRACK_MIN:
            owned = _read_gags(width, height, book_pixel)
            if owned is not None:
                return HudScreen("gags", gags=owned)
    if tasks:
        shown = [all(_is_parchment(get_pixel(*center.offset(dx, SHIFT + dy).to_client(width, height)))
                     for dx, dy in _SCROLL_DOTS) for center in TASK_CENTERS]
        if any(shown):
            scrolls = _read_tasks(width, height, book_pixel)
            scrolls = tuple(task if up else None for task, up in zip(scrolls, shown))
            if any(t is not None for t in scrolls):
                return HudScreen("tasks", tasks=scrolls)
    return HudScreen()


_PAGES = {"gags": "gags", "trunk": "gags", "tasks": "toontasks"}
_DIRECTIONS = ("up", "down", "left", "right")


def _book_bindings() -> Bindings:
    press = {f"dpad_{d}": d for d in _DIRECTIONS}
    press |= {"rs_up": "stickUp", "rs_down": "stickDown"}
    return Bindings(press=press)


def _shifted(command: PointerCommand) -> PointerCommand:
    frame_at = command.frame_at.offset(0, SHIFT) if command.frame_at is not None else None
    return replace(command, point=command.point.offset(0, SHIFT), frame_at=frame_at)


class HudMapper:
    """D-pad hovers the gags, trunk items and tasks; right stick left/right clicks the
    gags/trunk arrows; on the trunk, A clicks what's hovered (a tab, the SOS filter) and
    right stick up/down scrolls the SOS cards, and LS cycles their filter. Walking still
    works (left stick).

    As on the book's Trunk tab, the trunk hovers its first item as soon as it shows, so
    A doesn't jump while it's up."""

    def __init__(self):
        self._book = BookMapper(_book_bindings())
        self._kind: str | None = None
        self._held: frozenset[str] = frozenset()

    def reset(self) -> None:
        self._book = BookMapper(_book_bindings())
        self._kind = None
        self._held = frozenset()

    def hovering(self) -> bool:
        return self._kind is not None and self._book.hovering(self._screen)

    def buttons(self, screen: HudScreen) -> frozenset[str]:
        """The buttons it takes from the overworld right now."""
        if screen.kind is None:
            return frozenset()
        taken = {f"dpad_{d}" for d in _DIRECTIONS} | {"rs_left", "rs_right"}
        if screen.kind == "trunk":
            taken |= {"a", "ls"}  # LS cycles the SOS filter there, as in the book (not sprint)
            if screen.trunk.tab == "SOS":
                taken |= {"rs_up", "rs_down"}
        return frozenset(taken)

    def update(self, buttons: frozenset[str], now: float, screen: HudScreen) -> list[PointerCommand]:
        if screen.kind != self._kind:
            # A new HUD (or gags and trunk switched): nothing hovered there yet.
            self._book = BookMapper(_book_bindings())
            self._kind = screen.kind
        if screen.kind is None:
            self._held = frozenset()
            return []
        buttons = buttons & self.buttons(screen)
        pressed, self._held = buttons - self._held, buttons
        self._screen = BookScreen(page=_PAGES[screen.kind], gags=screen.gags, trunk=screen.trunk, tasks=screen.tasks)
        commands = [_shifted(c) for c in self._book.update(buttons, now, self._screen)]
        if "rs_right" in pressed and screen.kind == "gags":
            commands.append(PointerCommand("click", TO_TRUNK, "to trunk"))
        elif "rs_left" in pressed and screen.kind == "trunk":
            commands.append(PointerCommand("click", TO_GAGS, "to gags"))
        return commands
