"""The estate mailbox, open: a cardboard box in the middle of the window showing one
item at a time, with red arrows either side to go through them, Take this item and
Discard this item stacked between them, and a yellow CLOSE MAILBOX button in its
bottom right (mailbox_popup captures, 1920x1009; taken to be centered like other
dialogs).

The D-pad's left and right click the arrows, A takes the item, X discards it and B
closes the mailbox. Nothing is hovered: the buttons show their own labels on hover.
"""

from collections.abc import Callable
from dataclasses import dataclass

from . import ui
from .battle import PointerCommand
from .bindings import Bindings, ButtonActions

RGB = tuple[int, int, int]
PixelReader = Callable[[int, int], RGB]


def _center(x: float, y: float) -> ui.UIPoint:
    return ui.UIPoint("center", x, y, "center")


LEFT = _center(-0.1878, 0.1373)
RIGHT = _center(0.1620, 0.1373)
TAKE = _center(-0.0050, 0.0880)
DISCARD = _center(-0.0050, 0.1960)
CLOSE = _center(0.2765, 0.2275)

_CREAM = (_center(-0.2, -0.3), _center(0.24, -0.2), _center(0.0, 0.015))  # the item's panel
_CARDBOARD = (_center(0.33, -0.15), _center(0.33, -0.25), _center(-0.36, 0.19))
_CLOSE_ROW = tuple(CLOSE.offset(-0.08 + 0.01 * i, 0.0) for i in range(17))  # across CLOSE MAILBOX


def _is_cream(c: RGB) -> bool:
    r, g, b = c
    return r > 215 and g > 210 and 160 < b < 200 and r - b > 35


def _is_cardboard(c: RGB) -> bool:
    r, g, b = c
    return 140 < r < 210 and 95 < g < 160 and 50 < b < 115 and r - g > 30 and g - b > 30


def _is_close_yellow(c: RGB) -> bool:
    r, g, b = c
    return r > 190 and g > 190 and b < 110


def _is_arrow_red(c: RGB) -> bool:
    r, g, b = c
    return r > 150 and r - g > 70 and r - b > 70


@dataclass(frozen=True)
class MailboxScreen:
    is_open: bool = False


def read_mailbox(width: int, height: int, get_pixel: PixelReader) -> MailboxScreen:
    def hits(points, test) -> int:
        return sum(test(get_pixel(*p.to_client(width, height))) for p in points)

    for p in (*_CREAM, *_CARDBOARD, LEFT, RIGHT, *_CLOSE_ROW):
        x, y = p.to_client(width, height)
        if not (0 <= x < width and 0 <= y < height):
            return MailboxScreen()  # cut off by a narrow window
    is_open = (hits(_CREAM, _is_cream) == len(_CREAM)
               and hits(_CARDBOARD, _is_cardboard) >= 2
               and hits((LEFT, RIGHT), _is_arrow_red) == 2
               and hits(_CLOSE_ROW, _is_close_yellow) >= 4)  # its green lettering covers the rest
    return MailboxScreen(is_open)


def default_mailbox_bindings() -> Bindings:
    return Bindings(press={"dpad_left": "previous", "dpad_right": "next", "a": "take", "x": "discard",
                           "b": "close"})


_CLICKS = {"previous": (LEFT, "previous item"), "next": (RIGHT, "next item"), "take": (TAKE, "take this item"),
           "discard": (DISCARD, "discard this item"), "close": (CLOSE, "close mailbox")}


class MailboxMapper:
    def __init__(self, bindings: Bindings | None = None):
        self.bindings = bindings or default_mailbox_bindings()
        self._actions = ButtonActions(self.bindings, 0.5, is_oneshot=lambda action: True,
                                      repeats=lambda action: action in ("previous", "next"))

    @property
    def buttons(self) -> frozenset[str]:
        return frozenset(self.bindings.press)

    def reset_buttons(self) -> None:
        self._actions.reset(ignore_held=True)

    def update(self, buttons: frozenset[str], now: float, screen: MailboxScreen) -> list[PointerCommand]:
        _, fired = self._actions.update(buttons, now)
        if not screen.is_open:
            return []
        return [PointerCommand("click", *_CLICKS[action]) for action in fired if action in _CLICKS]
