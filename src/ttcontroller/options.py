"""TTR's own Options window (Shift+Esc in game, or the Options icon before it).

A beige panel with four tabs along its top (Gameplay, Controls, Audio, Video: the
open one beige, the rest blue) and a round blue X at its top right. Below the tab's
title, a scrolling list of settings: a label on the left (some with a small blue ?
that explains the setting when hovered) and its control right-aligned on the right,
a toggle (green and yellow when on, yellow and brown when off), a dropdown (blue
outline), a yellow button, or a slider (Audio's volumes: a thin blue track with a
yellow knob). A tab can end in a centered button (Reset to Default).
A yellow knob on the right shows how far the list is scrolled.

The rows aren't kept as a fixed layout: each read scans a column through the
right-aligned controls (and one down the middle, for centered buttons) and finds
what's showing, so it works at any scroll position and on every tab.

Popups over it: an open dropdown's list (the same blue, taller than the box; a long
one, like Video's Resolution, runs past the list's clip and scrolls with the page), the
usual OK/Cancel-style dialog (ToonSync's Copy and Close) dimming the window, and the
Pronoun Picker: three lavender lists, the choice in a purple band, green arrows.

Measured at 1920x1009.
"""

from collections.abc import Callable
from dataclasses import dataclass

from . import ui
from .battle import PointerCommand
from .bindings import Bindings, ButtonActions
from .dialog import find_ok_cancel
from .held_scroll import HeldScroll

PixelReader = Callable[[int, int], ui.RGB]


def _center(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "center")


CLOSE = _center(0.4346, -0.2740)  # the X's white middle; blue either side
_CLOSE_SIDE = 0.0228
TABS = tuple(_center(x, -0.3266) for x in (-0.3052, -0.1021, 0.1011, 0.3042))
TAB_NAMES = ("gameplay", "controls", "audio", "video")
_TAB_PROBES = tuple(_center(x, -0.3414) for x in (-0.3469, -0.1437, 0.0595, 0.2626))  # off the icons
_PANEL_PROBES = (_center(-0.3766, -0.2027), _center(0.3667, -0.2027))  # either side of the title

# The scrolling list: where it's cut off, and the columns scanned for controls.
CLIP_TOP, CLIP_BOTTOM = -0.1650, 0.3137
_RIGHT_X = 0.3370  # through every right-aligned control
_MIDDLE_X = 0.0  # through centered buttons
_PANEL_LEFT, _PANEL_RIGHT = -0.43, 0.40  # how far a control's edges are looked for
_MIN_HEIGHT, _MAX_HEIGHT = 0.03, 0.075  # a control's height (an open dropdown list is taller)
_TOGGLE_MAX_WIDTH = 0.11
_TRACK_MIN_HEIGHT = 0.012  # a slider's track, where the knob isn't over the scanned column
_SLIDER_MIN_WIDTH = 0.2
SLIDER_KNOB = (0.046, 0.045)  # the knob's width and height
SLIDER_STEP = 0.05  # of the way along, per press
_HELP_X, _HELP_SIDE_X = -0.4054, -0.4123  # the ?'s white middle, and its blue left side
_KNOB_X, _KNOB_TOP, _KNOB_BOTTOM = 0.4093, -0.1219, 0.2834
DROPDOWN_STEP = 0.0446  # between the items of an open dropdown
_DROPDOWN_PAD = 0.004  # from the list's outline to its first item
# A list cut off by the clip: its items are found from their lines of text, down a strip
# through the start of each (they're left-aligned), every few pixels across.
_TEXT_STRIP = (0.03, 0.13)  # from the list's left edge
_TEXT_MIN_HEIGHT = 0.012

# The frame's color in Options: the tabs' blue (gold is hard to see on the beige).
FRAME_BLUE = (29, 144, 227)

# The Pronoun Picker: three lists (left to right), each with arrows above and below.
PRONOUN_XS = (-0.2577, 0.0040, 0.2656)
PRONOUN_BOX_Y, PRONOUN_BOX_SIZE = -0.0803, (0.172, 0.192)
PRONOUN_DOWN_Y = 0.0282
PRONOUN_UP_Y = -0.1888  # not seen yet (hidden at the top of a list): the down arrow's mirror
_PRONOUN_LIST_YS = (-0.1432, -0.0243)
_PRONOUN_BAND_Y = -0.0917
_PRONOUN_SIDE = -0.07  # left of the lists' (centered) words
_PRONOUN_FILL = (_center(-0.1288, -0.1432), _center(0.1388, -0.1432))
PRONOUN_RESET = _center(-0.1269, 0.2453)
PRONOUN_DONE = _center(0.1269, 0.2453)  # Looks fine!


