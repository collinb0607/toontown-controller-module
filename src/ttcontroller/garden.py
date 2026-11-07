"""The gardening HUD: a pale yellow panel on the left edge, in a garden.

It has one or two round buttons (Pick/Full/Plant Flower on top, Water below) above
the basket. Y clicks the top one and X the bottom one while it's up, instead of
showing gags and tasks.

Selling the basket (at the garden's wheelbarrow) asks to confirm in a popup of its
own, with Cancel and Sell All in its bottom right rather than the usual dialog's
places: A sells, B cancels.

Plant Flower can open the bean picker: a row of nine jellybeans to add to the
planting, with Cancel, Reset and Plant below. The D-pad moves along the beans
(wrapping, with the highlight frame), A adds the hovered one, B cancels, X resets
and Y plants. Once as many beans as can be planted are in, the row of beans goes,
and then A plants too.

A failed planting (a bean combination that doesn't make a flower) says so in a
popup with just an OK button, centered under its message: A or B clicks it.

Measured at 1920x1009, 1379x348 and tall 405x820 (gardening_hud captures). The
panel is found by scanning down its fill (its top is about 0.175 of the shorter side
from the window's top at every size), and the buttons are placed from its top.
"""

from collections.abc import Callable
from dataclasses import dataclass

from . import ui
from .bindings import Bindings, ButtonActions
from .battle import PointerCommand
from .ui import RGB

PixelReader = Callable[[int, int], RGB]

_SCAN_X = 0.012  # from the left edge: inside the panel, left of its buttons
_HEIGHT = (0.28, 0.36)  # the panel's fill down that column (0.315 at 1920x1009)
_LABEL_GAP = 0.03  # the most fill a label's letters can break (Remove's: 0.02)
_BUTTON_X = 0.0654
_BUTTON_DYS = (0.0545, 0.1497)  # each button's middle, below the panel's top
_BUTTON_SPOTS = ((0.0, 0.0), (-0.02, 0.0), (0.02, 0.0), (0.0, -0.02), (0.0, 0.02))
_BUTTON_MIN = 3  # spots that aren't panel fill, for a button to be there
_BORDER_X = 0.004  # the panel's green border, left of the fill: within this of the edge (a pixel or two wide)


def _center(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "center")


# The sell popup, measured at 1920x1009 (gardening_sell_popup) and taken to be
# centered like TTR's other dialogs.
SELL_CANCEL = _center(0.1492, 0.2874)
SELL_ALL = _center(0.2993, 0.2859)
# The bean picker, measured at 1920x1009 (gardening_bean_picker captures) and taken
# to be centered like other dialogs.
PLANT_CANCEL = _center(-0.1506, 0.1724)
PLANT_RESET = _center(-0.0005, 0.1724)
PLANT = _center(0.1492, 0.1710)
_PLANT_FILL = (_center(0.337, -0.2027), _center(0.0, -0.1234), _center(0.337, 0.1938), _center(-0.337, 0.1938))
BEANS = 9  # red, green, orange, purple, blue, pink, yellow, cyan, gray
_BEAN_X0, _BEAN_STEP, _BEAN_Y = -0.2071, 0.05228, -0.0535
BEAN_SIZE = (0.050, 0.056)  # a bean's cell, for the highlight frame
_BEAN_MARGIN = (-0.016, 0.019)  # a spot on a cell's white margin, beside its bean
_BEANS_MIN = 7  # cells with their white margin showing, for the row to be there


# OK-only popups (gardening_failed_combo_popup, 1920x1009): the OK button is on the
# window's middle column, its height depending on the message, so it's searched for
# down that column; the popup's fill shows either side of it.
_OK_SCAN = (-0.1, 0.4)  # from the window's middle
_OK_DROP = 0.0115  # from the button's top edge down to its middle (its white tick hides the middle)
_OK_FILL = ((-0.1, 0.0), (0.1, 0.0), (0.0, -0.06))


def bean_point(i: int) -> ui.UIPoint:
    return _center(_BEAN_X0 + _BEAN_STEP * i, _BEAN_Y)


_SELL_FILL = (_center(-0.4559, -0.0045), _center(0.4361, -0.0045), _center(0.0, 0.2136))


def _is_cancel_red(c: RGB) -> bool:
    r, g, b = c
    return r > 170 and g < 110 and b < 110


def _is_ok_blue(c: RGB) -> bool:
    r, g, b = c
    return b > 180 and b - r > 80


