"""LB + RB together: a combo of its own (a screenshot).

Each bumper also does something alone (the friends list, the book's pages, battle
teammates), so a bumper pressed on its own is held back for a moment to see if the
other one follows. Pressed together, the combo fires and neither counts until it's
let go; otherwise the bumper goes through as usual, just that moment late (a quick
tap, let go within the moment, goes through as it's let go).
"""

from dataclasses import replace

from .controller import ControllerState

COMBO_WINDOW_SECONDS = 0.08
COMBO_BUTTONS = frozenset({"lb", "rb"})


class ButtonCombo:
    def __init__(self, buttons: frozenset[str] = COMBO_BUTTONS, window: float = COMBO_WINDOW_SECONDS) -> None:
        self.buttons = buttons
        self.window = window
        self._pending: dict[str, float] = {}  # pressed, waiting to see if the other follows
        self._passed: set[str] = set()  # pressed alone: goes through
        self._used: set[str] = set()  # part of a combo: held back until let go

    def update(self, state: ControllerState, now: float) -> tuple[ControllerState, bool]:
        """The state with any button held back taken out, and whether the combo just fired."""
        down = state.buttons & self.buttons
        tapped = set()  # let go while held back: a quick tap, passed on now (for one frame)
        for name in self.buttons - down:
            if self._pending.pop(name, None) is not None:
                tapped.add(name)
            self._passed.discard(name)
            self._used.discard(name)
        for name in down - self._pending.keys() - self._passed - self._used:
            self._pending[name] = now
        fired = False
        if len(self._pending) == len(self.buttons):
            fired = True
            self._used |= set(self._pending)
            self._pending.clear()
        for name, since in list(self._pending.items()):
            if now - since >= self.window:
                del self._pending[name]
                self._passed.add(name)
        held_back = set(self._pending) | self._used
        if held_back or tapped:
            state = replace(state, buttons=(state.buttons - held_back) | tapped)
        return state, fired
