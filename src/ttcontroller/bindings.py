"""Turn button presses into actions using a press table and a hold table.

Shared by the overworld and battle mappers. A button can have:
  - a press action, which is held while the button is held (for TTR keys), or
    fires once when pressed (for one-shot actions), and can auto-repeat;
  - a hold action, which fires after holding the button for hold_seconds. Then
    its press action fires as a tap on an early release instead.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

# Stick directions act like extra buttons so they can be bound too.
STICK_BUTTONS = ("ls_up", "ls_down", "ls_left", "ls_right", "rs_up", "rs_down", "rs_left", "rs_right")


def stick_buttons(prefix: str, x: float, y: float, threshold: float) -> set[str]:
    """Directions a stick is pushed past the threshold (SDL's y is negative when pushed up)."""
    held = set()
    if y < -threshold:
        held.add(f"{prefix}_up")
    elif y > threshold:
        held.add(f"{prefix}_down")
    if x < -threshold:
        held.add(f"{prefix}_left")
    elif x > threshold:
        held.add(f"{prefix}_right")
    return held


@dataclass
class Bindings:
    press: dict[str, str] = field(default_factory=dict)
    hold: dict[str, str] = field(default_factory=dict)

    def buttons(self) -> set[str]:
        return set(self.press) | set(self.hold)


@dataclass(frozen=True)
class RepeatTiming:
    delay: float = 0.4  # before the first repeat
    interval: float = 0.12  # between repeats


class ButtonActions:
    def __init__(self, bindings: Bindings, hold_seconds: float, is_oneshot: Callable[[str], bool],
                 repeats: Callable[[str], bool] = lambda action: False, repeat: RepeatTiming = RepeatTiming()):
        self.bindings = bindings
        self.hold_seconds = hold_seconds
        self.is_oneshot = is_oneshot
        self.repeats = repeats
        self.repeat = repeat
        self.reset()

    def reset(self, ignore_held: bool = False) -> None:
        """Forget all button state. With ignore_held, buttons held at the next update
        do nothing until released, so letting go of one can't look like a fresh tap."""
        self._prev: frozenset[str] = frozenset()
        self._down_at: dict[str, float] = {}
        self._hold_fired: set[str] = set()
        self._next_repeat: dict[str, float] = {}
        self._ignored: set[str] = set()
        self._ignore_held_next = ignore_held

    def ignore_held(self) -> None:
        """Make the buttons held right now do nothing until they're released."""
        self._ignored |= self._prev
        self._prev = frozenset()
        self._down_at.clear()
        self._next_repeat.clear()

    def update(self, buttons: frozenset[str], now: float) -> tuple[set[str], list[str]]:
        """Return (actions to hold right now, one-shot actions that fired this frame)."""
        if self._ignore_held_next:
            self._ignore_held_next = False
            self._ignored |= buttons
        self._ignored &= buttons  # a released button counts again
        buttons = buttons - self._ignored
        pressed = buttons - self._prev
        released = self._prev - buttons
        self._prev = buttons
        held: set[str] = set()
        fired: list[str] = []

        for button, action in self.bindings.press.items():
            if button in self.bindings.hold:
                continue  # handled below, since it depends on how long it's held
            if not self.is_oneshot(action):
                if button in buttons:
                    held.add(action)
            elif button in pressed:
                fired.append(action)
                if self.repeats(action):
                    self._next_repeat[button] = now + self.repeat.delay
            elif button in buttons and button in self._next_repeat and now >= self._next_repeat[button]:
                fired.append(action)
                self._next_repeat[button] = now + self.repeat.interval
            if button not in buttons:
                self._next_repeat.pop(button, None)

        for button, hold_action in self.bindings.hold.items():
            if button in pressed:
                self._down_at[button] = now
                self._hold_fired.discard(button)
            elif button in buttons and button in self._down_at and button not in self._hold_fired:
                if now - self._down_at[button] >= self.hold_seconds:
                    fired.append(hold_action)
                    self._hold_fired.add(button)
            if button in released:
                if button in self._down_at and button not in self._hold_fired:
                    press_action = self.bindings.press.get(button)
                    if press_action:
                        fired.append(press_action)
                self._down_at.pop(button, None)

        return held, fired
