"""TTR's OK/Cancel dialogs: a pale yellow panel centered on the window, with a blue
OK circle and a red Cancel circle side by side near its bottom. Dialogs differ in
height (the run prompt, saving and loading a gag preset), so the buttons are found
by scanning for the Cancel circle rather than at a fixed spot.
"""

from collections.abc import Callable

from . import ui

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]

_OK_X, _CANCEL_X = -0.0555, 0.0541
_SCAN_X = 0.047  # through the Cancel circle, left of its white X
_SCAN_TOP, _SCAN_BOTTOM = -0.1, 0.35
_FILL_XS = (-0.22, -0.2, 0.2, 0.22)  # dialog fill on either side of the buttons


def _center(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "center")


def _is_cancel_red(c: RGB) -> bool:
    return c[0] > 170 and c[1] < 90 and c[2] < 95 and c[0] - c[1] > 100


def is_dialog_yellow(c: RGB) -> bool:
    return c[0] > 240 and c[1] > 240 and 160 < c[2] < 215


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
    return _center(_OK_X, y), _center(_CANCEL_X, y)
