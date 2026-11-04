"""Overworld mapping: controller state in, TTR controls to hold out.

The mapper is declarative: every frame it returns the full set of TTR controls
(names from settings.json, e.g. "forward", "jump") that should be held right now.
The output layer diffs that against what is already held, so a key can never
get stuck down.

Bindings map a button to an action. An action is either a TTR control name
(held while the button is held) or one of the special actions below.
"""

from dataclasses import dataclass, field
from typing import Protocol

from . import ui
from .controller import ControllerState
from .movement import MovementTuning, stick_to_movement


class ScreenView(Protocol):
    def is_visible(self, button: ui.Button) -> bool: ...


# Actions that do more than hold a TTR key.
SPECIAL_ACTIONS = {
    "sprint": "double-tap forward to sprint",
    "friendsList": "open the friends list, or close it if it's open",
    "back": "close whatever is open (the friends list for now)",
}

# Right stick directions act like extra buttons so they can be bound too.
STICK_BUTTONS = ("rs_up", "rs_down", "rs_left", "rs_right")


@dataclass
class Bindings:
    # Button -> action while pressed. If the button also has a hold action,
    # this fires as a quick tap when the button is released early instead.
    press: dict[str, str] = field(default_factory=lambda: {
        "a": "jump",
        "b": "back",
        "l3": "sprint",
        "r3": "cameraNext",
        "rb": "friendsList",
        "dpad_left": "showGags",
        "dpad_right": "showTasks",
        "dpad_up": "showMap",
        "start": "stickerBook",
        "rs_up": "lookUp",
        "rs_down": "lookDown",
    })
    # Button -> action after holding it for hold_seconds.
    hold: dict[str, str] = field(default_factory=lambda: {
        "start": "options",
    })


@dataclass
class Timing:
    # Holding a button with a hold action this long triggers it.
    hold_seconds: float = 0.5
    # Sprint is a fresh double-tap of forward, even if forward is already held:
    # release, tap, release, then hold. Each of the first three steps lasts this long.
    sprint_step_seconds: float = 0.06
    # Clicking sprint while standing still arms it for this long.
    sprint_arm_seconds: float = 1.0
    # Right stick tilt needed to count as a stick button press.
    stick_button_threshold: float = 0.5


# One-shot key presses last this long so the game sees both the press and release.
PULSE_SECONDS = 0.06
_SPRINT_STEPS = (False, True, False)


def stick_buttons(x: float, y: float, threshold: float) -> set[str]:
    held = set()
    if y < -threshold:
        held.add("rs_up")
    elif y > threshold:
        held.add("rs_down")
    if x < -threshold:
        held.add("rs_left")
    elif x > threshold:
        held.add("rs_right")
    return held


class OverworldMapper:
    def __init__(self, bindings: Bindings | None = None, tuning: MovementTuning = MovementTuning(),
                 timing: Timing | None = None):
        self.bindings = bindings or Bindings()
        self.tuning = tuning
        self.timing = timing or Timing()
        self.reset()

    def reset(self) -> None:
        self._prev_buttons: frozenset[str] = frozenset()
        self._pulses: dict[str, float] = {}
        self._clicks: list[ui.Button] = []
        self._down_at: dict[str, float] = {}
        self._hold_fired: set[str] = set()
        self._sprint_armed_until: float | None = None
        self._sprint_started_at: float | None = None

    def take_clicks(self) -> list[ui.Button]:
        """On-screen buttons to click, requested since the last call."""
        clicks, self._clicks = self._clicks, []
        return clicks

    def update(self, state: ControllerState, now: float, screen: ScreenView | None = None) -> set[str]:
        buttons = frozenset(state.buttons | stick_buttons(*state.right_stick, self.timing.stick_button_threshold))
        pressed = buttons - self._prev_buttons
        released = self._prev_buttons - buttons
        self._prev_buttons = buttons

        controls = stick_to_movement(*state.left_stick, self.tuning)

        for button, action in self.bindings.press.items():
            if button in self.bindings.hold:
                continue  # handled below, since it depends on how long it's held
            if action in SPECIAL_ACTIONS:
                if button in pressed:
                    self._run(action, now, screen)
            elif button in buttons:
                controls.add(action)

        for button, action in self.bindings.hold.items():
            self._update_hold(button, action, pressed, released, buttons, now, screen)

        self._update_sprint(controls, now)

        self._pulses = {c: until for c, until in self._pulses.items() if now < until}
        controls.update(self._pulses)
        return controls

    def _run(self, action: str, now: float, screen: ScreenView | None) -> None:
        """Do a one-shot action: a special action, or a quick tap of a TTR control."""
        if action == "sprint":
            self._sprint_armed_until = now + self.timing.sprint_arm_seconds
        elif action in ("friendsList", "back"):
            # The friends list key only opens it; closing takes a click on its X.
            # The screen is only checked on a press, since reading pixels is slow.
            if screen is not None and screen.is_visible(ui.FRIENDS_CLOSE):
                self._clicks.append(ui.FRIENDS_CLOSE)
            elif action == "friendsList":
                self._pulse("friendsList", now)
        else:
            self._pulse(action, now)

    def _pulse(self, control: str, now: float) -> None:
        self._pulses[control] = now + PULSE_SECONDS

    def _update_hold(self, button, hold_action, pressed, released, buttons, now, screen) -> None:
        if button in pressed:
            self._down_at[button] = now
            self._hold_fired.discard(button)
        elif button in buttons and button in self._down_at and button not in self._hold_fired:
            if now - self._down_at[button] >= self.timing.hold_seconds:
                self._run(hold_action, now, screen)
                self._hold_fired.add(button)
        if button in released:
            if button in self._down_at and button not in self._hold_fired:
                press_action = self.bindings.press.get(button)
                if press_action:
                    self._run(press_action, now, screen)
            self._down_at.pop(button, None)

    def _update_sprint(self, controls: set[str], now: float) -> None:
        if "forward" not in controls:
            self._sprint_started_at = None
            if self._sprint_armed_until is not None and now > self._sprint_armed_until:
                self._sprint_armed_until = None
            return

        if self._sprint_armed_until is not None and self._sprint_started_at is None:
            self._sprint_started_at = now
            self._sprint_armed_until = None

        if self._sprint_started_at is not None:
            step = int((now - self._sprint_started_at) / self.timing.sprint_step_seconds)
            if step < len(_SPRINT_STEPS):
                if not _SPRINT_STEPS[step]:
                    controls.discard("forward")
            else:
                self._sprint_started_at = None
