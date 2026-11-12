"""Make-a-Toon: the five steps of making a new toon, reached from an empty slot on toon
selection.

1. CHOOSE YOUR STYLE: two round buttons (shorts or a skirt) low in the middle.
2. CHOOSE YOUR TYPE (species, head, body, legs) and 3. CHOOSE YOUR COLOR (toon color,
   head, body, legs): four rows on the right, each a dark blue bar with a yellow arrow
   either end (the top one bigger), and a Shuffle button below them. Once shuffled,
   Shuffle gets arrows of its own (back to the toon before, and forward again).
4. CHOOSE YOUR CLOTHES: shirts, its color, bottoms, its color (big, small, big, small).
5. CHOOSE YOUR NAME: a blue panel of lists (Title, First, and Last in two columns), each
   with a round checkbox above it and green arrows above and below it when ticked;
   Shuffle and Type-A-Name below. Type-A-Name swaps the lists for a text box with Submit
   and Pick-A-Name. Then pale yellow dialogs: "Are you sure you want to choose this
   name?" (Yes, No), "The Toon Council will review your name" (Continue Submission,
   Cancel Submission) and Enter or Skip the Toontorial.

Every step has a round X in the bottom left (leave Make-a-Toon) and round back and next
arrows in the bottom right (the first step only next, greyed until a style is picked; the
last a check mark where next was, and next above it, which submits the toon without
picking a name yet). Two blue arrows low in the middle turn the toon while held.

Measured at 1920x1009, then checked at 983x331, 667x534, 597x534 and 1293x392: the X and
arrows are anchored to their corners, the turn arrows to the bottom middle, and the rows
and the name panel to the middle (in a narrow window they run off the right or left
edge). The style buttons weren't seen at another size, so they're looked for from the
middle and from the bottom middle.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from . import ui
from .battle import PointerCommand
from .bindings import Bindings, ButtonActions
from .held_scroll import HeldScroll
from .name_keyboard import CLEAR_PRESSES, NameKeyboard

TYPED_SECONDS = 0.3  # after a key is typed, TTR's box isn't trusted to read empty yet

PixelReader = Callable[[int, int], ui.RGB]

# Everything was measured in pixels at 1920x1009.
_W, _H, _U = 1920, 1009, 1009
_ANCHORS = {"c": ("center", "center"), "r": ("right", "center"), "l": ("left", "center"),
            "cb": ("center", "bottom"), "bl": ("left", "bottom"), "br": ("right", "bottom"),
            "tc": ("center", "top")}


def _pt(anchor: str, px: float, py: float) -> ui.UIPoint:
    h, v = _ANCHORS[anchor]
    bx = {"left": 0.0, "center": _W / 2, "right": float(_W)}[h]
    by = {"top": 0.0, "center": _H / 2, "bottom": float(_H)}[v]
    return ui.UIPoint(h, (px - bx) / _U, (py - by) / _U, v)


# The corners: X, back, next (the check mark on the last step, with next above it).
CLOSE = _pt("bl", 75, 935)
BACK = _pt("br", 1692, 937)
NEXT = _pt("br", 1843, 937)
NAME_NEXT = _pt("br", 1843, 787)
_RING_DY = -27  # px: a round button's blue ring, above its white middle
ROTATE = (_pt("cb", 833, 937), _pt("cb", 1085, 937))

# The title along the top: green on Type and Name, cyan on Color.
_TITLE_Y = 62
_TITLE_XS = tuple(540 + 20 * i for i in range(43))

# Steps 2 to 4: rows on the right (y, big?), around x 1455.
_ROW_X = 1455
_BODY_ROWS = ((330, True), (444, False), (545, False), (646, False))
_CLOTHES_ROWS = ((330, True), (444, False), (570, True), (683, False))
_ARROW_X = {True: (1322, 1585), False: (1363, 1545)}  # left and right arrows' middles
_FILL_DY = {True: (-24, 28), False: (-16, 18)}  # the bar's fill above and below its label
_FILL_XS = (1400, 1510)
_ROW_SIZE = {True: (0.33, 0.09), False: (0.235, 0.065)}
_SHUFFLE_Y = 797
_SHUFFLE_ARROWS = (1353, 1555)
# The blue edge just outside each of Shuffle's arrows: there whether the arrow is lit or
# greyed (back is greyed at the first shuffle, forward at the last).
_SHUFFLE_EDGES = (1335, 1575)
_SHUFFLE_PROBES = ((1420, 778), (1490, 778), (1420, 814), (1490, 814))
SHUFFLE_SIZE = (0.15, 0.055)
SHUFFLE_ARROWS_SIZE = (0.26, 0.065)

# Step 1: the two style buttons.
_STYLE = ((757, 906), (1162, 906))
STYLE_SIZE = (0.15, 0.15)

# Step 5: the name panel.
_PANEL_PROBES = ((540, 390), (780, 390), (840, 390))
_LIST_XS = (452, 653, 855, 1032)  # Title, First, Last (its two columns)
_LIST_FILL_Y = 610
_CHECKS = ((395, 390), (596, 390), (902, 390))  # Title, First, Last
_LIST_CHECK = (0, 1, 2, 2)  # which checkbox each list goes with
_ARROW_UP_Y, _ARROW_DOWN_Y = 425, 640
_LIST_MIDDLE_Y = 532
LIST_SIZE = (0.165, 0.25)
_NAME_SHUFFLE = (748, 707)
_TYPE_A_NAME = (748, 778)
# Type-A-Name: its (paler) panel, the text box, Submit and Pick-A-Name.
_TYPE_PANEL = ((470, 420), (1030, 420), (470, 600), (1030, 600))
_TEXT_BOX = ((700, 428), (820, 428))  # below the text (descenders reach about 400)
# Inside the box, where its text is: empty, only the caret shows, a 1 px line at x 756
# (y 357 to 390). The text is centered, so it shows either side of that.
_BOX_XS = tuple(x for x in range(600, 908, 2) if abs(x - 756) > 3)
_BOX_YS = tuple(range(356, 395, 3))
_PILLS = ((650, 708), (850, 708))
_SUBMIT = (751, 708)
_PICK_A_NAME = (749, 777)
# The Toon Council's dialog: Continue and Cancel Submission.
_SUBMISSION = ((960, 602), (960, 667))
_SUBMISSION_PROBES = ((845, 600), (1075, 600), (845, 664), (1075, 664))
# Its cream, in the margins either side of the text (the name's line can reach the middle).
_SUBMISSION_CREAM = ((790, 400), (1130, 400), (790, 520), (1130, 520))
# Yes/No dialogs: found by the red No circle, anywhere in this box.
_DIALOG_BOX = (480, 300, 1320, 850)


@dataclass(frozen=True)
class Row:
    """A row on steps 2 to 4: its middle, its arrows and how big a frame goes round it."""
    point: ui.UIPoint
    left: ui.UIPoint | None
    right: ui.UIPoint | None
    size: tuple[float, float]
    shuffle: bool = False


@dataclass(frozen=True)
class NameList:
    point: ui.UIPoint  # the middle of its box (where the frame goes)
    up: ui.UIPoint
    down: ui.UIPoint
    check: ui.UIPoint
    ticked: bool


@dataclass(frozen=True)
class MakeAToonScreen:
    # "style", "type", "color", "clothes", "name", "typename", "confirm" (Yes/No: the
    # name, or the Toontorial) or "submission"; None when not in Make-a-Toon.
    kind: str | None = None
    rows: tuple[Row, ...] = ()  # steps 2 to 4, Shuffle last
    style: tuple[ui.UIPoint, ...] = ()
    lists: tuple[NameList, ...] = ()
    back: ui.UIPoint | None = None
    next: ui.UIPoint | None = None  # None while greyed out
    done: ui.UIPoint | None = None  # the check mark on the Name step
    # Name: Shuffle and Type-A-Name; typename: Submit and Pick-A-Name; confirm: Yes and
    # No; submission: Continue and Cancel Submission.
    buttons: tuple[ui.UIPoint, ...] = ()
    box_empty: bool = True  # typename: nothing typed in TTR's name box

    @property
    def is_open(self) -> bool:
        return self.kind is not None


def _is_button_blue(c: ui.RGB) -> bool:
    r, g, b = c
    return b > 190 and r < 135 and 95 < g < 215


def _is_white(c: ui.RGB) -> bool:
    return min(c) > 225


def _is_navy(c: ui.RGB) -> bool:
    r, g, b = c
    return r < 25 and 68 < g < 105 and 112 < b < 170


def _is_arrow_yellow(c: ui.RGB) -> bool:
    r, g, b = c
    return r > 200 and g > 150 and b < 100


def _is_edge_blue(c: ui.RGB) -> bool:
    r, g, b = c
    return r < 40 and 90 < g < 170 and b > 160


def _is_shuffle_blue(c: ui.RGB) -> bool:
    r, g, b = c
    return r < 60 and 120 < g < 200 and b > 210


def _is_panel_blue(c: ui.RGB) -> bool:
    r, g, b = c
    return r < 45 and 150 < g < 190 and b > 235


def _is_type_blue(c: ui.RGB) -> bool:
    r, g, b = c
    return r < 110 and 150 < g < 210 and b > 235


def _is_pale(c: ui.RGB) -> bool:
    return min(c) > 185


def _is_title_green(c: ui.RGB) -> bool:
    # Bright, or dimmed under a dialog: (0, 250, 127) or (0, 125, 64).
    r, g, b = c
    return r < 20 and g > 100 and 0.35 * g < b < 0.65 * g


def _is_title_cyan(c: ui.RGB) -> bool:
    r, g, b = c
    return r < 60 and g > 180 and b > 180 and abs(g - b) < 50


def _is_pill_yellow(c: ui.RGB) -> bool:
    r, g, b = c
    return r > 150 and g > 130 and r - b > 100 and abs(r - g) < 60


def _is_cream(c: ui.RGB) -> bool:
    r, g, b = c
    return r > 245 and g > 245 and 165 < b < 215


def _is_no_red(c: ui.RGB) -> bool:
    r, g, b = c
    return r > 170 and g < 90 and b < 90


def _is_yes_blue(c: ui.RGB) -> bool:
    r, g, b = c
    return b > 120 and b - r > 50 and b - g > 30


def read_make_a_toon(width: int, height: int, get_pixel: PixelReader) -> MakeAToonScreen:
    unit = min(width, height)

    def px(p: ui.UIPoint) -> ui.RGB:
        x, y = p.to_client(width, height)
        return get_pixel(min(max(x, 0), width - 1), min(max(y, 0), height - 1))

    def at(anchor: str, x: float, y: float) -> ui.RGB:
        return px(_pt(anchor, x, y))

    def round_button(anchor: str, x: float, y: float) -> bool:
        return _is_white(at(anchor, x, y)) and _is_button_blue(at(anchor, x, y + _RING_DY))

    def title(test: Callable[[ui.RGB], bool]) -> int:
        return sum(test(at("tc", x, _TITLE_Y)) for x in _TITLE_XS)

    if not round_button("bl", 75, 935) or not _is_button_blue(at("bl", 45, 935)):
        if title(_is_title_green) >= 10:
            return _read_dialog(width, height, get_pixel, px, at)
        return MakeAToonScreen()

    back = BACK if round_button("br", 1692, 937) else None
    nxt = NEXT if round_button("br", 1843, 937) else None

    # The Name step (or Type-A-Name): the blue panel, from the middle or the left.
    name_next = NAME_NEXT if round_button("br", 1843, 787) else None
    done = NEXT if _is_button_blue(at("br", 1843, 937 + _RING_DY)) else None
    for anchor in ("c", "l"):
        if (all(_is_panel_blue(at(anchor, x, y)) for x, y in _PANEL_PROBES)
                and all(_is_pale(at(anchor, x, _LIST_FILL_Y)) for x in _LIST_XS)):
            lists = tuple(NameList(_pt(anchor, x, _LIST_MIDDLE_Y), _pt(anchor, x, _ARROW_UP_Y),
                                   _pt(anchor, x, _ARROW_DOWN_Y), _pt(anchor, *_CHECKS[_LIST_CHECK[i]]),
                                   max(at(anchor, *_CHECKS[_LIST_CHECK[i]])) < 90)
                          for i, x in enumerate(_LIST_XS))
            return MakeAToonScreen("name", lists=lists, back=back, next=name_next, done=done,
                                   buttons=(_pt(anchor, *_NAME_SHUFFLE), _pt(anchor, *_TYPE_A_NAME)))
        if (all(_is_type_blue(at(anchor, x, y)) for x, y in _TYPE_PANEL)
                and all(_is_white(at(anchor, x, y)) for x, y in _TEXT_BOX)
                and all(_is_pill_yellow(at(anchor, x, y)) for x, y in _PILLS)):
            empty = not any(max(at(anchor, x, y)) < 120 for y in _BOX_YS for x in _BOX_XS)
            return MakeAToonScreen("typename", back=back, next=name_next, done=done,
                                   buttons=(_pt(anchor, *_SUBMIT), _pt(anchor, *_PICK_A_NAME)), box_empty=empty)

    # Steps 2 to 4: the rows, from the middle or the right.
    for anchor in ("c", "r"):
        for layout in (_BODY_ROWS, _CLOTHES_ROWS):
            if not all(_is_navy(at(anchor, x, y + dy)) for y, big in layout
                       for dy in _FILL_DY[big] for x in _FILL_XS):
                continue
            rows = [Row(_pt(anchor, _ROW_X, y), _pt(anchor, _ARROW_X[big][0], y),
                        _pt(anchor, _ARROW_X[big][1], y), _ROW_SIZE[big]) for y, big in layout]
            if sum(_is_shuffle_blue(at(anchor, x, y)) for x, y in _SHUFFLE_PROBES) >= 3:
                if all(_is_edge_blue(at(anchor, x, _SHUFFLE_Y)) for x in _SHUFFLE_EDGES):
                    rows.append(Row(_pt(anchor, _ROW_X, _SHUFFLE_Y), _pt(anchor, _SHUFFLE_ARROWS[0], _SHUFFLE_Y),
                                    _pt(anchor, _SHUFFLE_ARROWS[1], _SHUFFLE_Y), SHUFFLE_ARROWS_SIZE, True))
                else:
                    rows.append(Row(_pt(anchor, _ROW_X, _SHUFFLE_Y), None, None, SHUFFLE_SIZE, True))
            if layout is _CLOTHES_ROWS:
                kind = "clothes"
            else:
                kind = "color" if title(_is_title_cyan) > title(_is_title_green) else "type"
            return MakeAToonScreen(kind, rows=tuple(rows), back=back, next=nxt)

    # Step 1: the style buttons, from the middle or the bottom.
    for anchor in ("c", "cb"):
        if all(_is_white(at(anchor, x, y - 36)) and _is_button_blue(at(anchor, x - 57, y))
               and _is_button_blue(at(anchor, x + 57, y)) for x, y in _STYLE):
            return MakeAToonScreen("style", style=tuple(_pt(anchor, x, y) for x, y in _STYLE), next=nxt)
    return MakeAToonScreen()


def _read_dialog(width, height, get_pixel, px, at) -> MakeAToonScreen:
    """The dialogs on the Name step (the X and arrows are hidden under them)."""
    if (all(_is_cream(at("c", x, y)) for x, y in _SUBMISSION_CREAM)
            and all(_is_pill_yellow(at("c", x, y)) for x, y in _SUBMISSION_PROBES)):
        return MakeAToonScreen("submission", buttons=tuple(_pt("c", x, y) for x, y in _SUBMISSION))
    found = _find_yes_no(width, height, get_pixel)
    if found is not None:
        return MakeAToonScreen("confirm", buttons=found)
    return MakeAToonScreen()


def _find_yes_no(width: int, height: int, get_pixel: PixelReader) -> tuple[ui.UIPoint, ui.UIPoint] | None:
    """A pale yellow dialog's blue Yes and red No circles, side by side: dialogs differ in
    size and place (with the name's length), so the red circle is searched for."""
    unit = min(width, height)

    def to_client(x: float, y: float) -> tuple[int, int]:
        return _pt("c", x, y).to_client(width, height)

    left, top = to_client(_DIALOG_BOX[0], _DIALOG_BOX[1])
    right, bottom = to_client(_DIALOG_BOX[2], _DIALOG_BOX[3])
    left, top, right, bottom = max(left, 0), max(top, 0), min(right, width - 1), min(bottom, height - 1)
    step = max(3, round(0.009 * unit))
    above = round(0.045 * unit)  # the dialog's cream above the circle (the walls behind can be red too)
    hit = next(((x, y) for y in range(top, bottom, step) for x in range(left, right, step)
                if _is_no_red(get_pixel(x, y)) and y >= above and _is_cream(get_pixel(x, y - above))), None)
    if hit is None:
        return None
    # The red circle's middle: its widest row within a circle's reach of the hit.
    reach = round(0.03 * unit)
    best = None
    for y in range(hit[1], min(hit[1] + 2 * reach, height), 2):
        xs = [x for x in range(max(hit[0] - 2 * reach, 0), min(hit[0] + 2 * reach, width), 2)
              if _is_no_red(get_pixel(x, y))]
        if xs and (best is None or xs[-1] - xs[0] > best[1] - best[0]):
            best = (xs[0], xs[-1], y)
    if best is None or best[1] - best[0] < 0.015 * unit:
        return None
    nx, ny = (best[0] + best[1]) // 2, best[2]
    if not _is_cream(get_pixel(nx, max(ny - round(0.05 * unit), 0))):
        return None
    # Yes: the nearest blue to the left, on the same line.
    blues = [x for x in range(nx - round(0.04 * unit), max(nx - round(0.45 * unit), 0), -2)
             if _is_yes_blue(get_pixel(x, ny))]
    if not blues:
        return None
    # Its right edge, less the No circle's half width (the two are the same size).
    yx = blues[0] - (best[1] - best[0]) // 2

    def point(x: int, y: int) -> ui.UIPoint:
        return ui.UIPoint("center", (x - width / 2) / unit, (y - height / 2) / unit, "center")

    return point(yx, ny), point(nx, ny)


def default_make_a_toon_bindings() -> Bindings:
    press = {"a": "select", "b": "back", "x": "shuffle", "y": "typeName", "start": "next",
             "lb": "prevStep", "rb": "nextStep", "rt": "noName", "rs_left": "rotateLeft", "rs_right": "rotateRight"}
    for direction in ("up", "down", "left", "right"):
        press[f"dpad_{direction}"] = direction
        press[f"ls_{direction}"] = direction
    return Bindings(press=press)


MAKE_A_TOON_ACTIONS = {
    "select": "pick the style hovered; Shuffle when it's hovered; on the Name step, tick or untick the "
              "list's checkbox; on the name keyboard, type the letter hovered; Submit; Yes, Continue Submission or Enter Toontorial in a dialog",
    "back": "the back arrow (the X on the first step: leave Make-a-Toon); on the name keyboard, clear the name "
            "and Pick-A-Name; Pick-A-Name while typing a name; No, Cancel Submission or Skip Toontorial in a dialog",
    "shuffle": "Shuffle; on the name keyboard, delete a letter",
    "typeName": "on the Name step: Type-A-Name (the name keyboard opens), and again: Pick-A-Name; "
                "on the name keyboard, a space",
    "next": "the next arrow, or the check mark on the Name step; on the name keyboard, "
            "close it and Submit",
    "noName": "on the Name step: the arrow above the check mark (submit the toon without picking a name yet)",
    "prevStep": "the back arrow", "nextStep": "the next arrow",
    "rotateLeft": "hold: turn the toon left", "rotateRight": "hold: turn the toon right",
    "up": "the row (or the name list) above, or scroll the name list up",
    "down": "the row below, or scroll the name list down",
    "left": "the row's left arrow; the style or name list to the left",
    "right": "the row's right arrow; the style or name list to the right",
}

FIRST_LIST = 1  # the Name step starts on First (ticked from the start)
_ROTATES = {"rotateLeft": 0, "rotateRight": 1}
_DIRECTIONS = ("up", "down", "left", "right")
_STEPS = ("style", "type", "color", "clothes", "name")
_NAME_KINDS = ("name", "typename", "confirm", "submission")


@dataclass
class MakeAToonMapper:
    bindings: Bindings = field(default_factory=default_make_a_toon_bindings)
    settle_seconds: float = 0.25

    def __post_init__(self):
        self._actions = ButtonActions(self.bindings, 0.5, is_oneshot=lambda action: action not in _ROTATES,
                                      repeats=lambda action: action in _DIRECTIONS)
        self._scroll = HeldScroll()
        self._kind: str | None = None
        self.row: int | None = None  # steps 2 to 4: the row hovered
        self.style: int | None = None
        self.column: int | None = None  # the Name step: the list hovered
        self._rotating: int | None = None  # which turn arrow is held down
        self._hovered: tuple | None = None  # the row hovered as last drawn (it can grow: Shuffle's arrows)
        self._settle_until = 0.0
        # Type-A-Name's on-screen keyboard (M14): open whenever Type-A-Name shows, until B
        # or Start closes it; a direction opens it again.
        self.keyboard = NameKeyboard()
        self.keyboard_open = False
        self._typed_until = 0.0

    @property
    def buttons(self) -> frozenset[str]:
        return frozenset(self.bindings.press)

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)
        self._scroll.stop(finish=False)
        self._kind = None
        self._rotating = None
        self.row = self.style = self.column = None

    def showing_keyboard(self, screen: MakeAToonScreen) -> bool:
        return screen.kind == "typename" and self._kind == "typename" and self.keyboard_open and bool(screen.buttons)

    def hovering(self, screen: MakeAToonScreen) -> bool:
        return ((screen.kind in ("type", "color", "clothes") and self.row is not None)
                or (screen.kind == "style" and self.style is not None)
                or (screen.kind == "name" and self.column is not None)
                or self._rotating is not None or self._scroll.holding)

    def update(self, buttons: frozenset[str], now: float, screen: MakeAToonScreen) -> list[PointerCommand]:
        held, fired = self._actions.update(buttons, now)
        commands: list[PointerCommand] = []
        if screen.kind != "name":
            commands += self._scroll.stop(finish=False)
        commands += self._scroll.update({self.bindings.press.get(b) for b in buttons})
        rest = []
        for action in fired:
            repeat = self._scroll.repeat(action)
            if repeat is None:
                rest.append(action)
            else:
                commands += repeat  # still held on a list's arrow: hold it down instead
        commands += self._rotate(held, screen)
        if now < self._settle_until:
            return commands
        if screen.kind != self._kind:
            commands += self._arrive(screen)
        elif (screen.kind == "typename" and screen.box_empty and not self.keyboard.empty
              and now >= self._typed_until):
            self.keyboard.clear()  # emptied some other way (the real keyboard): a capital next
        elif (screen.kind in ("type", "color", "clothes") and self.row is not None and self.row < len(screen.rows)
              and self._rotating is None and (screen.rows[self.row].point, screen.rows[self.row].size) != self._hovered):
            # The row hovered changed shape (Shuffle gets its arrows once shuffled): the pointer
            # moves out past them.
            commands.append(self._hover_row(screen))
        for action in rest:
            commands += self._run(action, screen, now)
        return commands

    def _arrive(self, screen: MakeAToonScreen) -> list[PointerCommand]:
        """A new step: its first item is hovered straight away (the user asked for that
        here, unlike other screens): the left style, the top row, the First list. Back on
        the Name step from Type-A-Name or a dialog, the same list again."""
        before, self._kind = self._kind, screen.kind
        if screen.kind == "name":
            if before not in _NAME_KINDS or self.column is None:
                self.column = FIRST_LIST
            return [self._hover_list(screen)]
        if screen.kind == "typename":
            # TTR's box is read, not remembered: empty starts a new name; with text, it's
            # kept and taken as mid-word. Back from a dialog (No, Cancel Submission), the
            # name typed here is still known.
            self.keyboard_open = True
            keyboard = self.keyboard
            if screen.box_empty:
                keyboard.clear()
            elif not (before in ("confirm", "submission") and keyboard.text):
                keyboard.text, keyboard.prefix = "", True
            return []
        if screen.kind in _NAME_KINDS:
            return []  # the dialogs: the column is kept for coming back
        self.row = self.style = self.column = None
        if screen.kind == "style" and screen.style:
            self.style = 0
            return [self._hover_style(screen)]
        if screen.kind in ("type", "color", "clothes") and screen.rows:
            self.row = 0
            return [self._hover_row(screen)]
        return []

    def _rotate(self, held: set[str], screen: MakeAToonScreen) -> list[PointerCommand]:
        """The right stick held left or right holds a turn arrow down."""
        want = None
        if screen.kind in _STEPS and screen.kind != "name":
            want = next((_ROTATES[a] for a in ("rotateLeft", "rotateRight") if a in held), None)
        if want == self._rotating:
            return []
        commands = []
        if self._rotating is not None:
            commands.append(PointerCommand("release", ROTATE[self._rotating], "stop turning"))
            commands += self._rehover(screen)
        self._rotating = want
        if want is not None:
            commands.append(PointerCommand("hold", ROTATE[want], f"turn {'left' if want == 0 else 'right'}"))
        return commands

    def _rehover(self, screen: MakeAToonScreen) -> list[PointerCommand]:
        if screen.kind in ("type", "color", "clothes") and self.row is not None and self.row < len(screen.rows):
            return [self._hover_row(screen)]
        if screen.kind == "style" and self.style is not None:
            return [self._hover_style(screen)]
        return []

    def _hover_row(self, screen: MakeAToonScreen) -> PointerCommand:
        row = screen.rows[self.row]
        self._hovered = (row.point, row.size)
        return PointerCommand("hover", row.point, "shuffle" if row.shuffle else f"row {self.row + 1}", size=row.size,
                              pointer=True)

    def _hover_style(self, screen: MakeAToonScreen) -> PointerCommand:
        return PointerCommand("hover", screen.style[self.style], f"style {self.style + 1}", size=STYLE_SIZE,
                              pointer=True)

    def _hover_list(self, screen: MakeAToonScreen) -> PointerCommand:
        return PointerCommand("hover", screen.lists[self.column].point, f"name list {self.column + 1}",
                              size=LIST_SIZE, pointer=True)

    def _click(self, point: ui.UIPoint, name: str, now: float, settle: bool = True) -> list[PointerCommand]:
        if settle:
            self._settle_until = now + self.settle_seconds
        return [PointerCommand("click", point, name)]

    def _step(self, point: ui.UIPoint | None, name: str, now: float) -> list[PointerCommand]:
        """To another step (or out): the hover starts over there, once it shows."""
        if point is None:
            return []
        return self._click(point, name, now)

    @staticmethod
    def _type(text: str) -> PointerCommand:
        """Keys typed into TTR's name box (the text is the command's name): letters
        (capitals with Shift), " " and "\\b" (backspace). The point isn't used."""
        return PointerCommand("type", _pt("c", *_SUBMIT), text)

    def _run_keyboard(self, action: str, screen: MakeAToonScreen, now: float) -> list[PointerCommand]:
        keyboard = self.keyboard
        if action in _DIRECTIONS:
            keyboard.move(action)
            return []
        if action in ("select", "typeName", "shuffle"):
            self._typed_until = now + TYPED_SECONDS
        if action == "select":
            return [self._type(keyboard.type_letter())]
        if action == "typeName":
            return [self._type(" ")] if keyboard.space() else []
        if action == "shuffle":
            return [self._type("\b")] if keyboard.delete() else []
        if action == "next":
            self.keyboard_open = False
            return self._click(screen.buttons[0], "submit", now)
        if action == "back":
            # Empty TTR's box all at once, then back to the lists (Pick-A-Name).
            self.keyboard_open = False
            self.keyboard.clear()
            return [self._type("\b" * CLEAR_PRESSES)] + self._click(screen.buttons[1], "pick-a-name", now)
        return []  # nothing else while typing

    def _run(self, action: str, screen: MakeAToonScreen, now: float) -> list[PointerCommand]:
        kind = screen.kind
        if kind == "typename" and self.keyboard_open:
            return self._run_keyboard(action, screen, now)
        if kind in ("confirm", "submission"):
            if action == "select":
                return self._click(screen.buttons[0], "yes", now)
            if action == "back":
                return self._click(screen.buttons[1], "no", now)
            return []
        if kind in ("name", "typename") and action == "noName":
            return self._step(screen.next, "no name yet", now)
        if kind == "typename":
            if action in ("select", "next"):
                return self._click(screen.buttons[0], "submit", now)
            if action in ("back", "typeName"):  # Y toggles back, as well as B
                return self._click(screen.buttons[1], "pick-a-name", now)
            if action in _DIRECTIONS:  # the keyboard again
                self.keyboard_open = True
            return []
        if action in ("prevStep", "back"):
            if kind == "style":
                return self._step(CLOSE, "leave make-a-toon", now) if action == "back" else []
            if kind == "name" and screen.back is None:
                # Renaming a toon (Name Your Toon! on toon selection): no back arrow, only the X to cancel.
                return self._step(CLOSE, "cancel naming", now) if action == "back" else []
            return self._step(screen.back, "back a step", now)
        if action in ("nextStep", "next"):
            if kind == "name":
                return self._step(screen.done, "done", now) if action == "next" else []
            return self._step(screen.next, "next step", now)
        if kind == "style":
            return self._run_style(action, screen, now)
        if kind == "name":
            return self._run_name(action, screen, now)
        if kind in ("type", "color", "clothes"):
            return self._run_rows(action, screen, now)
        return []

    def _run_style(self, action: str, screen: MakeAToonScreen, now: float) -> list[PointerCommand]:
        if action in ("left", "right", "up", "down"):
            if self.style is None:
                self.style = 0
            elif action in ("left", "right"):
                self.style = 0 if action == "left" else 1
            return [self._hover_style(screen)]
        if action == "select" and self.style is not None:
            return self._click(screen.style[self.style], f"pick style {self.style + 1}", now)
        return []

    def _run_rows(self, action: str, screen: MakeAToonScreen, now: float) -> list[PointerCommand]:
        rows = screen.rows
        if self.row is not None and self.row >= len(rows):
            self.row = len(rows) - 1
        if action == "shuffle" and rows and rows[-1].shuffle:
            return self._click(rows[-1].point, "shuffle", now, settle=False)
        if action in _DIRECTIONS and self.row is None:
            self.row = 0
            return [self._hover_row(screen)]
        if self.row is None:
            return []
        row = rows[self.row]
        if action in ("up", "down"):
            moved = self.row + (1 if action == "down" else -1)
            if not 0 <= moved < len(rows):
                return []
            self.row = moved
            return [self._hover_row(screen)]
        if action in ("left", "right"):
            arrow = row.left if action == "left" else row.right
            if arrow is None:
                return []
            return self._click(arrow, f"{'shuffle' if row.shuffle else f'row {self.row + 1}'} {action}", now,
                               settle=False)
        if action == "select" and row.shuffle:
            return self._click(row.point, "shuffle", now, settle=False)
        return []

    def _run_name(self, action: str, screen: MakeAToonScreen, now: float) -> list[PointerCommand]:
        if action == "shuffle":
            return self._click(screen.buttons[0], "shuffle", now, settle=False)
        if action == "typeName":
            return self._click(screen.buttons[1], "type-a-name", now)
        if action in _DIRECTIONS and self.column is None:
            self.column = 0
            return [self._hover_list(screen)]
        if self.column is None:
            return []
        name_list = screen.lists[self.column]
        if action in ("left", "right"):
            moved = self.column + (1 if action == "right" else -1)
            if not 0 <= moved < len(screen.lists):
                return []
            self.column = moved
            return [self._hover_list(screen)]
        if action in ("up", "down"):
            if not name_list.ticked:
                return []
            arrow = name_list.up if action == "up" else name_list.down
            self._scroll.clicked(action, arrow, after=[self._hover_list(screen)])
            return self._click(arrow, f"name list {self.column + 1} {action}", now, settle=False)
        if action == "select":
            # Ticking or unticking redraws the lists (their arrows come and go).
            return self._click(name_list.check, f"checkbox {self.column + 1}", now) + [self._hover_list(screen)]
        return []
