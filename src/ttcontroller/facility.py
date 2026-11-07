"""Facility nametags: in a Cog HQ, the facilities (Cashbot HQ's CASHBOT VAULT, COIN
MINT and BULLION MINT) have nametags that TTR pins to the window's margins when
they're off to the side or behind, like other buildings' and cogs'. Clicking one
opens a popup in the top right: the facility's name and picture, a green Teleport
Here! button and a small red X in its bottom right (facility_nametags and
facility_nametags_popup, 1920x1009).

The margin tags sit in fixed cells, and a tag moves between them as you turn:
- the bottom row: cells 0.22 apart from the window's middle, their tags' tops 0.1338
  above the bottom (more cells in a wider window, test_1626x711);
- a column down either side, 0.11 in from the edge: tops at -0.0223 + 0.22 * k from
  the middle (more cells in a taller window, gardening_hud_5_405x820).
A tag's box is centered on its cell and grows down with its lines.

A facility's tag is told from the rest by its first line of text: a light gray box
with mid-gray, outlined letters, no black (cogs' names are black) and no color
(buildings' are blue, toons' and NPCs' colored). Only Cashbot HQ's are measured; the
boxes are a little see-through, so another HQ's ground may tint them.

LB clicks the first tag (they're ordered around the margins: the left column top to
bottom, the bottom row left to right, the right column bottom to top). With the
popup open, LB and RB click the previous and next tag (RB's friends list is behind
the popup anyway), A clicks Teleport Here! and B the X.
"""

from collections.abc import Callable
from dataclasses import dataclass

from . import ui
from .battle import PointerCommand
from .bindings import Bindings, ButtonActions

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]

CELL_STEP = 0.22
BOTTOM_TOP = 0.1338  # the bottom row's tag tops, above the window's bottom
SIDE_X = 0.11  # the side columns' middles, in from the edges
SIDE_TOP = -0.0223  # a side cell's tag top, from the window's middle (plus CELL_STEP * k)
_BOTTOM_MIN_EDGE = 0.22  # a bottom cell's middle at least this far from the sides (past the columns)
_LINE = (0.004, 0.026)  # the tag's first line of text, below its top
_HALF_WIDTH = 0.06  # sampled either side of the middle (the narrowest tag, COIN MINT, is 0.15 wide)
_ABOVE = 0.008  # the scene above the tag's top
_EDGE_DIFF = 20  # the scene above differs from the box's fill by at least this, somewhere
_CLICK_Y = 0.015  # where a tag is clicked, below its top
# The arrow under a tag (lower the more lines it has): a cog's is orange, a building's blue.
_ARROW_HALF_WIDTH = 0.035
_ARROW_YS = (0.03, 0.14)  # below the tag's top

# The popup, anchored to the top right (only seen at 1920x1009).
TELEPORT = ui.UIPoint("right", -0.1209, 0.3231, "top")
CLOSE = ui.UIPoint("right", -0.0208, 0.3974, "top")
_PANEL = tuple(ui.UIPoint("right", x, y, "top") for x in (-0.1982, -0.0396) for y in (0.0991, 0.2775))
_TELEPORT_SIDE = 0.02


def _is_box(c: RGB) -> bool:
    return min(c) > 125 and max(c) - min(c) < 45


def _is_letter(c: RGB) -> bool:
    return max(c) - min(c) < 20 and 50 <= max(c) <= 140


def _is_black(c: RGB) -> bool:
    return max(c) < 50


def _is_colored(c: RGB) -> bool:
    return max(c) - min(c) > 70


def _is_arrow_colored(c: RGB) -> bool:
    r, g, b = c
    return (r > 180 and r - g > 80 and r - b > 120) or (b > 180 and b - r > 90)


def _is_panel_gray(c: RGB) -> bool:
    r, g, b = c
    return 140 < r < 215 and 0 <= b - r < 20 and abs(g - r) < 15


def _is_teleport_green(c: RGB) -> bool:
    r, g, b = c
    return g > 120 and g - r > 40 and g - b > 50


def _is_close_red(c: RGB) -> bool:
    r, g, b = c
    return r > 95 and r - g > 35 and r - b > 25


def _cells(width: int, height: int) -> list[tuple[float, float]]:
    """Every margin cell's middle and tag top, in pixels, in the order they're cycled."""
    unit = min(width, height)
    k_max = int(height / unit / CELL_STEP) + 2
    sides = [SIDE_TOP + CELL_STEP * k for k in range(-k_max, k_max + 1)]
    lowest = height / 2 / unit - BOTTOM_TOP - CELL_STEP / 2  # clear of the bottom row
    sides = [t for t in sides if -height / 2 / unit + 0.05 < t < lowest]
    left = [(SIDE_X * unit, height / 2 + t * unit) for t in sides]
    right = [(width - SIDE_X * unit, height / 2 + t * unit) for t in reversed(sides)]
    k_max = int(width / unit / CELL_STEP) + 1
    bottom = [(width / 2 + CELL_STEP * k * unit, height - BOTTOM_TOP * unit) for k in range(-k_max, k_max + 1)]
    bottom = [(x, y) for x, y in bottom if _BOTTOM_MIN_EDGE * unit <= x <= width - _BOTTOM_MIN_EDGE * unit]
    return left + bottom + right


