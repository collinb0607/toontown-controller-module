"""Battles: where TTR draws the battle screens, how to recognize them, and
controller navigation of the gag picker, target choice and trunk.

Every battle panel is centered on the window, so positions are offsets from
the center in units of the window's shorter side (see ui.py). Measured from
captures at 1920x1009, 1552x578, 1082x464, 1071x374 and tall 435x817, 316x652.

The highlight is the real mouse cursor parked on a button, so TTR shows its
own hover effect and gag info card.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from . import ui
from .bindings import Bindings, ButtonActions
from .dialog import find_ok_cancel

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]

TRACKS = ("Toon-Up", "Trap", "Lure", "Sound", "Throw", "Squirt", "Drop")
LEVELS = 7

_COL0, _COL_STEP = -0.3231, 0.0907
_ROW0, _ROW_STEP = -0.2195, 0.0674
# A spot on each cell's background, away from the gag icon and the count.
_CELL_BG = (-0.030, -0.017)


def _center(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "center")


def cell(row: int, col: int) -> ui.UIPoint:
    return _center(_COL0 + col * _COL_STEP, _ROW0 + row * _ROW_STEP)


# Highlight frame sizes (units of the window's shorter side), like the book's Gags page
# and Trunk: a gag button, and the trunk's items by the start of their names.
GAG_SIZE = (0.080, 0.057)
TRUNK_SIZES = (("tab ", (0.0912, 0.0912)), ("SOS card", (0.125, 0.162)), ("SOS filter", (0.1231, 0.0297)),
               ("filter ", (0.1187, 0.0286)), ("damage remote", (0.0824, 0.1209)),
               ("healing remote", (0.0824, 0.1209)),
               ("doodle trick", (0.0703, 0.0451)))  # the trick's blue button, the part that's clicked


# An SOS card is hovered on its CALL button; its frame goes around the whole card,
# whose center is this far from CALL (measured at 1920x1009).
SOS_CARD_CENTER = (0.0372, -0.0644)
# The orange arrow boxes on "which cog/toon?", the same size in both rows. A cog's is
# centered on its point; a toon's point (on the row through the arrows' shafts) is
# this far above its box's center.
TARGET_SIZE = (0.132, 0.075)
TOON_BOX_DY = 0.0144


def trunk_size(name: str) -> tuple[float, float] | None:
    return next((size for start, size in TRUNK_SIZES if name.startswith(start)), None)


PASS = _center(0.3717, 0.0510)
RUN = _center(0.4886, 0.0510)
TRUNK = _center(0.4311, 0.1620)
TARGET_BACK = _center(-0.3518, 0.0193)
WAITING_BACK = _center(-0.2131, 0.0332)
# The "Run all the way back to the playground?" dialog's OK and Cancel buttons.
RUN_YES = _center(-0.0555, 0.1200)
RUN_NO = _center(0.0541, 0.1200)

# Rows that hold one arrow button per cog (above) or per teammate (below) on the
# "which cog/toon?" screen. The toon row crosses the down arrows' shafts.
COG_ARROW_ROW = -0.0788
TOON_ARROW_ROW = 0.105
_ARROW_SCAN_HALF_WIDTH = 0.42

# Toon panels along the bottom, one per toon, each with a circle showing the gag
# that toon picked (or "?"). Their spacing depends only on how many toons there
# are and whether the window is wider than tall, not on its exact size.
_PANEL_SPACING = {True: {2: 0.254, 3: 0.276, 4: 0.251}, False: {2: 0.187, 3: 0.2055, 4: 0.187}}
_PANEL_MIDDLE = -0.0075
_PANEL_HALF_WIDTH = 0.088
_PANEL_MIN_COLUMNS = 7  # of 11
_CHOICE_OFFSET = 0.0415  # choice circle center, right of the panel center
_CHOICE_ROW = 0.412
_PANEL_ROWS = tuple(0.37 + 0.01 * i for i in range(11))

# Trunk tabs down its left side. Pink slips has no tab page: it goes straight to "which cog?".
TRUNK_TABS = (("SOS", -0.173), ("pink slips", -0.0788), ("remotes", 0.0253), ("doodle", 0.1244))
_TAB_X = -0.4955
_TAB_PROBES_X = (-0.448, -0.444)  # lighter blue behind the open tab
_SOS_CALL_XS = (-0.3251, -0.1893, -0.0535, 0.0823)  # the CALL button on each column of cards
_SOS_TOP, _SOS_BOTTOM = -0.18, 0.175  # the visible part of the scrolling card list
SOS_LIST = _center(-0.12, 0.0)
# The filter dropdown above the cards. Its options open downward from the button,
# the first ("All") right over it.
SOS_FILTERS = ("All", "Restock", "Toon-Up", "Trap", "Lure", "Sound", "Throw", "Squirt", "Drop", "Other")
SOS_FILTER = _center(0.154, -0.2116)
_FILTER_OPTION_X, _FILTER_STEP = 0.149, 0.0305
_FILTER_LIST_X = 0.20  # right of the option names
# Somewhere on the panel that does nothing: clicking off the open list closes it.
FILTER_CLOSE = _center(0.0, -0.21)
_FILTER_ITEM = "SOS filter"
FILTER_OPEN_SECONDS = 0.1  # for the list to open before clicking an option in it
# The yellow scrollbar knob, centered here at the top and bottom of its track.
_SOS_KNOB_X, _SOS_KNOB_TOP, _SOS_KNOB_BOTTOM = 0.2032, -0.16, 0.145
# A row of cards isn't a whole number of mouse wheel notches, so scroll most of the
# way, then a notch at a time until the next row is fully in view.
SOS_SCROLL_NOTCHES = 5
SOS_EXTRA_NOTCHES = 4
_SOS_ROW_STEP = 0.18
# The right stick turns the wheel a notch at a time over the cards, as in the book's
# Trunk; once they've stopped moving for this long, the card under the cursor is hovered.
SOS_STICK_SETTLE_SECONDS = 0.2
_REMOTE_XS = (-0.3053, -0.1982, -0.0912)
_REMOTE_ROWS = (("damage", -0.0837), ("healing", 0.1065))
_TRICK_ROW0, _TRICK_STEP, _TRICK_ROWS = -0.1829, 0.0551, 7
_TRICK_ICON_X, _TRICK_X = -0.062, -0.0377  # probe on the blue button, click its center


def is_panel_red(c: RGB) -> bool:
    return c[0] > 200 and c[0] - c[1] > 120 and c[0] - c[2] > 120


def is_label_yellow(c: RGB) -> bool:
    return c[0] > 210 and c[1] > 200 and c[2] < 110


def is_white(c: RGB) -> bool:
    return min(c) > 225


def is_usable_gag(c: RGB) -> bool:
    """Usable gag buttons are blue, bright cyan or silvery blue (level 7). Gags you
    can't use are dark gray, and locked ones show the track's own color."""
    r, g, b = c
    return b >= 125 and g >= 105 and b - r >= 40 and b - g >= 15


def is_trunk_blue(c: RGB) -> bool:
    r, g, b = c
    return 40 < r < 95 and 90 < g < 150 and 125 < b < 185 and b - r > 60


def _is_bright_blue(c: RGB) -> bool:
    """Usable remotes and doodle trick icons."""
    return c[2] > 190 and c[2] - c[0] > 100


def _is_list_blue(c: RGB) -> bool:
    """The open filter list."""
    return 205 < c[0] < 228 and 232 < c[1] < 252 and c[2] > 245


def _is_knob_yellow(c: RGB) -> bool:
    return c[0] > 220 and c[1] > 220 and c[2] < 130


def _is_call_red(c: RGB) -> bool:
    """A usable SOS card's CALL button (unavailable ones are pale pink)."""
    return c[0] > 200 and c[1] < 120 and c[2] < 120 and c[0] - c[1] > 100


