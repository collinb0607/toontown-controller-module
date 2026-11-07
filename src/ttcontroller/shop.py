"""Goofy's Gag Shop: recognizing it, and controller navigation of its gag grid,
buying (one or as many as fit), delete mode, and the gag preset.

The shop panel is centered on the window like the battle panels, so positions
are offsets from the center in units of the window's shorter side (see ui.py).
Measured from captures at 1920x1009, 1156x326 and tall 502x821. In narrow
windows TTR pushes the preset and trash buttons off the left edge.

After a trolley game the shop has two buttons on the right instead of Done:
Exit to Playground above, and Play Again where Done is.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from . import ui
from .battle import DIRECTIONS, TRACKS, PointerCommand, is_usable_gag, move, nearest_usable
from .bindings import Bindings, ButtonActions
from .dialog import find_ok_cancel

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]

LEVELS = 7
_COL0, _COL_STEP = -0.1670, 0.0788
_ROW0, _ROW_STEP = -0.1962, 0.0585
# A spot on each gag button's background, away from the icon and the count.
_CELL_BG = (-0.024, -0.013)


def _center(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "center")


def cell(row: int, col: int) -> ui.UIPoint:
    return _center(_COL0 + col * _COL_STEP, _ROW0 + row * _ROW_STEP)


SAVE_PRESET = _center(-0.5352, 0.0104)
LOAD_PRESET = _center(-0.4262, 0.0104)
TRASH = _center(-0.4807, 0.1343)  # turns delete mode on and off
DONE = _center(0.4787, 0.1343)
PLAY_AGAIN = DONE  # the trolley shop's, in Done's place
EXIT = _center(0.4782, 0.0208)  # the trolley shop's Exit to Playground
# Spots on Exit's blue edges, away from its door icon and lettering (green panel in
# the normal shop).
_EXIT_PROBES = tuple(_center(x, y) for x, y in ((0.3964, -0.0045), (0.5600, -0.0045), (0.4787, -0.0223)))
GAG_SIZE = (0.072, 0.050)  # a gag button, for the highlight frame


def is_shop_green(c: RGB) -> bool:
    r, g, b = c
    return g > 180 and g - r > 80 and g - b > 55


def is_button_blue(c: RGB) -> bool:
    r, g, b = c
    return b > 200 and b - r > 100


def is_delete_red(c: RGB) -> bool:
    """Gags you can delete one of, in delete mode (lighter when hovered)."""
    r, g, b = c
    return r > 160 and r - g > 70 and r - b > 70


# Each track's label band, left of its gags.
_TRACK_BANDS: tuple[Callable[[RGB], bool], ...] = (
    lambda c: c[0] > 180 and c[2] > 220 and c[1] < 180,  # Toon-Up purple
    lambda c: c[0] > 220 and c[1] > 220 and c[2] < 140,  # Trap yellow
    lambda c: c[1] > 160 and c[0] < 120 and c[2] < 120,  # Lure green
    lambda c: c[2] > 200 and c[0] < 130 and c[1] < 140,  # Sound blue
    lambda c: c[0] > 220 and 100 < c[1] < 180 and c[2] < 110,  # Throw orange
    lambda c: c[0] > 220 and c[1] < 110 and c[2] > 160,  # Squirt pink
    lambda c: c[1] > 210 and c[2] > 220 and c[0] < 120,  # Drop cyan
)
_BAND_X = -0.35
# The green panel left and right of the gag grid.
PANEL = ui.Button("gag shop", DONE,
                  tuple(_center(-0.365, y) for y in (-0.15, -0.05, 0.05, 0.15))
                  + tuple(_center(0.366, y) for y in (-0.15, 0.0, 0.15)),
                  is_shop_green, min_hits=6)


@dataclass(frozen=True)
class ShopScreen:
    kind: str | None = None  # "shop", "dialog" (a preset OK/Cancel over the shop), or None
    usable: tuple[tuple[bool, ...], ...] = ()  # shop: [track][level], what a click would buy (or delete)
    delete_mode: bool = False
    ok: ui.UIPoint | None = None  # dialog
    cancel: ui.UIPoint | None = None
    trolley: bool = False  # after a trolley game: Exit to Playground and Play Again instead of Done


def read_shop(width: int, height: int, get_pixel: PixelReader) -> ShopScreen:
    def looks(point: ui.UIPoint, test) -> bool:
        return test(get_pixel(*point.to_client(width, height)))

    if ui.is_visible(PANEL, width, height, get_pixel):
        bands = sum(looks(_center(_BAND_X, _ROW0 + r * _ROW_STEP), test) for r, test in enumerate(_TRACK_BANDS))
        if bands >= 6:
            colors = [[get_pixel(*cell(r, c).offset(*_CELL_BG).to_client(width, height)) for c in range(LEVELS)]
                      for r in range(len(TRACKS))]
            # In delete mode the gags you have turn red; nothing is red otherwise.
            delete_mode = any(is_delete_red(c) for row in colors for c in row)
            test = is_delete_red if delete_mode else is_usable_gag
            usable = tuple(tuple(test(c) for c in row) for row in colors)
            trolley = all(looks(p, is_button_blue) for p in _EXIT_PROBES)
            return ShopScreen("shop", usable=usable, delete_mode=delete_mode, trolley=trolley)
    # A preset dialog dims the shop behind it.
    buttons = find_ok_cancel(width, height, get_pixel)
    if buttons is not None:
        return ShopScreen("dialog", ok=buttons[0], cancel=buttons[1])
    return ShopScreen()


SHOP_ACTIONS = {
    "up": "move the highlight up", "down": "move the highlight down",
    "left": "move the highlight left", "right": "move the highlight right",
    "select": "buy one of the highlighted gag (delete one in delete mode), or OK in a dialog",
    "buy_max": "buy as many of the highlighted gag as fit (delete them all in delete mode)",
    "delete_mode": "turn delete mode on or off",
    "save_preset": "save your gags as your usual set", "load_preset": "buy your usual set",
    "back": "leave delete mode, cancel a dialog, or leave the shop (Exit to Playground after a trolley game)",
    "play_again": "after a trolley game: Play Again",
}


def default_shop_bindings() -> Bindings:
    press = {"a": "select", "b": "back", "x": "delete_mode", "y": "buy_max",
             "lb": "save_preset", "rb": "load_preset", "rt": "play_again"}
    for direction in DIRECTIONS:
        press[f"dpad_{direction}"] = direction
        press[f"ls_{direction}"] = direction
    return Bindings(press=press)


@dataclass
class ShopTiming:
    # After a click that changes the screen, ignore input until it has.
    settle_seconds: float = 0.25
    # Buy max: one click per this long until the gag can't be bought.
    repeat_seconds: float = 0.1
    max_clicks: int = 100


DEFAULT_GAG = (4, 3)


@dataclass
class ShopMapper:
    bindings: Bindings = field(default_factory=default_shop_bindings)
    timing: ShopTiming = field(default_factory=ShopTiming)

    def __post_init__(self):
        self.set_bindings(self.bindings)
        self.gag: tuple[int, int] = DEFAULT_GAG  # remembered between visits
        self._kind: str | None = None
        self._delete_mode = False
        self._toggled = False  # delete mode was just switched
        self._settle_until = 0.0
        # Buy max in progress: (gag, clicks left, next click at).
        self._buying: tuple[tuple[int, int], int, float] | None = None

    def set_bindings(self, bindings: Bindings) -> None:
        self.bindings = bindings
        self._actions = ButtonActions(bindings, 0.5, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in DIRECTIONS)

    @property
    def buttons(self) -> set[str]:
        return self.bindings.buttons()

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)
        self._buying = None

    def update(self, buttons: frozenset[str], now: float, screen: ShopScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons & self.buttons, now)
        if now < self._settle_until:
            return []
        commands: list[PointerCommand] = []
        if (screen.kind, screen.delete_mode) != (self._kind, self._delete_mode):
            self._kind, self._delete_mode = screen.kind, screen.delete_mode
            self._buying = None
            commands += self._on_appear(screen)
        if fired:
            self._buying = None  # any button stops buy max
        for action in fired:
            commands += self._run(action, screen, now)
        commands += self._keep_buying(screen, now)
        return commands

    def _on_appear(self, screen: ShopScreen) -> list[PointerCommand]:
        if screen.kind == "dialog":
            return [PointerCommand("hover", screen.ok, "OK")]
        if screen.kind == "shop":
            if self._toggled:
                # Back to the gag you were on, even if it can't be bought or deleted now.
                self._toggled = False
                return [self._hover_gag()]
            pos = nearest_usable(screen.usable, self.gag)
            if pos is not None:
                self.gag = pos
            return [self._hover_gag()]
        return []

    def _hover_gag(self) -> PointerCommand:
        r, c = self.gag
        return PointerCommand("hover", cell(r, c), self._gag_name(), size=GAG_SIZE)

    def _gag_name(self) -> str:
        r, c = self.gag
        return f"{TRACKS[r]} level {c + 1}"

    def _click(self, point: ui.UIPoint, name: str, now: float) -> list[PointerCommand]:
        self._settle_until = now + self.timing.settle_seconds
        self._kind = None  # set up whatever shows next
        return [PointerCommand("click", point, name)]

    def _keep_buying(self, screen: ShopScreen, now: float) -> list[PointerCommand]:
        if self._buying is None or screen.kind != "shop":
            return []
        gag, left, next_at = self._buying
        r, c = gag
        if left <= 0 or not screen.usable[r][c]:
            self._buying = None  # can't buy (or delete) any more
            return []
        if now < next_at:
            return []
        self._buying = (gag, left - 1, now + self.timing.repeat_seconds)
        return [PointerCommand("click", cell(r, c), self._gag_name())]

    def _run(self, action: str, screen: ShopScreen, now: float) -> list[PointerCommand]:
        if screen.kind == "dialog":
            if action == "select":
                return self._click(screen.ok, "OK", now)
            if action == "back":
                return self._click(screen.cancel, "Cancel", now)
            return []
        if screen.kind != "shop":
            return []
        if action in DIRECTIONS:
            self.gag = move(screen.usable, self.gag, action)
            return [self._hover_gag()]
        if action == "select":
            # Buying changes only the count, so no need to wait for the screen.
            r, c = self.gag
            return [PointerCommand("click", cell(r, c), self._gag_name())]
        if action == "buy_max":
            self._buying = (self.gag, self.timing.max_clicks, now)
            return self._keep_buying(screen, now)
        if action == "delete_mode":
            # The highlight comes back to the same gag once the mode has switched.
            self._toggled = True
            return self._click(TRASH, "delete mode", now)
        if action == "save_preset":
            return self._click(SAVE_PRESET, "save preset", now)
        if action == "load_preset":
            return self._click(LOAD_PRESET, "load preset", now)
        if action == "back":
            if screen.delete_mode:
                self._toggled = True
                return self._click(TRASH, "leave delete mode", now)
            if screen.trolley:
                return self._click(EXIT, "exit to playground", now)
            return self._click(DONE, "done", now)
        if action == "play_again" and screen.trolley:
            return self._click(PLAY_AGAIN, "play again", now)
        return []
