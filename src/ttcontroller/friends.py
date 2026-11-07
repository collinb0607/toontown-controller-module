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

Some buttons ask first, in a pale yellow popup left of the panel: Go To a toon in
another district ("Do you want to switch to X?", Yes and No), and Friends on a toon
who already is one ("Stop being Toon friends", then "Are you sure...?", Yes and No).
A presses Yes or Stop being Toon friends, B No or Cancel, and once the popups are
done the hover goes back to the panel's button. Measured at 1920x1009
(friends_teleport_popup, friends_friends_popup, _confirmation): each popup is about
0.485 wide and its left edge moves a little, so it's found by its fill along a row
near its top; its buttons are placed from its middle (Yes and No 0.075 either side,
Cancel on it, Stop 0.0996 left and 0.0709 above Cancel), and their row, which
depends on the message, is searched for down those columns. The same popup with one
button on its middle says how it went: OK ("... is no longer your friend": A or B)
or Cancel ("Asking ... to be your friend": B; A does nothing).

A toon asking to be your friend shows a smaller peach popup near the top middle
("... would like to be your friend.", OK and No: A OK, B No), whatever else is open
(friends_friend_request_popup, 1920x1009: 0.336 wide, OK and No 0.041 either side
of its middle, its top 0.433 above the window's middle). It's found the same way.

Ignore and Report open a dialog in the middle of the window instead, with a green
border and its buttons 0.0755 above the border's bottom: Ignore and Cancel, Stop
Ignoring and Cancel, Cancel alone (a friend can't be ignored), or Report's reasons
(a column of yellow buttons) above Cancel (friends_ignore, friends_stop_ignoring,
friends_ignore_a_friend, friends_report_reason; 1920x1009). A presses the blue button,
B Cancel; on Report the D-pad moves through the reasons and A picks one. Other
centered dialogs (the gag shop's, gardening's, the book's) look the same, so these
are only looked for right after Ignore or Report was pressed here, and while one
dialog follows another.
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

_POPUP_FILL_Y = 0.04  # a row inside a popup's top, above its message
_POPUP_SCAN = (-1.3, -0.2)  # searched for between these, from the right edge
_POPUP_WIDTH = (0.42, 0.55)
_POPUP_BUTTONS = (0.15, 0.31)  # its buttons' row is between these, below the top
_POPUP_YES_NO_DX = 0.0749  # No right of the middle, Yes as far left
_POPUP_STOP = (-0.0996, -0.0709)  # Stop being Toon friends, from Cancel
# Ignore and Report's centered dialogs.
_DIALOG_REACH = 0.5  # its green border is within this of the window's middle, every way
_DIALOG_BUTTONS_DY = 0.0755  # its buttons' middle, above the border's bottom
_DIALOG_REASON_DX = -0.15  # Report's reasons are found down this column, from the middle
_DIALOG_SECONDS = 1.0  # how long after Ignore, Report or the last dialog one may still show

# A friend request: the smaller peach popup.
_REQUEST_FILL_Y = -0.42  # a row just inside its top, above its message (from the window's middle)
_REQUEST_SCAN = (-0.3, 0.7)  # searched for between these, from the window's middle
_REQUEST_WIDTH = (0.28, 0.40)
_REQUEST_BUTTONS = (-0.36, -0.20)  # its buttons' row is between these, from the window's middle
_REQUEST_DX = 0.0413  # OK left of its middle, No right
_YES_BLUE = ((0, -0.009), (-0.009, 0), (-0.006, -0.006), (-0.003, -0.006), (-0.008, -0.002), (0.008, 0.007))


def _is_no_red(c: RGB) -> bool:
    r, g, b = c
    return r > 165 and r - g > 60 and r - b > 60  # shaded, lighter at its top


def _is_yes_blue(c: RGB) -> bool:
    r, g, b = c
    return b > 170 and b - r > 55 and b - g > 40


def _is_stop_blue(c: RGB) -> bool:
    """Stop being Toon friends: a grayer blue-violet than Yes."""
    r, g, b = c
    return b > 120 and b - r > 30 and b - g > 25


def _is_border_green(c: RGB) -> bool:
    r, g, b = c
    return g > r + 40 and g > b + 30


def _is_dialog_blue(c: RGB) -> bool:
    """Ignore's and Stop Ignoring's blue: darker than Yes."""
    r, g, b = c
    return b > 140 and b - r > 60 and b - g > 45


def _is_reason_yellow(c: RGB) -> bool:
    r, g, b = c
    return r > 180 and g > 170 and b < 120


def _is_request_peach(c: RGB) -> bool:
    r, g, b = c
    return r > 245 and 215 < g < 240 and 180 < b < 210


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
    kind: str | None = None  # "list", "panel" (a toon's panel), "popup" (one of its buttons asking first), or None
    rows: tuple[ui.UIPoint, ...] = ()  # list: the names showing, top to bottom
    details: bool = False  # panel: Toon Details is open too
    whisper: bool = False  # list or panel: a whisper is open too (its X goes first on B)
    yes: ui.UIPoint | None = None  # popup: what A presses (Yes, Stop being Toon friends)
    no: ui.UIPoint | None = None  # and B (No, Cancel)
    popup: str = ""  # which: "yes/no", "already friends", "OK", "cancel", "friend request" or "dialog"
    options: tuple[ui.UIPoint, ...] = ()  # popup: Report's reasons, top to bottom


def _row(i: int) -> ui.UIPoint:
    """A row of an evenly spaced list (friends_all's spacing; the reader finds the real ones)."""
    return _right(_NAME_X, _ROW0 + i * _ROW_STEP)


# The names' rows aren't evenly spaced the same way every time (21.6 px apart in
# friends_all, 16.5 in friends_list_bug, both 1920x1009), so each name is found as its
# own band of text down the list. The hovered one sits on a yellow highlight that can
# touch the next name's text, so highlight and text are told apart.
_LIST_TOP, _LIST_BOTTOM = 0.1834, 0.3650  # the list's names lie between these, from the top
_BAND_MIN = 0.006  # a name's band is at least this tall
_BAND_GAP = 2  # pixels of nothing a name's band may have inside it (an i's dot)
_BAND_TALL = 0.024  # taller than this, a band is two names touching (a g's tail on the next): split
_BAND_EDGE = 0.007  # where to look for the split: this far inside either end


def _is_highlight(c: RGB) -> bool:
    r, g, b = c
    return r > 220 and g > 200 and b < 120


def _name_rows(width: int, height: int, get_pixel: PixelReader) -> list[ui.UIPoint]:
    """Where to click each name in the list, top to bottom."""
    unit = min(width, height)
    left = _right(_NAME_LEFT, 0).to_client(width, height)[0]
    xs = [left + round(k * 0.004 * unit) for k in range(20)]
    top, bottom = (round(y * unit) for y in (_LIST_TOP, _LIST_BOTTOM))
    kinds, inks = [], []
    for y in range(top, min(bottom, height)):
        pixels = [get_pixel(x, y) for x in xs if x < width]
        ink = sum(min(c) < 180 for c in pixels)
        inks.append(ink)
        if sum(_is_highlight(c) for c in pixels) >= 3:
            kinds.append("h")
        elif ink >= 2:
            kinds.append("t")
        else:
            kinds.append(".")
    bands: list[list] = []  # [kind, first y, last y]
    for i, kind in enumerate(kinds):
        y = top + i
        if kind == ".":
            continue
        if bands and bands[-1][0] == kind and y - bands[-1][2] <= _BAND_GAP + 1:
            bands[-1][2] = y
        else:
            bands.append([kind, y, y])
    split: list[tuple[int, int]] = []
    for kind, first, last in bands:
        while kind == "t" and last - first + 1 > _BAND_TALL * unit:
            # Two names touching: split at the thinnest row away from the ends.
            edge = round(_BAND_EDGE * unit)
            cut = min(range(first + edge, last - edge + 1), key=lambda y: inks[y - top])
            split.append((first, cut - 1))
            first = cut + 1
        split.append((first, last))
    rows = [ui.UIPoint("right", _NAME_X, (first + last) / 2 / unit, "top") for first, last in split
            if last - first + 1 >= _BAND_MIN * unit]
    return rows[:VISIBLE_ROWS]


def _red_run(width: int, height: int, get_pixel: PixelReader, x: int, top: int, bottom: int,
             unit: int, test: Callable[[RGB], bool] = None, size: float = 0.03) -> tuple[int, int] | None:
    """The first red (or test's) button down column x, about size tall: its color's top
    and bottom (the white X or tick in its middle is inside that)."""
    test = test or _is_no_red
    first = next((y for y in range(max(0, top), min(height, bottom), 2) if test(get_pixel(x, y))), None)
    if first is None:
        return None
    hits = [y for y in range(first, min(height, first + round(1.35 * size * unit))) if test(get_pixel(x, y))]
    if hits[-1] - hits[0] < 0.65 * size * unit:
        return None
    return hits[0], hits[-1]


def _fill_run(width: int, get_pixel: PixelReader, y: int, left: int, right: int, unit: int,
              test: Callable[[RGB], bool]) -> tuple[int, int] | None:
    """The longest run of a popup's fill along row y."""
    step = max(1, unit // 300)
    xs = [x for x in range(max(0, left), min(width - 1, right), step) if test(get_pixel(x, y))]
    runs, start = [], None
    for i, x in enumerate(xs):
        start = x if start is None else start
        if i + 1 == len(xs) or xs[i + 1] - x > 2 * step:
            runs.append((start, x))
            start = None
    return max(runs, key=lambda r: r[1] - r[0], default=None)


def _read_request(width: int, height: int, get_pixel: PixelReader) -> FriendsScreen | None:
    unit = min(width, height)

    def at(p: ui.UIPoint) -> RGB:
        return get_pixel(*p.to_client(width, height))

    y = round(height / 2 + _REQUEST_FILL_Y * unit)
    left, right = (round(width / 2 + dx * unit) for dx in _REQUEST_SCAN)
    run = _fill_run(width, get_pixel, y, left, right, unit, _is_request_peach)
    if run is None or not _REQUEST_WIDTH[0] * unit <= run[1] - run[0] <= _REQUEST_WIDTH[1] * unit:
        return None
    middle = (run[0] + run[1]) / 2
    no_x = round(middle + _REQUEST_DX * unit)
    top, bottom = (round(height / 2 + dy * unit) for dy in _REQUEST_BUTTONS)
    red = _red_run(width, height, get_pixel, no_x, top, bottom, unit, size=0.023)
    if red is None:
        return None
    no = ui.UIPoint("center", (no_x - width / 2) / unit, (sum(red) / 2 - height / 2) / unit, "center")
    ok = no.offset(-2 * _REQUEST_DX, 0)
    if (sum(_is_no_red(at(p)) for p in ui.around(no, 0.007)) >= 3
            and sum(_is_yes_blue(at(p)) for p in ui.around(ok, 0.007)) >= 3
            and _is_request_peach(at(no.offset(-_REQUEST_DX, 0)))):
        return FriendsScreen("popup", yes=ok, no=no, popup="friend request")
    return None


def _read_popup(width: int, height: int, get_pixel: PixelReader) -> FriendsScreen | None:
    unit = min(width, height)

    def at(p: ui.UIPoint) -> RGB:
        return get_pixel(*p.to_client(width, height))

    # The popup's fill across a row just inside its top, right of the middle.
    y = round(_POPUP_FILL_Y * unit)
    left, right = (round(width + dx * unit) for dx in _POPUP_SCAN)
    run = _fill_run(width, get_pixel, y, left, right, unit, _is_popup_yellow)
    if run is None or not _POPUP_WIDTH[0] * unit <= run[1] - run[0] <= _POPUP_WIDTH[1] * unit:
        return _read_request(width, height, get_pixel)
    middle = (run[0] + run[1]) / 2
    top, bottom = (round(y * unit) for y in _POPUP_BUTTONS)

    def point(x: float, y: float) -> ui.UIPoint:
        return ui.UIPoint("right", (x - width) / unit, y / unit)

    # Yes and No either side of the middle (Go To's district switch, unfriending's confirm).
    no_x = round(middle + _POPUP_YES_NO_DX * unit)
    red = _red_run(width, height, get_pixel, no_x, top, bottom, unit)
    if red is not None:
        no = point(no_x, sum(red) / 2)
        yes = no.offset(-2 * _POPUP_YES_NO_DX, 0)
        if (sum(_is_no_red(at(p)) for p in ui.around(no, 0.009)) >= 3
                and sum(_is_yes_blue(at(yes.offset(dx, dy))) for dx, dy in _YES_BLUE) >= 4
                and _is_popup_yellow(at(no.offset(-_POPUP_YES_NO_DX, 0)))):
            return FriendsScreen("popup", yes=yes, no=no, popup="yes/no")
    # Already friends: Stop being Toon friends above, Cancel on the middle.
    red = _red_run(width, height, get_pixel, round(middle), top, bottom, unit)
    if red is not None:
        cancel = point(middle, sum(red) / 2)
        stop = cancel.offset(*_POPUP_STOP)
        if (sum(_is_no_red(at(p)) for p in ui.around(cancel, 0.009)) >= 3
                and _is_popup_yellow(at(cancel.offset(0.1, 0))) and _is_popup_yellow(at(cancel.offset(-0.1, 0)))):
            if sum(_is_stop_blue(at(p)) for p in ui.around(stop, 0.008)) >= 3:
                return FriendsScreen("popup", yes=stop, no=cancel, popup="already friends")
            return FriendsScreen("popup", no=cancel, popup="cancel")  # asking a toon to be friends
    # OK on the middle ("... is no longer your friend").
    blue = _red_run(width, height, get_pixel, round(middle), top, bottom, unit, test=_is_yes_blue)
    if blue is not None:
        ok = point(middle, sum(blue) / 2)
        if (sum(_is_yes_blue(at(ok.offset(dx, dy))) for dx, dy in _YES_BLUE) >= 4
                and _is_popup_yellow(at(ok.offset(0.1, 0))) and _is_popup_yellow(at(ok.offset(-0.1, 0)))):
            return FriendsScreen("popup", yes=ok, no=ok, popup="OK")
    return _read_request(width, height, get_pixel)


def _clusters(xs: list[int], gap: int) -> list[tuple[int, int]]:
    runs, start = [], None
    for i, x in enumerate(xs):
        start = x if start is None else start
        if i + 1 == len(xs) or xs[i + 1] - x > gap:
            runs.append((start, x))
            start = None
    return runs


def _read_dialog(width: int, height: int, get_pixel: PixelReader) -> FriendsScreen | None:
    """Ignore's and Report's dialogs, in the middle of the window."""
    unit = min(width, height)
    cx, cy = width // 2, height // 2
    reach = round(_DIALOG_REACH * unit)

    def edge(points) -> int | None:
        return next((i for i, (x, y) in enumerate(points) if _is_border_green(get_pixel(x, y))), None)

    down = edge([(cx, y) for y in range(cy, min(height, cy + reach))])
    up = edge([(cx, y) for y in range(cy, max(-1, cy - reach), -1)])
    left = edge([(x, cy) for x in range(cx, max(-1, cx - reach), -1)])
    right = edge([(x, cy) for x in range(cx, min(width, cx + reach))])
    if None in (down, up, left, right) or min(left, right) < 0.2 * unit:
        return None
    bottom, top = cy + down, cy - up
    row = bottom - round(_DIALOG_BUTTONS_DY * unit)
    xs = range(cx - left + 4, cx + right - 4)
    gap = round(0.025 * unit)  # across the white X or tick in a button's middle
    reds = _clusters([x for x in xs if _is_no_red(get_pixel(x, row))], gap)
    blues = _clusters([x for x in xs if _is_dialog_blue(get_pixel(x, row))], gap)
    reds = [r for r in reds if r[1] - r[0] >= 0.015 * unit]
    blues = [b for b in blues if b[1] - b[0] >= 0.015 * unit]
    if len(reds) > 1 or len(blues) > 1 or not (reds or blues):
        return None

    def button(run: tuple[int, int], test) -> ui.UIPoint | None:
        x = (run[0] + run[1]) // 2
        found = _red_run(width, height, get_pixel, x, row - round(0.03 * unit), row + round(0.03 * unit), unit,
                         test=test)
        if found is None:
            return None
        return ui.UIPoint("center", (x - width / 2) / unit, (sum(found) / 2 - height / 2) / unit, "center")

    no = button(reds[0], _is_no_red) if reds else None
    yes = button(blues[0], _is_dialog_blue) if blues else None
    if (reds and no is None) or (blues and yes is None):
        return None
    options = ()
    if no is not None and yes is None:
        # Report's reasons: yellow buttons down a column (their lettering is part of them;
        # the pale fill between them isn't).
        x = cx + round(_DIALOG_REASON_DX * unit)
        stop = no.to_client(width, height)[1] - round(0.04 * unit)
        runs, start, yellow = [], None, 0
        for y in range(top + 2, stop):
            c = get_pixel(x, y)
            inside = not _is_popup_yellow(c) and not _is_border_green(c)
            if inside and start is None:
                start, yellow = y, 0
            if inside:
                yellow += _is_reason_yellow(c)
            elif start is not None:
                if yellow >= 0.015 * unit and 0.025 * unit <= y - start <= 0.055 * unit:
                    runs.append((start + y - 1) / 2)
                start = None
        options = tuple(ui.UIPoint("center", 0.0, (y - height / 2) / unit, "center") for y in runs)
    return FriendsScreen("popup", yes=yes if yes is not None else None, no=no if no is not None else yes,
                         popup="dialog", options=options)


def _whispering(width: int, height: int, get_pixel: PixelReader) -> bool:
    return (ui.is_visible(ui.WHISPER_CLOSE, width, height, get_pixel)
            and ui.is_visible(ui.WHISPER_BAR, width, height, get_pixel))


def read_friends(width: int, height: int, get_pixel: PixelReader, dialogs: bool = False) -> FriendsScreen:
    """dialogs: Ignore or Report was just pressed, so look for their dialogs too."""
    popup = _read_popup(width, height, get_pixel)
    if popup is not None:
        return popup
    if dialogs:
        dialog = _read_dialog(width, height, get_pixel)
        if dialog is not None:
            return dialog
    if ui.is_visible(ui.FRIENDS_CLOSE, width, height, get_pixel):
        rows = []
        rows = _name_rows(width, height, get_pixel)
        return FriendsScreen("list", rows=tuple(rows), whisper=_whispering(width, height, get_pixel))
    if ui.is_visible(PORTRAIT, width, height, get_pixel):
        return FriendsScreen("panel", details=ui.is_visible(DETAILS, width, height, get_pixel),
                             whisper=_whispering(width, height, get_pixel))
    return FriendsScreen()


FRIENDS_ACTIONS = {
    "up": "move up the list (scrolling at the top), or up the toon's buttons",
    "down": "move down the list (scrolling at the bottom), or down the toon's buttons",
    "left": "previous page of the list", "right": "next page of the list",
    "select": "open the highlighted toon, or press the highlighted button (in a popup: Yes, OK, Ignore, Stop being Toon friends, or the Report reason hovered)",
    "back": "end a whisper (its X), then close Toon Details, the toon's panel, or the list (in a popup: No or Cancel)",
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
        self._from_popup = False  # a popup was answered: keep the panel's button when it's back
        self._dialog_until = float("-inf")  # Ignore's or Report's dialog may show until then
        self.option: int | None = None  # Report's reason hovered (None: none yet)
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

    def expects_dialog(self, now: float) -> bool:
        """Ignore or Report was just pressed (or one of their dialogs just showed): read
        the centered dialogs too."""
        return now < self._dialog_until

    def update(self, buttons: frozenset[str], now: float, screen: FriendsScreen) -> list[PointerCommand]:
        if screen.popup == "dialog":
            self._dialog_until = now + _DIALOG_SECONDS
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
            self.option = None
            if screen.kind == "list":
                self.row = 0
                commands += self._hover_row(screen)
            elif screen.kind == "panel":
                if not self._from_popup:
                    self.button = 0
                commands.append(self._hover_button())
            if screen.kind != "popup":
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
        if screen.kind == "popup" and screen.options and action in ("up", "down"):
            # Report's reasons: the first press hovers the top one.
            step = -1 if action == "up" else 1
            self.option = 0 if self.option is None else max(0, min(len(screen.options) - 1, self.option + step))
            return [PointerCommand("hover", screen.options[self.option], f"reason {self.option + 1}")]
        if screen.kind == "popup" and screen.options and action == "select":
            if self.option is None:
                return []
            self.option = min(self.option, len(screen.options) - 1)
            self._dialog_until = now + _DIALOG_SECONDS
            commands = self._click(screen.options[self.option], f"reason {self.option + 1}", now)
            self._from_popup = True
            return commands
        if screen.kind == "popup":
            if action not in ("select", "back") or (screen.yes if action == "select" else screen.no) is None:
                return []
            if screen.popup == "dialog":
                self._dialog_until = now + _DIALOG_SECONDS  # another may follow
            point, name = (screen.yes, f"{screen.popup} yes") if action == "select" else (screen.no, f"{screen.popup} no")
            commands = self._click(point, name, now)
            self._from_popup = True
            return commands
        if action == "back" and screen.whisper:
            # The whisper's X first; the list or panel stays, on the same row or button.
            again = self._hover_row(screen) if screen.kind == "list" else [self._hover_button()]
            return [PointerCommand("click", ui.WHISPER_CLOSE.center, "close whisper"), *again]
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
            if point in (IGNORE, REPORT):
                self._dialog_until = now + self.settle_seconds + _DIALOG_SECONDS
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
