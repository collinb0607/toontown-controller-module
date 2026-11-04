"""Battles: where TTR draws the battle screens, how to recognize them, and
controller navigation of the gag picker and target choice.

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


PASS = _center(0.3717, 0.0510)
RUN = _center(0.4886, 0.0510)
TRUNK = _center(0.4311, 0.1620)
TARGET_BACK = _center(-0.3518, 0.0193)
WAITING_BACK = _center(-0.2131, 0.0332)
# The "Run all the way back to the playground?" dialog's OK and Cancel buttons.
RUN_YES = _center(-0.0555, 0.1200)
RUN_NO = _center(0.0541, 0.1200)

# Rows that hold one arrow button per cog (above) or per toon (below) on the
# "which cog/toon?" screen. The toon row is a guess from the panel layout. [VERIFY]
COG_ARROW_ROW = -0.0788
TOON_ARROW_ROW = 0.119
_ARROW_SCAN_HALF_WIDTH = 0.42


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


def is_dialog_yellow(c: RGB) -> bool:
    return c[0] > 240 and c[1] > 240 and 160 < c[2] < 215


def is_notepad_yellow(c: RGB) -> bool:
    return c[0] > 230 and c[1] > 230 and c[2] < 100


def _is_arrow_orange(c: RGB) -> bool:
    return c[0] > 230 and 140 < c[1] < 215 and c[2] < 160


def _is_arrow_blue(c: RGB) -> bool:
    return c[2] > 200 and c[0] < 100 and c[1] < 130


# Screen detectors. The probes avoid text and icons.
PICKER = ui.Button("gag picker", cell(0, 0),
                   tuple(_center(0.288, -0.21 + 0.045 * i) for i in range(10)), is_panel_red, min_hits=8)
TARGET = ui.Button("which cog/toon", TARGET_BACK,
                   tuple(_center(x, 0.02) for x in (-0.235, -0.22, -0.19, 0.19, 0.22, 0.235)),
                   is_label_yellow, min_hits=5)
WAITING = ui.Button("waiting for other toons", WAITING_BACK,
                    tuple(_center(x, y) for y in (-0.02, 0.088) for x in (-0.12, -0.05, 0.05, 0.12, 0.19)),
                    is_white, min_hits=8)
# The yellow notepad to the right of the gag grid, which stays when the trunk
# replaces the grid. Probes skip the "Total gags" text and stay inside tall windows.
NOTEPAD = ui.Button("trunk", TRUNK,
                    tuple(_center(x, y) for y in (-0.10, -0.06, -0.02) for x in (0.36, 0.40, 0.43)
                          if (x, y) != (0.43, -0.06)),
                    is_notepad_yellow, min_hits=7)
# The run dialog's pale yellow panel spans x -0.249..0.249 and y -0.108..0.188;
# these probes sit above the question and beside the buttons.
RUN_CONFIRM = ui.Button("run: are you sure?", RUN_YES,
                        tuple(_center(x, -0.08) for x in (-0.2, -0.1, 0.0, 0.1, 0.2))
                        + tuple(_center(x, 0.12) for x in (-0.22, -0.16, 0.16, 0.22)),
                        is_dialog_yellow, min_hits=8)


@dataclass(frozen=True)
class BattleScreen:
    kind: str | None = None  # "picker", "trunk", "target", "waiting", "confirm_run", or None when no battle panel shows
    usable: tuple[tuple[bool, ...], ...] = ()  # picker: [track][level]
    targets: tuple[ui.UIPoint, ...] = ()  # target: one arrow per cog (or toon), left to right


def _scan_arrows(width: int, height: int, get_pixel: PixelReader, row: float) -> list[ui.UIPoint]:
    """Find arrow buttons along a row: a run of blue with orange on both sides."""
    unit = min(width, height)
    y = round(height / 2 + row * unit)
    x0 = max(0, round(width / 2 - _ARROW_SCAN_HALF_WIDTH * unit))
    x1 = min(width - 1, round(width / 2 + _ARROW_SCAN_HALF_WIDTH * unit))
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
        before = kinds[max(0, start - 8):start]
        after = kinds[i:i + 8]
        if "o" in before and "o" in after and i - start >= 3:
            x = x0 + (start + i - 1) / 2
            found.append(_center((x - width / 2) / unit, row))
    return found


def read_screen(width: int, height: int, get_pixel: PixelReader) -> BattleScreen:
    """Work out which battle screen is showing, and what's on it."""
    if ui.is_visible(PICKER, width, height, get_pixel):
        usable = tuple(
            tuple(is_usable_gag(get_pixel(*cell(r, c).offset(*_CELL_BG).to_client(width, height)))
                  for c in range(LEVELS))
            for r in range(len(TRACKS)))
        return BattleScreen("picker", usable=usable)
    # The notepad without the gag grid means the trunk is open.
    if ui.is_visible(NOTEPAD, width, height, get_pixel):
        return BattleScreen("trunk")
    if ui.is_visible(TARGET, width, height, get_pixel):
        targets = (_scan_arrows(width, height, get_pixel, COG_ARROW_ROW)
                   or _scan_arrows(width, height, get_pixel, TOON_ARROW_ROW))
        return BattleScreen("target", targets=tuple(targets))
    if ui.is_visible(WAITING, width, height, get_pixel):
        return BattleScreen("waiting")
    if ui.is_visible(RUN_CONFIRM, width, height, get_pixel):
        return BattleScreen("confirm_run")
    return BattleScreen()