def _is_popup_yellow(c: RGB) -> bool:
    r, g, b = c
    return r > 240 and g > 240 and 170 < b < 210


def is_panel_yellow(c: RGB) -> bool:
    r, g, b = c
    return r > 240 and g > 240 and 120 < b < 165


def is_border_green(c: RGB) -> bool:
    r, g, b = c
    return g > 130 and g - r > 70 and g - b > 70


@dataclass(frozen=True)
class GardenScreen:
    top: ui.UIPoint | None = None  # the top button, if there is one
    bottom: ui.UIPoint | None = None
    selling: bool = False  # the sell popup is up (over everything else)
    ok: ui.UIPoint | None = None  # an OK-only popup's OK button (a failed bean combination)
    planting: bool = False  # the bean picker popup is up
    beans: bool = False  # and its row of beans (gone once no more can be added)

    @property
    def is_open(self) -> bool:
        return (self.top is not None or self.bottom is not None or self.selling or self.planting
                or self.ok is not None)

    @property
    def popup(self) -> bool:
        """A gardening popup is up (it takes A and B; the NPC bubble search can misread it)."""
        return self.selling or self.planting or self.ok is not None


def _read_sell(width: int, height: int, get_pixel: PixelReader) -> bool:
    def hits(points, test) -> int:
        return sum(test(get_pixel(*p.to_client(width, height))) for p in points)

    return (hits(_SELL_FILL, _is_popup_yellow) == len(_SELL_FILL)
            and hits(ui.around(SELL_CANCEL, 0.009), _is_cancel_red) >= 3
            and hits(_blue_button(SELL_ALL), _is_ok_blue) >= 3)


def _blue_button(point: ui.UIPoint) -> tuple[ui.UIPoint, ...]:
    """Spots on a blue tick button's blue, around its white tick."""
    return tuple(point.offset(dx, dy) for dx, dy in ((-0.006, -0.006), (-0.003, -0.006), (-0.008, -0.002),
                                                     (0.008, 0.007)))


def _read_planting(width: int, height: int, get_pixel: PixelReader) -> GardenScreen | None:
    def hits(points, test) -> int:
        return sum(test(get_pixel(*p.to_client(width, height))) for p in points)

    if not (hits(_PLANT_FILL, _is_popup_yellow) == len(_PLANT_FILL)
            and hits(ui.around(PLANT_CANCEL, 0.009), _is_cancel_red) >= 3
            and hits(ui.around(PLANT_RESET, 0.009), _is_cancel_red) >= 3
            and hits(_blue_button(PLANT), _is_ok_blue) >= 3):
        return None
    margins = [bean_point(i).offset(*_BEAN_MARGIN) for i in range(BEANS)]
    beans = hits(margins, lambda c: min(c) > 225) >= _BEANS_MIN
    return GardenScreen(planting=True, beans=beans)


def _read_ok(width: int, height: int, get_pixel: PixelReader) -> ui.UIPoint | None:
    unit = min(width, height)
    x = width // 2
    top, bottom = (round(height / 2 + y * unit) for y in _OK_SCAN)
    first = next((y for y in range(max(0, top), min(height, bottom)) if _is_ok_blue(get_pixel(x, y))), None)
    if first is None:
        return None
    point = _center(0.0, (first - height / 2) / unit + _OK_DROP)
    if sum(_is_ok_blue(get_pixel(*p.to_client(width, height))) for p in _blue_button(point)) < 3:
        return None
    if not all(_is_popup_yellow(get_pixel(*point.offset(dx, dy).to_client(width, height))) for dx, dy in _OK_FILL):
        return None
    return point