def _is_panel_green(c: RGB) -> bool:
    """Toon panels are see-through, but stay greener than the street behind them."""
    r, g, b = c
    return g - r >= 20 and g - b >= 20 and g >= 100


def _is_question_teal(c: RGB) -> bool:
    """The "?" circle of a toon who hasn't picked a gag yet."""
    r, g, b = c
    return r < 100 and 90 < g < 170 and g - r > 50 and b - r > 15 and g - b > 15


def _is_arrow_orange(c: RGB) -> bool:
    return c[0] > 230 and 140 < c[1] < 215 and c[2] < 160


def _is_arrow_blue(c: RGB) -> bool:
    return c[2] > 200 and c[0] < 100 and c[1] < 130


# Screen detectors. The probes avoid text and icons.
# The trunk replaces the gag grid inside the same red panel. The notepad can't be
# used to spot it because hovering an item turns the notepad into an info card.
PICKER = ui.Button("gag picker", cell(0, 0),
                   tuple(_center(0.288, -0.21 + 0.045 * i) for i in range(10)), is_panel_red, min_hits=8)
TARGET = ui.Button("which cog/toon", TARGET_BACK,
                   tuple(_center(x, 0.02) for x in (-0.235, -0.22, -0.19, 0.19, 0.22, 0.235)),
                   is_label_yellow, min_hits=5)
WAITING = ui.Button("waiting for other toons", WAITING_BACK,
                    tuple(_center(x, y) for y in (-0.02, 0.088) for x in (-0.12, -0.05, 0.05, 0.12, 0.19)),
                    is_white, min_hits=8)


def _is_back_blue(c: RGB) -> bool:
    r, g, b = c
    return b > 150 and b - r > 90 and b - g > 50


# Its Back button's blue too: the trunk HUD's SOS cards are white at all of WAITING's
# spots (trunk_hud_bug), but its panel's blue is greyer.
WAITING_BACK_BLUE = ui.Button("waiting back button", WAITING_BACK,
                              tuple(WAITING_BACK.offset(dx, dy) for dx, dy in
                                    ((0, 0), (-0.02, 0), (0.02, 0), (0, -0.012), (0, 0.012))),
                              _is_back_blue, min_hits=4)
TRUNK_RED = ui.Button("trunk", TRUNK, tuple(_center(0.302, y) for y in (-0.2, -0.1, 0.0, 0.1, 0.2)),
                      is_panel_red, min_hits=5)
TRUNK_BLUE = ui.Button("trunk", TRUNK,
                       tuple(_center(-0.43, y) for y in (-0.125, -0.025, 0.075, 0.17))
                       + tuple(_center(x, 0.205) for x in (-0.3, -0.1, 0.1)),
                       is_trunk_blue, min_hits=6)


