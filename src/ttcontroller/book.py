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
- Districts: a list of districts, each with a colored dot on its right. It opens
  with your current district (green name) chosen; clicking another chooses it
  (orange name) and lights up Teleport Here!. A SpeedChat-only district asks to
  confirm with an OK/Cancel dialog.
- Map: each place shows "Go To <place>" when hovered and teleports when clicked
  (if you have its teleport access). Places you haven't found yet are under
  clouds, and hovering them does nothing. Go Home and Back to Playground buttons
  sit below the map, each missing while you're already there.
- Gags: the Gags tab is a grid of the gags you have, one track a row, to hover for
  their info (nothing to click). The Trunk tab is the battle's trunk, shrunk and
  moved (see _TRUNK_SCALE), except SOS cards have no Call button.
- ToonTasks: up to four task scrolls, two by two; a blank scroll has no task.
  Hovering a scroll lifts it a little and shows its reward. A task you can drop
  has a trash can in its top right, which asks to confirm with an OK/Cancel dialog.
- Resistance Rank: just to look at, a few pages of it turned by the small blue
  arrows either side of "Page 1/4" at the bottom.
- Cog Gallery: a grid of cogs, a suit a row, with that suit's icon (tie, gavel,
  dollar sign, bar graph) down the left to show its buildings. A cog you can
  summon has a small blue button in its bottom right, which opens Issue a Cog
  Summons over the dimmed book: one to three summon buttons and a close X.
  Picking one asks to confirm (a Yes/No dialog over it); once confirmed, the same
  popup shows a message instead of buttons, closed with its X.
