"""LB + RB together: a combo of its own.

Each bumper also does something alone (the friends list, the book's pages, battle
teammates), so a bumper pressed on its own is held back for a moment to see if the
other one follows. Pressed together, the combo starts and neither counts until it's
let go; otherwise the bumper goes through as usual, just that moment late (a quick
tap, let go within the moment, goes through as it's let go).

While both are held, D-pad left and right switch to the TTR window on that side (one
toon; app.py does the switching), and the D-pad doesn't reach the screen underneath.
Let go of both without touching the D-pad, and it's a screenshot (the user, Nov 9: the
screenshot used to fire as both went down).
"""

from dataclasses import replace

from .controller import ControllerState

COMBO_WINDOW_SECONDS = 0.08
COMBO_BUTTONS = frozenset({"lb", "rb"})
SIDES = {"dpad_left": -1, "dpad_right": 1}


class ButtonCombo:
    def __init__(self, buttons: frozenset[str] = COMBO_BUTTONS, window: float = COMBO_WINDOW_SECONDS) -> None:
        self.buttons = buttons
        self.window = window
        self._pending: dict[str, float] = {}  # pressed, waiting to see if the other follows
        self._passed: set[str] = set()  # pressed alone: goes through
        self._used: set[str] = set()  # part of a combo: held back until let go
        self._before: frozenset[str] = frozenset()  # last frame's buttons
        self._taken: set[str] = set()  # D-pad directions the combo used, until let go
        self._switched = False  # the D-pad was used during this combo: no screenshot

    def update(self, state: ControllerState, now: float) -> tuple[ControllerState, bool, int]:
        """The state with any button held back taken out, whether the combo just ended as a
        screenshot, and a window switch: -1 (left), 1 (right) or 0."""
        pressed = state.buttons - self._before
        self._before = state.buttons
        was_on = bool(self._used)
        down = state.buttons & self.buttons
        tapped = set()  # let go while held back: a quick tap, passed on now (for one frame)
        for name in self.buttons - down:
            if self._pending.pop(name, None) is not None:
                tapped.add(name)
            self._passed.discard(name)
            self._used.discard(name)
        for name in down - self._pending.keys() - self._passed - self._used:
            self._pending[name] = now
        if len(self._pending) == len(self.buttons):
            self._used |= set(self._pending)
            self._pending.clear()
            self._switched = False
        for name, since in list(self._pending.items()):
            if now - since >= self.window:
                del self._pending[name]
                self._passed.add(name)
        step = 0
        self._taken &= state.buttons
        if self._used:
            for name, side in SIDES.items():
                if name in pressed:
                    step = side
                    self._switched = True
                if name in state.buttons:
                    self._taken.add(name)
        screenshot = was_on and not self._used and not self._switched
        held_back = set(self._pending) | self._used | self._taken
        if held_back or tapped:
            state = replace(state, buttons=(state.buttons - held_back) | tapped)
        return state, screenshot, step