@dataclass(frozen=True)
class Row:
    kind: str  # "toggle", "dropdown", "button" or "slider"
    y: float  # the control's middle, from the window's center
    left: float  # the control's edges
    right: float
    height: float
    on: bool | None = None  # a toggle's state
    help_y: float | None = None  # where its ? is, if it has one
    knob: float | None = None  # a slider's knob (its middle); left and right are its track's ends

    @property
    def point(self) -> ui.UIPoint:
        """Where to hover and click it (a slider: its knob)."""
        if self.knob is not None:
            return _center(self.knob, self.y)
        return _center((self.left + self.right) / 2, self.y)

    @property
    def help(self) -> ui.UIPoint | None:
        return None if self.help_y is None else _center(_HELP_X, self.help_y)

    @property
    def centered(self) -> bool:
        """A button in the middle of the panel (Reset to Default), not a row's control."""
        return self.right < 0.3


@dataclass(frozen=True)
class OptionsScreen:
    # "options", "dropdown" (a dropdown's list open), "dialog" (OK/Cancel-style) or "pronouns"
    kind: str | None = None
    tab: int | None = None
    rows: tuple[Row, ...] = ()  # fully in view, top to bottom
    cut: tuple[bool, bool] = (False, False)  # a control cut off at the top, at the bottom
    can_scroll: tuple[bool, bool] = (False, False)  # up, down (from the knob)
    items: tuple[ui.UIPoint, ...] = ()  # an open dropdown's items in view, top to bottom
    item_size: tuple[float, float] = (0.0, 0.0)
    more: tuple[bool, bool] = (False, False)  # an open dropdown cut off at the top, at the bottom
    list_edges: tuple[float | None, float | None] = (None, None)  # its top and bottom, if in view
    dialog: tuple[ui.UIPoint, ui.UIPoint] | None = None


def is_panel(c: ui.RGB) -> bool:
    """The beige panel (lighter toward its middle), not a control's yellow or white."""
    r, g, b = c
    return r >= 232 and 4 <= r - g <= 26 and 155 <= b <= 228 and g - b >= 22


def _is_outline_blue(c: ui.RGB) -> bool:
    r, g, b = c
    return b > 215 and r < 100 and 130 < g < 210


def _is_vivid(c: ui.RGB) -> bool:
    """A usable control's yellow, brown (a toggle that's off) or blue outline. Greyed-out
    ones (the toon's preferences before logging in) are washed out."""
    r, g, b = c
    return (_is_outline_blue(c) or (r > 235 and g > 225 and b < 120)
            or (r < 175 and g < 135 and b < 100 and r - b > 50))


def _is_list_fill(c: ui.RGB) -> bool:
    r, g, b = c
    return b > 240 and g > 225 and 195 < r < 240


def _is_text(c: ui.RGB) -> bool:
    return max(c) < 130


def _is_track_blue(c: ui.RGB) -> bool:
    r, g, b = c
    return 50 < r < 115 and 160 < g < 210 and b > 210


def _is_white(c: ui.RGB) -> bool:
    return min(c) > 225


def _is_help_blue(c: ui.RGB) -> bool:
    r, g, b = c
    return b > 180 and b - r > 150


def _is_knob(c: ui.RGB) -> bool:
    r, g, b = c
    return r > 225 and g > 215 and abs(r - g) < 14 and b < 210


def _is_warm(c: ui.RGB) -> bool:
    """The open tab's beige, bright or dimmed under a popup."""
    r, g, b = c
    return r > 90 and r > b + 15 and g > b


def _is_tab_blue(c: ui.RGB) -> bool:
    r, g, b = c
    return b > 80 and b > r + 60


def _is_lavender(c: ui.RGB) -> bool:
    r, g, b = c
    return b > 240 and 185 < r < 225 and 185 < g < 225


def _is_band_purple(c: ui.RGB) -> bool:
    r, g, b = c
    return b > 230 and r > 190 and g < 160


def _is_picker_fill(c: ui.RGB) -> bool:
    r, g, b = c
    return r > 235 and g > 235 and 160 < b < 215