@dataclass(frozen=True)
class Item:
    """Something to highlight and click on a screen laid out freely, like the trunk."""
    name: str
    point: ui.UIPoint
    tab: bool = False


@dataclass(frozen=True)
class BattleScreen:
    kind: str | None = None  # "picker", "trunk", "target", "waiting", "confirm_run", or None when no battle panel shows
    usable: tuple[tuple[bool, ...], ...] = ()  # picker: [track][level]
    teammates: tuple[ui.UIPoint, ...] = ()  # picker, waiting: toons' gag choices, left to right
    unpicked: tuple[ui.UIPoint, ...] = ()  # picker, waiting: "?" circles of toons still choosing
    targets: tuple[ui.UIPoint, ...] = ()  # target: one arrow per cog (or toon), left to right
    tab: str | None = None  # trunk: the open tab
    items: tuple[Item, ...] = ()  # trunk: tabs, then what's usable on the open tab (or the filter options)
    filter_open: bool = False  # trunk: the SOS filter list is open
    can_scroll: tuple[bool, bool] = (False, False)  # trunk: the SOS list can scroll (up, down)
    close: ui.UIPoint | None = None  # picker: the red X at its top right (planting a gag tree, not a battle)


# Planting a gag tree in the garden shows the same gag panel, with a red X at its top
# right to close it (gardening_plant_gag_tree, 1920x1009). In battle that spot is the
# panel's dark red frame.
PICKER_CLOSE = _center(0.5629, -0.2740)


def _has_close(width: int, height: int, get_pixel: PixelReader) -> bool:
    x, y = PICKER_CLOSE.to_client(width, height)
    margin = round(0.014 * min(width, height))
    if not (margin <= x < width - margin and margin <= y < height - margin):
        return False  # off a narrow window's edge
    r, g, b = get_pixel(x, y)
    if not (r > 200 and min(g, b) > 150):  # the X's white middle
        return False
    ring = (get_pixel(*p.to_client(width, height)) for p in ui.around(PICKER_CLOSE, 0.013))
    return sum(c[0] > 170 and c[0] - c[1] > 80 for c in ring) >= 3


def _scan_arrows(width: int, height: int, get_pixel: PixelReader, row: float) -> list[ui.UIPoint]:
    """Find arrow buttons along a row: a run of blue with orange on both sides."""
    unit = min(width, height)
    y = round(height / 2 + row * unit)
    x0 = max(0, round(width / 2 - _ARROW_SCAN_HALF_WIDTH * unit))
    x1 = min(width - 1, round(width / 2 + _ARROW_SCAN_HALF_WIDTH * unit))
    outline = max(8, round(0.012 * unit))
    kinds = []
    for x in range(x0, x1 + 1):
        c = get_pixel(x, y)
        kinds.append("o" if _is_arrow_orange(c) else "b" if _is_arrow_blue(c) else ".")
    found = []
    i = 0
    while i < len(kinds):
        if kinds[i] != "b":
            i += 1
            continue
        start = i
        while i < len(kinds) and kinds[i] == "b":
            i += 1
        # The arrow has a dark outline a few pixels wide between the blue and the orange.
        before = kinds[max(0, start - outline):start]
        after = kinds[i:i + outline]
        if "o" in before and "o" in after and i - start >= 3:
            x = x0 + (start + i - 1) / 2
            found.append(_center((x - width / 2) / unit, row))
    return found


def panel_centers(count: int, wide: bool) -> list[float]:
    spacing = _PANEL_SPACING[wide][count]
    return [_PANEL_MIDDLE + (i - (count - 1) / 2) * spacing for i in range(count)]


def _has_panel(width: int, height: int, get_pixel: PixelReader, x: float) -> bool:
    """Check the left part of a toon panel (left of its choice circle) column by column.
    Nametags, faces and toons can cover some rows, so each column only needs a few,
    and a big face (a laff meter) can cover a few columns (battle_waiting_hover: 7 left)."""
    columns = 0
    for i in range(11):
        cx = x - _PANEL_HALF_WIDTH + 0.005 + 0.008 * i
        hits = sum(_is_panel_green(get_pixel(*_center(cx, y).to_client(width, height))) for y in _PANEL_ROWS)
        columns += hits >= 4
    return columns >= _PANEL_MIN_COLUMNS


def _read_choices(width: int, height: int, get_pixel: PixelReader) -> dict:
    """Choice circles of toons who have picked a gag, and of those still choosing ("?").
    Your own shows "?" while you pick, and your gag once you have."""
    wide = width >= height
    for count in (4, 3, 2):
        centers = panel_centers(count, wide)
        if not all(_has_panel(width, height, get_pixel, x) for x in centers):
            continue
        chosen, unpicked = [], []
        for x in centers:
            circle = _center(x + _CHOICE_OFFSET, _CHOICE_ROW)
            spots = [circle.offset(dx, dy) for dx, dy in ((0, 0), (-0.018, 0), (0.018, 0), (0, -0.018), (0, 0.018))]
            if sum(_is_question_teal(get_pixel(*p.to_client(width, height))) for p in spots) < 3:
                chosen.append(circle)
            else:
                unpicked.append(circle)
        return {"teammates": tuple(chosen), "unpicked": tuple(unpicked)}
    return {}