- Fishing: three tabs. Bucket lists your fish ten at a time, with triangles above
  and below to scroll it (the wheel doesn't); clicking one shows it, and it opens
  on the top one. The tiny red X in the bottom left of the fish shown releases it,
  after an OK/Cancel confirm.
- Racing: Customize (the kart, turned with LEFT and RIGHT buttons, and a row of
  accessory icons at the bottom), Records (just to look at) and Trophy. Golf has
  Records and Trophy (its Records scroll, with triangles above and below). A Trophy tab is 30 small trophies, ten by three, and three
  big ones below; one not earned yet is a gray card with a "?" (nothing to hover),
  and hovering an earned one tints it yellow and shows what it took.
- Cog Disguise: a tab per suit down its right side, written sideways (Bossbot,
  Lawbot, Cashbot, Sellbot); the current one's lettering is red. Some suits have
  blue arrows either side of their name plate to flip between versions.
- Gardening: four tabs. Basket is like Fishing's Bucket (smaller lettering, so more
  rows, and its red X is on the card's right). Album lists up to eight flower names
  beside the one shown, each clickable (blue while hovered, yellow as it's picked;
  a "????" in green isn't collected), with triangles above and below flipping to
  the next genus. Trophies and Specials are just to look at.
- Snapshots: the list of snapshots on the left, the one shown on the right with blue
  arrows either side of its name to flip through them, and a trash can beside Add
  Caption. Deleting asks in a yellow Yep!/Cancel panel over the bottom right of the
  book (the book isn't dimmed, and it hides the lower page tabs).
- Events: tabs Calendar, Hosting and Invitations. The Calendar is a month of days,
  seven by six (days outside the month gray, today yellow), each with its number in
  blue at the top and its events below, one line each (a long title without a time
  can wrap onto a second). Hovering an event's text pops up what it is. Blue arrows
  either side of the month's name change month, and triangles above and below the
  filter in the top right (Show All...) change it.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, replace

from . import ui
from .battle import DIRECTIONS as BATTLE_DIRECTIONS
from .battle import _REMOTE_ROWS, _REMOTE_XS, BattleMapper, BattleScreen, Item, PointerCommand, _read_trunk, move
from .battle import trunk_size as _battle_trunk_size
from .bindings import Bindings, ButtonActions
from .dialog import find_ok_cancel
from .held_scroll import HeldScroll

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


def _is_dot(c: RGB) -> bool:
    return max(c) - min(c) > 80


def _is_chosen_orange(c: RGB) -> bool:
    return c[0] > 200 and 120 < c[1] < 200 and c[2] < 160


def _is_current_green(c: RGB) -> bool:
    return c[1] > 170 and c[0] < 170 and c[2] < 170


def _is_cloud(c: RGB) -> bool:
    return min(c) > 195 and c[2] >= c[0] - 5 and max(c) - min(c) < 60


def _is_button_yellow(c: RGB) -> bool:
    return c[0] > 200 and c[1] > 200 and c[2] < 80


def _read_map(width: int, height: int, get_pixel: PixelReader) -> tuple[tuple[tuple[str, ui.UIPoint], ...],
                                                                        bool, bool]:
    def shows(probes) -> bool:
        return all(_is_button_yellow(get_pixel(*p.to_client(width, height))) for p in probes)

    places = tuple((name, point) for name, point in MAP_PLACES
                   if sum(_is_cloud(get_pixel(*point.offset(dx, dy).to_client(width, height)))
                          for dx, dy in _CLOUD_SAMPLES) < _CLOUD_MIN)
    return places, shows(_GO_HOME_PROBES), shows(_PLAYGROUND_PROBES)


def _read_trophies(width: int, height: int, get_pixel: PixelReader) -> tuple[int, ...]:
    """The trophies earned: their card is white (pale yellow while hovered), not gray."""
    def earned(point: ui.UIPoint) -> bool:
        c = get_pixel(*point.offset(*_TROPHY_CARD).to_client(width, height))
        return c[0] > 235 and c[1] > 235

    return tuple(i for i, point in enumerate(TROPHIES) if earned(point))


def _accessory(i: int) -> ui.UIPoint:
    return _center(_ACCESSORY_X0 + _ACCESSORY_STEP * i, _ACCESSORY_Y)


def fish_row(i: int) -> ui.UIPoint:
    return _center(_FISH_X, _FISH_Y0 + _FISH_STEP * i)


def flower_row(i: int) -> ui.UIPoint:
    return _center(_FISH_X, _FLOWER_Y0 + _FLOWER_STEP * i)


def album_flower(i: int) -> ui.UIPoint:
    return _center(_ALBUM_FLOWER_X, _ALBUM_FLOWER_Y0 + _ALBUM_FLOWER_STEP * i)


def _read_album_flowers(width: int, height: int, get_pixel: PixelReader) -> tuple[ui.UIPoint, ...]:
    """The Flower Album's collected names, top to bottom (dark lettering; a green "????"
    is one not collected)."""
    rows = []
    for i in range(ALBUM_FLOWERS):
        y = _ALBUM_FLOWER_Y0 + _ALBUM_FLOWER_STEP * i
        ink = sum(max(get_pixel(*_center(x, y + dy).to_client(width, height))) < 90
                  for x in _ALBUM_INK_XS for dy in (-0.004, 0.0, 0.004))
        if ink >= 3:
            rows.append(album_flower(i))
    return tuple(rows)


def _is_fish_lettering(c: RGB) -> bool:
    return max(c) < 90 or (c[1] > c[0] + 30 and c[1] > c[2] + 30)


def _read_fish(width: int, height: int, get_pixel: PixelReader, page: str = "fishing") -> tuple[ui.UIPoint, ...]:
    """The fish (or flower) names showing in the Bucket (or Basket), top to bottom (a row
    with lettering: dark, or green for the one picked)."""
    row_at, rows_max = (fish_row, FISH_ROWS) if page == "fishing" else (flower_row, FLOWER_ROWS)
    rows = []
    for i in range(rows_max):
        point = row_at(i)
        ink = sum(_is_fish_lettering(get_pixel(*_center(x, point.y + dy).to_client(width, height)))
                  for x in _FISH_INK_XS for dy in (-0.003, 0.0, 0.003))
        if ink < 3:
            break
        rows.append(point)
    return tuple(rows)


def cog_cell(col: int, row: int) -> ui.UIPoint:
    return _center(_COG_X0 + _COG_STEP_X * col, _COG_Y0 + _COG_STEP_Y * row)


def summon_button(cog: tuple[int, int]) -> ui.UIPoint:
    return cog_cell(*cog).offset(*SUMMON_OFFSET)


def _read_disguise(width: int, height: int, get_pixel: PixelReader) -> tuple[int | None, tuple[str, ...]]:
    """Cog Disguise's current suit (the tab with red lettering) and its arrows showing."""
    reds = [sum(_is_red_ink(get_pixel(*tab.offset(x - tab.x, dy).to_client(width, height)))
                for x in _SUIT_INK_XS for dy in _SUIT_INK_DYS) for tab in SUIT_TABS]
    current = max(range(len(reds)), key=reds.__getitem__) if max(reds) >= 5 else None
    arrows = tuple(side for side, p in DISGUISE_ARROWS.items()
                   if _is_arrow_blue(get_pixel(*p.to_client(width, height))))
    return current, arrows


@dataclass(frozen=True)
class Calendar:
    events: tuple[tuple[int, ...], ...]  # each day's events (left to right, top to bottom): their first lines
    today: int | None = None  # the yellow day
    first: int | None = None  # the shown month's first day (the first not gray)
    months: tuple[str, ...] = ()  # the month arrows showing ("stickLeft", "stickRight")
    filter_up: bool = False  # the filter's triangles that work
    filter_down: bool = False


def calendar_day(i: int) -> ui.UIPoint:
    """Day i's number (left to right, top to bottom)."""
    return _center(_DAY_X0 + _DAY_STEP_X * (i % CALENDAR_COLS), _DAY_Y0 + _DAY_STEP_Y * (i // CALENDAR_COLS))


def calendar_event(i: int, line: int) -> ui.UIPoint:
    """Where to hover day i's event starting on that line."""
    return calendar_day(i).offset(_EVENT_HOVER_DX, _EVENT_DY0 + _EVENT_STEP * line)


def _is_dark(c: RGB) -> bool:
    return max(c) < 90


def _read_calendar(width: int, height: int, get_pixel: PixelReader) -> Calendar:
    unit = min(width, height)
    events, today, first = [], None, None
    for i in range(CALENDAR_COLS * CALENDAR_ROWS):
        fill = [get_pixel(*calendar_day(i).offset(dx, 0.08).to_client(width, height)) for dx in (-0.045, 0.0, 0.045)]
        if sum(c[0] > 230 and c[1] > 200 and c[2] < 80 for c in fill) >= 2:
            today = i
        gray = sum(170 < min(c) and max(c) < 205 for c in fill) >= 2
        if first is None and not gray:
            first = i
        lines = []
        for line in range(CALENDAR_LINES):
            found = _read_event_line(width, height, get_pixel, i, line, unit)
            if found is None:
                break
            lines.append(found)
        events.append(_group_lines(width, height, get_pixel, i, lines, unit))
    months = tuple(side for side, p in MONTH_ARROWS.items()
                   if _is_arrow_blue(get_pixel(*p.to_client(width, height))))
    up, down = (_is_triangle_on(get_pixel(*p.to_client(width, height))) for p in (FILTER_UP, FILTER_DOWN))
    return Calendar(tuple(events), today, first, months, up, down)


def _is_triangle_on(c: RGB) -> bool:
    return c[2] - c[0] > 60


def _read_event_line(width, height, get_pixel, day: int, line: int, unit: int) -> tuple[int, int, int] | None:
    """A line of a day's text: where it starts and ends, and where its first word ends
    (in client pixels), or None if it's blank."""
    number = calendar_day(day)
    y = number.offset(0, _EVENT_DY0 + _EVENT_STEP * line).to_client(width, height)[1]
    left = number.offset(_DAY_LEFT, 0).to_client(width, height)[0]
    right = number.offset(_DAY_RIGHT, 0).to_client(width, height)[0]
    dys = (-round(0.003 * unit), 0, round(0.003 * unit))
    ink = [any(_is_dark(get_pixel(x, y + dy)) for dy in dys) for x in range(left, right)]
    if sum(ink) < 3:
        return None
    start = ink.index(True)
    end = len(ink) - 1 - ink[::-1].index(True)
    gap, word_end, blank = round(0.004 * unit), end, 0
    for x in range(start, end + 1):
        blank = 0 if ink[x] else blank + 1
        if blank >= gap:
            word_end = x - blank
            break
    return left + start, left + end, left + word_end


def _group_lines(width, height, get_pixel, day: int, lines, unit: int) -> tuple[int, ...]:
    """Each event's first line: a line carries on the one above (a wrapped title) when
    both stop short of the edge (a line too long to fit is cut off at it, like the
    timed ones, "12:00 AM End-Fri...") and this line's first word wouldn't have fit
    after the one above."""
    if len(lines) < 2:
        return tuple(range(len(lines)))
    left = calendar_day(day).offset(_DAY_LEFT, 0).to_client(width, height)[0]
    right = calendar_day(day).offset(_DAY_RIGHT, 0).to_client(width, height)[0]
    short = right - round(0.010 * unit)
    firsts = [0]
    for k in range(1, len(lines)):
        above, here = lines[k - 1], lines[k]
        wrapped = (above[1] < short and here[1] < short
                   and (above[1] - above[0]) + round(0.005 * unit) + (here[2] - here[0]) > right - left)
        if not wrapped:
            firsts.append(k)
    return tuple(firsts)


def _read_snapshot_confirm(width: int, height: int, get_pixel: PixelReader) -> bool:
    """The Snapshots delete confirm: its yellow panel, with a blue Yep! and red Cancel."""
    if not all(_is_confirm_yellow(get_pixel(*p.to_client(width, height))) for p in _SNAPSHOT_CONFIRM_PANEL):
        return False
    sides = (-0.012, 0.012)
    yep = any(_is_arrow_blue(get_pixel(*SNAPSHOT_YEP.offset(dx, 0).to_client(width, height))) for dx in sides)
    cancel = any(ui.is_red(get_pixel(*SNAPSHOT_CANCEL.offset(dx, 0).to_client(width, height))) for dx in sides)
    return yep and cancel


def _is_confirm_yellow(c: RGB) -> bool:
    r, g, b = c
    return r > 235 and g > 235 and 160 < b < 215


def _is_red_ink(c: RGB) -> bool:
    r, g, b = c
    return r > 150 and g < 90 and b < 90


def _is_arrow_blue(c: RGB) -> bool:
    r, g, b = c
    return b > 150 and b - r > 80


def _is_summon_blue(c: RGB) -> bool:
    # Dark blue, or light blue while hovered.
    return c[2] > 150 and c[0] < 110 and c[2] - c[0] > 80


def _read_summon_cogs(width: int, height: int, get_pixel: PixelReader) -> tuple[tuple[int, int], ...]:
    return tuple((col, row) for row in range(COG_ROWS) for col in range(COG_COLS)
                 if sum(_is_summon_blue(get_pixel(*cog_cell(col, row).offset(dx, dy).to_client(width, height)))
                        for dx, dy in _SUMMON_SAMPLES) >= _SUMMON_MIN)


def _is_popup_yellow(c: RGB) -> bool:
    return c[0] > 240 and c[1] > 240 and 160 < c[2] < 215


def _is_summon_available(c: RGB) -> bool:
    yellow = c[0] > 170 and c[1] > 160 and c[2] < 60
    hovered = c[2] > 160 and c[1] > 130 and c[0] < 80
    return yellow or hovered


def _read_summons(width: int, height: int, get_pixel: PixelReader) -> tuple[ui.UIPoint, ...] | None:
    """Issue a Cog Summons' available buttons if it's open (None if it isn't): colored
    bands down its button column that are yellow, or light blue while hovered (dark
    teal is unavailable). A message there instead has none."""
    if not all(_is_popup_yellow(get_pixel(*p.to_client(width, height))) for p in _SUMMONS_PANEL):
        return None
    if not ui.is_red(get_pixel(*SUMMONS_CLOSE.offset(-0.012, 0).to_client(width, height))):
        return None
    unit = min(width, height)
    px = round(width / 2 + _SUMMONS_SCAN_X * unit)
    top, bottom = (round(height / 2 + y * unit) for y in (_SUMMONS_TOP, _SUMMONS_BOTTOM))
    buttons, run = [], []
    for py in range(top, bottom + 2):
        if py <= bottom and not _is_popup_yellow(get_pixel(px, py)):
            run.append(py)
            continue
        if run and run[-1] - run[0] >= _SUMMONS_MIN_HEIGHT * unit:
            middle = get_pixel(px, (run[0] + run[-1]) // 2)
            if _is_summon_available(middle):
                buttons.append(_center(SUMMONS_BUTTON_X, ((run[0] + run[-1]) / 2 - height / 2) / unit))
        run = []
    return tuple(buttons)


def _is_trash_blue(c: RGB) -> bool:
    return c[2] > 95 and c[2] > c[0] + 25 and c[0] < 100


def _read_tasks(width: int, height: int, get_pixel: PixelReader) -> tuple[ui.UIPoint | bool | None, ...]:
    def at(point: ui.UIPoint, dx: float, dy: float) -> RGB:
        return get_pixel(*point.offset(dx, dy).to_client(width, height))

    tasks = []
    for center in TASK_CENTERS:
        ink = sum(max(at(center, x, y)) < 110 for x in _TASK_TITLE_XS for y in _TASK_TITLE_DYS)
        if ink < _TASK_TITLE_MIN:
            tasks.append(None)
            continue
        trash = [y for y in _TRASH_DYS
                 if sum(_is_trash_blue(at(center, _TRASH_DX + dx, y)) for dx in (-0.006, 0.0, 0.006)) >= 2]
        tasks.append(center.offset(_TRASH_DX, sum(trash) / len(trash)) if len(trash) >= _TRASH_MIN else False)
    return tuple(tasks)


def gag_point(row: int, col: int) -> ui.UIPoint:
    return _center(_GAG_X0 + _GAG_STEP_X * col, _GAG_Y0 + _GAG_STEP_Y * row)


def _is_gag_blue(c: RGB) -> bool:
    return c[2] > 200 and c[0] < 120 and c[1] > 100


def _read_gags(width: int, height: int, get_pixel: PixelReader) -> tuple[tuple[bool, ...], ...] | None:
    owned = tuple(tuple(any(_is_gag_blue(get_pixel(*gag_point(r, c).offset(dx, dy).to_client(width, height)))
                            for dx, dy in _GAG_PROBES) for c in range(GAG_COLS)) for r in range(GAG_ROWS))
    return owned if any(map(any, owned)) else None


def to_book(point: ui.UIPoint) -> ui.UIPoint:
    """A point on the battle trunk to where it is on the book's Trunk tab."""
    return _center(point.x * _TRUNK_SCALE + _TRUNK_OFFSET[0], point.y * _TRUNK_SCALE + _TRUNK_OFFSET[1])


def to_battle(point: ui.UIPoint) -> ui.UIPoint:
    return _center((point.x - _TRUNK_OFFSET[0]) / _TRUNK_SCALE, (point.y - _TRUNK_OFFSET[1]) / _TRUNK_SCALE)


def _read_book_trunk(width: int, height: int, get_pixel: PixelReader) -> BattleScreen | None:
    unit = min(width, height)

    def battle_pixel(x: int, y: int) -> RGB:
        # A pixel where the battle trunk would have it, read from where the book has it.
        return get_pixel(round(width / 2 + _TRUNK_SCALE * (x - width / 2) + _TRUNK_OFFSET[0] * unit),
                         round(height / 2 + _TRUNK_SCALE * (y - height / 2) + _TRUNK_OFFSET[1] * unit))

    trunk = _read_trunk(width, height, battle_pixel)
    if trunk.tab is None:
        return None
    if trunk.tab == "remotes":
        # Unlike in battle, remotes you don't have can be hovered too, for their info.
        tabs = tuple(i for i in trunk.items if i.tab)
        slots = tuple(Item(f"{kind} remote {i + 1}", _center(x, y))
                      for kind, y in _REMOTE_ROWS for i, x in enumerate(_REMOTE_XS))
        return BattleScreen("trunk", tab=trunk.tab, items=tabs + slots)
    if trunk.tab != "SOS" or trunk.filter_open:
        return trunk
    # Cards fully in view, down each column.
    cards = []
    top, bottom = (round(height / 2 + y * unit) for y in (_CARD_LIST_TOP, _CARD_LIST_BOTTOM))
    for col, margin in enumerate(_CARD_MARGIN_XS):
        px = round(width / 2 + margin * unit)
        whites = [py for py in range(top, bottom + 1) if min(get_pixel(px, py)) > 235]
        # A card's lettering can reach the margin, so small gaps don't end it.
        runs: list[list[int]] = []
        for py in whites:
            if runs and py - runs[-1][-1] <= _CARD_GAP * unit:
                runs[-1].append(py)
            else:
                runs.append([py])
        for run in runs:
            if run[0] > top and run[-1] < bottom and run[-1] - run[0] >= _CARD_MIN_HEIGHT * unit:
                y = ((run[0] + run[-1]) / 2 - height / 2) / unit
                cards.append(Item(f"SOS card {col + 1} at {y:.2f}", to_battle(_center(margin + _CARD_CENTER_DX, y))))
    return BattleScreen("trunk", tab=trunk.tab, items=trunk.items + tuple(cards), can_scroll=trunk.can_scroll)


def _read_districts(width: int, height: int, get_pixel: PixelReader) -> tuple[tuple[ui.UIPoint, ...], int | None,
                                                                              int | None]:
    def at(x: float, y: float) -> RGB:
        return get_pixel(*_px(width, height, x, y))

    names, chosen, current = [], None, None
    for i in range(_MAX_DISTRICTS):
        y = _DISTRICT0_Y + _DISTRICT_STEP * i
        if not any(_is_dot(at(_DISTRICT_DOT_X, y + dy)) for dy in _NAME_DYS):
            break
        names.append(_center(_DISTRICT_X, y))
        colors = [at(x, y + dy) for x in _NAME_XS for dy in _NAME_DYS]
        if sum(map(_is_chosen_orange, colors)) >= 10:
            chosen = i
        elif sum(map(_is_current_green, colors)) >= 10:
            current = i
    return tuple(names), chosen, current


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

# Districts, measured at 1920x1009. The list doesn't scroll with today's district count.
_DISTRICT_X = -0.337  # click here, inside even the shortest name
_DISTRICT_DOT_X = -0.0704
_DISTRICT0_Y = -0.2265
_DISTRICT_STEP = 0.0325
_MAX_DISTRICTS = 20
_NAME_XS = tuple(-0.367 + 0.004 * k for k in range(50))
_NAME_DYS = (-0.004, 0.0, 0.004)
TELEPORT = _center(0.2101, 0.1938)

# The map, measured at 1920x1009: where each place's "Go To" label shows when hovered.
MAP_PLACES = (
    ("Toontown Central", _center(-0.001, -0.0352)),
    ("Donald's Dock", _center(0.2874, -0.0481)),
    ("Daisy Gardens", _center(-0.1467, 0.0976)),
    ("Minnie's Melodyland", _center(0.0476, -0.1432)),
    ("The Brrrgh", _center(0.2299, -0.2056)),
    ("Donald's Dreamland", _center(-0.0436, -0.2988)),
    ("Goofy Speedway", _center(-0.2676, -0.0837)),
    ("Chip 'n Dale's Acorn Acres", _center(0.0961, 0.1472)),
    ("Sellbot HQ", _center(-0.3399, 0.1581)),
    ("Cashbot HQ", _center(-0.336, -0.3266)),
    ("Lawbot HQ", _center(0.3389, -0.3404)),
    ("Bossbot HQ", _center(0.336, 0.1452)),
)
_CLOUD_SAMPLES = tuple((0.005 * i, 0.005 * j) for i in range(-4, 5) for j in range(-4, 5))
_CLOUD_MIN = 30  # of the 81 samples; an open place has at most a dozen (the Brrrgh's snow)
# Gags, measured at 1920x1009: the gag buttons, one track a row (Toon-Up to Drop).
_GAG_X0, _GAG_STEP_X = -0.1838, 0.0869
_GAG_Y0, _GAG_STEP_Y = -0.3221, 0.0644
GAG_ROWS = GAG_COLS = 7
GAG_SIZE = (0.077, 0.055)
_GAG_PROBES = ((-0.022, 0.020), (0.022, 0.020))  # blue fill at the bottom corners of a gag you have
CUPCAKE = (4, 0)  # Throw's first gag: every toon has it

# The Trunk tab is the battle trunk (battle.py) at this scale, moved by this much:
# a point there maps here as book = battle * scale + offset, in units from the center.
_TRUNK_SCALE = 0.910
_TRUNK_OFFSET = (0.1245, -0.1128)
# SOS cards (no Call buttons here, so they're found by their white faces): the left
# margin of each column of cards, and the list's top and bottom.
_CARD_MARGIN_XS = tuple(-0.1893 + 0.1239 * i for i in range(4))
_CARD_CENTER_DX = 0.0549
_CARD_LIST_TOP, _CARD_LIST_BOTTOM = -0.280, 0.051
_CARD_MIN_HEIGHT = 0.12
_CARD_LIST_MIDDLE = _center(0.0485, -0.115)  # where to turn the wheel when no card is hovered
# After scrolling the cards with the right stick, once they've stopped moving for this
# long, the card under the cursor is highlighted.
_SCROLL_SETTLE_SECONDS = 0.2
_CARD_GAP = 0.013  # (the gap between rows of cards is 0.015) the most a card's white margin is broken by its lettering

# ToonTasks, measured at 1920x1009: each scroll's center, top left to bottom right.
TASK_CENTERS = tuple(_center(x, y) for y in (-0.181, 0.1194) for x in (-0.225, 0.228))
TASK_LIFT = 0.016  # how far a hovered scroll rises
_TASK_TITLE_XS = tuple(-0.07 + 0.005 * i for i in range(29))
_TASK_TITLE_DYS = (-0.140, -0.133, -0.126, -0.120)  # its title, lifted or not
_TASK_TITLE_MIN = 5  # dark title pixels for a scroll to have a task
_TRASH_DX = 0.1606
_TRASH_DYS = tuple(-0.095 + 0.004 * i for i in range(11))  # covers the lifted scroll too
_TRASH_MIN = 3

# Resistance Rank, measured at 1920x1009: the arrows either side of its page number.
RANK_PAGE_ARROWS = {"left": _center(-0.0545, 0.2349), "right": _center(0.0471, 0.2339)}

# Cog Gallery, measured at 1920x1009: the cells (8 cogs a row, a suit a row), the
# summon button in a cell's bottom right, and the suit icons down the left.
_COG_X0, _COG_STEP_X = -0.330, 0.0995
_COG_Y0, _COG_STEP_Y = -0.2720, 0.1417
COG_COLS, COG_ROWS = 8, 4
SUMMON_OFFSET = (0.0297, 0.0377)
_SUMMON_SAMPLES = tuple((0.0198 + 0.003 * i, 0.0277 + 0.003 * j) for i in range(8) for j in range(8))
_SUMMON_MIN = 6  # of the 64 samples (a cog's own blue face reaches 2)
SUIT_ICONS = {direction: _center(-0.4063, y) for direction, y in
              (("up", -0.2820), ("left", -0.1333), ("right", 0.0104), ("down", 0.1590))}  # tie, gavel, $, graph
# Issue a Cog Summons: its buttons are found down this column (their left ends, clear
# of lettering), clicked here, and the close X.
_SUMMONS_SCAN_X = -0.0119
_SUMMONS_TOP, _SUMMONS_BOTTOM = -0.3068, -0.1129
SUMMONS_BUTTON_X = 0.1487
SUMMONS_CLOSE = _center(0.3489, -0.1006)
_SUMMONS_PANEL = (_center(-0.355, -0.350), _center(-0.256, -0.104))  # the popup's pale yellow
_SUMMONS_MIN_HEIGHT = 0.020

# Fishing, measured at 1920x1009: the Bucket's fish names and scroll triangles, and the
# Album's triangles. The tabs along the top are Bucket, Album and Trophies.
_FISH_X, _FISH_Y0, _FISH_STEP = -0.2577, -0.1060, 0.01927
FISH_ROWS = 10
_FISH_INK_XS = tuple(-0.2884 + 0.002 * i for i in range(36))
FISH_SCROLL_UP = _center(-0.2001, -0.1384)
FISH_SCROLL_DOWN = _center(-0.2001, 0.1214)
RELEASE_FISH = _center(0.1031, 0.0159)
ALBUM_UP = _center(0.0, -0.3375)
ALBUM_DOWN = _center(0.0, 0.2359)
BUCKET_TAB, ALBUM_TAB = 0, 1
# Gardening, measured at 1920x1009: the Basket (same place as the Bucket, rows closer
# together) and the Album's names. Its tabs are Basket, Album, Trophies and Specials;
# its Album triangles are where Fishing's are.
_FLOWER_Y0, _FLOWER_STEP = -0.1056, 0.01487
FLOWER_ROWS = 14  # as many as fit (not seen full)
FLOWER_SCROLL_UP = _center(-0.2001, -0.1432)
FLOWER_SCROLL_DOWN = _center(-0.2001, 0.1214)
RELEASE_FLOWER = _center(0.3380, 0.0124)
_ALBUM_FLOWER_X, _ALBUM_FLOWER_Y0, _ALBUM_FLOWER_STEP = 0.0694, -0.2334, 0.04965
ALBUM_FLOWERS = 8
_ALBUM_INK_XS = tuple(0.0406 + 0.004 * i for i in range(25))
# The lists per page: (scroll up, scroll down, the release X, "full" when this many show).
_LISTS = {"fishing": (FISH_SCROLL_UP, FISH_SCROLL_DOWN, RELEASE_FISH, FISH_ROWS),
          "gardening": (FLOWER_SCROLL_UP, FLOWER_SCROLL_DOWN, RELEASE_FLOWER, 10)}

# Racing and Golf, measured at 1920x1009. Customize: the kart's turn buttons and the
# accessory icons along the bottom. Trophy: the trophies, small then big.
KART_TURN = {"stickLeft": _center(-0.127, -0.0193), "stickRight": _center(0.127, -0.0193)}
_ACCESSORY_X0, _ACCESSORY_STEP, _ACCESSORY_Y = -0.2299, 0.0656, 0.2611
ACCESSORIES = 8
ACCESSORY_SIZE = (0.058, 0.060)
TROPHIES = (tuple(_center(-0.3791 + 0.0855 * c, -0.2879 + 0.1150 * r) for r in range(3) for c in range(10))
            + tuple(_center(x, 0.1392) for x in (-0.1249, 0.0, 0.1249)))
_TROPHY_CARD = (-0.025, 0.035)  # a spot on a trophy's card clear of the trophy (or "?")
# The tabs along the top, by page: which one is Customize, and which is Trophy.
_CUSTOMIZE_TAB = {"racing": 0}
_TROPHY_TAB = {"racing": 2, "golf": 1}
# Golf's Records tab scrolls its courses with triangles above and below the list.
GOLF_RECORDS_TAB = 0
GOLF_RECORDS_SCROLL = {"up": _center(0.0278, -0.3464), "down": _center(0.0278, 0.2651)}

# Cog Disguise, measured at 1920x1009: the suit tabs (top to bottom) and the blue arrows.
SUIT_TABS = tuple(_center(0.3845, y) for y in (-0.2265, -0.0798, 0.0610, 0.1948))
SUIT_NAMES = ("Bossbot", "Lawbot", "Cashbot", "Sellbot")
_SUIT_INK_XS = tuple(0.3746 + 0.002 * i for i in range(11))
_SUIT_INK_DYS = tuple(-0.042 + 0.006 * i for i in range(15))
DISGUISE_ARROWS = {"left": _center(-0.3409, 0.2126), "right": _center(-0.0793, 0.2126)}

# Snapshots, measured at 1920x1009: the arrows, the trash can and its delete confirm.
SNAPSHOT_ARROWS = {"left": _center(0.0743, 0.0530), "right": _center(0.3746, 0.0530)}
SNAPSHOT_TRASH = _center(0.3419, 0.1224)
SNAPSHOT_YEP = _center(0.1744, 0.2235)
SNAPSHOT_CANCEL = _center(0.2740, 0.2235)
_SNAPSHOT_CONFIRM_PANEL = tuple(_center(x, y) for x in (-0.0099, 0.2200, 0.4559) for y in (0.0550, 0.1838))

# The Events Calendar, measured at 1920x1009: the days' numbers, their event lines,
# the month arrows and the filter's triangles.
CALENDAR_TAB = 0
_DAY_X0, _DAY_STEP_X, _DAY_Y0, _DAY_STEP_Y = -0.3721, 0.1239, -0.2924, 0.0931
CALENDAR_COLS, CALENDAR_ROWS = 7, 6
_EVENT_DY0, _EVENT_STEP = 0.0198, 0.01586
CALENDAR_LINES = 4  # as many as fit in a day
_DAY_LEFT, _DAY_RIGHT = -0.059, 0.060  # a day's text, from its number's x
_EVENT_HOVER_DX = -0.030  # on an event's text, near its start
DAY_NUMBER_SIZE = (0.034, 0.022)
MONTH_ARROWS = {"stickLeft": _center(-0.1834, -0.3642), "stickRight": _center(0.1834, -0.3642)}
FILTER_UP = _center(0.3092, -0.3979)
FILTER_DOWN = _center(0.3092, -0.3464)
FILTER_OPTIONS = 4  # Show All first; going back from the last takes three clicks up
# TTR takes a moment to redraw the calendar: it's kept once it reads the same this long
# (and, after a month or filter change, differs from before, or this long has passed).
_CALENDAR_STEADY_SECONDS = 0.15
_CALENDAR_CHANGE_SECONDS = 1.5

GO_HOME = _center(0.0723, 0.2711)
BACK_TO_PLAYGROUND = _center(0.2676, 0.2711)
_GO_HOME_PROBES = (_center(0.0297, 0.2552), _center(0.1140, 0.2552))
_PLAYGROUND_PROBES = (_center(0.1784, 0.2552), _center(0.3568, 0.2552))


@dataclass(frozen=True)
class BookScreen:
    tabs: tuple[ui.UIPoint, ...] = ()  # the page tabs, top to bottom
    current: int | None = None  # index into tabs
    page: str | None = None  # the current page, by its tab's icon (None if it isn't known)
    top_tabs: tuple[ui.UIPoint, ...] = ()
    top_current: int | None = None
    dialog: tuple[ui.UIPoint, ui.UIPoint] | None = None  # an OK/Cancel dialog over the book
    districts: tuple[ui.UIPoint, ...] = ()  # on the Districts page: each district's name
    district_chosen: int | None = None  # the one clicked (orange), if not the current one
    district_current: int | None = None  # the one you're in (green)
    places: tuple[tuple[str, ui.UIPoint], ...] = ()  # on the Map page: the places not under clouds
    go_home: bool = False  # the Map page's Go Home button is showing
    back_to_playground: bool = False
    gags: tuple[tuple[bool, ...], ...] | None = None  # on the Gags tab: which gags you have
    trunk: BattleScreen | None = None  # on the Trunk tab: read as the battle trunk (in its places)
    # On the ToonTasks page: each scroll's task (None for a blank scroll), as where to
    # click its trash can, or False if it can't be deleted.
    tasks: tuple[ui.UIPoint | bool | None, ...] = ()
    summon_cogs: tuple[tuple[int, int], ...] = ()  # on the Cog Gallery: the cells with a summon button
    snapshot_arrows: tuple[str, ...] = ()  # on Snapshots: its arrows showing ("left", "right")
    snapshot_trash: bool = False  # and its trash can (there's a snapshot to delete)
    calendar: Calendar | None = None  # on Events' Calendar tab
    fish: tuple[ui.UIPoint, ...] = ()  # on Fishing's Bucket (or Gardening's Basket): the names showing
    flowers: tuple[ui.UIPoint, ...] = ()  # on Gardening's Album: the collected names, top to bottom
    trophies: tuple[int, ...] = ()  # on a Trophy tab: the trophies earned (indexes into TROPHIES)
    suit_current: int | None = None  # on Cog Disguise: the suit tab picked (into SUIT_TABS)
    suit_arrows: tuple[str, ...] = ()  # and its blue arrows showing ("left", "right")
    summons_open: bool = False  # Issue a Cog Summons is open
    summons: tuple[ui.UIPoint, ...] = ()  # its available buttons, top to bottom (none for a message)

    @property
    def is_open(self) -> bool:
        return bool(self.tabs) or self.dialog is not None or self.summons_open

    @property
    def hovers(self) -> bool:
        """Whether something is highlighted with the cursor (so it isn't parked)."""
        return (self.dialog is not None or self.page in PAGE_ROWS or bool(self.places)
                or self.trunk is not None or self.summons_open)


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
            summons = _read_summons(width, height, get_pixel)
            if summons is not None:
                return BookScreen(summons_open=True, summons=summons)
        elif _read_snapshot_confirm(width, height, get_pixel):
            return BookScreen(dialog=(SNAPSHOT_YEP, SNAPSHOT_CANCEL))
        return BookScreen()
    kinds, edges = found
    current = kinds.index("pressed") if "pressed" in kinds else None
    # Only the current page's icon is needed (reading one takes a lot of pixels).
    page = _page(width, height, get_pixel, current, *edges) if current is not None else None
    top_tabs, top_current = _top_tabs(width, height, get_pixel)
    tabs = tuple(_center(_TAB_X, _TAB0_Y + _TAB_STEP * i) for i in range(len(kinds)))
    districts, chosen, current_district = (_read_districts(width, height, get_pixel) if page == "districts"
                                           else ((), None, None))
    places, go_home, playground = _read_map(width, height, get_pixel) if page == "map" else ((), False, False)
    trunk = _read_book_trunk(width, height, get_pixel) if page == "gags" else None
    gags = _read_gags(width, height, get_pixel) if page == "gags" and trunk is None else None
    tasks = _read_tasks(width, height, get_pixel) if page == "toontasks" else ()
    summon_cogs = _read_summon_cogs(width, height, get_pixel) if page == "cog gallery" else ()
    fish = (_read_fish(width, height, get_pixel, page) if page in _LISTS and top_current == BUCKET_TAB
            else ())
    flowers = (_read_album_flowers(width, height, get_pixel) if page == "gardening" and top_current == ALBUM_TAB
               else ())
    trophies = (_read_trophies(width, height, get_pixel)
                if top_current is not None and top_current == _TROPHY_TAB.get(page) else ())
    suit_current, suit_arrows = (_read_disguise(width, height, get_pixel) if page == "cog disguise"
                                 else (None, ()))
    snapshot_arrows = tuple(side for side, p in SNAPSHOT_ARROWS.items()
                            if page == "snapshots" and _is_arrow_blue(get_pixel(*p.to_client(width, height))))
    snapshot_trash = page == "snapshots" and min(get_pixel(*SNAPSHOT_TRASH.to_client(width, height))) < 200
    calendar = (_read_calendar(width, height, get_pixel) if page == "events" and top_current == CALENDAR_TAB
                else None)
    return BookScreen(tabs, current, page, top_tabs, top_current, districts=districts, district_chosen=chosen,
                      district_current=current_district, places=places, go_home=go_home,
                      back_to_playground=playground, gags=gags, trunk=trunk, tasks=tasks, summon_cogs=summon_cogs,
                      fish=fish, flowers=flowers, trophies=trophies, suit_current=suit_current, suit_arrows=suit_arrows,
                      snapshot_arrows=snapshot_arrows, snapshot_trash=snapshot_trash, calendar=calendar)


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
    "select": "press the highlighted button (Teleport Here! on Districts, OK in a dialog)",
    "up": "move up a page's buttons (or choose the district above)",
    "down": "move down a page's buttons (or choose the district below)",
    "left": "change a setting (the SpeedChat color), the next place left on the map, or the snapshot before",
    "right": "change a setting (the SpeedChat color), the next place right on the map, or the next snapshot",
    "goHome": "the map's Go Home button",
    "pageAction": "the map's Back to Playground button, delete the highlighted ToonTask (one with a trash can), "
                  "release the fish (or flower) picked, or delete the snapshot shown",
    "filter": "press the left stick: the Events Calendar's next filter (back to the first after the last)",
    "stickUp": "right stick up: scroll the Trunk's SOS cards up, or the Cog Gallery's tie (Bossbot)",
    "stickDown": "right stick down: scroll the Trunk's SOS cards down, or the Cog Gallery's bar graph (Sellbot)",
    "stickLeft": "right stick left: the Cog Gallery's gavel (Lawbot), turn the kart on Racing's Customize tab, "
                 "or the Events Calendar's month before",
    "stickRight": "right stick right: the Cog Gallery's dollar sign (Cashbot), turn the kart, or the next month",
}


def default_book_bindings() -> Bindings:
    press = {"lb": "prevPage", "rb": "nextPage", "lt": "prevTab", "rt": "nextTab", "b": "close", "a": "select",
             "y": "goHome", "x": "pageAction", "ls": "filter",
             "rs_up": "stickUp", "rs_down": "stickDown", "rs_left": "stickLeft", "rs_right": "stickRight"}
    # The left stick too: the toon can't walk while the book is open.
    for direction in ("up", "down", "left", "right"):
        press[f"dpad_{direction}"] = direction
        press[f"ls_{direction}"] = direction
    return Bindings(press=press)


_DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}


def _nearest(here: tuple[str, ui.UIPoint], places, direction: tuple[int, int]) -> tuple[str, ui.UIPoint] | None:
    """The closest place roughly in a direction (within 60 degrees of it), favoring
    ones straight that way."""
    best, best_score = None, float("inf")
    for name, point in places:
        dx, dy = point.x - here[1].x, point.y - here[1].y
        dist = (dx * dx + dy * dy) ** 0.5
        if name == here[0] or dist == 0:
            continue
        cos = (dx * direction[0] + dy * direction[1]) / dist
        if cos < 0.5:
            continue
        score = dist * (1 + 2 * (1 - cos))
        if score < best_score:
            best, best_score = (name, point), score
    return best


# Each page with controls: its buttons, top to bottom.
PAGE_ROWS = {"options": OPTIONS_ROWS}
# Buttons with a setting changed by left/right: the arrows to click.
_ARROWS = {SPEEDCHAT_COLOR: (COLOR_LEFT, COLOR_RIGHT)}


def _trunk_bindings() -> Bindings:
    """The battle trunk's bindings that apply in the book (B still closes the book)."""
    press = {"a": "select", "ls": "sos_filter"}
    for direction in ("up", "down", "left", "right"):
        press[f"dpad_{direction}"] = direction
        press[f"ls_{direction}"] = direction
    return Bindings(press=press)


def _trunk_size(name: str) -> tuple[float, float] | None:
    """The battle trunk's frame sizes, at the book trunk's scale."""
    size = _battle_trunk_size(name)
    return None if size is None else (size[0] * _TRUNK_SCALE, size[1] * _TRUNK_SCALE)


# Buttons that change the page or tab, or close the book (Start is the book key), so
# whatever was highlighted is gone.
_LEAVES_PAGE = frozenset({"lb", "rb", "lt", "rt", "b", "start"})

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
        self._held: frozenset[str] = frozenset()
        self._scrolled: tuple[float, ui.UIPoint] | None = None  # when and where the cards were last scrolled
        self._left_page = False
        self.row = 0
        self._shown: tuple | None = None  # what was last hovered for: (page, dialog showing)
        self._page: str | None = None
        self._district: int | None = None  # the district last clicked, before the page shows it
        self._place: str | None = None  # the map place hovered
        self._gag: tuple[int, int] | None = None  # the gag hovered on the Gags tab (none at first)
        self._task: int | None = None  # the ToonTask hovered (none at first)
        self._cog: tuple[int, int] | None = None  # the summon button hovered (none at first)
        self._summon = 0  # the button hovered in Issue a Cog Summons
        self._fish = 0  # the Bucket row chosen (it opens on the top one)
        self._flower = 0  # the Flower Album name chosen (it opens on the top one)
        self._accessory: int | None = None  # the Customize tab's accessory icon hovered (none at first)
        self._trophy: int | None = None  # the trophy hovered (none at first)
        self._tab: tuple | None = None  # the page and top tab these are for
        self._turning: str | None = None  # the kart turn button held down ("stickLeft"/"stickRight")
        self._held_scroll = HeldScroll()  # a list's scroll triangle, held down while its direction is
        # The Events Calendar, as read before anything was hovered (its popups cover days),
        # and the day and event there hovered: (day, event index), None for nothing yet.
        self._calendar: Calendar | None = None
        self._day: tuple[int, int] | None = None
        self._calendar_seen: tuple[Calendar, float] | None = None  # a reading not kept yet, and since when
        self._calendar_before: tuple[Calendar, float] | None = None  # the one before a change, and when
        self._releasing = False  # the release confirm is up (or about to be)
        # The Trunk tab works like the battle trunk, so it's run by a battle mapper.
        self._trunk = BattleMapper(_trunk_bindings())

    def set_bindings(self, bindings: Bindings) -> None:
        self.bindings = bindings
        self._actions = ButtonActions(bindings, 0.5, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in ("prevPage", "nextPage", "up", "down", "stickUp", "stickDown"))

    @property
    def buttons(self) -> set[str]:
        # The Trunk tab's too (LS cycles the SOS filter), so they don't also do their
        # overworld action (LS is sprint).
        return self.bindings.buttons() | self._trunk.buttons

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)
        self._held_scroll.stop(finish=False)
        self._shown = None
        self._trunk.reset_buttons()

    def _known(self, screen: BookScreen) -> BookScreen:
        """The screen, with the page last seen when its tab can't be told (an Events
        popup can cover the page tabs)."""
        if screen.tabs and screen.page is None and self._tab is not None and self._tab[0] is not None:
            top = screen.top_current if screen.top_current is not None else self._tab[1]
            return replace(screen, page=self._tab[0], top_current=top)
        return screen

    @property
    def hovered_task(self) -> int | None:
        """The ToonTask hovered on the ToonTasks page, if one is (for its hint)."""
        return self._task

    def hovering(self, screen: BookScreen) -> bool:
        """Whether something on the book is hovered (so the cursor isn't parked)."""
        screen = self._known(screen)
        return (screen.hovers or (screen.gags is not None and self._gag is not None)
                or (screen.tasks and self._task is not None)
                or (screen.page == "cog gallery" and self._cog is not None)
                or self._accessory is not None or self._trophy is not None
                or (screen.page == "events" and self._day is not None))

    def take_left_page(self) -> bool:
        """Whether a button that leaves the page (or closes the book) was pressed since
        the last call, so the highlight frame should go."""
        left, self._left_page = self._left_page, False
        return left

    def take_taps(self) -> list[str]:
        """TTR controls to tap, asked for since the last call: the turn keys flip pages
        and the book key closes it."""
        taps, self._taps = self._taps, []
        return taps

    def update(self, buttons: frozenset[str], now: float, screen: BookScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons, now)
        screen = self._known(screen)
        if (buttons - self._held) & _LEAVES_PAGE:
            self._left_page = True
        self._held = buttons
        commands: list[PointerCommand] = []
        if screen.gags is None:
            self._gag = None
        if not screen.tasks and screen.dialog is None:
            self._task = None
        elif screen.tasks and self._task is not None and screen.tasks[self._task] is None:
            self._task = None  # deleted
        if screen.dialog is not None and self._releasing:
            pass  # the list is hidden behind the confirm: keep the fish
        elif self._releasing and screen.fish and now >= self._settle_until:
            # The confirm closed: back on the fish released (or the one moved into its row).
            self._releasing = False
            self._fish = min(self._fish, len(screen.fish) - 1)
            commands.append(PointerCommand("click", screen.fish[self._fish], f"fish {self._fish + 1}"))
        elif not screen.fish and now >= self._settle_until:
            self._fish = 0
            self._releasing = False
        if screen.page != "cog gallery" and not screen.summons_open and screen.dialog is None:
            self._cog = None
        if (screen.page, screen.top_current) != self._tab:
            # A new page or tab: nothing hovered there yet.
            self._tab = (screen.page, screen.top_current)
            self._flower = 0
            commands += self._held_scroll.stop(finish=False)
            self._calendar, self._day, self._calendar_seen, self._calendar_before = None, None, None, None
            self._accessory = self._trophy = None
        commands += self._turn_kart(buttons, screen)
        if self._calendar is None and screen.calendar is not None and now >= self._settle_until:
            commands += self._settle_calendar(screen.calendar, now)
        commands += self._held_scroll.update({self.bindings.press.get(b) for b in buttons})
        if screen.trunk is not None and screen.dialog is None:
            # The battle mapper moves around the trunk; its points are turned into the book's.
            for c in self._trunk.update(buttons, now, screen.trunk):
                size = _trunk_size(c.name) if c.kind == "hover" else None
                commands.append(PointerCommand(c.kind, to_book(c.point), c.name, c.notches, c.delay, size))
            fired = [a for a in fired if a not in ("up", "down", "left", "right", "select")]
            for action in [a for a in fired if a in ("stickUp", "stickDown")]:
                scroll = self._scroll_trunk(screen.trunk, action == "stickUp")
                if scroll:
                    self._scrolled = (now, scroll[0].point)
                commands += scroll
            if self._scrolled is not None and now - self._scrolled[0] >= _SCROLL_SETTLE_SECONDS:
                commands += self._hover_card_at(screen.trunk, self._scrolled[1])
                self._scrolled = None
        else:
            self._trunk.reset_buttons()
        if now >= self._settle_until:
            shown = (screen.page, screen.dialog is not None)
            if shown != self._shown:
                self._shown = shown
                # A new page starts at its top button. A dialog hides the page, so
                # coming back from one keeps the button it was opened from.
                if screen.dialog is None and screen.page != self._page:
                    self._page = screen.page
                    self.row = 0
                    self._district = None
                    self._place = None
                commands += self._hover(screen)
        for action in fired:
            held = self._held_scroll.repeat(action)
            if held is not None:
                commands += held  # still held on a scroll triangle: hold it down instead
            elif screen.dialog is not None:
                commands += self._run_dialog(action, screen, now)
            elif screen.summons_open:
                commands += self._run_summons(action, screen, now)
            elif action in _TAPS:
                self._taps.append(_TAPS[action])
            elif now >= self._settle_until:
                commands += self._run(action, screen, now)
        return commands

    def _run_districts(self, action: str, screen: BookScreen) -> list[PointerCommand]:
        if action in ("up", "down") and screen.districts:
            # From the one last clicked: the page can take a moment to show it.
            base = next((i for i in (self._district, screen.district_chosen, screen.district_current)
                         if i is not None), 0)
            self._district = (base + (-1 if action == "up" else 1)) % len(screen.districts)
            return [PointerCommand("click", screen.districts[self._district], f"district {self._district + 1}")]
        if action == "select":
            return [PointerCommand("click", TELEPORT, "teleport here")]
        return []

    def _scroll_trunk(self, trunk: BattleScreen, up: bool) -> list[PointerCommand]:
        """A wheel notch over the SOS cards, where the hovered card is (so the cursor
        stays on the list), or the middle of the list."""
        if trunk.tab != "SOS" or trunk.filter_open or not trunk.can_scroll[0 if up else 1]:
            return []
        item = self._trunk.trunk_item
        point = to_book(item.point) if item is not None and item.name.startswith("SOS card") else _CARD_LIST_MIDDLE
        return [PointerCommand("scroll", point, "scroll SOS cards", notches=1 if up else -1)]

    def _turn_kart(self, buttons: frozenset[str], screen: BookScreen) -> list[PointerCommand]:
        """The kart turns while its LEFT or RIGHT button is held, so the right stick holds
        the mouse button down on it for as long as the stick is pushed."""
        on_customize = screen.top_current is not None and screen.top_current == _CUSTOMIZE_TAB.get(screen.page)
        turning = None
        if on_customize and screen.dialog is None:
            turning = next((action for action in KART_TURN
                            if any(self.bindings.press.get(b) == action for b in buttons)), None)
        if turning == self._turning:
            return []
        commands = []
        if self._turning is not None:
            commands.append(PointerCommand("release", KART_TURN[self._turning], "stop turning kart"))
        if turning is not None:
            commands.append(PointerCommand("hold", KART_TURN[turning], f"turn kart {turning[5:].lower()}"))
        self._turning = turning
        return commands

    def _run_customize(self, action: str, now: float) -> list[PointerCommand]:
        if action == "select" and self._accessory is not None:
            return self._click(_accessory(self._accessory), f"accessory {self._accessory + 1}", now)
        if action not in ("left", "right"):
            return []
        if self._accessory is None:
            self._accessory = 0
        else:
            self._accessory = max(0, min(ACCESSORIES - 1, self._accessory + (-1 if action == "left" else 1)))
        return [PointerCommand("hover", _accessory(self._accessory), f"accessory {self._accessory + 1}",
                               size=ACCESSORY_SIZE)]

    def _run_calendar(self, action: str, now: float) -> list[PointerCommand]:
        calendar = self._calendar
        if calendar is None:
            return []
        if action in MONTH_ARROWS:
            if action not in calendar.months:
                return []
            self._change_calendar(now)  # read the new month afresh
            return self._click(MONTH_ARROWS[action], f"month {action[5:].lower()}", now)
        if action == "filter":
            self._change_calendar(now)
            if calendar.filter_down:
                return self._click(FILTER_DOWN, "next filter", now)
            # On the last: back up to the first.
            commands = self._click(FILTER_UP, "first filter", now)
            commands += [PointerCommand("click", FILTER_UP, "first filter", delay=0.15)
                         for _ in range(FILTER_OPTIONS - 2)]
            self._settle_until = now + self.settle_seconds + 0.15 * (FILTER_OPTIONS - 2)
            return commands
        if action not in _DIRECTIONS:
            return []
        days = calendar.events
        if self._day is None:
            return []
        else:
            day, event = self._day
            if action == "up":
                if event > 0:
                    self._day = (day, event - 1)
                elif day >= CALENDAR_COLS:
                    above = day - CALENDAR_COLS
                    self._day = (above, max(len(days[above]) - 1, 0))
                else:
                    return []
            elif action == "down":
                if event < len(days[day]) - 1:
                    self._day = (day, event + 1)
                elif day + CALENDAR_COLS < len(days):
                    self._day = (day + CALENDAR_COLS, 0)
                else:
                    return []
            else:
                step = -1 if action == "left" else 1
                if not 0 <= day + step < len(days):
                    return []
                self._day = (day + step, 0)
        return [self._hover_day()]

    def _change_calendar(self, now: float) -> None:
        self._calendar_before = (self._calendar, now)
        self._calendar, self._day, self._calendar_seen = None, None, None

    def _settle_calendar(self, reading: Calendar, now: float) -> list[PointerCommand]:
        """Keep the calendar once TTR has finished drawing it; then (arriving, or a new
        month or filter) straight onto today's first event, or the month's first day."""
        if self._calendar_seen is None or self._calendar_seen[0] != reading:
            self._calendar_seen = (reading, now)
            return []
        if now - self._calendar_seen[1] < _CALENDAR_STEADY_SECONDS:
            return []
        if (self._calendar_before is not None and reading == self._calendar_before[0]
                and now - self._calendar_before[1] < _CALENDAR_CHANGE_SECONDS):
            return []  # still the one from before the change
        self._calendar, self._calendar_seen, self._calendar_before = reading, None, None
        self._day = (reading.today if reading.today is not None else reading.first or 0, 0)
        return [self._hover_day()]

    def _hover_day(self) -> PointerCommand:
        """The event hovered (its popup shows), or a day with none just by its number;
        the frame goes around the number either way."""
        day, event = self._day
        lines = self._calendar.events[day]
        point = calendar_event(day, lines[event]) if lines else calendar_day(day)
        name = f"day {day + 1} event {event + 1}" if lines else f"day {day + 1}"
        return PointerCommand("hover", point, name, size=DAY_NUMBER_SIZE, frame_at=calendar_day(day))

    def _run_disguise(self, action: str, screen: BookScreen, now: float) -> list[PointerCommand]:
        if action in DISGUISE_ARROWS:
            if action not in screen.suit_arrows:
                return []
            return self._click(DISGUISE_ARROWS[action], f"disguise {action}", now)
        if screen.suit_current is None:
            return []
        # Like Districts, each suit tab is clicked as you go.
        suit = screen.suit_current + (-1 if action == "up" else 1)
        if not 0 <= suit < len(SUIT_TABS):
            return []
        return self._click(SUIT_TABS[suit], SUIT_NAMES[suit], now)

    def _run_trophies(self, action: str, screen: BookScreen) -> list[PointerCommand]:
        # Only trophies earned: a "?" has nothing to hover.
        if action not in _DIRECTIONS or not screen.trophies:
            return []
        if self._trophy not in screen.trophies:
            self._trophy = screen.trophies[0]
        else:
            here = (str(self._trophy), TROPHIES[self._trophy])
            nearest = _nearest(here, [(str(i), TROPHIES[i]) for i in screen.trophies], _DIRECTIONS[action])
            if nearest is None:
                return []
            self._trophy = int(nearest[0])
        # No frame: a hovered trophy tints yellow.
        return [PointerCommand("hover", TROPHIES[self._trophy], f"trophy {self._trophy + 1}")]

    def _run_flower_album(self, action: str, screen: BookScreen, now: float) -> list[PointerCommand]:
        if action in ("stickUp", "stickDown"):
            # The triangles: the next genus, shown from its top name.
            self._flower = 0
            return self._click(ALBUM_UP if action == "stickUp" else ALBUM_DOWN, f"album {action[5:].lower()}", now)
        if not screen.flowers:
            return []
        self._flower = min(self._flower, len(screen.flowers) - 1)
        row = self._flower + (-1 if action == "up" else 1)
        if not 0 <= row < len(screen.flowers):
            return []
        self._flower = row
        return [PointerCommand("click", screen.flowers[row], f"flower {row + 1}")]

    def _run_fishing(self, action: str, screen: BookScreen, now: float) -> list[PointerCommand]:
        if screen.top_current == ALBUM_TAB:
            return self._click(ALBUM_UP if action == "up" else ALBUM_DOWN, f"album {action}", now)
        scroll_up, scroll_down, _, full = _LISTS[screen.page]
        if not screen.fish:
            return []
        # Like Districts, each fish is clicked as you go (hovering does nothing).
        self._fish = min(self._fish, len(screen.fish) - 1)  # one may have been released
        row = self._fish + (-1 if action == "up" else 1)
        if 0 <= row < len(screen.fish):
            self._fish = row
            return [PointerCommand("click", screen.fish[row], f"fish {row + 1}")]
        if row < 0 or len(screen.fish) >= full:
            # Past the top or a full bottom row: scroll, and click the fish moved into it.
            arrow = scroll_up if row < 0 else scroll_down
            again = PointerCommand("click", screen.fish[self._fish], f"fish {self._fish + 1}")
            self._held_scroll.clicked(action, arrow, after=[again])
            return [PointerCommand("click", arrow, f"scroll fish {action}"), again]
        return []

    def _run_cog_gallery(self, action: str, screen: BookScreen, now: float) -> list[PointerCommand]:
        suits = {"stickUp": "up", "stickLeft": "left", "stickRight": "right", "stickDown": "down"}
        if action in suits:
            return self._click(SUIT_ICONS[suits[action]], f"{suits[action]} suit", now)
        if action == "select" and self._cog in screen.summon_cogs:
            self._summon = 0
            return self._click(summon_button(self._cog), "summon button", now)
        if action not in _DIRECTIONS or not screen.summon_cogs:
            return []
        if self._cog not in screen.summon_cogs:
            self._cog = screen.summon_cogs[0]
        else:
            here = (str(self._cog), summon_button(self._cog))
            others = [(str(c), summon_button(c)) for c in screen.summon_cogs]
            nearest = _nearest(here, others, _DIRECTIONS[action])
            if nearest is None:
                return []
            self._cog = next(c for c in screen.summon_cogs if str(c) == nearest[0])
        return [PointerCommand("hover", summon_button(self._cog), "summon button")]

    def _run_summons(self, action: str, screen: BookScreen, now: float) -> list[PointerCommand]:
        if action == "close" or (action == "select" and not screen.summons):
            # A message (no buttons) closes with A too.
            return self._click(SUMMONS_CLOSE, "close summons", now)
        if not screen.summons:
            return []
        if action in ("up", "down"):
            self._summon = max(0, min(len(screen.summons) - 1, self._summon + (-1 if action == "up" else 1)))
            return [PointerCommand("hover", screen.summons[self._summon], f"summon {self._summon + 1}")]
        if action == "select":
            self._summon = min(self._summon, len(screen.summons) - 1)
            return self._click(screen.summons[self._summon], f"summon {self._summon + 1}", now)
        return []

    def _run_tasks(self, action: str, screen: BookScreen, now: float) -> list[PointerCommand]:
        if action == "pageAction":
            trash = screen.tasks[self._task] if self._task is not None else None
            # The trash can asks to confirm; the dialog is the usual OK/Cancel.
            return self._click(trash, f"delete task {self._task + 1}", now) if trash else []
        present = [i for i, task in enumerate(screen.tasks) if task is not None]
        if not present:
            return []
        if self._task is None:
            self._task = present[0]
        else:
            here = (str(self._task), TASK_CENTERS[self._task])
            others = [(str(i), TASK_CENTERS[i]) for i in present]
            nearest = _nearest(here, others, _DIRECTIONS[action])
            if nearest is None:
                return []
            self._task = int(nearest[0])
        return self._hover_task()

    def _hover_task(self) -> list[PointerCommand]:
        # Where the scroll sits once it's lifted by the hover. No highlight frame: the
        # lifted scroll shows which one it is.
        point = TASK_CENTERS[self._task].offset(0, -TASK_LIFT)
        return [PointerCommand("hover", point, f"task {self._task + 1}")]

    def _hover_card_at(self, trunk: BattleScreen, point: ui.UIPoint) -> list[PointerCommand]:
        """Highlight the card nearest a point (after scrolling, the one under the cursor)."""
        cards = [i for i in trunk.items if i.name.startswith("SOS card")]
        if not cards:
            return []

        def distance(item: Item) -> float:
            p = to_book(item.point)
            return (p.x - point.x) ** 2 + (p.y - point.y) ** 2

        card = min(cards, key=distance)
        self._trunk.trunk_item = card
        return [PointerCommand("hover", to_book(card.point), card.name, size=_trunk_size(card.name))]

    def _map_place(self, screen: BookScreen) -> tuple[str, ui.UIPoint] | None:
        """The hovered place, or Toontown Central (or the first open place) to start."""
        places = dict(screen.places)
        for name in (self._place, MAP_PLACES[0][0]):
            if name in places:
                return name, places[name]
        return screen.places[0] if screen.places else None

    def _run_map(self, action: str, screen: BookScreen, now: float) -> list[PointerCommand]:
        if action == "goHome" and screen.go_home:
            return self._click(GO_HOME, "go home", now)
        if action == "pageAction" and screen.back_to_playground:
            return self._click(BACK_TO_PLAYGROUND, "back to playground", now)
        here = self._map_place(screen)
        if here is None:
            return []
        if action == "select":
            # Clicked either way: without teleport access it just does nothing.
            return self._click(here[1], f"go to {here[0]}", now)
        if action in _DIRECTIONS:
            nearest = _nearest(here, screen.places, _DIRECTIONS[action])
            if nearest is not None:
                self._place = nearest[0]
                return [PointerCommand("hover", nearest[1], nearest[0])]
        return []

    def _hover(self, screen: BookScreen) -> list[PointerCommand]:
        if screen.dialog is not None:
            return [PointerCommand("hover", screen.dialog[0], "OK")]
        if screen.summons:
            # Opened fresh, the top button; back from declining a summons, the one picked.
            self._summon = min(self._summon, len(screen.summons) - 1)
            return [PointerCommand("hover", screen.summons[self._summon], f"summon {self._summon + 1}")]
        if screen.summons_open:
            return []  # a message, with only its close X
        if screen.page == "cog gallery" and self._cog in screen.summon_cogs:
            # Back from Issue a Cog Summons: the same cog's button again.
            return [PointerCommand("hover", summon_button(self._cog), "summon button")]
        if screen.tasks and self._task is not None:
            # Back from the delete dialog (cancelled): the same task again.
            return self._hover_task()
        if screen.page == "map":
            here = self._map_place(screen)
            if here is None:
                return []
            self._place = here[0]
            return [PointerCommand("hover", here[1], here[0])]
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
        if screen.page == "districts" and action in ("up", "down", "select"):
            return self._run_districts(action, screen)
        if screen.page == "map":
            return self._run_map(action, screen, now)
        if screen.page == "cog gallery":
            return self._run_cog_gallery(action, screen, now)
        if (screen.page == "gardening" and screen.top_current == ALBUM_TAB
                and action in ("up", "down", "stickUp", "stickDown")):
            return self._run_flower_album(action, screen, now)
        if action in ("up", "down") and (screen.page == "fishing" or
                                         (screen.page == "gardening" and screen.top_current == BUCKET_TAB)):
            return self._run_fishing(action, screen, now)
        if (screen.top_current is not None and screen.top_current == _CUSTOMIZE_TAB.get(screen.page)
                and action in ("left", "right", "select")):
            return self._run_customize(action, now)
        if (screen.page == "golf" and screen.top_current == GOLF_RECORDS_TAB
                and action in ("up", "down", "stickUp", "stickDown")):
            direction = action[5:].lower() if action.startswith("stick") else action
            self._held_scroll.clicked(action, GOLF_RECORDS_SCROLL[direction])
            return self._click(GOLF_RECORDS_SCROLL[direction], f"scroll records {direction}", now)
        if (screen.top_current is not None and screen.top_current == _TROPHY_TAB.get(screen.page)
                and action in _DIRECTIONS):
            return self._run_trophies(action, screen)
        if screen.page in _LISTS and action == "pageAction" and screen.fish:
            # Its confirm is the usual OK/Cancel dialog.
            self._releasing = True
            return self._click(_LISTS[screen.page][2], "release", now)
        if (screen.page == "events" and screen.top_current == CALENDAR_TAB
                and (action in _DIRECTIONS or action in MONTH_ARROWS or action == "filter")):
            return self._run_calendar(action, now)  # only its own: LT/RT still switch tabs
        if screen.page == "snapshots" and action in SNAPSHOT_ARROWS and action in screen.snapshot_arrows:
            return self._click(SNAPSHOT_ARROWS[action], f"snapshot {action}", now)
        if screen.page == "snapshots" and action == "pageAction" and screen.snapshot_trash:
            return self._click(SNAPSHOT_TRASH, "delete snapshot", now)  # then its Yep!/Cancel
        if screen.page == "cog disguise" and action in ("up", "down", "left", "right"):
            return self._run_disguise(action, screen, now)
        if screen.page == "resistance rank" and action in RANK_PAGE_ARROWS:
            return self._click(RANK_PAGE_ARROWS[action], f"rank page {action}", now)
        if screen.tasks and action in ("up", "down", "left", "right", "pageAction"):
            return self._run_tasks(action, screen, now)
        if screen.gags is not None and action in ("up", "down", "left", "right"):
            if self._gag is None or not screen.gags[self._gag[0]][self._gag[1]]:
                # Start on the cupcake (or the first gag you have, just in case).
                start = CUPCAKE if screen.gags[CUPCAKE[0]][CUPCAKE[1]] else next(
                    (r, c) for r in range(GAG_ROWS) for c in range(GAG_COLS) if screen.gags[r][c])
                self._gag = start
            else:
                self._gag = move(screen.gags, self._gag, action)
            r, c = self._gag
            return [PointerCommand("hover", gag_point(r, c), f"gag {r + 1},{c + 1}", size=GAG_SIZE)]
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
