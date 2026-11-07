"""The screens before the game: the start-up screen and toon selection.

Both have a Quit button in the bottom right, with the Options icon (a little
shticker-book remote) beside it. The start-up screen says PRESS ANY KEY TO ENTER;
toon selection says PICK A TOON TO PLAY over six toon cards, three by two, each with
a trash can in its bottom right (an empty slot has none, and makes a new toon).
The Options icon opens TTR's Options over either screen, closed with the round
blue X at its top right. Deleting asks twice: the usual OK/Cancel over the dimmed screen, then a bigger
"Delete Toon?" dialog wanting "delete" typed into its box before OK.

Measured at 1920x1009.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from . import ui
from .battle import PointerCommand
from .bindings import Bindings, ButtonActions
from .dialog import find_ok_cancel

PixelReader = Callable[[int, int], ui.RGB]


def _center(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "center")


def _corner(x: float, y: float) -> ui.UIPoint:
    """From the bottom right corner."""
    return ui.UIPoint("right", x, y, "bottom")


QUIT = _corner(-0.1288, -0.0505)
OPTIONS_CLOSE = _center(0.4346, -0.2740)  # the X's white middle; blue either side
_OPTIONS_PANEL = (_center(0.0, 0.055), _center(-0.2577, -0.054))
OPTIONS = _corner(-0.2973, -0.0585)
_QUIT_PROBES = (_corner(-0.2180, -0.0505), _corner(-0.0396, -0.0505), _corner(-0.1288, -0.0684))

# The row through PICK A TOON TO PLAY, and through PRESS ANY KEY (left of the cards' yellow).
_TITLE_XS = tuple(-0.4500 + 0.009 * i for i in range(100))
_TITLE_Y = 0.0644
_PRESS_XS = tuple(-0.4361 + 0.006 * i for i in range(100))
_PRESS_Y = 0.3077

# The toon cards, top row then bottom (where to hover and click), and their trash cans.
SLOTS = (_center(-0.4232, -0.1749), _center(0.0089, -0.1531), _center(0.4316, -0.1635),
         _center(-0.4321, 0.2275), _center(0.0020, 0.2632), _center(0.4316, 0.2304))
TRASH = (_center(-0.3186, -0.0411), _center(0.1645, -0.0639), _center(0.5481, -0.0342),
         _center(-0.2696, 0.3246), _center(0.1288, 0.3820), _center(0.5778, 0.3326))
_TRASH_PROBES = ((0.0, 0.0), (-0.006, 0.0), (0.006, 0.0), (0.0, -0.010), (0.0, 0.010))
START_SLOT = 1  # the top row's middle

# The "Delete Toon?" dialog: its text box, OK and Cancel.
_TYPE_BOX = (_center(-0.1586, -0.0144), _center(-0.0099, -0.0144), _center(0.1387, -0.0144))
TYPE_OK = _center(-0.1100, 0.0748)
TYPE_CANCEL = _center(0.0999, 0.0748)
CONFIRM_WORD = "delete"


@dataclass(frozen=True)
class PregameScreen:
    # "startup", "toons", "options" (TTR's Options over either), "confirm" (OK/Cancel)
    # or "type" (type "delete")
    kind: str | None = None
    trash: tuple[bool, ...] = ()  # on toon selection: which slots have a toon to delete
    dialog: tuple[ui.UIPoint, ui.UIPoint] | None = None  # the OK/Cancel confirm's buttons


def _is_quit_cyan(c: ui.RGB) -> bool:
    # Bright, or dimmed under a dialog.
    r, g, b = c
    return r < 60 and g > 80 and b > 100 and b >= g


def _is_yellowish(c: ui.RGB) -> bool:
    r, g, b = c
    return r > 100 and g > 0.75 * r and b < 0.4 * r


def _is_close_blue(c: ui.RGB) -> bool:
    return c[2] > 180 and c[2] - c[0] > 120


def _is_panel_beige(c: ui.RGB) -> bool:
    r, g, b = c
    return r > 240 and g > 225 and 180 < b < 240


def _is_trash(c: ui.RGB) -> bool:
    r, g, b = c
    return r < 110 and b > r + 40 and b > 105 and max(c) < 180


def _is_blue(c: ui.RGB) -> bool:
    return c[2] > 140 and c[2] - c[0] > 50


def read_pregame(width: int, height: int, get_pixel: PixelReader) -> PregameScreen:
    def at(p: ui.UIPoint) -> ui.RGB:
        return get_pixel(*p.to_client(width, height))

    if not all(_is_quit_cyan(at(p)) for p in _QUIT_PROBES):
        return PregameScreen()
    # Options first: toon selection's title still shows above it.
    if (min(at(OPTIONS_CLOSE)) > 220
            and all(_is_close_blue(at(OPTIONS_CLOSE.offset(dx, 0))) for dx in (-0.0228, 0.0228))
            and all(_is_panel_beige(at(p)) for p in _OPTIONS_PANEL)):
        return PregameScreen("options")
    title = sum(_is_yellowish(at(ui.UIPoint("center", x, _TITLE_Y))) for x in _TITLE_XS)
    if title >= 20:
        spots = ((-0.012, 0.0), (0.008, 0.006), (-0.008, -0.006))  # off the buttons' white shine
        if (all(min(at(p)) > 235 for p in _TYPE_BOX) and any(_is_blue(at(TYPE_OK.offset(*d))) for d in spots)
                and any(ui.is_red(at(TYPE_CANCEL.offset(*d))) for d in spots)):
            return PregameScreen("type")
        dialog = find_ok_cancel(width, height, get_pixel)
        if dialog is not None:
            return PregameScreen("confirm", dialog=dialog)
        trash = tuple(sum(_is_trash(at(t.offset(*d))) for d in _TRASH_PROBES) >= 3 for t in TRASH)
        return PregameScreen("toons", trash=trash)
    press = sum(at(_center(x, _PRESS_Y))[0] > 200 and at(_center(x, _PRESS_Y))[1] > 160
                and at(_center(x, _PRESS_Y))[2] < 100 for x in _PRESS_XS)
    if press >= 15:
        return PregameScreen("startup")
    return PregameScreen()


def default_pregame_bindings() -> Bindings:
    press = {"a": "select", "b": "back", "x": "delete", "y": "confirmDelete", "start": "options"}
    for direction in ("up", "down", "left", "right"):
        press[f"dpad_{direction}"] = direction
        press[f"ls_{direction}"] = direction
    return Bindings(press=press, hold={"b": "quit"})


PREGAME_ACTIONS = {
    "select": "pick the toon (or empty slot) hovered, or OK in the first delete confirm",
    "back": "Cancel in a delete confirm, or close Options",
    "delete": "delete the toon hovered (its trash can)",
    "confirmDelete": "in the second delete confirm, type \"delete\" and press OK",
    "options": "the Options button (start-up screen and toon selection), or close Options again",
    "quit": "hold: the Quit button (start-up screen and toon selection)",
    "up": "toon selection: the card above", "down": "the card below",
    "left": "the card left", "right": "the card right",
}

_MOVES = {"up": -3, "down": 3, "left": -1, "right": 1}


@dataclass
class PregameMapper:
    bindings: Bindings = field(default_factory=default_pregame_bindings)
    settle_seconds: float = 0.25
    hold_seconds: float = 0.5

    def __post_init__(self):
        self.set_bindings(self.bindings)
        self.slot = START_SLOT
        self._kind: str | None = None
        self._settle_until = 0.0

    def set_bindings(self, bindings: Bindings) -> None:
        self.bindings = bindings
        self._actions = ButtonActions(bindings, self.hold_seconds, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in _MOVES)

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)
        self._kind = None

    def pause(self) -> None:
        """While TTR's Options is open over these screens (read by its own reader): when it
        closes, toon selection comes back on the same toon, and nothing held fires."""
        self._actions.reset(ignore_held=True)
        if self._kind is not None:
            self._kind = "options"

    def hovering(self, screen: PregameScreen) -> bool:
        return screen.kind in ("toons", "confirm")

    def update(self, buttons: frozenset[str], now: float, screen: PregameScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons, now)
        commands: list[PointerCommand] = []
        if screen.kind != self._kind and now >= self._settle_until:
            if screen.kind == "toons" and self._kind not in ("confirm", "type", "options"):
                self.slot = START_SLOT  # arriving: the top row's middle
            # Back from a confirm (either way): the same toon again.
            self._kind = screen.kind
            if screen.kind == "toons":
                commands.append(self._hover_slot())
            elif screen.kind == "confirm":
                commands.append(PointerCommand("hover", screen.dialog[0], "OK"))
        if now < self._settle_until:
            return commands
        for action in fired:
            commands += self._run(action, screen, now)
        return commands

    def _hover_slot(self) -> PointerCommand:
        return PointerCommand("hover", SLOTS[self.slot], f"toon {self.slot + 1}")

    def _click(self, point: ui.UIPoint, name: str, now: float, delay: float = 0.0) -> list[PointerCommand]:
        self._settle_until = now + self.settle_seconds + delay
        return [PointerCommand("click", point, name, delay=delay)]

    def _run(self, action: str, screen: PregameScreen, now: float) -> list[PointerCommand]:
        if screen.kind in ("startup", "toons"):
            if action == "options":
                return self._click(OPTIONS, "options", now)
            if action == "quit":
                return self._click(QUIT, "quit", now)
        if screen.kind == "options":
            if action in ("back", "options"):  # B, or Start again
                return self._click(OPTIONS_CLOSE, "close options", now)
        elif screen.kind == "toons":
            if action in _MOVES:
                slot = self.slot + _MOVES[action]
                same_row = action in ("up", "down") or slot // 3 == self.slot // 3
                if not (0 <= slot < len(SLOTS) and same_row):
                    return []
                self.slot = slot
                return [self._hover_slot()]
            if action == "select":
                return self._click(SLOTS[self.slot], f"pick toon {self.slot + 1}", now)
            if action == "delete" and screen.trash and screen.trash[self.slot]:
                return self._click(TRASH[self.slot], f"delete toon {self.slot + 1}", now)
        elif screen.kind == "confirm":
            if action == "select":
                return self._click(screen.dialog[0], "OK", now)
            if action == "back":
                return self._click(screen.dialog[1], "cancel", now)
        elif screen.kind == "type":
            # Only Y deletes here (not A), to be really sure: it types the word and presses OK.
            if action == "confirmDelete":
                return [PointerCommand("type", TYPE_OK, CONFIRM_WORD)] + self._click(TYPE_OK, "OK", now, delay=0.2)
            if action == "back":
                return self._click(TYPE_CANCEL, "cancel", now)
        return []
