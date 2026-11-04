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
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from . import ui
from .battle import PointerCommand
from .bindings import Bindings, ButtonActions

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
    kind: str | None = None  # "list", "panel" (a toon's panel), or None
    rows: tuple[ui.UIPoint, ...] = ()  # list: the names showing, top to bottom
    details: bool = False  # panel: Toon Details is open too


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


def read_friends(width: int, height: int, get_pixel: PixelReader) -> FriendsScreen:
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
    "select": "open the highlighted toon, or press the highlighted button",
    "back": "close Toon Details, the toon's panel, or the list",
    "goTo": "teleport to the toon (Go To)", "whisper": "whisper to the toon",
}


def default_friends_bindings() -> Bindings:
    press = {"a": "select", "b": "back", "x": "goTo", "y": "whisper"}
    for direction in ("up", "down", "left", "right"):
        press[f"dpad_{direction}"] = direction
        press[f"ls_{direction}"] = direction
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
        self._settle_until = 0.0

    def set_bindings(self, bindings: Bindings) -> None:
        self.bindings = bindings
        self._actions = ButtonActions(bindings, 0.5, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in ("up", "down"))

    @property
    def buttons(self) -> set[str]:
        return self.bindings.buttons()

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)
        self._kind = None

    def update(self, buttons: frozenset[str], now: float, screen: FriendsScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons, now)
        if now < self._settle_until:
            return []
        commands: list[PointerCommand] = []
        if screen.kind != self._kind:
            self._kind = screen.kind
            if screen.kind == "list":
                self.row = 0
                commands += self._hover_row(screen)
            elif screen.kind == "panel":
                self.button = 0
                commands.append(self._hover_button())
        for action in fired:
            commands += self._run(action, screen, now)
        return commands

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
                return [PointerCommand("click", point, name)]
            return self._click(point, name, now)
        if action == "goTo":
            return self._click(GO_TO, "go to", now)
        if action == "whisper":
            return self._click(WHISPER, "whisper", now)
        if action == "back":
            if screen.details:
                return [PointerCommand("click", DETAILS_CLOSE, "close toon details"), self._hover_button()]
            return self._click(PANEL_CLOSE, "close toon panel", now)
        return []