def _scan_calls(width: int, height: int, get_pixel: PixelReader, x: float) -> list[float]:
    """Rows of red CALL buttons down one column of SOS cards, fully in view. The
    lettering covers most of the red, and the solid edges are only a pixel or two
    thick, so every pixel row is checked at a few spots across the button."""
    unit = min(width, height)
    xs = sorted({round(width / 2 + (x + dx) * unit) for dx in (-0.02, -0.016, -0.012, -0.008, -0.004, 0.0, 0.004, 0.008, 0.012)})
    top, bottom = (round(height / 2 + y * unit) for y in (_SOS_TOP, _SOS_BOTTOM))
    gap = 0.015 * unit
    rows, run = [], []
    for py in range(top, bottom + 1):
        if any(_is_call_red(get_pixel(px, py)) for px in xs):
            if run and py - run[-1] > gap:
                rows.append(run)
                run = []
            run.append(py)
    if run:
        rows.append(run)
    # Skip buttons cut off at the edge of the list.
    return [((r[0] + r[-1]) / 2 - height / 2) / unit for r in rows
            if r[0] > top + 1 and r[-1] < bottom - 1 and r[-1] - r[0] >= 0.006 * unit]


def _read_knob(width: int, height: int, get_pixel: PixelReader) -> tuple[bool, bool]:
    """Whether the SOS list can scroll up and down, from where its knob sits.
    With no knob, everything fits and it can't scroll at all."""
    unit = min(width, height)
    px = round(width / 2 + _SOS_KNOB_X * unit)
    top, bottom = (round(height / 2 + y * unit) for y in (_SOS_TOP, _SOS_BOTTOM))
    knob = [py for py in range(top, bottom + 1) if _is_knob_yellow(get_pixel(px, py))]
    if not knob:
        return False, False
    middle = ((knob[0] + knob[-1]) / 2 - height / 2) / unit
    return middle > _SOS_KNOB_TOP, middle < _SOS_KNOB_BOTTOM


def _read_trunk(width: int, height: int, get_pixel: PixelReader) -> BattleScreen:
    def looks(point: ui.UIPoint, test) -> bool:
        return test(get_pixel(*point.to_client(width, height)))

    items = [Item(f"tab {name}", _center(_TAB_X, y), tab=True) for name, y in TRUNK_TABS]
    tab = next((name for name, y in TRUNK_TABS
                if all(looks(_center(x, y), is_trunk_blue) for x in _TAB_PROBES_X)), None)
    choices = _read_choices(width, height, get_pixel)
    if tab == "SOS":
        options = [_center(_FILTER_OPTION_X, SOS_FILTER.y + i * _FILTER_STEP) for i in range(len(SOS_FILTERS))]
        if sum(looks(_center(_FILTER_LIST_X, o.y), _is_list_blue) for o in options[1:9]) >= 6:
            items += [Item(f"filter {name}", o) for name, o in zip(SOS_FILTERS, options)]
            return BattleScreen("trunk", tab=tab, items=tuple(items), filter_open=True, **choices)
        for col, x in enumerate(_SOS_CALL_XS):
            items += [Item(f"SOS card {col + 1} at {y:.2f}", _center(x, y))
                      for y in _scan_calls(width, height, get_pixel, x)]
        items.append(Item(_FILTER_ITEM, SOS_FILTER))
        return BattleScreen("trunk", tab=tab, items=tuple(items),
                            can_scroll=_read_knob(width, height, get_pixel), **choices)
    elif tab == "remotes":
        for kind, y in _REMOTE_ROWS:
            items += [Item(f"{kind} remote {i + 1}", _center(x, y)) for i, x in enumerate(_REMOTE_XS)
                      if looks(_center(x - 0.032, y), _is_bright_blue)
                      and looks(_center(x - 0.032, y + 0.04), _is_bright_blue)]
    elif tab == "doodle":
        for i in range(_TRICK_ROWS):
            y = _TRICK_ROW0 + i * _TRICK_STEP
            if looks(_center(_TRICK_ICON_X, y), _is_bright_blue):
                items.append(Item(f"doodle trick {i + 1}", _center(_TRICK_X, y)))
    return BattleScreen("trunk", tab=tab, items=tuple(items), **choices)


def read_screen(width: int, height: int, get_pixel: PixelReader) -> BattleScreen:
    """Work out which battle screen is showing, and what's on it."""
    if ui.is_visible(PICKER, width, height, get_pixel):
        usable = tuple(
            tuple(is_usable_gag(get_pixel(*cell(r, c).offset(*_CELL_BG).to_client(width, height)))
                  for c in range(LEVELS))
            for r in range(len(TRACKS)))
        close = PICKER_CLOSE if _has_close(width, height, get_pixel) else None
        return BattleScreen("picker", usable=usable, close=close, **_read_choices(width, height, get_pixel))
    if ui.is_visible(TRUNK_RED, width, height, get_pixel) and ui.is_visible(TRUNK_BLUE, width, height, get_pixel):
        return _read_trunk(width, height, get_pixel)
    if ui.is_visible(TARGET, width, height, get_pixel):
        targets = (_scan_arrows(width, height, get_pixel, COG_ARROW_ROW)
                   or _scan_arrows(width, height, get_pixel, TOON_ARROW_ROW))
        return BattleScreen("target", targets=tuple(targets))
    if ui.is_visible(WAITING, width, height, get_pixel) and ui.is_visible(WAITING_BACK_BLUE, width, height, get_pixel):
        return BattleScreen("waiting", **_read_choices(width, height, get_pixel))
    # Other OK/Cancel dialogs (like the gag shop's) have their buttons lower down.
    buttons = find_ok_cancel(width, height, get_pixel)
    if buttons is not None and abs(buttons[0].y - RUN_YES.y) < 0.02:
        return BattleScreen("confirm_run")
    return BattleScreen()