def read_options(width: int, height: int, get_pixel: PixelReader) -> OptionsScreen:
    unit = min(width, height)

    def at(p: ui.UIPoint) -> ui.RGB:
        return get_pixel(*p.to_client(width, height))

    def px(x: float, y: float) -> ui.RGB:
        return get_pixel(round(width / 2 + x * unit), round(height / 2 + y * unit))

    # The Pronoun Picker covers the X and most of the tabs.
    if (all(_is_lavender(px(x + _PRONOUN_SIDE, y)) for x in PRONOUN_XS for y in _PRONOUN_LIST_YS)
            and all(_is_band_purple(px(x + _PRONOUN_SIDE, _PRONOUN_BAND_Y)) for x in PRONOUN_XS)
            and all(_is_picker_fill(at(p)) for p in _PRONOUN_FILL)):
        return OptionsScreen("pronouns")

    middle = at(CLOSE)
    if not (min(middle) > 105 and max(middle) - min(middle) < 40
            and all(_is_tab_blue(at(CLOSE.offset(dx, 0))) for dx in (-_CLOSE_SIDE, _CLOSE_SIDE))):
        return OptionsScreen()
    warm = [i for i, p in enumerate(_TAB_PROBES) if _is_warm(at(p))]
    blue = sum(_is_tab_blue(at(p)) for p in _TAB_PROBES)
    if len(warm) != 1 or blue != 3:
        return OptionsScreen()
    tab = warm[0]
    dialog = find_ok_cancel(width, height, get_pixel)
    if dialog is not None:
        return OptionsScreen("dialog", tab, dialog=dialog)
    if not all(is_panel(at(p)) for p in _PANEL_PROBES):
        return OptionsScreen()

    top, bottom = (round(height / 2 + y * unit) for y in (CLIP_TOP, CLIP_BOTTOM))
    to_y = lambda py: (py - height / 2) / unit
    to_x = lambda qx: (qx - width / 2) / unit

    def runs(x: float) -> list[tuple[int, int]]:
        """Stretches of the column that aren't panel (gaps of a pixel or two bridged)."""
        qx = round(width / 2 + x * unit)
        found: list[list[int]] = []
        for py in range(top, bottom + 1):
            if not is_panel(get_pixel(qx, py)):
                if found and py - found[-1][1] <= 3:
                    found[-1][1] = py
                else:
                    found.append([py, py])
        return [(a, b) for a, b in found]

    def edges(py: int, qx: int) -> tuple[int, int]:
        """A control's left and right edges along a row: where the panel starts again."""
        lo, hi = round(width / 2 + _PANEL_LEFT * unit), round(width / 2 + _PANEL_RIGHT * unit)
        out = []
        for step, stop in ((-1, lo), (1, hi)):
            x, panel = qx, 0
            while x != stop and panel < 4:
                x += step
                panel = panel + 1 if is_panel(get_pixel(x, py)) else 0
            out.append(x - step * panel)
        return out[0], out[1]

    def find_help(py: int) -> float | None:
        """The ? left of a row's label, a little above the control's middle: its blue
        left side down a short column, white at its middle."""
        qx, wx = (round(width / 2 + x * unit) for x in (_HELP_SIDE_X, _HELP_X))
        ys = [y for y in range(py - round(0.025 * unit), py + round(0.01 * unit) + 1)
              if _is_help_blue(get_pixel(qx, y))]
        if len(ys) < 0.008 * unit:
            return None
        y = (ys[0] + ys[-1]) // 2
        if not any(_is_white(get_pixel(wx, y + d)) for d in range(-round(0.008 * unit), round(0.008 * unit) + 1)):
            return None
        return to_y(y)

    def slider(py: int, qx: int) -> Row | None:
        """A slider along this line: mostly its track's blue, with the knob the stretch
        that isn't."""
        left, right = edges(py, qx)
        if (right - left) / unit < _SLIDER_MIN_WIDTH:
            return None
        xs = range(left + 6, right - 5)
        blue = [_is_track_blue(get_pixel(x, py)) for x in xs]
        if sum(blue) < 0.5 * len(blue):
            return None
        knob = [x for x, b in zip(xs, blue) if not b]
        mid = (knob[0] + knob[-1]) / 2 if knob else (left + right) / 2
        return Row("slider", to_y(py), to_x(left), to_x(right), SLIDER_KNOB[1], knob=to_x(mid),
                   help_y=find_help(py))

    def cut_list(a: int, b: int, qx: int) -> OptionsScreen | None:
        """A dropdown's list running past the clip: mostly its pale blue fill down the
        column, with its items where the lines of text are."""
        if sum(_is_list_fill(get_pixel(qx, py)) for py in range(a, b + 1)) < 0.6 * (b - a + 1):
            return None
        hi, lo = a > top, b < bottom - 2  # its top and bottom outlines in view
        if hi and not any(_is_outline_blue(get_pixel(qx, py)) for py in range(a, min(b, a + 4) + 1)):
            return None
        left, right = edges((a + b) // 2, qx)
        xs = range(left + round(_TEXT_STRIP[0] * unit), left + round(_TEXT_STRIP[1] * unit), 3)
        lines: list[list[int]] = []
        for py in range(a, b + 1):
            if any(_is_text(get_pixel(x, py)) for x in xs):
                if lines and py - lines[-1][1] <= 2:
                    lines[-1][1] = py
                else:
                    lines.append([py, py])
        ys = [to_y((s + e) / 2) for s, e in lines
              if s > top + 1 and e < bottom - 3 and (e - s + 1) / unit >= _TEXT_MIN_HEIGHT]
        if not ys:
            return None
        mid = (to_x(left) + to_x(right)) / 2
        return OptionsScreen("dropdown", tab, items=tuple(_center(mid, y) for y in ys),
                             item_size=((right - left) / unit, DROPDOWN_STEP), more=(not hi, not lo),
                             list_edges=(to_y(a) if hi else None, to_y(b) if lo else None))

    rows: list[Row] = []
    cut = [False, False]
    for column in (_RIGHT_X, _MIDDLE_X):
        qx = round(width / 2 + column * unit)
        for a, b in runs(column):
            h = (b - a + 1) / unit
            if column == _RIGHT_X and h > _MAX_HEIGHT and (a <= top or b >= bottom - 2):
                found = cut_list(a, b, qx)
                if found is not None:
                    return found
            if a <= top or b >= bottom - 2:
                if column == _RIGHT_X:
                    cut[0 if a <= top else 1] = True
                continue
            if not any(_is_vivid(get_pixel(qx, py)) for py in range(a, b + 1)):
                continue
            if column == _RIGHT_X and _TRACK_MIN_HEIGHT <= h <= _MAX_HEIGHT:
                found = slider((a + b) // 2, qx)
                if found is not None:
                    rows.append(found)
                    continue
            if h < _MIN_HEIGHT:
                continue
            blue = any(_is_outline_blue(get_pixel(qx, py)) for py in range(a, min(b, a + 4) + 1))
            if blue and h > _MAX_HEIGHT and column == _RIGHT_X:
                # A dropdown's list, open over the rows below it.
                left, right = edges(a + round(0.02 * unit), qx)
                count = max(1, round((h - 2 * _DROPDOWN_PAD) / DROPDOWN_STEP))
                ys = [to_y(a) + _DROPDOWN_PAD + DROPDOWN_STEP * (i + 0.5) for i in range(count)]
                mid = (to_x(left) + to_x(right)) / 2
                return OptionsScreen("dropdown", tab, items=tuple(_center(mid, y) for y in ys),
                                     item_size=((right - left) / unit, DROPDOWN_STEP),
                                     list_edges=(to_y(a), to_y(b)))
            if h > _MAX_HEIGHT:
                continue
            mid_y = (a + b) // 2
            if any(abs(r.y - to_y(mid_y)) < 0.02 for r in rows):
                continue  # already found down the other column (a wide dropdown)
            left, right = edges(mid_y, qx)
            if column == _MIDDLE_X and to_x(right) > 0.3:
                continue  # a right-aligned control, missed by the first column
            w = (right - left) / unit
            if blue:
                kind, on = "dropdown", None
            elif w < _TOGGLE_MAX_WIDTH:
                # On: green on the left (the knob on the right); off: the knob on the left.
                g = get_pixel(left + round(0.012 * unit), mid_y)
                kind, on = "toggle", g[1] > g[0] + 20 and g[2] > 100
            else:
                kind, on = "button", None
            rows.append(Row(kind, to_y(mid_y), to_x(left), to_x(right), h, on, find_help(mid_y)))

    rows.sort(key=lambda r: r.y)
    # The knob: the longest stretch of its yellow down the track (a stray pixel can pass).
    kx = round(width / 2 + _KNOB_X * unit)
    knob, run = (0, -1), None
    for py in range(top, bottom + 1):
        if _is_knob(get_pixel(kx, py)):
            run = (run[0] if run else py, py)
            if run[1] - run[0] > knob[1] - knob[0]:
                knob = run
        elif run and py - run[1] > 2:
            run = None
    if knob[1] - knob[0] > 0.02 * unit:
        y = to_y((knob[0] + knob[1]) / 2)
        can_scroll = (y > _KNOB_TOP + 0.006, y < _KNOB_BOTTOM - 0.006)
    else:
        can_scroll = (False, False)
    return OptionsScreen("options", tab, tuple(rows), (cut[0], cut[1]), can_scroll)



# --- Controls -------------------------------------------------------------------

_ROW_FRAME_LEFT = -0.4242  # left of the ? icons
_FRAME_PAD = 0.012
DROPDOWN_CLOSE_X = -0.30  # somewhere on the panel that does nothing: clicking off a list closes it
_SAME_ROW = 0.012  # rows closer than this (after a scroll is allowed for) are the same row
SCROLL_NOTCHES = 2  # per wheel turn when moving past the rows in view
MAX_SCROLLS = 6  # turns tried before giving up on finding a row further on
STICK_SETTLE_SECONDS = 0.2  # after the right stick scrolls, before the row under the cursor is hovered


def row_frame(row: Row) -> tuple[ui.UIPoint, tuple[float, float]]:
    """Where the highlight frame goes for a row, and its size: around the whole row
    (its ? and label too) so it's clear which setting it is, or just around a
    centered button."""
    height = max(row.height, 0.05) + _FRAME_PAD
    if row.centered:
        return row.point, (row.right - row.left + _FRAME_PAD, height)
    right = row.right + _FRAME_PAD / 2
    return _center((_ROW_FRAME_LEFT + right) / 2, row.y - 0.004), (right - _ROW_FRAME_LEFT, height)


def _shift(before: tuple[Row, ...], after: tuple[Row, ...], direction: int) -> float | None:
    """How far the rows moved between two reads (negative is up), from the shift that
    lines the most of them up again, kind for kind. direction: +1 if the list was
    scrolled down (so the rows moved up), -1 if up."""
    best: tuple[int, float] | None = None
    for b in before:
        for a in after:
            d = a.y - b.y
            if a.kind != b.kind or d * direction > 0.003:
                continue
            score = sum(any(x.kind == y.kind and abs(y.y + d - x.y) < 0.008 for x in after) for y in before)
            if best is None or (score, -abs(d)) > (best[0], -abs(best[1])):
                best = (score, d)
    return None if best is None else best[1]


def default_options_bindings() -> Bindings:
    press = {"a": "select", "b": "back", "start": "close", "y": "help", "x": "reset",
             "lt": "prevTab", "rt": "nextTab", "rs_up": "scrollUp", "rs_down": "scrollDown"}
    for direction in ("up", "down", "left", "right"):
        press[f"dpad_{direction}"] = direction
        press[f"ls_{direction}"] = direction
    return Bindings(press=press)


OPTIONS_ACTIONS = {
    "select": "the hovered setting: flip a toggle, open a dropdown, press a button; in a list, pick the item",
    "back": "close a dropdown's list, cancel a popup, or close Options",
    "close": "close Options (or the list or popup open in it)",
    "help": "show what the hovered setting does (hovers its ?); again to go back",
    "reset": "Pronoun Picker: its Reset button",
    "prevTab": "the tab to the left", "nextTab": "the tab to the right",
    "scrollUp": "scroll the settings up", "scrollDown": "scroll the settings down",
    "up": "the setting above (scrolling when it's out of view)", "down": "the setting below",
    "left": "a toggle: off; a slider: down a step; Pronoun Picker: the list to the left",
    "right": "a toggle: on; a slider: up a step; Pronoun Picker: the list to the right",
}

_MOVES = ("up", "down", "left", "right", "scrollUp", "scrollDown")


@dataclass
class _ListScroll:
    """A wheel notch turned past the end of a dropdown's list in view."""
    direction: int  # +1 down, -1 up
    edges: tuple[float | None, float | None]  # the list's top and bottom before, if in view
    y: float  # the hovered item's middle before


@dataclass
class _Scroll:
    direction: int  # +1 down, -1 up
    before: tuple[Row, ...]
    y: float  # where the row it's moving from was (or would be), before the scroll
    tries: int


class OptionsMapper:
    def __init__(self, bindings: Bindings | None = None, settle_seconds: float = 0.25):
        self.settle_seconds = settle_seconds
        self._held_scroll = HeldScroll()
        self.set_bindings(bindings or default_options_bindings())
        self._forget()

    def set_bindings(self, bindings: Bindings) -> None:
        self.bindings = bindings
        self._actions = ButtonActions(bindings, 0.5, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in _MOVES)

    @property
    def buttons(self) -> set[str]:
        return self.bindings.buttons()

    def _forget(self) -> None:
        self._kind: str | None = None
        self.tab: int | None = None
        self.row_y: float | None = None  # the hovered row's control, from the window's center
        self.on_help = False
        self.item = 0  # in an open dropdown
        self.column = 0  # in the Pronoun Picker
        self._settle_until = 0.0
        self._scroll: _Scroll | None = None
        self._list_scroll: _ListScroll | None = None
        self._notch: float | None = None  # how far a notch moved a dropdown's list, once seen
        self._stick: tuple[float, float | None] | None = None  # (when, row y) after a right stick scroll
        # Where the last drag left a slider's knob (row y, knob x, when): a read taken
        # while it's still moving would be behind.
        self._dragged: tuple[float, float, float] | None = None

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)
        self._held_scroll.stop(finish=False)

    def hovering(self, screen: OptionsScreen) -> bool:
        return screen.kind in ("dropdown", "dialog", "pronouns") or (
            screen.kind == "options" and self.row_y is not None)

    def _row(self, screen: OptionsScreen, y: float | None = None, near: float = _SAME_ROW) -> Row | None:
        """The row read now that's at y (the hovered row's, by default)."""
        y = self.row_y if y is None else y
        if y is None or not screen.rows:
            return None
        row = min(screen.rows, key=lambda r: abs(r.y - y))
        return row if abs(row.y - y) < near else None

    def _hover_row(self, row: Row) -> list[PointerCommand]:
        self.row_y, self.on_help = row.y, False
        at, size = row_frame(row)
        return [PointerCommand("hover", row.point, f"{row.kind} setting", size=size, frame_at=at, color=FRAME_BLUE)]

    def _click(self, point: ui.UIPoint, name: str, now: float) -> list[PointerCommand]:
        self._settle_until = now + self.settle_seconds
        return [PointerCommand("click", point, name)]

    def _wheel(self, screen: OptionsScreen, direction: int, notches: int, now: float) -> list[PointerCommand]:
        row = self._row(screen)
        where = row.point if row is not None else _center(0.0, (CLIP_TOP + CLIP_BOTTOM) / 2)
        self._settle_until = now + self.settle_seconds
        return [PointerCommand("scroll", where, "options list", notches=-direction * notches)]

    def _hover_pronouns(self) -> PointerCommand:
        box = _center(PRONOUN_XS[self.column], PRONOUN_BOX_Y)
        return PointerCommand("hover", box, f"pronoun list {self.column + 1}", size=PRONOUN_BOX_SIZE,
                              color=FRAME_BLUE)

    def _hover_item(self, screen: OptionsScreen) -> PointerCommand:
        return PointerCommand("hover", screen.items[self.item], f"dropdown item {self.item + 1}",
                              size=(screen.item_size[0] + _FRAME_PAD / 2, screen.item_size[1]), color=FRAME_BLUE)

    def update(self, buttons: frozenset[str], now: float, screen: OptionsScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons, now)
        commands = self._held_scroll.update({self.bindings.press.get(b) for b in buttons})
        if screen.kind is None:
            if self._kind is not None and now >= self._settle_until:
                self._forget()
            return commands
        if now < self._settle_until:
            return commands
        if screen.kind != self._kind or (screen.kind == "options" and screen.tab != self.tab):
            commands += self._arrive(screen)
        elif screen.kind == "options":
            commands += self._follow_scroll(screen, now)
        elif screen.kind == "dropdown" and self._list_scroll is not None:
            commands += self._follow_list(screen)
        for action in fired:
            if now < self._settle_until:
                break
            commands += self._run(action, screen, now)
        return commands

    def _arrive(self, screen: OptionsScreen) -> list[PointerCommand]:
        came_from, self._kind = self._kind, screen.kind
        self._scroll = self._stick = self._list_scroll = None
        if screen.kind == "options":
            if screen.tab != self.tab:
                # A new tab (or Options just opened): nothing hovered until a direction is pressed.
                self.tab, self.row_y, self.on_help = screen.tab, None, False
                return []
            # Back from a list or popup: the setting it was opened from.
            row = self._row(screen, near=0.05)
            if row is not None and came_from is not None:
                return self._hover_row(row)
            return []
        if screen.kind == "dropdown":
            # Its list opens with the current choice over the box.
            y = self.row_y if self.row_y is not None else screen.items[0].y
            self.item = min(range(len(screen.items)), key=lambda i: abs(screen.items[i].y - y))
            return [self._hover_item(screen)]
        if screen.kind == "dialog":
            return [PointerCommand("hover", screen.dialog[0], "OK")]
        self.column = 0
        return [self._hover_pronouns()]

    def _follow_scroll(self, screen: OptionsScreen, now: float) -> list[PointerCommand]:
        """Once a scroll has settled: the row it was for, or the row now under the cursor."""
        if self._stick is not None:
            if now - self._stick[0] < STICK_SETTLE_SECONDS:
                return []
            _, y = self._stick
            self._stick = None
            if y is None or not screen.rows:
                return []
            return self._hover_row(min(screen.rows, key=lambda r: abs(r.y - y)))
        if self._scroll is None:
            return []
        s, self._scroll = self._scroll, None
        d = _shift(s.before, screen.rows, s.direction)
        if d is None:
            # Nothing lines up (it moved further than the view): the first row in that direction.
            y = CLIP_TOP - 1 if s.direction > 0 else CLIP_BOTTOM + 1
        else:
            y = s.y + d
        row = self._next(screen, y, s.direction)
        if row is not None:
            return self._hover_row(row)
        if screen.can_scroll[s.direction > 0] and s.tries < MAX_SCROLLS and (d is None or abs(d) > 0.002):
            self._scroll = _Scroll(s.direction, screen.rows, y, s.tries + 1)
            return self._wheel(screen, s.direction, SCROLL_NOTCHES, now)
        # The end of the list: stay on the row it started from.
        row = self._row(screen, y, near=0.05)
        return self._hover_row(row) if row is not None else []

    def _follow_list(self, screen: OptionsScreen) -> list[PointerCommand]:
        """After a notch past the end of a dropdown's list: the item that came next. How
        far the list moved comes from an edge in view both times (or the last notch's)."""
        s, self._list_scroll = self._list_scroll, None
        d = None
        for before, after in zip(s.edges, screen.list_edges):
            if before is not None and after is not None:
                d = after - before
                break
        if d is not None and abs(d) > 0.002:
            self._notch = abs(d)
        elif d is None and self._notch is not None:
            d = -s.direction * self._notch
        ys = [p.y for p in screen.items]
        if d is None:
            # Not known how far it went: the last item in view that way.
            self.item = len(ys) - 1 if s.direction > 0 else 0
        else:
            # The next item, or the same one if it didn't move (the end of the list).
            y = s.y + d + (s.direction * DROPDOWN_STEP if abs(d) > 0.002 else 0.0)
            self.item = min(range(len(ys)), key=lambda i: abs(ys[i] - y))
        return [self._hover_item(screen)]

    def _slide(self, row: Row, direction: int, now: float) -> list[PointerCommand]:
        """Drag a slider's knob a step along its track."""
        knob = row.knob
        if self._dragged is not None and abs(self._dragged[0] - row.y) < _SAME_ROW and now - self._dragged[2] < 0.6:
            knob = self._dragged[1]
        lo, hi = row.left + SLIDER_KNOB[0] / 2, row.right - SLIDER_KNOB[0] / 2
        to = max(lo, min(hi, knob + direction * SLIDER_STEP * (hi - lo)))
        if abs(to - knob) < 0.001:
            return []
        self._dragged = (row.y, to, now)
        return [PointerCommand("drag", _center(knob, row.y), f"slider {'right' if direction > 0 else 'left'}",
                               to=_center(to, row.y))]

    @staticmethod
    def _next(screen: OptionsScreen, y: float, direction: int) -> Row | None:
        beyond = [r for r in screen.rows if (r.y - y) * direction > _SAME_ROW]
        return min(beyond, key=lambda r: abs(r.y - y)) if beyond else None

    def _run(self, action: str, screen: OptionsScreen, now: float) -> list[PointerCommand]:
        if screen.kind == "options":
            return self._run_options(action, screen, now)
        if screen.kind == "dropdown":
            if action in ("up", "down"):
                direction = 1 if action == "down" else -1
                self.item = max(0, min(len(screen.items) - 1, self.item))
                item = self.item + direction
                if 0 <= item < len(screen.items):
                    self.item = item
                    return [self._hover_item(screen)]
                if screen.more[direction > 0]:
                    # Past the items in view: the list scrolls with the page, a notch at a time.
                    point = screen.items[self.item]
                    self._list_scroll = _ListScroll(direction, screen.list_edges, point.y)
                    self._settle_until = now + self.settle_seconds
                    return [PointerCommand("scroll", point, "dropdown list", notches=-direction)]
                return [self._hover_item(screen)]
            if action == "select":
                self.item = max(0, min(len(screen.items) - 1, self.item))
                return self._click(screen.items[self.item], f"dropdown item {self.item + 1}", now)
            if action in ("back", "close"):
                return self._click(_center(DROPDOWN_CLOSE_X, screen.items[0].y), "close dropdown", now)
            return []
        if screen.kind == "dialog":
            if action == "select":
                return self._click(screen.dialog[0], "OK", now)
            if action in ("back", "close"):
                return self._click(screen.dialog[1], "cancel", now)
            return []
        # The Pronoun Picker.
        if action in ("left", "right"):
            column = self.column + (1 if action == "right" else -1)
            if 0 <= column < len(PRONOUN_XS):
                self.column = column
                return [self._hover_pronouns()]
            return []
        if action in ("up", "down"):
            held = self._held_scroll.repeat(action)
            if held is not None:
                return held
            arrow = _center(PRONOUN_XS[self.column], PRONOUN_UP_Y if action == "up" else PRONOUN_DOWN_Y)
            back = self._hover_pronouns()
            self._held_scroll.clicked(action, arrow, after=[back])
            return [PointerCommand("click", arrow, f"pronoun list {self.column + 1} {action}"), back]
        if action in ("select", "back", "close"):
            self._held_scroll.stop(finish=False)
            return self._click(PRONOUN_DONE, "looks fine", now)
        if action == "reset":
            return self._click(PRONOUN_RESET, "reset pronouns", now)
        return []

    def _run_options(self, action: str, screen: OptionsScreen, now: float) -> list[PointerCommand]:
        if action in ("back", "close"):
            return self._click(CLOSE, "close options", now)
        if action in ("prevTab", "nextTab") and screen.tab is not None:
            tab = screen.tab + (1 if action == "nextTab" else -1)
            if 0 <= tab < len(TABS):
                return self._click(TABS[tab], f"{TAB_NAMES[tab]} tab", now)
            return []
        if action in ("up", "down"):
            direction = 1 if action == "down" else -1
            if self.row_y is None:
                if screen.rows:  # the first press: the top row in view
                    return self._hover_row(screen.rows[0])
                y, direction = CLIP_TOP - 1, 1  # none in view (all greyed out): look further down
            else:
                y = self.row_y
                target = self._next(screen, y, direction)
                if target is not None:
                    return self._hover_row(target)
            if not screen.can_scroll[direction > 0]:
                return []
            self._scroll = _Scroll(direction, screen.rows, y, 0)
            return self._wheel(screen, direction, SCROLL_NOTCHES, now)
        if action in ("scrollUp", "scrollDown"):
            direction = 1 if action == "scrollDown" else -1
            if not screen.can_scroll[direction > 0]:
                return []
            commands = self._wheel(screen, direction, 1, now)
            self._settle_until = now  # the stick keeps turning it; the hover waits instead
            self._stick = (now, self.row_y)
            return commands
        row = self._row(screen)
        if row is None:
            return []
        if action == "select":
            self.on_help = False
            return self._click(row.point, f"{row.kind} setting", now)
        if action in ("left", "right") and row.kind == "slider":
            return self._slide(row, 1 if action == "right" else -1, now)
        if action in ("left", "right") and row.kind == "toggle" and row.on is not None:
            if row.on != (action == "right"):
                return self._click(row.point, f"toggle {'on' if action == 'right' else 'off'}", now)
            return []
        if action == "help" and row.help is not None:
            if self.on_help:
                return self._hover_row(row)
            self.on_help = True
            at, size = row_frame(row)
            return [PointerCommand("hover", row.help, "setting help", size=size, frame_at=at, color=FRAME_BLUE)]
        return []