def read_garden(width: int, height: int, get_pixel: PixelReader) -> GardenScreen:
    if _read_sell(width, height, get_pixel):
        return GardenScreen(selling=True)
    planting = _read_planting(width, height, get_pixel)
    if planting is not None:
        return planting
    ok = _read_ok(width, height, get_pixel)
    if ok is not None:
        return GardenScreen(ok=ok)
    unit = min(width, height)
    x = round(_SCAN_X * unit)
    # The longest run of panel fill down the column, in the top two thirds. A wide
    # button label (Remove) reaches past the panel's edge, so its letters don't end it.
    gap = round(_LABEL_GAP * unit)
    best, start, last = (0, 0), None, None
    for y in range(0, round(height * 2 / 3) + 1):
        if is_panel_yellow(get_pixel(x, y)):
            if start is None or y - last > gap:
                start = y
            last = y
            if y - start > best[1] - best[0]:
                best = (start, y)
    top, bottom = best
    if not (_HEIGHT[0] * unit <= bottom - top <= _HEIGHT[1] * unit):
        return GardenScreen()
    middle = (top + bottom) // 2
    if not any(is_border_green(get_pixel(bx, middle)) for bx in range(0, round(_BORDER_X * unit) + 1)):
        return GardenScreen()

    def button(dy: float) -> ui.UIPoint | None:
        point = ui.UIPoint("left", _BUTTON_X, top / unit + dy)
        filled = sum(not is_panel_yellow(get_pixel(*point.offset(sx, sy).to_client(width, height)))
                     for sx, sy in _BUTTON_SPOTS)
        return point if filled >= _BUTTON_MIN else None

    return GardenScreen(*(button(dy) for dy in _BUTTON_DYS))


def default_garden_bindings() -> Bindings:
    """The panel's buttons (top, bottom), the sell popup's (select, back) and the bean
    picker's (left/right, select, back, reset, plant)."""
    press = {"y": "top", "x": "bottom", "a": "select", "b": "back"}
    for d in ("up", "down", "left", "right"):
        press[f"dpad_{d}"] = d
    return Bindings(press=press)


_SELL_ACTIONS = {"select", "back"}
# The bean picker's: Y and X there plant and reset instead of the panel's buttons.
_PLANT_ACTIONS = {"select", "back", "top", "bottom", "up", "down", "left", "right"}
_PANEL_ACTIONS = {"top", "bottom"}


class GardenMapper:
    def __init__(self, bindings: Bindings | None = None):
        self.bindings = bindings or default_garden_bindings()
        self._actions = ButtonActions(self.bindings, 0.5, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in ("left", "right"))
        self.bean: int | None = None  # the bean hovered in the picker (None: the picker isn't up)
        self._beans_shown = False

    def buttons(self, screen: GardenScreen) -> frozenset[str]:
        """The buttons it takes: the bean picker's, the sell popup's A and B, or the
        panel's Y and X (A still jumps then)."""
        actions = (_PLANT_ACTIONS if screen.planting else _SELL_ACTIONS if screen.selling or screen.ok
                   else _PANEL_ACTIONS)
        return frozenset(b for b, a in self.bindings.press.items() if a in actions)

    @property
    def hovering(self) -> bool:
        return self.bean is not None and self._beans_shown

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)

    def _hover_bean(self) -> PointerCommand:
        return PointerCommand("hover", bean_point(self.bean), f"bean {self.bean + 1}", size=BEAN_SIZE)

    def update(self, buttons: frozenset[str], now: float, screen: GardenScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons, now)
        commands = []
        if not screen.planting:
            self.bean = None  # it opens on the red bean next time
            self._beans_shown = False
        elif screen.beans and not self._beans_shown:
            # Opened (on the red bean), or the beans are back after a reset (on the one last hovered).
            self.bean = 0 if self.bean is None else self.bean
            commands.append(self._hover_bean())
        if screen.planting:
            self._beans_shown = screen.beans
        for action in fired:
            if screen.planting:
                commands += self._run_planting(action, screen)
                continue
            if screen.ok is not None:
                point, name = (screen.ok, "OK") if action in _SELL_ACTIONS else (None, "")
            elif screen.selling:
                point, name = {"select": (SELL_ALL, "sell all"), "back": (SELL_CANCEL, "cancel selling")}.get(
                    action, (None, ""))
            else:
                point = screen.top if action == "top" else screen.bottom if action == "bottom" else None
                name = f"garden {action} button"
            if point is not None:
                commands.append(PointerCommand("click", point, name))
        return commands

    def _run_planting(self, action: str, screen: GardenScreen) -> list[PointerCommand]:
        if action in ("left", "right") and screen.beans:
            self.bean = (self.bean + (1 if action == "right" else -1)) % BEANS
            return [self._hover_bean()]
        if action == "select" and screen.beans:
            return [PointerCommand("click", bean_point(self.bean), f"add bean {self.bean + 1}")]
        if action == "top" or (action == "select" and not screen.beans):
            return [PointerCommand("click", PLANT, "plant")]
        if action == "bottom":
            return [PointerCommand("click", PLANT_RESET, "reset beans")]
        if action == "back":
            return [PointerCommand("click", PLANT_CANCEL, "cancel planting")]
        return []
