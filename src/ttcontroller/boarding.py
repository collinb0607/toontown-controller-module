"""The boarding group panel: near a Cog HQ facility's or boss's elevator, a small blue
tab with an orange edge sits at the window's left edge ("Show Boarding Group" when
hovered). Clicking it opens an orange panel beside it: a white list of the group's
members (the leader first, with a star), or Start a Group (a round blue icon) when
you're in none, "Going To:" the elevator's destination, and a red X in its bottom right
that leaves the group (disbands it, for the leader) after an "Are you sure?" Yes/No
(the usual OK/Cancel dialog, already handled by dialog.DialogMapper). Clicking the tab
again closes the panel. Clicking a member's name opens their toon panel in the top
right (friends.py), whose Boarding Group section has Invite, or Kick for the leader.

Controls (the user, Nov 7, 2026): the right stick right opens the panel and left closes
it; while it's open, the D-pad up/down hovers the members (or Start a Group; nothing is
hovered at first, except Start a Group, which is hovered as soon as the panel opens,
and TTR's own hover, the name turning yellow, shows which), A clicks
the one hovered, and holding B clicks the red X. The left stick still walks. It stays in
use until put away: after the gags, a toon's panel or a dialog had the controls, the D-pad
works there again and the hover goes back where it was (or to Start a Group).

Measured at 1920x1009 (boarding_groups_* captures) and checked at 1502x520 and 871x939:
the tab and panel are anchored to the left edge and the window's middle.
"""

from collections.abc import Callable
from dataclasses import dataclass

from . import ui
from .battle import PointerCommand

PixelReader = Callable[[int, int], ui.RGB]

_W, _H, _U = 1920, 1009, 1009


def _pt(px: float, py: float) -> ui.UIPoint:
    """A point measured in pixels at 1920x1009, from the left edge and the middle."""
    return ui.UIPoint("left", px / _U, (py - _H / 2) / _U, "center")


TAB = _pt(12, 482)
_TAB_BLUE = tuple(_pt(12, y) for y in (474, 482, 490))  # blue there whether it points right (closed) or left
_TAB_EDGES = (_pt(2, 480), _pt(22, 480))  # its orange edge, either side of the blue
_PANEL_ORANGE = (_pt(40, 600), _pt(40, 620))
_LIST_WHITE = (_pt(250, 430), _pt(250, 540), _pt(60, 540))
# The panel's height follows the group's size (4 toons for a facility, 8 for a boss:
# boarding_groups_8_toons), so its layout is placed from its own edges: the list's
# white top (found up column _TOP_X) and the panel's orange bottom (down column _BOTTOM_X).
_TOP_X, _BOTTOM_X = 250, 40
_ROW0_DY, _ROW_STEP, _ROWS = 22, 35, 8  # the members' names: the first below the list's top, then apart
_LEAVE_X, _LEAVE_DY = 272, -73  # the red X, above the panel's bottom (575 and 647 on the two sizes)
_START_X = 160  # Start a Group's icon, searched for down this column
_START_SIZE = (0.02, 0.05)  # its blue's height
START = _pt(160, 515)  # where it is on the 4-toon panel
LEAVE = _pt(272, 575)  # and the red X
_NAME_XS = tuple(85 + 3 * i for i in range(52))
_NAME_CLICK_X = 105  # a little into the name: the name's own text is what's clickable


@dataclass(frozen=True)
class BoardingScreen:
    kind: str | None = None  # "closed" (just the tab), "open", or None (no tab)
    leave: ui.UIPoint | None = None  # open: the red X
    members: tuple[ui.UIPoint, ...] = ()  # open: where to click each member's name, top to bottom
    start: ui.UIPoint | None = None  # open, in no group: Start a Group

    @property
    def items(self) -> tuple[ui.UIPoint, ...]:
        """What up/down move through."""
        return self.members or ((self.start,) if self.start else ())


