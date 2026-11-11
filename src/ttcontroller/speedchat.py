"""The speedchat menu: moving through its menus and submenus with the D-pad.

The top menu sits at the top left. Hovering a row with an arrow opens its submenu
to the right, and clicking a phrase says it (and closes speedchat). Submenus go
wherever TTR puts them: overlapping their parent, or pushed up to fit in the
window. So each one is found on screen by following the highlighted rows out
from the top menu.

The highlight color can be changed in TTR's options, so nothing here depends on
it: a highlighted row is any strongly colored one, and a menu is a light gray
panel with a darker edge. Rows are always the same height, in units of the
window's shorter side (see ui.py).
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from . import ui
from .battle import PointerCommand
from .bindings import Bindings, ButtonActions

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]

ROW_HEIGHT = 0.03303
_PADDING = 0.0087  # top and bottom padding together
_TOP_MARGIN_X = 0.138  # inside the top menu's left edge
_TOP_PROBE_Y = -0.43  # from the window's center; inside the top menu at any size
_HOVER_X = 0.025  # from a menu's left edge
# Where the top menu really is: its left edge (0.1336 to 0.1368 measured) and its top
# (0.485 to 0.505 above the center). A light gray backdrop, like a cog building's walls
# in battle, passes the margin check too, but runs on past the menu's edge.
_TOP_LEFT_RANGE = (0.125, 0.145)
_TOP_TOP_RANGE = (-0.53, -0.46)

# The UNITE! row's shape, to find it wherever it is in the top menu (which rows
# show depends on the toon and where they are): how many of 9 points down the row
# are dark text, every 0.002 across from the menu's left edge. Measured at 1920x1009.
_INK_STEP = 0.002
_INK_DYS = tuple(k * 0.0025 for k in range(-4, 5))
UNITE_INK = tuple(int(c) for c in "005621148008844368008800228220883331007400000000000000000000000000000000000000000000000210")
_UNITE_MATCH = 0.8


def _is_panel(c: RGB) -> bool:
    return min(c) > 120 and max(c) > 160 and max(c) - min(c) < 60


def _is_colored(c: RGB) -> bool:
    return max(c) - min(c) > 60


def _is_leader_orange(c: RGB) -> bool:
    """In a boarding group, the top menu's GROUP LEADER row is always orange, (225, 131, 42),
    hovered or not (speedchat_boarding_hello)."""
    r, g, b = c
    return r > 190 and 100 < g < 160 and b < 70


_RUN_GAP = 3  # pixels


def _is_run(c: RGB) -> bool:
    """Part of a highlighted row: the highlight color, its dark text, or a blend of the
    two at a letter's edge. A pale highlight (lavender) blends into dimmer pixels that are
    just as tinted for their brightness (MY PHRASES' S, speedchat_bug_2), while the gray
    panel past the row's end barely is."""
    return _is_colored(c) or sum(c) < 250 or max(c) - min(c) > 0.2 * max(c)


@dataclass(frozen=True)
class Menu:
    left: ui.UIPoint  # left edge, top of the panel
    rows: tuple[ui.UIPoint, ...]  # where to hover each row
    highlighted: int | None = None


@dataclass(frozen=True)
class SpeedchatScreen:
    menus: tuple[Menu, ...] = ()  # the top menu, then each open submenu
    unite: int | None = None  # the top menu's UNITE! row, when looked for and found
    looked_for_unite: bool = False

    @property
    def is_open(self) -> bool:
        return bool(self.menus)


def _measure(width: int, height: int, get_pixel: PixelReader, xm: int, y0: int, unit: int):
    """The panel whose left margin column xm passes through y0: (top, bottom, row count), or None."""
    start = get_pixel(xm, y0)
    if not _is_panel(start):
        return None
    floor = sum(start) - 75

    def inside(y: int) -> bool:
        c = get_pixel(xm, y)
        return _is_panel(c) and sum(c) >= floor

    top = y0
    while top > 0 and inside(top - 1):
        top -= 1
    bottom = y0
    while bottom < height - 1 and inside(bottom + 1):
        bottom += 1
    row = ROW_HEIGHT * unit
    count = round((bottom - top + 1 - _PADDING * unit) / row)
    # A menu cut off by the window's bottom edge has no padding left there.
    cut = bottom >= height - 2
    residual = bottom - top + 1 - count * row - (0 if cut else _PADDING * unit)
    if count < 1 or (abs(residual) > 0.008 * unit and not cut):
        return None
    return top, bottom, count


def _menu(width: int, height: int, get_pixel: PixelReader, left: int, y0: int, unit: int):
    xm = left + max(1, round(0.002 * unit))
    measured = _measure(width, height, get_pixel, xm, y0, unit)
    if measured is None:
        return None
    top, bottom, count = measured
    row = ROW_HEIGHT * unit
    pad = (bottom - top + 1 - count * row) / 2 if bottom < height - 2 else _PADDING * unit / 2
    ys = [top + pad + (i + 0.5) * row for i in range(count)]
    ys = [y for y in ys if y < height - 0.25 * row]
    hover_x = (left + _HOVER_X * unit) / unit
    rows = tuple(ui.UIPoint("left", hover_x, y / unit) for y in ys)
    colored = []  # (row, leader orange): the hovered row, and GROUP LEADER's always-orange one
    for i, y in enumerate(ys):
        # Across the start of the row, where text can cover most points but never the arrow.
        hits = [c for k in range(16) for dy in (-0.006, 0, 0.006)
                if _is_colored(c := get_pixel(left + round((0.006 + 0.006 * k) * unit), round(y + dy * unit)))]
        if len(hits) >= 3:
            colored.append((i, sum(map(_is_leader_orange, hits)) * 2 > len(hits)))
    highlighted = colored[0][0] if colored else None
    menu = Menu(ui.UIPoint("left", left / unit, top / unit), rows, highlighted)
    return menu, (top, bottom), ys, colored


def _where_speedchat_opens(menu: Menu, width: int, height: int, unit: int) -> bool:
    top = menu.left.y - height / 2 / unit
    return (_TOP_LEFT_RANGE[0] <= menu.left.x <= _TOP_LEFT_RANGE[1]
            and _TOP_TOP_RANGE[0] <= top <= _TOP_TOP_RANGE[1])


def _find_child(width: int, height: int, get_pixel: PixelReader, left: int, y: int, unit: int,
                parent_span: tuple[int, int]):
    """The submenu open beside a highlighted row: where its left edge is, or None."""
    x = left + round(0.008 * unit)
    limit = min(width - 2, left + round(0.9 * unit))
    # The row ends where a few pixels in a row aren't part of it: a lone pixel on the
    # edge of a letter can be neither the highlight color nor dark (HELLO's).
    gap = 0
    while x < limit and gap < _RUN_GAP:
        gap = 0 if _is_run(get_pixel(x, y)) else gap + 1
        x += 1
    x -= gap
    # A submenu can open as little as 0.045 in from its parent's edge (UNITE > Jellybeans).
    if x >= limit or x < left + 0.025 * unit:
        return None
    window = range(x, min(width - 1, x + round(0.012 * unit)))
    brightest = max(sum(get_pixel(px, y)) for px in window)
    child = next(px for px in window if sum(get_pixel(px, y)) >= brightest - 30)
    measured = _measure(width, height, get_pixel, child + max(1, round(0.002 * unit)), y, unit)
    if measured is None:
        return None
    top, bottom, _ = measured
    if abs(top - parent_span[0]) <= 2 and abs(bottom - parent_span[1]) <= 2:
        return None  # just the highlighted row's own menu, past the end of the highlight
    return child


def _ink(get_pixel: PixelReader, left: int, y: int, unit: int) -> list[int]:
    return [sum(sum(get_pixel(left + round((0.004 + i * _INK_STEP) * unit), y + round(dy * unit))) < 250
                for dy in _INK_DYS) for i in range(len(UNITE_INK))]


def _correlation(a, b) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    da = [v - ma for v in a]
    db = [v - mb for v in b]
    norm = (sum(v * v for v in da) * sum(v * v for v in db)) ** 0.5
    return sum(x * y for x, y in zip(da, db)) / norm if norm else 0.0


def _unite_score(ink: list[int]) -> float:
    """How well a row's text matches UNITE!, allowing a few samples' slip (small windows)."""
    n = len(ink)
    return max(_correlation(ink[max(0, s):n + min(0, s)], UNITE_INK[max(0, -s):n - max(0, s)])
               for s in range(-3, 4))


def find_unite(width: int, height: int, get_pixel: PixelReader, menu: Menu) -> int | None:
    """The UNITE! row of the top menu, or None if it isn't there."""
    unit = min(width, height)
    left = menu.left.to_client(width, height)[0]
    scores = [_unite_score(_ink(get_pixel, left, row.to_client(width, height)[1], unit)) for row in menu.rows]
    best = max(range(len(scores)), key=scores.__getitem__, default=None)
    return best if best is not None and scores[best] >= _UNITE_MATCH else None


def read_speedchat(width: int, height: int, get_pixel: PixelReader, look_for_unite: bool = False) -> SpeedchatScreen:
    if not ui.is_visible(ui.SPEEDCHAT_MENU, width, height, get_pixel):
        return SpeedchatScreen()
    unit = min(width, height)
    # Find the top menu's left edge from inside its margin.
    y0 = round(height / 2 + _TOP_PROBE_Y * unit)
    left = round(_TOP_MARGIN_X * unit)
    while left > 0 and _is_panel(get_pixel(left - 1, y0)) and sum(get_pixel(left - 1, y0)) > 450:
        left -= 1
    menus: list[Menu] = []
    while len(menus) < 8:
        found = _menu(width, height, get_pixel, left, y0, unit)
        if found is None:
            break
        menu, span, ys, colored = found
        if not menus and not _where_speedchat_opens(menu, width, height, unit):
            return SpeedchatScreen()
        if menu.highlighted is None:
            menus.append(menu)
            break
        # More than one colored row (GROUP LEADER's orange): the hovered one is the one
        # whose submenu is open, or else the one that isn't orange.
        child = None
        for i, _ in colored:
            child = _find_child(width, height, get_pixel, left, round(ys[i]), unit, span)
            if child is not None:
                menu = Menu(menu.left, menu.rows, i)
                break
        else:
            plain = [i for i, orange in colored if not orange]
            menu = Menu(menu.left, menu.rows, plain[0] if plain else colored[0][0])
        menus.append(menu)
        if child is None:
            break
        y0 = round(ys[menu.highlighted])
        left = child
    if look_for_unite and menus:
        return SpeedchatScreen(tuple(menus), find_unite(width, height, get_pixel, menus[0]), True)
    return SpeedchatScreen(tuple(menus))


SPEEDCHAT_ACTIONS = {
    "up": "move up the menu", "down": "move down the menu",
    "right": "open the highlighted submenu", "left": "back to the menu before",
    "select": "say the highlighted phrase, or open its submenu",
    "back": "back to the menu before, or close speedchat from the top menu",
}


def default_speedchat_bindings() -> Bindings:
    press = {"a": "select", "b": "back"}
    # Only the D-pad, so the left stick still walks.
    for direction in ("up", "down", "left", "right"):
        press[f"dpad_{direction}"] = direction
    return Bindings(press=press)


@dataclass
class SpeedchatMapper:
    bindings: Bindings = field(default_factory=default_speedchat_bindings)
    # A submenu takes a moment to open after its row is hovered.
    open_seconds: float = 0.4

    def __post_init__(self):
        self.set_bindings(self.bindings)
        self.depth = 0
        self.row = 0
        self._open = False
        self._entering_until: float | None = None
        self._closing_until = 0.0
        self._unite_until: float | None = None

    def go_to_unite(self, now: float) -> None:
        """The unite hotkey: go to UNITE! > Toon-Up once speedchat is open."""
        self._unite_until = now + 2 * self.open_seconds + 1.0
        self._closing_until = 0.0

    @property
    def wants_unite(self) -> bool:
        return self._unite_until is not None

    def set_bindings(self, bindings: Bindings) -> None:
        self.bindings = bindings
        self._actions = ButtonActions(bindings, 0.5, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in ("up", "down"))

    @property
    def buttons(self) -> set[str]:
        return self.bindings.buttons()

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)
        self._open = False
        self._entering_until = None

    def update(self, buttons: frozenset[str], now: float, screen: SpeedchatScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons, now)
        if self._unite_until is not None and now > self._unite_until:
            self._unite_until = None
        if not screen.is_open:
            self._open = False
            self._closing_until = 0.0
            return []
        if now < self._closing_until:
            return []  # a phrase was said: speedchat is closing
        commands: list[PointerCommand] = []
        if self._unite_until is not None:
            if not screen.looked_for_unite:
                return []  # wait for a look at the top menu
            self._unite_until = None
            if screen.unite is not None:
                # Hover UNITE!, then go into its submenu (Toon-Up first) once it opens.
                self._open = True
                self.depth, self.row = 0, screen.unite
                self._entering_until = now + self.open_seconds
                return [self._hover(screen)]
        if not self._open:
            self._open = True
            self.depth, self.row = 0, 0
            commands.append(self._hover(screen))
        self.depth = min(self.depth, len(screen.menus) - 1)
        if self._entering_until is not None:
            if self._child_open(screen):
                self._entering_until = None
                self.depth += 1
                self.row = 0
                commands.append(self._hover(screen))
            elif now > self._entering_until:
                self._entering_until = None
        for action in fired:
            commands += self._run(action, screen, now)
        return commands

    def _child_open(self, screen: SpeedchatScreen) -> bool:
        return (len(screen.menus) > self.depth + 1
                and screen.menus[self.depth].highlighted == self.row)

    def _hover(self, screen: SpeedchatScreen) -> PointerCommand:
        rows = screen.menus[self.depth].rows
        self.row = max(0, min(self.row, len(rows) - 1))
        return PointerCommand("hover", rows[self.row], f"speedchat menu {self.depth + 1} row {self.row + 1}")

    def _run(self, action: str, screen: SpeedchatScreen, now: float) -> list[PointerCommand]:
        rows = screen.menus[self.depth].rows
        if action in ("up", "down"):
            self._entering_until = None
            self.row = (self.row + (-1 if action == "up" else 1)) % len(rows)
            return [self._hover(screen)]
        if action in ("right", "select"):
            if self._child_open(screen):
                self.depth += 1
                self.row = 0
                return [self._hover(screen)]
            if action == "right":
                # The submenu may still be opening: enter it once it shows.
                self._entering_until = now + self.open_seconds
                return []
            self._closing_until = now + self.open_seconds
            return [PointerCommand("click", rows[self.row], "speedchat phrase")]
        if action in ("left", "back"):
            self._entering_until = None
            if self.depth > 0:
                self.depth -= 1
                self.row = screen.menus[self.depth].highlighted or 0
                return [self._hover(screen)]
            if action == "back":
                self._closing_until = now + self.open_seconds
                return [PointerCommand("click", ui.SPEEDCHAT.center, "close speedchat")]
        return []