# --- Navigation -------------------------------------------------------------

DIRECTIONS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}

BATTLE_ACTIONS = {
    "up": "move the highlight up", "down": "move the highlight down",
    "left": "move the highlight left", "right": "move the highlight right",
    "select": "click the highlighted gag, target or trunk item, or OK when asked if you want to run",
    "back": "go back (on the target, waiting and trunk screens), or cancel running",
    "run": "run from the battle", "trunk": "open or close the trunk", "pass": "pass this turn",
    "teammates": "switch between your gags and hovering teammates' gag choices (left/right to pick one)",
    "sos_filter": "show the next kind of SOS card (All, Restock, Toon-Up, ...)",
    "sos_scroll_up": "scroll the SOS cards up", "sos_scroll_down": "scroll the SOS cards down",
}


def default_battle_bindings() -> Bindings:
    press = {"a": "select", "b": "back", "x": "trunk", "y": "pass", "lb": "teammates", "ls": "sos_filter",
             "rs_up": "sos_scroll_up", "rs_down": "sos_scroll_down"}
    for direction in DIRECTIONS:
        press[f"dpad_{direction}"] = direction
        press[f"ls_{direction}"] = direction
    return Bindings(press=press, hold={"b": "run"})


def move(usable, pos: tuple[int, int], direction: str) -> tuple[int, int]:
    """Step to the next usable gag in a direction, skipping unusable and locked ones."""
    r, c = pos
    dr, dc = DIRECTIONS[direction]
    if dc:
        cc = c + dc
        while 0 <= cc < LEVELS:
            if usable[r][cc]:
                return r, cc
            cc += dc
        return pos
    rr = r + dr
    while 0 <= rr < len(usable):
        options = [cc for cc in range(LEVELS) if usable[rr][cc]]
        if options:
            # Closest level in that track; on a tie, the stronger gag.
            return rr, min(options, key=lambda cc: (abs(cc - c), -cc))
        rr += dr
    return pos


_STEPS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def step(items, current: ui.UIPoint, direction: str):
    """The closest item in a direction, favoring ones straight ahead."""
    dx, dy = _STEPS[direction]
    best, best_cost = None, None
    for item in items:
        ax, ay = item.point.x - current.x, item.point.y - current.y
        along = ax * dx + ay * dy
        if along <= 0.01:
            continue
        cost = along + 2 * (abs(ax * dy) + abs(ay * dx))
        if best_cost is None or cost < best_cost:
            best, best_cost = item, cost
    return best


def _distance(a: ui.UIPoint, b: ui.UIPoint) -> float:
    return abs(a.x - b.x) + abs(a.y - b.y)


def nearest_usable(usable, pos: tuple[int, int]) -> tuple[int, int] | None:
    r, c = pos
    cells = [(rr, cc) for rr in range(len(usable)) for cc in range(LEVELS) if usable[rr][cc]]
    if not cells:
        return None
    # Prefer staying in the same track, then the closest level, then the stronger gag.
    return min(cells, key=lambda p: (abs(p[0] - r) * 10 + abs(p[1] - c), -p[1]))


@dataclass(frozen=True)
class PointerCommand:
    kind: str  # "hover" (park the cursor), "click", or "scroll" (turn the wheel there)
    point: ui.UIPoint
    name: str
    notches: int = 0  # scroll: positive is up
    delay: float = 0.0  # click: seconds to wait after the previous command
    # hover: the item's width and height (units of the window's shorter side), for
    # the highlight frame drawn around it. None draws no frame.
    size: tuple[float, float] | None = None
    frame_at: ui.UIPoint | None = None  # hover: draw the frame here instead of around the point
    color: tuple[int, int, int] | None = None  # hover: the frame's color (None: the usual gold)
    to: ui.UIPoint | None = None  # drag: press at point, move here, let go


@dataclass
class BattleTiming:
    hold_seconds: float = 0.5
    # After a click, ignore input until the next screen has had time to appear.
    settle_seconds: float = 0.25


# Where the highlight starts before any gag has been picked: the middle of Throw.
DEFAULT_GAG = (4, 3)


