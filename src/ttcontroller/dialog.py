"""TTR's OK/Cancel dialogs: a pale yellow panel centered on the window, with a blue
OK circle and a red Cancel circle side by side near its bottom. Dialogs differ in
height (the run prompt, saving and loading a gag preset), so the buttons are found
by scanning for the Cancel circle rather than at a fixed spot. OK's blue circle must
be beside it too: the new toon tutorial's popup has a red picture where Cancel would
be (new_toon_popup), and only an OK (read by the garden's OK-only popup reader).
"""

from collections.abc import Callable

from . import ui

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]

_OK_X, _CANCEL_X = -0.0555, 0.0541
_SCAN_X = 0.047  # through the Cancel circle, left of its white X
_SCAN_TOP, _SCAN_BOTTOM = -0.1, 0.35
_OK_SIDE = 0.012  # OK's blue either side of its white tick
_FILL_XS = (-0.15, -0.13, 0.13, 0.15)  # dialog fill on either side of the buttons (the narrowest dialog, Exit Toontown?, is 0.34 wide)


def _center(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "center")


def _is_cancel_red(c: RGB) -> bool:
    return c[0] > 170 and c[1] < 90 and c[2] < 95 and c[0] - c[1] > 100


def _is_ok_blue(c: RGB) -> bool:
    r, g, b = c
    return b > 140 and b - r > 50


def is_dialog_yellow(c: RGB) -> bool:
    return c[0] > 240 and c[1] > 240 and 160 < c[2] < 215


_ALONE_SCAN_X = -0.010  # down a lone Cancel's circle, left of its white X
_ALONE_X = -0.002  # its middle
_ALONE_FILL_XS = (-0.15, -0.06, 0.06, 0.15)  # dialog fill either side: no OK beside it


def _is_alone_red(c: RGB) -> bool:
    # A lone Cancel's red, lighter (pinker) at its top: (250, 144, 149) down to (168, 46, 49).
    r, g, b = c
    return r > 150 and r - g > 60 and r - b > 60


def find_cancel_alone(width: int, height: int, get_pixel: PixelReader) -> ui.UIPoint | None:
    """A centered dialog with just a red Cancel in its middle: "You cannot leave this area
    because you are part of a Boarding Group." (boarding_groups_restricted_popup). A or B
    clicks it."""
    unit = min(width, height)
    px = round(width / 2 + _ALONE_SCAN_X * unit)
    top, bottom = (round(height / 2 + y * unit) for y in (_SCAN_TOP, _SCAN_BOTTOM))
    reds = [py for py in range(max(top, 0), min(bottom, height)) if _is_alone_red(get_pixel(px, py))]
    if not reds:
        return None
    run = [reds[0]]
    for py in reds[1:]:
        if py - run[-1] > 3:
            break
        run.append(py)
    if not 0.018 * unit <= run[-1] - run[0] <= 0.05 * unit:
        return None
    y = ((run[0] + run[-1]) / 2 - height / 2) / unit
    if not all(is_dialog_yellow(get_pixel(*_center(x, y).to_client(width, height))) for x in _ALONE_FILL_XS):
        return None
    if not is_dialog_yellow(get_pixel(*_center(0.0, y - 0.05).to_client(width, height))):
        return None
    return _center(_ALONE_X, y)


def find_ok_cancel(width: int, height: int, get_pixel: PixelReader) -> tuple[ui.UIPoint, ui.UIPoint] | None:
    """The OK and Cancel buttons of the dialog showing, if one is."""
    unit = min(width, height)
    px = round(width / 2 + _SCAN_X * unit)
    top, bottom = (round(height / 2 + y * unit) for y in (_SCAN_TOP, _SCAN_BOTTOM))
    reds = [py for py in range(top, bottom + 1) if _is_cancel_red(get_pixel(px, py))]
    if not reds or reds[-1] - reds[0] > 0.05 * unit:
        return None
    y = ((reds[0] + reds[-1]) / 2 - height / 2) / unit
    fill = sum(is_dialog_yellow(get_pixel(*_center(x, y).to_client(width, height))) for x in _FILL_XS)
    if fill < 3:
        return None
    ok = _center(_OK_X, y)
    if not all(_is_ok_blue(get_pixel(*ok.offset(dx, 0.0).to_client(width, height))) for dx in (-_OK_SIDE, _OK_SIDE)):
        return None
    return ok, _center(_CANCEL_X, y)


class DialogMapper:
    """A and B on an OK/Cancel dialog that no other screen owns, while walking around
    with nothing else open: "Do you want to teleport to your Estate?" (estate_popup) is
    laid out like the battle's Run? prompt but comes up outside battles."""

    BUTTONS = frozenset({"a", "b"})

    def __init__(self):
        from .bindings import Bindings, ButtonActions
        self._actions = ButtonActions(Bindings(press={"a": "ok", "b": "cancel"}), 0.5,
                                      is_oneshot=lambda action: True)

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)

    def update(self, buttons: frozenset[str], now: float, dialog: tuple[ui.UIPoint, ui.UIPoint]):
        """dialog: its OK and Cancel (find_ok_cancel). Returns PointerCommands."""
        from .battle import PointerCommand
        _, fired = self._actions.update(buttons, now)
        ok, cancel = dialog
        return [PointerCommand("click", ok if action == "ok" else cancel, f"dialog {action}") for action in fired]
