"""The friends list and a toon's panel.

The friends list sits in the top right, anchored to the right edge, in units of
the window's shorter side (see ui.py). It shows 8 names at a time, with big
triangles above and below them to scroll (the mouse wheel doesn't work), arrows at
the bottom to change page (online friends, all friends, nearby pets, nearby
toons), and a close button between them.

Clicking a name swaps the list for that toon's panel: their portrait, then
Friends, Go To (teleport), Whisper, Ignore and Report, a Toon Details triangle in
the bottom left and a close button in the bottom right. Toon Details opens a
bigger panel to its left, with its own Close button.

Go To can ask first, in a yellow popup left of the panel ("... is in district X, and
you're in district Y. Do you want to switch to X?"), with Yes and No: A says yes, B
no, and the hover goes back to the panel's button. Measured at 1920x1009
(friends_teleport_popup): its buttons are 0.2488 below the top, No 0.4306 left of
the right edge and Yes 0.1497 left of No. Only one window size was measured, so the
No button is searched for along its row rather than taken at a fixed spot.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from . import ui
from .battle import PointerCommand
from .bindings import Bindings, ButtonActions
from .held_scroll import HeldScroll

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]


def _right(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("right", x, y)


VISIBLE_ROWS = 8
_NAME_LEFT = -0.2012
_NAME_X = -0.1893  # a little into the name: only the name's own text is clickable
_ROW0, _ROW_STEP = 0.1942, 0.02138
SCROLL_UP = _right(-0.1129, 0.1695)
SCROLL_DOWN = _right(-0.1129, 0.3826)
PAGE_LEFT = _right(-0.1913, 0.4192)
PAGE_RIGHT = _right(-0.0327, 0.4192)
LIST_CLOSE = ui.FRIENDS_CLOSE.center

_BUTTON_X = -0.1189
FRIEND = _right(_BUTTON_X, 0.2131)
GO_TO = _right(_BUTTON_X, 0.2527)
WHISPER = _right(_BUTTON_X, 0.2944)
IGNORE = _right(_BUTTON_X, 0.338)
REPORT = _right(_BUTTON_X, 0.3826)
TOON_DETAILS = _right(-0.1774, 0.4311)
PANEL_CLOSE = _right(-0.0327, 0.4262)
# Up and down move through these.
PANEL_BUTTONS = ((FRIEND, "friends"), (GO_TO, "go to"), (WHISPER, "whisper"), (IGNORE, "ignore"),
                 (REPORT, "report"), (TOON_DETAILS, "toon details"))

DETAILS_CLOSE = _right(-0.6125, 0.4271)
# How long a toon's panel takes to replace the list after a name is clicked.
PANEL_OPEN_SECONDS = 0.3
# Toon Details' Close ignores clicks until the panel has finished opening, and can
# miss one now and then: it's clicked again if still open this long after, a few times.
DETAILS_OPEN_SECONDS = 0.4
DETAILS_RETRY_SECONDS = 0.5
DETAILS_CLOSE_TRIES = 3

_TELEPORT_Y = 0.2488  # the Yes/No buttons' row, below the top
_TELEPORT_YES_DX = -0.1497  # Yes, left of No
_TELEPORT_SCAN = (-1.2, -0.3)  # No's middle is searched for between these, from the right edge
_TELEPORT_SCAN_DY = -0.009  # through No's red, above its white X
_YES_BLUE = ((0, -0.009), (-0.009, 0), (-0.006, -0.006), (-0.003, -0.006), (-0.008, -0.002), (0.008, 0.007))
_TELEPORT_FILL = ((0.1, 0.0), (-0.0749, 0.0), (-0.0749, 0.045), (_TELEPORT_YES_DX - 0.1, 0.0))  # from No


def _is_no_red(c: RGB) -> bool:
    r, g, b = c
    return r > 165 and r - g > 60 and r - b > 60  # shaded, lighter at its top


def _is_yes_blue(c: RGB) -> bool:
    r, g, b = c
    return b > 170 and b - r > 55 and b - g > 40


def _is_popup_yellow(c: RGB) -> bool:
    r, g, b = c
    return r > 240 and g > 240 and 150 < b < 215


def _is_portrait_yellow(c: RGB) -> bool:
    return c[0] > 230 and c[1] > 210 and c[2] < 120


def _is_close_red(c: RGB) -> bool:
    return ui.is_red(c) or (c[0] > 220 and c[1] > 170 and c[2] < 100)  # gold while hovered


PORTRAIT = ui.Button("toon panel", FRIEND, tuple(_right(x, y) for x in (-0.1834, -0.0198) for y in (0.06, 0.1, 0.14)),
                     _is_portrait_yellow, min_hits=5)
DETAILS = ui.Button("toon details close", DETAILS_CLOSE,
                    tuple(DETAILS_CLOSE.offset(dx, dy) for dx, dy in ((-0.013, 0), (0.013, 0), (0, -0.013), (0, 0.013))),
                    _is_close_red, min_hits=3)


@dataclass(frozen=True)
class FriendsScreen:
    kind: str | None = None  # "list", "panel" (a toon's panel), "teleport" (Go To's Yes/No popup), or None
    rows: tuple[ui.UIPoint, ...] = ()  # list: the names showing, top to bottom
    details: bool = False  # panel: Toon Details is open too
    yes: ui.UIPoint | None = None  # teleport: the popup's Yes and No
    no: ui.UIPoint | None = None


def _row(i: int) -> ui.UIPoint:
    return _right(_NAME_X, _ROW0 + i * _ROW_STEP)


def _has_name(width: int, height: int, get_pixel: PixelReader, i: int) -> bool:
    """Names are colored text on white (or on yellow while hovered)."""
    unit = min(width, height)
    left = _right(_NAME_LEFT, 0).to_client(width, height)[0]
    y = _row(i).to_client(width, height)[1]
    hits = 0
    for dy in (-0.004, 0, 0.004):
        for k in range(20):
            if min(get_pixel(left + round(k * 0.004 * unit), y + round(dy * unit))) < 180:
                hits += 1
    return hits >= 3


def _read_teleport(width: int, height: int, get_pixel: PixelReader) -> FriendsScreen | None:
    unit = min(width, height)
    y = round(_TELEPORT_Y * unit)
    scan_y = y + round(_TELEPORT_SCAN_DY * unit)
    left, right = (max(0, round(width + dx * unit)) for dx in _TELEPORT_SCAN)
    step = max(1, unit // 500)
    reds = [x for x in range(left, min(width, right)) if x % step == 0 and _is_no_red(get_pixel(x, scan_y))]
    # Runs of red the width of a button (about 0.03): its middle is No's.
    runs, start = [], None
    for i, x in enumerate(reds):
        if start is None:
            start = x
        if i + 1 == len(reds) or reds[i + 1] - x > 3 * step:
            runs.append((start, x))
            start = None
    for a, b in runs:
        if not 0.015 * unit <= b - a <= 0.04 * unit:
            continue
        no = ui.UIPoint("right", ((a + b) / 2 - width) / unit, _TELEPORT_Y)
        yes = no.offset(_TELEPORT_YES_DX, 0)

        def hits(points, test) -> int:
            return sum(test(get_pixel(*p.to_client(width, height))) for p in points)

        if (hits(ui.around(no, 0.009), _is_no_red) >= 3
                and hits(tuple(yes.offset(dx, dy) for dx, dy in _YES_BLUE), _is_yes_blue) >= 4
                and hits(tuple(no.offset(dx, dy) for dx, dy in _TELEPORT_FILL), _is_popup_yellow)
                == len(_TELEPORT_FILL)):
            return FriendsScreen("teleport", yes=yes, no=no)
    return None


def read_friends(width: int, height: int, get_pixel: PixelReader) -> FriendsScreen:
    teleport = _read_teleport(width, height, get_pixel)
    if teleport is not None:
        return teleport
    if ui.is_visible(ui.FRIENDS_CLOSE, width, height, get_pixel):
        rows = []
        for i in range(VISIBLE_ROWS):
            if not _has_name(width, height, get_pixel, i):
                break
            rows.append(_row(i))
        return FriendsScreen("list", rows=tuple(rows))
    if ui.is_visible(PORTRAIT, width, height, get_pixel):
        return FriendsScreen("panel", details=ui.is_visible(DETAILS, width, height, get_pixel))
    return FriendsScreen()


FRIENDS_ACTIONS = {
    "up": "move up the list (scrolling at the top), or up the toon's buttons",
    "down": "move down the list (scrolling at the bottom), or down the toon's buttons",
    "left": "previous page of the list", "right": "next page of the list",
    "select": "open the highlighted toon, or press the highlighted button (Yes in Go To's popup)",
    "back": "close Toon Details, the toon's panel, or the list (No in Go To's popup)",
    "goTo": "teleport to the toon (Go To)", "whisper": "whisper to the toon",
}


def default_friends_bindings() -> Bindings:
    press = {"a": "select", "b": "back", "x": "goTo", "y": "whisper"}
    # Only the D-pad, so the left stick still walks.
    for direction in ("up", "down", "left", "right"):
        press[f"dpad_{direction}"] = direction
    return Bindings(press=press)


@dataclass
class FriendsMapper:
    bindings: Bindings = field(default_factory=default_friends_bindings)
    settle_seconds: float = 0.25

    def __post_init__(self):
        self.set_bindings(self.bindings)
        self.row = 0
        self.button = 0
        self._kind: str | None = None
        self._from_popup = False  # the teleport popup just closed: keep the panel's button
        self._settle_until = 0.0
        self._details_opened_at = float("-inf")
        self._details_retry_at: float | None = None
        self._details_tries = 0
        self._held_scroll = HeldScroll()  # a scroll triangle, held down while its direction is

    def set_bindings(self, bindings: Bindings) -> None:
        self.bindings = bindings
        self._actions = ButtonActions(bindings, 0.5, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in ("up", "down"))

    @property
    def buttons(self) -> set[str]:
        return self.bindings.buttons()

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)
        self._held_scroll.stop(finish=False)
        self._kind = None

    def update(self, buttons: frozenset[str], now: float, screen: FriendsScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons, now)
        commands = self._held_scroll.stop(finish=False) if screen.kind != "list" else []
        commands += self._held_scroll.update({self.bindings.press.get(b) for b in buttons})
        fired_rest = []
        for action in fired:
            held = self._held_scroll.repeat(action)
            if held is None:
                fired_rest.append(action)
            else:
                commands += held  # still held on a scroll triangle: hold it down instead
        fired = fired_rest
        if now < self._settle_until:
            return commands
        if screen.kind != self._kind:
            self._kind = screen.kind
            if screen.kind == "list":
                self.row = 0
                commands += self._hover_row(screen)
            elif screen.kind == "panel":
                if not self._from_popup:
                    self.button = 0
                commands.append(self._hover_button())
            if screen.kind != "teleport":
                self._from_popup = False
        if self._details_retry_at is not None and now >= self._details_retry_at:
            if screen.kind == "panel" and screen.details and self._details_tries < DETAILS_CLOSE_TRIES:
                commands += self._close_details(now)
            else:
                self._details_retry_at = None
        for action in fired:
            commands += self._run(action, screen, now)
        return commands

    def _close_details(self, now: float) -> list[PointerCommand]:
        delay = max(0.0, self._details_opened_at + DETAILS_OPEN_SECONDS - now)
        self._details_tries += 1
        self._details_retry_at = now + delay + DETAILS_RETRY_SECONDS
        return [PointerCommand("click", DETAILS_CLOSE, "close toon details", delay=delay), self._hover_button()]

    def _hover_row(self, screen: FriendsScreen) -> list[PointerCommand]:
        if not screen.rows:
            return []
        self.row = max(0, min(self.row, len(screen.rows) - 1))
        return [PointerCommand("hover", screen.rows[self.row], f"friend {self.row + 1}")]

    def _hover_button(self) -> PointerCommand:
        point, name = PANEL_BUTTONS[self.button]
        return PointerCommand("hover", point, name)

    def _click(self, point: ui.UIPoint, name: str, now: float) -> list[PointerCommand]:
        """Click something that changes the screen, then look again once it settles."""
        self._settle_until = now + self.settle_seconds
        self._kind = None
        return [PointerCommand("click", point, name)]

    def _run(self, action: str, screen: FriendsScreen, now: float) -> list[PointerCommand]:
        if screen.kind == "teleport":
            if action not in ("select", "back"):
                return []
            self._from_popup = True
            point, name = (screen.yes, "teleport yes") if action == "select" else (screen.no, "teleport no")
            commands = self._click(point, name, now)
            self._from_popup = True
            return commands
        if screen.kind == "list":
            return self._run_list(action, screen, now)
        if screen.kind == "panel":
            return self._run_panel(action, screen, now)
        return []

    def _run_list(self, action: str, screen: FriendsScreen, now: float) -> list[PointerCommand]:
        if action in ("up", "down"):
            step = -1 if action == "up" else 1
            if not screen.rows:
                return []
            row = self.row + step
            if 0 <= row < len(screen.rows):
                self.row = row
                return self._hover_row(screen)
            if row < 0 or len(screen.rows) == VISIBLE_ROWS:
                # Past the top or a full bottom row: scroll, and stay on the same row.
                arrow = SCROLL_UP if row < 0 else SCROLL_DOWN
                self._held_scroll.clicked(action, arrow, after=self._hover_row(screen))
                return [PointerCommand("click", arrow, "scroll up" if row < 0 else "scroll down"),
                        *self._hover_row(screen)]
            return []
        if action in ("left", "right"):
            return self._click(PAGE_LEFT if action == "left" else PAGE_RIGHT, f"page {action}", now)
        if action == "select" and screen.rows:
            return self._click(screen.rows[self.row], f"open friend {self.row + 1}", now)
        if action in ("goTo", "whisper") and screen.rows:
            # Open the toon's panel, then press the button once it shows.
            point, name = (GO_TO, "go to") if action == "goTo" else (WHISPER, "whisper")
            commands = self._click(screen.rows[self.row], f"open friend {self.row + 1}", now)
            self._settle_until = now + PANEL_OPEN_SECONDS + self.settle_seconds
            return commands + [PointerCommand("click", point, name, delay=PANEL_OPEN_SECONDS)]
        if action == "back":
            return self._click(LIST_CLOSE, "close friends list", now)
        return []

    def _run_panel(self, action: str, screen: FriendsScreen, now: float) -> list[PointerCommand]:
        if action in ("up", "down"):
            self.button = max(0, min(len(PANEL_BUTTONS) - 1, self.button + (-1 if action == "up" else 1)))
            return [self._hover_button()]
        if action == "select":
            point, name = PANEL_BUTTONS[self.button]
            if point == TOON_DETAILS:
                # Toon Details opens beside the panel; stay on the same button.
                self._details_opened_at = now
                return [PointerCommand("click", point, name)]
            return self._click(point, name, now)
        if action == "goTo":
            self.button = 1
            return self._click(GO_TO, "go to", now)
        if action == "whisper":
            return self._click(WHISPER, "whisper", now)
        if action == "back":
            if screen.details:
                self._details_tries = 0
                return self._close_details(now)
            return self._click(PANEL_CLOSE, "close toon panel", now)
        return []