def _is_facility_tag(width: int, height: int, get_pixel: PixelReader, cx: float, top: float) -> bool:
    unit = min(width, height)
    xs = range(round(cx - _HALF_WIDTH * unit), round(cx + _HALF_WIDTH * unit), 3)
    if xs.start < 0 or xs.stop > width or top - _ABOVE * unit < 0 or top + _LINE[1] * unit >= height:
        return False
    n = letters = 0
    box: list[RGB] = []
    for y in range(round(top + _LINE[0] * unit), round(top + _LINE[1] * unit), 3):
        for x in xs:
            c = get_pixel(x, y)
            if _is_black(c) or _is_colored(c):
                return False  # a cog's black name, or a building's, toon's or NPC's colors
            n += 1
            if _is_box(c):
                box.append(c)
            letters += _is_letter(c)
    if len(box) < 0.5 * n or letters < 0.25 * n:
        return False
    # An edge along its top: the scene above isn't the box's color (a light patch of
    # scene, or a bigger panel, would be). Light ground can be above (Lawbot HQ's).
    fill = tuple(sorted(c[i] for c in box)[len(box) // 2] for i in range(3))
    above = round(top - _ABOVE * unit)
    if sum(max(abs(a - b) for a, b in zip(get_pixel(x, above), fill)) < _EDGE_DIFF for x in xs) > 0.3 * len(xs):
        return False
    # Its arrow is gray, not a cog's orange (their names can fade to gray in a light place).
    xs = range(round(cx - _ARROW_HALF_WIDTH * unit), round(cx + _ARROW_HALF_WIDTH * unit), 3)
    ys = range(round(top + _ARROW_YS[0] * unit), min(height, round(top + _ARROW_YS[1] * unit)), 3)
    return not any(_is_arrow_colored(get_pixel(x, y)) for y in ys for x in xs)


def find_facility_tags(width: int, height: int, get_pixel: PixelReader) -> tuple[ui.UIPoint, ...]:
    """Where to click each facility's nametag in the margins, in the order they're cycled."""
    unit = min(width, height)
    return tuple(ui.UIPoint("center", (cx - width / 2) / unit, (top - height / 2) / unit + _CLICK_Y, "center")
                 for cx, top in _cells(width, height) if _is_facility_tag(width, height, get_pixel, cx, top))


def read_facility_popup(width: int, height: int, get_pixel: PixelReader) -> bool:
    """The popup from clicking a facility's nametag is up."""
    def at(p: ui.UIPoint, dx: float = 0.0, dy: float = 0.0) -> RGB:
        x, y = p.offset(dx, dy).to_client(width, height)
        return get_pixel(x, y) if 0 <= x < width and 0 <= y < height else (0, 0, 0)

    return (all(_is_panel_gray(at(p)) for p in _PANEL)
            and all(_is_teleport_green(at(TELEPORT, dx, dy))  # round (a cog's panel has a green bar)
                    for dx, dy in ((-_TELEPORT_SIDE, 0), (0, 0), (_TELEPORT_SIDE, 0), (0, -_TELEPORT_SIDE),
                                   (0, _TELEPORT_SIDE)))
            and sum(_is_close_red(at(CLOSE, dx)) for dx in (-0.004, 0.0, 0.004)) >= 2)


@dataclass(frozen=True)
class FacilityScreen:
    tags: tuple[ui.UIPoint, ...] = ()  # facility nametags in the margins
    popup: bool = False  # a facility's popup is up


def read_facility(width: int, height: int, get_pixel: PixelReader) -> FacilityScreen:
    return FacilityScreen(find_facility_tags(width, height, get_pixel),
                          read_facility_popup(width, height, get_pixel))


def default_facility_bindings() -> Bindings:
    return Bindings(press={"lb": "previous", "rb": "next", "a": "teleport", "b": "close"})


class FacilityMapper:
    def __init__(self, bindings: Bindings | None = None):
        self.bindings = bindings or default_facility_bindings()
        self._actions = ButtonActions(self.bindings, 0.5, is_oneshot=lambda action: True)
        self._last: ui.UIPoint | None = None  # the tag last clicked

    def buttons(self, screen: FacilityScreen) -> frozenset[str]:
        """With the popup up, all of them; otherwise just LB, to open the first."""
        if screen.popup:
            return frozenset(self.bindings.press)
        return frozenset(b for b, a in self.bindings.press.items() if a == "previous") if screen.tags else frozenset()

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)

    def _tag(self, screen: FacilityScreen, step: int) -> ui.UIPoint | None:
        if not screen.tags:
            return None
        if self._last is None:
            return screen.tags[0]
        here = min(range(len(screen.tags)),
                   key=lambda i: (screen.tags[i].x - self._last.x) ** 2 + (screen.tags[i].y - self._last.y) ** 2)
        return screen.tags[(here + step) % len(screen.tags)]

    def update(self, buttons: frozenset[str], now: float, screen: FacilityScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons, now)
        commands = []
        for action in fired:
            if not screen.popup:
                if action == "previous" and screen.tags:
                    self._last = screen.tags[0]
                    commands.append(PointerCommand("click", self._last, "facility nametag"))
                continue
            if action in ("previous", "next"):
                tag = self._tag(screen, -1 if action == "previous" else 1)
                if tag is not None:
                    self._last = tag
                    commands.append(PointerCommand("click", tag, f"{action} facility nametag"))
            elif action == "teleport":
                commands.append(PointerCommand("click", TELEPORT, "teleport here"))
            elif action == "close":
                commands.append(PointerCommand("click", CLOSE, "close facility popup"))
        return commands
