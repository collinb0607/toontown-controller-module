"""The shticker book: changing pages and the tabs along a page's top.

While the book is open the world is hidden behind a plain blue backdrop. The
book is centered, in units of the window's shorter side (see ui.py). Its pages
are a column of square tabs down its right edge, one icon each. Not every toon
has every page and they can come in a different order, so a page is known by
its tab's icon, not its place in the column. The current page's tab is drawn
pressed in: its bevel is dark on the left and light on the right, the other
way round from the rest.

Some pages have tabs of their own above the book (the Gags page has Gags and
Trunk). The current one is brightly colored; the others are pale.

An OK/Cancel dialog over the book (Exit Toontown?) dims everything behind it,
backdrop included, so the book is known by the dimmed backdrop then.

Pages with controls of their own:
- Options & Codes: Submit, the SpeedChat color (hovering its box previews it, with
  arrows either side to change it), Open Options and Exit Toontown. The code box
  is skipped, since there's no way to type.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from . import ui
from .battle import PointerCommand
from .bindings import Bindings, ButtonActions
from .dialog import find_ok_cancel

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]


def _center(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "center")


# Measured at 1915x1006.
BACKDROP = (13, 38, 102)
DIM_BACKDROP = (7, 19, 51)  # behind a dialog
_BELOW_BOOK_Y = 0.338
_BACKDROP_PROBES = tuple(_center(-0.45 + 0.05 * i, _BELOW_BOOK_Y) for i in range(19))
_BACKDROP_MIN_HITS = 14

# The page tabs: the first and last columns of each tab's plain gray face, and the
# center of the first tab. Tabs stack down from the top with no gaps.
_TAB_LEFT = 0.4448
_TAB_RIGHT = 0.4836
_TAB_X = 0.4642
_TAB0_Y = -0.3738
_TAB_STEP = 0.04389
_MAX_TABS = 18
_EDGE_SEARCH = 0.008  # how far either side of a face's expected edge to look for it
_ROW_DYS = (-0.012, -0.004, 0.004, 0.012)  # rows through a tab that clear its separators
_ICON_HALF_HEIGHT = 0.019

# The tabs above the book, along this row. Anything that isn't backdrop is a tab.
_TOP_TAB_Y = -0.4553
_TOP_TAB_LEFT, _TOP_TAB_RIGHT = -0.50, 0.50
_TOP_TAB_STEP = 0.004
_TOP_TAB_MIN_WIDTH = 0.08

PAGES = ("options", "districts", "map", "gags", "toontasks", "resistance rank", "cog gallery", "fishing",
         "racing", "cog disguise", "gardening", "golf", "snapshots", "events")

# Each page's tab icon: the mean color of a 5x5 grid over the tab's face, row by row.
# Made with signature() from captures/book_trunk_1920x1009.png.
ICONS = {
    "options": (204, 204, 204, 153, 133, 116, 191, 169, 132, 218, 204, 169, 206, 198, 185, 204, 204, 204, 150, 124, 96, 165, 135, 79, 137, 110, 59, 175, 164, 147, 204, 204, 204, 142, 118, 93, 138, 115, 70, 132, 106, 65, 180, 170, 161, 204, 204, 204, 139, 114, 91, 142, 120, 80, 132, 107, 71, 179, 170, 161, 204, 204, 204, 145, 124, 107, 129, 104, 81, 130, 104, 82, 181, 173, 166),
    "districts": (194, 197, 194, 106, 148, 125, 80, 140, 114, 53, 117, 112, 169, 182, 181, 104, 134, 116, 95, 181, 170, 109, 178, 163, 37, 80, 66, 57, 80, 70, 100, 132, 105, 109, 149, 115, 104, 167, 151, 40, 78, 64, 33, 52, 37, 145, 156, 146, 96, 98, 65, 80, 116, 101, 26, 54, 47, 86, 98, 89, 195, 195, 195, 137, 157, 153, 67, 101, 98, 101, 121, 118, 189, 190, 190),
    "map": (204, 204, 204, 204, 204, 204, 205, 203, 203, 217, 124, 125, 220, 109, 110, 204, 204, 204, 204, 204, 204, 218, 116, 117, 226, 60, 61, 207, 192, 193, 169, 169, 169, 96, 96, 97, 147, 50, 51, 114, 50, 51, 168, 165, 165, 122, 122, 122, 36, 36, 36, 13, 11, 12, 35, 35, 35, 119, 119, 119, 195, 195, 195, 195, 195, 195, 192, 192, 192, 195, 195, 195, 195, 195, 195),
    "gags": (204, 204, 204, 194, 192, 190, 197, 180, 162, 199, 174, 151, 175, 164, 155, 200, 200, 200, 199, 171, 146, 225, 188, 154, 202, 165, 132, 135, 125, 118, 171, 157, 146, 184, 148, 117, 175, 141, 110, 113, 96, 83, 135, 137, 144, 189, 188, 187, 103, 100, 105, 104, 106, 113, 107, 111, 124, 175, 175, 178, 211, 211, 211, 191, 192, 193, 165, 166, 170, 201, 201, 202, 211, 211, 211),
    "toontasks": (186, 180, 162, 214, 205, 177, 213, 205, 177, 212, 204, 176, 202, 196, 177, 209, 200, 174, 235, 223, 184, 236, 226, 190, 235, 224, 187, 208, 198, 170, 206, 200, 179, 235, 225, 190, 238, 228, 194, 242, 232, 199, 208, 200, 175, 199, 192, 170, 228, 216, 177, 227, 216, 178, 230, 219, 182, 201, 193, 168, 191, 189, 186, 188, 186, 181, 188, 186, 181, 187, 185, 179, 190, 189, 184),
    "resistance rank": (188, 196, 192, 64, 163, 114, 87, 185, 137, 71, 169, 120, 170, 188, 179, 100, 162, 130, 127, 206, 167, 242, 242, 241, 188, 229, 209, 62, 156, 108, 84, 165, 124, 108, 197, 152, 231, 233, 232, 145, 206, 175, 40, 153, 95, 148, 180, 164, 31, 185, 109, 45, 169, 174, 33, 184, 120, 117, 172, 145, 195, 195, 195, 156, 177, 166, 97, 160, 129, 140, 171, 156, 195, 195, 195),
    "cog gallery": (187, 187, 186, 138, 136, 134, 114, 112, 108, 137, 135, 132, 175, 174, 173, 137, 136, 135, 80, 78, 75, 106, 105, 104, 85, 82, 78, 123, 121, 118, 99, 97, 95, 81, 79, 77, 156, 156, 156, 100, 98, 96, 93, 89, 86, 160, 160, 159, 91, 87, 84, 101, 98, 95, 93, 90, 85, 148, 146, 144, 195, 195, 195, 162, 161, 161, 130, 127, 124, 151, 150, 149, 191, 191, 190),
    "fishing": (203, 204, 204, 171, 190, 202, 151, 182, 203, 199, 202, 204, 181, 194, 203, 129, 175, 205, 93, 175, 230, 94, 180, 239, 122, 182, 223, 124, 176, 212, 112, 178, 223, 131, 198, 245, 129, 197, 245, 125, 190, 235, 126, 178, 213, 175, 192, 204, 125, 182, 221, 109, 178, 226, 173, 193, 207, 190, 198, 204, 195, 195, 195, 195, 195, 195, 182, 190, 195, 195, 195, 195, 195, 195, 195),
    "racing": (194, 194, 194, 109, 109, 109, 94, 94, 94, 96, 96, 96, 180, 180, 180, 129, 129, 129, 118, 118, 118, 170, 170, 169, 141, 142, 141, 93, 93, 93, 113, 114, 113, 137, 138, 137, 127, 128, 124, 140, 140, 139, 93, 93, 93, 177, 177, 177, 110, 110, 110, 104, 104, 104, 112, 112, 112, 152, 152, 152, 186, 186, 186, 170, 170, 170, 144, 144, 144, 162, 162, 162, 186, 186, 186),
    "cog disguise": (200, 200, 200, 111, 111, 112, 101, 101, 102, 97, 97, 98, 192, 192, 192, 169, 169, 169, 104, 104, 105, 109, 109, 110, 109, 109, 110, 147, 147, 148, 140, 140, 141, 105, 105, 107, 99, 99, 101, 108, 108, 109, 121, 121, 122, 108, 108, 109, 123, 123, 124, 98, 98, 100, 119, 119, 120, 90, 90, 92, 170, 170, 170, 146, 146, 147, 136, 136, 137, 147, 147, 148, 174, 174, 174),
    "gardening": (199, 199, 199, 139, 147, 147, 97, 106, 106, 128, 138, 139, 195, 196, 196, 181, 186, 185, 109, 118, 120, 70, 79, 78, 96, 104, 105, 172, 179, 179, 184, 189, 189, 114, 124, 126, 95, 104, 105, 95, 103, 105, 176, 183, 182, 191, 194, 193, 159, 165, 165, 136, 146, 146, 145, 152, 151, 185, 189, 188, 186, 186, 186, 186, 186, 186, 153, 148, 136, 183, 183, 182, 186, 186, 186),
    "golf": (140, 189, 124, 219, 228, 168, 221, 230, 169, 223, 231, 170, 173, 208, 143, 154, 194, 130, 184, 174, 108, 217, 210, 120, 236, 235, 177, 189, 213, 151, 154, 195, 131, 223, 215, 115, 239, 222, 74, 221, 214, 116, 188, 213, 149, 154, 195, 131, 237, 237, 178, 222, 214, 104, 193, 176, 80, 164, 182, 111, 117, 168, 123, 128, 174, 126, 127, 172, 124, 134, 163, 106, 112, 163, 113),
    "snapshots": (204, 204, 204, 198, 197, 196, 125, 110, 66, 106, 93, 41, 154, 144, 114, 204, 204, 204, 134, 98, 87, 162, 96, 4, 194, 130, 2, 168, 131, 79, 204, 204, 204, 147, 97, 81, 162, 93, 7, 196, 129, 2, 168, 134, 85, 149, 133, 129, 105, 68, 57, 150, 94, 18, 188, 129, 6, 163, 138, 98, 182, 182, 182, 184, 184, 184, 172, 171, 170, 161, 159, 155, 176, 175, 175),
    "events": (204, 204, 204, 204, 204, 204, 204, 204, 204, 150, 181, 204, 69, 162, 226, 205, 204, 202, 213, 188, 163, 231, 188, 100, 247, 198, 46, 193, 190, 185, 222, 182, 130, 253, 187, 24, 253, 206, 26, 240, 187, 59, 204, 204, 203, 206, 205, 198, 240, 194, 66, 251, 162, 18, 216, 184, 147, 204, 204, 204, 186, 186, 186, 187, 183, 180, 194, 155, 127, 186, 186, 186, 186, 186, 186),
}
_ICON_MATCH = 20  # the most an icon can differ from its page's, on average per channel


def is_backdrop(c: RGB) -> bool:
    return sum(abs(p - q) for p, q in zip(c, BACKDROP)) < 40


def is_dim_backdrop(c: RGB) -> bool:
    return sum(abs(p - q) for p, q in zip(c, DIM_BACKDROP)) < 25


def _is_face(c: RGB) -> bool:
    return all(194 <= v <= 214 for v in c) and max(c) - min(c) < 8


# Options & Codes, measured at 1920x1009.
SUBMIT = _center(0.2270, -0.1001)
SPEEDCHAT_COLOR = _center(0.2200, 0.0649)  # hovering it previews the color
COLOR_LEFT = _center(0.1234, 0.0639)
COLOR_RIGHT = _center(0.3256, 0.0639)
OPEN_OPTIONS = _center(0.2270, 0.1705)
EXIT_TOONTOWN = _center(0.2270, 0.2448)
OPTIONS_ROWS = ((SUBMIT, "submit"), (SPEEDCHAT_COLOR, "speedchat color"), (OPEN_OPTIONS, "open options"),
                (EXIT_TOONTOWN, "exit toontown"))


@dataclass(frozen=True)
class BookScreen:
    tabs: tuple[ui.UIPoint, ...] = ()  # the page tabs, top to bottom
    current: int | None = None  # index into tabs
    page: str | None = None  # the current page, by its tab's icon (None if it isn't known)
    top_tabs: tuple[ui.UIPoint, ...] = ()
    top_current: int | None = None
    dialog: tuple[ui.UIPoint, ui.UIPoint] | None = None  # an OK/Cancel dialog over the book

    @property
    def is_open(self) -> bool:
        return bool(self.tabs) or self.dialog is not None

    @property
    def hovers(self) -> bool:
        """Whether something is highlighted with the cursor (so it isn't parked)."""
        return self.dialog is not None or self.page in PAGE_ROWS


def _px(width: int, height: int, x: float, y: float) -> tuple[int, int]:
    return _center(x, y).to_client(width, height)


def _face_edges(width: int, height: int, get_pixel: PixelReader, y: float) -> tuple[int, int, int] | None:
    """Along one row through a tab: the face's first and last columns, and that row in pixels."""
    unit = min(width, height)
    x0, py = _px(width, height, _TAB_LEFT, y)
    x1, _ = _px(width, height, _TAB_RIGHT, y)
    reach = max(2, round(_EDGE_SEARCH * unit))

    def edge(x: int, inward: int) -> bool:
        # Face here and inward of here, and a lighter or darker bevel just outside.
        face, outside = get_pixel(x, py), get_pixel(x - inward, py)
        return (_is_face(face) and _is_face(get_pixel(x + inward, py)) and _is_bevel(outside)
                and abs(sum(outside) - sum(face)) >= 30)

    # Searched from the inside out: the page beside the tabs can be shaded face gray,
    # but it's always outside the bevel.
    left = next((x for x in range(x0 + reach, x0 - reach, -1) if edge(x, 1)), None)
    right = next((x for x in range(x1 - reach, x1 + reach) if edge(x, -1)), None)
    if left is None or right is None:
        return None
    return left, right, py


def _edges(width: int, height: int, get_pixel: PixelReader) -> tuple[int, int] | None:
    """The first and last columns of the tabs' gray faces, from whichever rows show them
    (an icon can cover a face edge to edge)."""
    found = [_face_edges(width, height, get_pixel, _TAB0_Y + _TAB_STEP * i + dy)
             for i in range(4) for dy in _ROW_DYS]
    found = [f for f in found if f is not None]
    if len(found) < 3:
        return None
    lefts = sorted(f[0] for f in found)
    rights = sorted(f[1] for f in found)
    return lefts[len(lefts) // 2], rights[len(rights) // 2]


def _is_bevel(c: RGB) -> bool:
    return max(c) - min(c) < 16 and 140 <= min(c)


def _bevel(width: int, height: int, get_pixel: PixelReader, i: int, left: int, right: int) -> str | None:
    """Whether tab i is "raised" or "pressed" (the current page); None if there's no tab there."""
    votes = {"raised": 0, "pressed": 0}
    for dy in _ROW_DYS:
        _, py = _px(width, height, _TAB_X, _TAB0_Y + _TAB_STEP * i + dy)
        a, b = get_pixel(left - 1, py), get_pixel(right + 1, py)
        if not (_is_bevel(a) and _is_bevel(b)):
            continue
        light_left = sum(a) - sum(b)
        if abs(light_left) >= 60:
            votes["raised" if light_left > 0 else "pressed"] += 1
    kind = max(votes, key=votes.get)
    return kind if votes[kind] >= 2 else None


_GRID = 5


def signature(width: int, height: int, get_pixel: PixelReader, i: int, left: int, right: int,
              shift: int = 0) -> tuple[int, ...]:
    """Tab i's icon as the mean color of a grid over its face, row by row, given the face's
    columns. shift moves the grid down that many pixels."""
    unit = min(width, height)
    _, cy = _px(width, height, _TAB_X, _TAB0_Y + _TAB_STEP * i)
    cy += shift
    top, bottom = cy - _ICON_HALF_HEIGHT * unit, cy + _ICON_HALF_HEIGHT * unit
    left, right = left + 1, right - 1
    # Every pixel in each cell, so a pixel's shift in where the tab lands barely changes it.
    xs = [round(left + (right - left) * k / _GRID) for k in range(_GRID + 1)]
    ys = [round(top + (bottom - top) * k / _GRID) for k in range(_GRID + 1)]
    out = []
    for row in range(_GRID):
        for col in range(_GRID):
            colors = [get_pixel(x, y) for y in range(ys[row], ys[row + 1]) for x in range(xs[col], xs[col + 1])]
            out += [round(sum(c[ch] for c in colors) / len(colors)) for ch in range(3)]
    return tuple(out)


def identify(*icons: tuple[int, ...]) -> str | None:
    """The page whose icon is closest to any of these (e.g. one tab read at a few shifts)."""
    best, best_diff = None, _ICON_MATCH
    for page, known in ICONS.items():
        for icon in icons:
            if len(known) != len(icon):
                continue
            diff = sum(abs(p - q) for p, q in zip(icon, known)) / len(icon)
            if diff < best_diff:
                best, best_diff = page, diff
    return best


# Tabs' heights are worked out, not measured, so their icons can land a pixel or two off.
_SHIFTS = (-2, -1, 0, 1, 2)


def _page(width: int, height: int, get_pixel: PixelReader, i: int, left: int, right: int) -> str | None:
    return identify(*(signature(width, height, get_pixel, i, left, right, s) for s in _SHIFTS))


def _top_tabs(width: int, height: int, get_pixel: PixelReader) -> tuple[tuple[ui.UIPoint, ...], int | None]:
    runs: list[list[tuple[float, RGB]]] = []
    run: list[tuple[float, RGB]] = []
    steps = round((_TOP_TAB_RIGHT - _TOP_TAB_LEFT) / _TOP_TAB_STEP)
    for k in range(steps + 1):
        x = _TOP_TAB_LEFT + _TOP_TAB_STEP * k
        c = get_pixel(*_px(width, height, x, _TOP_TAB_Y))
        if is_backdrop(c):
            if run:
                runs.append(run)
            run = []
        else:
            run.append((x, c))
    if run:
        runs.append(run)
    runs = [r for r in runs if r[-1][0] - r[0][0] >= _TOP_TAB_MIN_WIDTH]
    if len(runs) < 2:
        return (), None
    points = tuple(_center((r[0][0] + r[-1][0]) / 2, _TOP_TAB_Y) for r in runs)

    def colorfulness(r):
        return sum(max(c) - min(c) for _, c in r) / len(r)

    return points, max(range(len(runs)), key=lambda k: colorfulness(runs[k]))


def _read_tabs(width: int, height: int, get_pixel: PixelReader) -> tuple[list[str], tuple[int, int]] | None:
    """Each tab's bevel ("raised" or "pressed"), top to bottom, and the faces' columns."""
    hits = sum(is_backdrop(get_pixel(*p.to_client(width, height))) for p in _BACKDROP_PROBES)
    if hits < _BACKDROP_MIN_HITS:
        return None
    edges = _edges(width, height, get_pixel)
    if edges is None:
        return None
    kinds = []
    for i in range(_MAX_TABS):
        kind = _bevel(width, height, get_pixel, i, *edges)
        if kind is None:
            break
        kinds.append(kind)
    return (kinds, edges) if len(kinds) >= 2 else None


def read_book(width: int, height: int, get_pixel: PixelReader) -> BookScreen:
    found = _read_tabs(width, height, get_pixel)
    if found is None:
        dim = sum(is_dim_backdrop(get_pixel(*p.to_client(width, height))) for p in _BACKDROP_PROBES)
        if dim >= _BACKDROP_MIN_HITS:
            dialog = find_ok_cancel(width, height, get_pixel)
            if dialog is not None:
                return BookScreen(dialog=dialog)
        return BookScreen()
    kinds, edges = found
    current = kinds.index("pressed") if "pressed" in kinds else None
    # Only the current page's icon is needed (reading one takes a lot of pixels).
    page = _page(width, height, get_pixel, current, *edges) if current is not None else None
    top_tabs, top_current = _top_tabs(width, height, get_pixel)
    tabs = tuple(_center(_TAB_X, _TAB0_Y + _TAB_STEP * i) for i in range(len(kinds)))
    return BookScreen(tabs, current, page, top_tabs, top_current)


def read_pages(width: int, height: int, get_pixel: PixelReader) -> list[str | None]:
    """Every tab's page, top to bottom (for tests and tools)."""
    found = _read_tabs(width, height, get_pixel)
    if found is None:
        return []
    kinds, edges = found
    return [_page(width, height, get_pixel, i, *edges) for i in range(len(kinds))]


BOOK_ACTIONS = {
    "prevPage": "the page above in the tabs down the right (taps TTR's turn left key)",
    "nextPage": "the page below in the tabs down the right (taps TTR's turn right key)",
    "prevTab": "the tab to the left along the page's top",
    "nextTab": "the tab to the right along the page's top",
    "close": "close the book, or cancel a dialog over it",
    "select": "press the highlighted button (OK in a dialog)",
    "up": "move up a page's buttons", "down": "move down a page's buttons",
    "left": "change a setting (the SpeedChat color)", "right": "change a setting (the SpeedChat color)",
}


def default_book_bindings() -> Bindings:
    press = {"lb": "prevPage", "rb": "nextPage", "lt": "prevTab", "rt": "nextTab", "b": "close", "a": "select"}
    # The left stick too: the toon can't walk while the book is open.
    for direction in ("up", "down", "left", "right"):
        press[f"dpad_{direction}"] = direction
        press[f"ls_{direction}"] = direction
    return Bindings(press=press)


# Each page with controls: its buttons, top to bottom.
PAGE_ROWS = {"options": OPTIONS_ROWS}
# Buttons with a setting changed by left/right: the arrows to click.
_ARROWS = {SPEEDCHAT_COLOR: (COLOR_LEFT, COLOR_RIGHT)}


# Actions that are just a tap of a TTR control.
_TAPS = {"prevPage": "left", "nextPage": "right", "close": "stickerBook"}


@dataclass
class BookMapper:
    bindings: Bindings = field(default_factory=default_book_bindings)
    settle_seconds: float = 0.25

    def __post_init__(self):
        self.set_bindings(self.bindings)
        self._settle_until = 0.0
        self._taps: list[str] = []
        self.row = 0
        self._shown: tuple | None = None  # what was last hovered for: (page, dialog showing)
        self._page: str | None = None

    def set_bindings(self, bindings: Bindings) -> None:
        self.bindings = bindings
        self._actions = ButtonActions(bindings, 0.5, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in ("prevPage", "nextPage", "up", "down"))

    @property
    def buttons(self) -> set[str]:
        return self.bindings.buttons()

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)
        self._shown = None

    def take_taps(self) -> list[str]:
        """TTR controls to tap, asked for since the last call: the turn keys flip pages
        and the book key closes it."""
        taps, self._taps = self._taps, []
        return taps

    def update(self, buttons: frozenset[str], now: float, screen: BookScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons, now)
        commands: list[PointerCommand] = []
        if now >= self._settle_until:
            shown = (screen.page, screen.dialog is not None)
            if shown != self._shown:
                self._shown = shown
                # A new page starts at its top button. A dialog hides the page, so
                # coming back from one keeps the button it was opened from.
                if screen.dialog is None and screen.page != self._page:
                    self._page = screen.page
                    self.row = 0
                commands += self._hover(screen)
        for action in fired:
            if screen.dialog is not None:
                commands += self._run_dialog(action, screen, now)
            elif action in _TAPS:
                self._taps.append(_TAPS[action])
            elif now >= self._settle_until:
                commands += self._run(action, screen, now)
        return commands

    def _hover(self, screen: BookScreen) -> list[PointerCommand]:
        if screen.dialog is not None:
            return [PointerCommand("hover", screen.dialog[0], "OK")]
        rows = PAGE_ROWS.get(screen.page)
        if not rows:
            return []
        point, name = rows[self.row]
        return [PointerCommand("hover", point, name)]

    def _run_dialog(self, action: str, screen: BookScreen, now: float) -> list[PointerCommand]:
        ok, cancel = screen.dialog
        if action == "select":
            return self._click(ok, "OK", now)
        if action == "close":
            return self._click(cancel, "cancel", now)
        return []

    def _click(self, point: ui.UIPoint, name: str, now: float) -> list[PointerCommand]:
        """Click something that changes the page, then look again once it settles."""
        self._settle_until = now + self.settle_seconds
        self._shown = None
        return [PointerCommand("click", point, name)]

    def _run(self, action: str, screen: BookScreen, now: float) -> list[PointerCommand]:
        rows = PAGE_ROWS.get(screen.page)
        if rows and action in ("up", "down"):
            self.row = max(0, min(len(rows) - 1, self.row + (-1 if action == "up" else 1)))
            return self._hover(screen)
        if rows and action in ("left", "right"):
            point, name = rows[self.row]
            if point in _ARROWS:
                arrow = _ARROWS[point][action == "right"]
                # Back onto the setting after, which shows it.
                return [PointerCommand("click", arrow, f"{name} {action}"), PointerCommand("hover", point, name)]
            return []
        if rows and action == "select":
            point, name = rows[self.row]
            if point in _ARROWS:
                return []
            return self._click(point, name, now)
        if action in ("prevTab", "nextTab") and screen.top_tabs and screen.top_current is not None:
            i = screen.top_current + (-1 if action == "prevTab" else 1)
            if 0 <= i < len(screen.top_tabs):
                return self._click(screen.top_tabs[i], f"top tab {i + 1}", now)
        return []