@dataclass
class BattleMapper:
    bindings: Bindings = field(default_factory=default_battle_bindings)
    timing: BattleTiming = field(default_factory=BattleTiming)

    def __post_init__(self):
        self.set_bindings(self.bindings)
        # Remembered across rounds and battles.
        self.gag: tuple[int, int] = DEFAULT_GAG
        self.target_index = 0
        self.trunk_item: Item | None = None
        self.sos_filter = 0  # index into SOS_FILTERS, as last picked through the module
        self._filtered = False  # just picked a filter: start on the first card
        self.teammate: int | None = None  # which teammate's choice is hovered, if any
        # "?" circles seen while picking: one of them is yours.
        self._maybe_mine: frozenset[ui.UIPoint] = frozenset()
        self._mine: ui.UIPoint | None = None
        # The target arrows seen on this "which cog/toon?" screen. The hovered arrow
        # lights up and can drop out of a read, so a shorter read is ignored.
        self._targets: tuple[ui.UIPoint, ...] = ()
        # While scrolling the SOS list: (+1 up / -1 down, where the highlight was, extra notches left).
        self._scrolling: tuple[int, ui.UIPoint, int] | None = None
        # After a right stick scroll: when, and where the wheel was turned.
        self._stick_scrolled: tuple[float, ui.UIPoint] | None = None
        self._kind: str | None = None
        self._settle_until = 0.0

    def set_bindings(self, bindings: Bindings) -> None:
        self.bindings = bindings
        self._actions = ButtonActions(bindings, self.timing.hold_seconds,
                                      is_oneshot=lambda action: True,
                                      repeats=lambda action: action in DIRECTIONS
                                      or action in ("sos_scroll_up", "sos_scroll_down"))

    @property
    def buttons(self) -> set[str]:
        return self.bindings.buttons()

    def reset_buttons(self) -> None:
        # A button still held when battle input picks up again (like B from a run
        # hold) needs a fresh press.
        self._actions.reset(ignore_held=True)

    def rehover(self) -> None:
        """Put the highlight back on the screen's usual spot, e.g. after speedchat moved the cursor."""
        self._kind = None

    def update(self, buttons: frozenset[str], now: float, screen: BattleScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons & self.buttons, now)
        if screen.kind == "picker":
            self._maybe_mine = frozenset(screen.unpicked)
            self._mine = None
        elif screen.kind == "waiting" and self._mine is None:
            changed = [p for p in screen.teammates if p in self._maybe_mine]
            if len(changed) == 1:
                # Remembered, so it's still skipped after teammates pick too.
                self._mine = changed[0]
        if now < self._settle_until:
            # Right after a click the old screen may still show; wait for the next one.
            return []

        commands: list[PointerCommand] = []
        if screen.kind != self._kind:
            self._kind = screen.kind
            commands += self._on_appear(screen, now)
        if screen.kind == "trunk" and self._filtered and not screen.filter_open and not commands:
            # The list closed after picking a filter (it can still be open at first).
            commands += self._appear_trunk(screen, now)
        if screen.kind == "target" and len(screen.targets) > len(self._targets):
            self._targets = screen.targets
        if screen.kind == "waiting" and self.teammate is None and self._others(screen):
            # Nothing to pick while waiting, so look at what teammates picked
            # (also once the first of them picks).
            self.teammate = 0
            commands.append(self._hover_teammate(screen))
        if screen.kind != "trunk":
            self._stick_scrolled = None
        elif self._stick_scrolled is not None and now - self._stick_scrolled[0] >= SOS_STICK_SETTLE_SECONDS:
            commands += self._hover_card_at(screen, self._stick_scrolled[1])
            self._stick_scrolled = None
        for action in fired:
            commands += self._run(action, screen, now)
        return commands

    def _others(self, screen: BattleScreen) -> tuple[ui.UIPoint, ...]:
        """Teammates' choices to hover. While waiting, your own circle shows your gag
        too: it's the one "?" from the picker that changed first, if only one did."""
        if screen.kind != "waiting":
            return screen.teammates
        return tuple(p for p in screen.teammates if p != self._mine)

    def _on_appear(self, screen: BattleScreen, now: float) -> list[PointerCommand]:
        if self._scrolling is not None:
            if screen.kind == "trunk":
                return self._after_scroll(screen, now)
            self._scrolling = None
        if screen.kind == "trunk":
            return self._appear_trunk(screen, now)
        if screen.kind in ("picker", "waiting"):
            self.teammate = None
        if screen.kind == "picker":
            pos = nearest_usable(screen.usable, self.gag)
            if pos is None:
                return []
            self.gag = pos
            return [self._hover_gag()]
        if screen.kind == "confirm_run":
            # B held from the run hold mustn't cancel when it's let go: only a new press does.
            self._actions.ignore_held()
            return [PointerCommand("hover", RUN_YES, "run: yes")]
        if screen.kind == "target":
            self._targets = screen.targets
            if screen.targets:
                self.target_index = min(self.target_index, len(screen.targets) - 1)
                return [self._hover_target()]
        return []

    def _appear_trunk(self, screen: BattleScreen, now: float) -> list[PointerCommand]:
        self.teammate = None
        if screen.filter_open:
            if self._filtered:
                return []  # a filter was just clicked: wait for the list to close
            return self._hover_trunk(self._filter_option(screen, self.sos_filter))
        content = [i for i in screen.items if not i.tab]
        last = self.trunk_item
        if self._filtered:
            # After picking a filter: the first card, or the dropdown if none match.
            self._filtered = False
            return self._hover_trunk(content[0]) if content else []
        if last is not None and last.name.startswith("filter "):
            last = next((i for i in content if i.name == _FILTER_ITEM), None)
        if last is not None and last.tab:
            # After switching tabs, stay on the tab list.
            item = next((i for i in screen.items if i.name == last.name), None)
        elif last is not None and content:
            item = min(content, key=lambda i: _distance(i.point, last.point))
        else:
            item = content[0] if content else next(
                (i for i in screen.items if i.name == f"tab {screen.tab}"), None)
        return self._hover_trunk(item) if item else []

    def _scroll(self, direction: int, notches: int, now: float) -> list[PointerCommand]:
        self._settle_until = now + self.timing.settle_seconds
        self._kind = None
        return [PointerCommand("scroll", SOS_LIST, "SOS list", direction * notches)]

    def _after_scroll(self, screen: BattleScreen, now: float) -> list[PointerCommand]:
        direction, origin, extra = self._scrolling
        # The first scroll moves the highlighted card's row most of a row away, so a
        # card near or past where it was is the row that was hidden. If nothing
        # moved (the end of the list), that's the same card, and scrolling stops.
        cards = [i for i in screen.items if not i.tab and i.name != _FILTER_ITEM
                 and (i.point.y < origin.y + _SOS_ROW_STEP / 4 if direction > 0
                      else i.point.y > origin.y - _SOS_ROW_STEP / 4)]
        if not cards and extra > 0:
            self._scrolling = (direction, origin, extra - 1)
            return self._scroll(direction, 1, now)
        self._scrolling = None
        if not cards:
            # The end of the list (or a row with no usable cards).
            return self._appear_trunk(screen, now)
        return self._hover_trunk(min(cards, key=lambda i: _distance(i.point, origin)))

    def _stick_scroll(self, screen: BattleScreen, up: bool, now: float) -> list[PointerCommand]:
        """A wheel notch over the SOS cards, where the hovered card is (so the cursor
        stays on the list), or the middle of the list."""
        if screen.tab != "SOS" or screen.filter_open or not screen.can_scroll[0 if up else 1]:
            return []
        item = self.trunk_item
        point = item.point if item is not None and item.name.startswith("SOS card") else SOS_LIST
        self._stick_scrolled = (now, point)
        return [PointerCommand("scroll", point, "scroll SOS cards", 1 if up else -1)]

    def _hover_card_at(self, screen: BattleScreen, point: ui.UIPoint) -> list[PointerCommand]:
        """Hover the card nearest a point: after scrolling, the one under the cursor."""
        cards = [i for i in screen.items if i.name.startswith("SOS card")]
        if not cards:
            return []
        return self._hover_trunk(min(cards, key=lambda i: _distance(i.point, point)))

    def _filter_option(self, screen: BattleScreen, index: int) -> Item:
        return next(i for i in screen.items if i.name == f"filter {SOS_FILTERS[index]}")

    def _pick_filter(self, screen: BattleScreen, index: int, now: float) -> list[PointerCommand]:
        self.sos_filter = index
        self._filtered = True
        option = self._filter_option(screen, index)
        return self._click(option.point, option.name, now)

    def _hover_trunk(self, item: Item) -> list[PointerCommand]:
        self.trunk_item = item
        frame_at = item.point.offset(*SOS_CARD_CENTER) if item.name.startswith("SOS card") else None
        return [PointerCommand("hover", item.point, item.name, size=trunk_size(item.name), frame_at=frame_at)]

    def _trunk_move(self, screen: BattleScreen, direction: str, now: float) -> list[PointerCommand]:
        current = self.trunk_item
        if current is None:
            return self._appear_trunk(screen, now)
        if screen.filter_open:
            if direction not in ("up", "down"):
                return []
            item = step(screen.items, current.point, direction)
            return self._hover_trunk(item) if item else []
        # The hovered item may light up and drop out of a read; step from where it was anyway.
        if direction in ("up", "down"):
            # Up and down stay within the tab list or within the cards; the
            # dropdown is above the top card once the list can't scroll up.
            pool = [i for i in screen.items if i.tab == current.tab and i.name != _FILTER_ITEM]
        else:
            pool = list(screen.items)
        item = step(pool, current.point, direction)
        if item is not None:
            return self._hover_trunk(item)
        if screen.tab != "SOS" or current.tab or direction not in ("up", "down"):
            return []
        sign = 1 if direction == "up" else -1
        if current.name != _FILTER_ITEM and screen.can_scroll[0 if sign > 0 else 1]:
            # Past the top or bottom of the visible cards: scroll the next row into view.
            self._scrolling = (sign, current.point, SOS_EXTRA_NOTCHES)
            return self._scroll(sign, SOS_SCROLL_NOTCHES, now)
        if sign > 0 and current.name != _FILTER_ITEM:
            return self._hover_trunk(next(i for i in screen.items if i.name == _FILTER_ITEM))
        return []

    def _hover_teammate(self, screen: BattleScreen) -> PointerCommand:
        others = self._others(screen)
        self.teammate = min(self.teammate, len(others) - 1)
        return PointerCommand("hover", others[self.teammate], f"teammate gag {self.teammate + 1}")

    def _move_teammate(self, screen: BattleScreen, action: str) -> list[PointerCommand]:
        if action not in ("left", "right") or not self._others(screen):
            return []
        if self.teammate is None:
            self.teammate = 0
        else:
            step = -1 if action == "left" else 1
            self.teammate = max(0, min(len(self._others(screen)) - 1, self.teammate + step))
        return [self._hover_teammate(screen)]

    def _hover_target(self) -> PointerCommand:
        self.target_index = min(self.target_index, len(self._targets) - 1)
        point = self._targets[self.target_index]
        frame_at = point.offset(0, TOON_BOX_DY) if abs(point.y - TOON_ARROW_ROW) < 0.01 else None
        return PointerCommand("hover", point, f"target {self.target_index + 1}", size=TARGET_SIZE, frame_at=frame_at)

    def _hover_gag(self) -> PointerCommand:
        r, c = self.gag
        return PointerCommand("hover", cell(r, c), f"{TRACKS[r]} level {c + 1}", size=GAG_SIZE)

    def _click(self, point: ui.UIPoint, name: str, now: float) -> list[PointerCommand]:
        self._settle_until = now + self.timing.settle_seconds
        # Forget the screen so whatever appears next (even the same kind) is set up fresh.
        self._kind = None
        return [PointerCommand("click", point, name)]

    def _run(self, action: str, screen: BattleScreen, now: float) -> list[PointerCommand]:
        if screen.kind == "picker":
            if screen.close is not None and action in ("back", "run"):
                return self._click(screen.close, "close", now)  # the gag tree's picker: no running
            if self.teammate is not None:
                # Hovering teammates' choices: left/right pick one; the teammates
                # button, A or B go back to your own gags.
                if action in ("teammates", "select", "back") or not screen.teammates:
                    self.teammate = None
                    return [self._hover_gag()]
                return self._move_teammate(screen, action)
            if action == "teammates":
                if not screen.teammates:
                    return []
                self.teammate = 0
                return [self._hover_teammate(screen)]
            if action in DIRECTIONS:
                self.gag = move(screen.usable, self.gag, action)
                return [self._hover_gag()]
            elif action == "select":
                # No usable check: the highlight only ever lands on usable gags, and the
                # hovered gag can look different from what the reader expects.
                r, c = self.gag
                return self._click(cell(r, c), f"{TRACKS[r]} level {c + 1}", now)
            elif action == "run":
                return self._click(RUN, "run", now)
            elif action == "trunk":
                return self._click(TRUNK, "trunk", now)
            elif action == "pass":
                return self._click(PASS, "pass", now)
        elif screen.kind == "target":
            if action in ("left", "right") and self._targets:
                # Wraps around at either end.
                step = -1 if action == "left" else 1
                self.target_index = (self.target_index + step) % len(self._targets)
                return [self._hover_target()]
            if action == "select" and self._targets:
                self.target_index = min(self.target_index, len(self._targets) - 1)
                return self._click(self._targets[self.target_index], f"target {self.target_index + 1}", now)
            if action in ("back", "run"):
                return self._click(TARGET_BACK, "back", now)
        elif screen.kind == "trunk":
            if self.teammate is not None:
                # Hovering teammates' choices, as in the gag picker.
                if action in ("teammates", "select", "back") or not screen.teammates:
                    self.teammate = None
                    item = self.trunk_item
                    return self._hover_trunk(item) if item else []
                return self._move_teammate(screen, action)
            if action == "teammates" and not screen.filter_open:
                if not screen.teammates:
                    return []
                self.teammate = 0
                return [self._hover_teammate(screen)]
            if screen.filter_open:
                if action == "select" and self.trunk_item is not None and self.trunk_item.name.startswith("filter "):
                    return self._pick_filter(screen, SOS_FILTERS.index(self.trunk_item.name[7:]), now)
                if action == "sos_filter":
                    return self._pick_filter(screen, (self.sos_filter + 1) % len(SOS_FILTERS), now)
                if action in ("back", "run"):
                    # Leave the filter as it was and go back to the dropdown.
                    self.trunk_item = Item(_FILTER_ITEM, SOS_FILTER)
                    return self._click(FILTER_CLOSE, "close filter list", now)
                if action in DIRECTIONS:
                    return self._trunk_move(screen, action, now)
                return []
            if action == "sos_filter" and screen.tab == "SOS":
                # The options always open in the same place, so click the next one
                # right after opening the list, without waiting to see it.
                self.sos_filter = (self.sos_filter + 1) % len(SOS_FILTERS)
                self._filtered = True
                option = _center(_FILTER_OPTION_X, SOS_FILTER.y + self.sos_filter * _FILTER_STEP)
                commands = self._click(SOS_FILTER, "SOS filter", now) + [
                    PointerCommand("click", option, f"filter {SOS_FILTERS[self.sos_filter]}", delay=FILTER_OPEN_SECONDS)]
                # Don't look until both clicks are done.
                self._settle_until += FILTER_OPEN_SECONDS + 0.1
                return commands
            if action in DIRECTIONS:
                return self._trunk_move(screen, action, now)
            if action in ("sos_scroll_up", "sos_scroll_down"):
                return self._stick_scroll(screen, action == "sos_scroll_up", now)
            if action == "select" and self.trunk_item is not None:
                return self._click(self.trunk_item.point, self.trunk_item.name, now)
            if action == "pass":
                return self._click(PASS, "pass", now)
            if action in ("back", "run", "trunk"):
                # The trunk button closes the trunk too.
                return self._click(TRUNK, "close trunk", now)
        elif screen.kind == "confirm_run":
            if action == "select":
                return self._click(RUN_YES, "run: yes", now)
            if action == "back":
                return self._click(RUN_NO, "run: no", now)
        elif screen.kind == "waiting":
            if action in ("back", "run"):
                return self._click(WAITING_BACK, "back", now)
            return self._move_teammate(screen, action)
        return []