# --- Navigation -------------------------------------------------------------

DIRECTIONS = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}

BATTLE_ACTIONS = {
    "up": "move the highlight up", "down": "move the highlight down",
    "left": "move the highlight left", "right": "move the highlight right",
    "select": "click the highlighted gag or target, or Yes when asked if you want to run",
    "back": "go back (on the target, waiting and trunk screens), or cancel running",
    "run": "run from the battle", "trunk": "open the trunk", "pass": "pass this turn",
}


def default_battle_bindings() -> Bindings:
    press = {"a": "select", "b": "back", "x": "trunk", "y": "pass"}
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


def nearest_usable(usable, pos: tuple[int, int]) -> tuple[int, int] | None:
    r, c = pos
    cells = [(rr, cc) for rr in range(len(usable)) for cc in range(LEVELS) if usable[rr][cc]]
    if not cells:
        return None
    # Prefer staying in the same track, then the closest level, then the stronger gag.
    return min(cells, key=lambda p: (abs(p[0] - r) * 10 + abs(p[1] - c), -p[1]))


@dataclass(frozen=True)
class PointerCommand:
    kind: str  # "hover" (park the cursor) or "click"
    point: ui.UIPoint
    name: str


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
        self._kind: str | None = None
        self._settle_until = 0.0

    def set_bindings(self, bindings: Bindings) -> None:
        self.bindings = bindings
        self._actions = ButtonActions(bindings, self.timing.hold_seconds,
                                      is_oneshot=lambda action: True,
                                      repeats=lambda action: action in DIRECTIONS)

    @property
    def buttons(self) -> set[str]:
        return self.bindings.buttons()

    def reset_buttons(self) -> None:
        self._actions.reset()

    def update(self, buttons: frozenset[str], now: float, screen: BattleScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons & self.buttons, now)
        if now < self._settle_until:
            # Right after a click the old screen may still show; wait for the next one.
            return []

        commands: list[PointerCommand] = []
        if screen.kind != self._kind:
            self._kind = screen.kind
            commands += self._on_appear(screen)
        for action in fired:
            commands += self._run(action, screen, now)
        return commands

    def _on_appear(self, screen: BattleScreen) -> list[PointerCommand]:
        if screen.kind == "picker":
            pos = nearest_usable(screen.usable, self.gag)
            if pos is None:
                return []
            self.gag = pos
            return [self._hover_gag()]
        if screen.kind == "confirm_run":
            return [PointerCommand("hover", RUN_YES, "run: yes")]
        if screen.kind == "target" and screen.targets:
            self.target_index = min(self.target_index, len(screen.targets) - 1)
            return [PointerCommand("hover", screen.targets[self.target_index], f"target {self.target_index + 1}")]
        return []

    def _hover_gag(self) -> PointerCommand:
        r, c = self.gag
        return PointerCommand("hover", cell(r, c), f"{TRACKS[r]} level {c + 1}")

    def _click(self, point: ui.UIPoint, name: str, now: float) -> list[PointerCommand]:
        self._settle_until = now + self.timing.settle_seconds
        # Forget the screen so whatever appears next (even the same kind) is set up fresh.
        self._kind = None
        return [PointerCommand("click", point, name)]

    def _run(self, action: str, screen: BattleScreen, now: float) -> list[PointerCommand]:
        if screen.kind == "picker":
            if action in DIRECTIONS:
                self.gag = move(screen.usable, self.gag, action)
                return [self._hover_gag()]
            elif action == "select" and screen.usable[self.gag[0]][self.gag[1]]:
                r, c = self.gag
                return self._click(cell(r, c), f"{TRACKS[r]} level {c + 1}", now)
            elif action == "run":
                return self._click(RUN, "run", now)
            elif action == "trunk":
                return self._click(TRUNK, "trunk", now)
            elif action == "pass":
                return self._click(PASS, "pass", now)
        elif screen.kind == "target":
            if action in ("left", "right") and screen.targets:
                step = -1 if action == "left" else 1
                self.target_index = max(0, min(len(screen.targets) - 1, self.target_index + step))
                return [PointerCommand("hover", screen.targets[self.target_index], f"target {self.target_index + 1}")]
            if action == "select" and screen.targets:
                return self._click(screen.targets[self.target_index], f"target {self.target_index + 1}", now)
            if action in ("back", "run"):
                return self._click(TARGET_BACK, "back", now)
        elif screen.kind == "trunk" and action in ("back", "run", "trunk"):
            # The trunk button closes the trunk too.
            return self._click(TRUNK, "close trunk", now)
        elif screen.kind == "confirm_run":
            if action == "select":
                return self._click(RUN_YES, "run: yes", now)
            if action == "back":
                return self._click(RUN_NO, "run: no", now)
        elif screen.kind == "waiting" and action in ("back", "run"):
            return self._click(WAITING_BACK, "back", now)
        return []