def _is_tab_blue(c: ui.RGB) -> bool:
    # (2, 157, 244), or lighter while hovered: (114, 245, 255) to (130, 247, 252).
    r, g, b = c
    return r < 150 and g > 140 and b > 200 and b - r > 100


def _is_orange(c: ui.RGB) -> bool:
    r, g, b = c
    return r > 190 and 80 < g < 175 and b < 110 and r - b > 120


def _is_panel_edge(c: ui.RGB) -> bool:
    # The panel's left edge: bright orange (247, 108, 25), or its darker brown inside
    # (152, 81, 38), which reaches lower on a taller panel.
    r, g, b = c
    return r > 140 and 60 < g < 175 and b < 110 and r - b > 90


def _is_white(c: ui.RGB) -> bool:
    return min(c) > 235


def _is_start_blue(c: ui.RGB) -> bool:
    r, g, b = c
    return b > 140 and b - r > 40


def read_boarding(width: int, height: int, get_pixel: PixelReader) -> BoardingScreen:
    unit = min(width, height)

    def at(p: ui.UIPoint) -> ui.RGB:
        x, y = p.to_client(width, height)
        return get_pixel(min(max(x, 0), width - 1), min(max(y, 0), height - 1))

    if not (all(_is_tab_blue(at(p)) for p in _TAB_BLUE) and all(_is_orange(at(p)) for p in _TAB_EDGES)):
        return BoardingScreen()
    if not (all(_is_panel_edge(at(p)) for p in _PANEL_ORANGE) and all(_is_white(at(p)) for p in _LIST_WHITE)):
        return BoardingScreen("closed")
    scale = unit / _U  # pixels measured at 1920x1009, to this window's

    def px(p: ui.UIPoint) -> tuple[int, int]:
        return p.to_client(width, height)

    def to_point(x: int, y: int) -> ui.UIPoint:
        return ui.UIPoint("left", x / unit, (y - height / 2) / unit, "center")

    # The list's top: up from a spot inside it to the first pixel that isn't white.
    tx, y = px(_LIST_WHITE[0])
    while y > 0 and _is_white(get_pixel(tx, y - 1)):
        y -= 1
    top = y
    # The panel's bottom: down its orange edge.
    bx, y = px(_PANEL_ORANGE[1])
    while y < height - 1 and _is_panel_edge(get_pixel(bx, y + 1)):
        y += 1
    bottom = y
    leave = to_point(round(_LEAVE_X * scale), round(bottom + _LEAVE_DY * scale))
    # Start a Group: its blue icon down the middle of the list.
    sx = round(_START_X * scale)
    blue = [y for y in range(top, bottom) if _is_start_blue(get_pixel(sx, y))]
    if blue and _START_SIZE[0] * unit <= blue[-1] - blue[0] <= _START_SIZE[1] * unit:
        return BoardingScreen("open", start=to_point(sx, (blue[0] + blue[-1]) // 2), leave=leave)
    members = []
    for i in range(_ROWS):
        y = round(top + (_ROW0_DY + i * _ROW_STEP) * scale)
        if y > bottom + _LEAVE_DY * scale:
            break
        ink = sum(min(get_pixel(round(x * scale), y + round(dy * scale))) < 150 for x in _NAME_XS for dy in (-3, 0, 3))
        if ink < 3:
            break
        members.append(to_point(round(_NAME_CLICK_X * scale), y))
    return BoardingScreen("open", members=tuple(members), leave=leave)


BOARDING_ACTIONS = {
    "rs_right": "open the boarding group panel (its tab at the left edge)",
    "rs_left": "close it",
    "dpad_up/down": "while it's open: hover the member above/below (or Start a Group)",
    "a": "while one is hovered: click it (a member opens their toon panel; Start a Group starts one)",
    "hold b": "while it's open, in a group: the red X (leave, or disband as the leader), then Yes/No",
}

HOLD_SECONDS = 0.5
RESUME_GAP = 0.25  # seconds without an update: something else had the controls meanwhile


class BoardingMapper:
    def __init__(self, hold_seconds: float = HOLD_SECONDS):
        self.hold_seconds = hold_seconds
        self.item: int | None = None  # what's hovered in the open panel
        self._held: frozenset[str] = frozenset()
        self._b_down_at: float | None = None
        self._b_fired = False
        self._was_open = False
        self._last: float | None = None  # when update last ran

    def reset(self) -> None:
        self.item = None
        self._held = frozenset()
        self._b_down_at = None
        self._b_fired = False
        self._was_open = False
        self._last = None

    def hovering(self, screen: BoardingScreen) -> bool:
        return screen.kind == "open" and self.item is not None

    def buttons(self, screen: BoardingScreen) -> frozenset[str]:
        """The buttons it takes from the overworld right now (holding B isn't taken: a
        tap still does what B does)."""
        if screen.kind == "closed":
            return frozenset({"rs_right"})
        if screen.kind == "open":
            taken = {"rs_left", "rs_right", "dpad_up", "dpad_down"}
            if self.item is not None:
                taken.add("a")
            return frozenset(taken)
        return frozenset()

    def update(self, buttons: frozenset[str], now: float, screen: BoardingScreen) -> list[PointerCommand]:
        """Called every frame the panel's controls are live. A gap means something else had
        them (the gags or tasks, a toon's panel, a dialog): coming back, buttons still held
        from then aren't fresh presses, and the hover goes back where it was."""
        resumed = self._last is not None and now - self._last > RESUME_GAP
        self._last = now
        if resumed:
            # Only what was already down before the gap and still is (a fresh press counts).
            self._held &= buttons
            self._b_down_at = None
        pressed, self._held = buttons - self._held, buttons
        commands: list[PointerCommand] = []
        if screen.kind != "open":
            self._b_down_at = None
            if screen.kind == "closed":
                # Put away: done with boarding groups for now (the user). Opened again, it
                # starts over. (Not read at all, e.g. covered for a moment, changes nothing.)
                self.item = None
                self._was_open = False
                if "rs_right" in pressed:
                    commands.append(PointerCommand("click", TAB, "open boarding group"))
            return commands
        items = screen.items
        if self.item is not None and self.item >= len(items):
            self.item = len(items) - 1 if items else None
        if self.item is None and screen.start is not None:
            # No group: Start a Group is hovered straight away (the user), so A starts one.
            self.item = 0
            commands.append(PointerCommand("hover", screen.start, "boarding group 1"))
        elif (resumed or not self._was_open) and self.item is not None and items:
            # Back from whatever had the controls: the same member again.
            commands.append(PointerCommand("hover", items[self.item], f"boarding group {self.item + 1}"))
        self._was_open = True
        if "rs_left" in pressed:
            self.item = None
            return [PointerCommand("click", TAB, "close boarding group")]
        for direction, step in (("dpad_up", -1), ("dpad_down", 1)):
            if direction in pressed and items:
                self.item = 0 if self.item is None else max(0, min(len(items) - 1, self.item + step))
                commands.append(PointerCommand("hover", items[self.item], f"boarding group {self.item + 1}"))
        if "a" in pressed and self.item is not None and items:
            name = "start a group" if screen.start else f"boarding member {self.item + 1}"
            commands.append(PointerCommand("click", items[self.item], name))
        # Holding B: the red X (only in a group; Start a Group's panel has nothing to leave).
        if "b" in buttons:
            if self._b_down_at is None:
                self._b_down_at, self._b_fired = now, False
            elif not self._b_fired and now - self._b_down_at >= self.hold_seconds and screen.members:
                self._b_fired = True
                commands.append(PointerCommand("click", screen.leave or LEAVE, "leave boarding group"))
        else:
            self._b_down_at = None
        return commands
