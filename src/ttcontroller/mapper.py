"""Overworld mapping: controller state in, TTR controls to hold out.

The mapper is declarative: every frame it returns the full set of TTR controls
(names from settings.json, e.g. "forward", "jump") that should be held right now.
The output layer diffs that against what is already held, so a key can never
get stuck down.
"""

from .controller import ControllerState
from .movement import MovementTuning, stick_to_movement

# Buttons that hold a TTR control for as long as they are held.
HOLD_BINDINGS = {
    "a": "jump",
    "rb": "friendsList",
    "dpad_left": "showGags",
    "dpad_right": "showTasks",
    "dpad_up": "showMap",
    "r3": "cameraNext",
}

# One-shot key presses last this long so the game sees both the press and release.
PULSE_SECONDS = 0.06
# Holding Start this long opens game settings instead of the shticker book.
START_HOLD_SECONDS = 0.5
# Sprint is a fresh double-tap of forward, even if forward is already held:
# release, tap, release, then hold. Each of the first three steps lasts this long.
SPRINT_STEP_SECONDS = 0.06
_SPRINT_STEPS = (False, True, False)
# Clicking L3 while standing still arms sprint for this long.
SPRINT_ARM_SECONDS = 1.0
# Right stick vertical tilt needed to look up/down.
LOOK_THRESHOLD = 0.5


class OverworldMapper:
    def __init__(self, tuning: MovementTuning = MovementTuning()):
        self.tuning = tuning
        self.reset()

    def reset(self) -> None:
        self._prev_buttons: frozenset[str] = frozenset()
        self._pulses: dict[str, float] = {}
        self._start_down_at: float | None = None
        self._start_hold_fired = False
        self._sprint_armed_until: float | None = None
        self._sprint_started_at: float | None = None

    def update(self, state: ControllerState, now: float) -> set[str]:
        buttons = state.buttons
        pressed = buttons - self._prev_buttons
        released = self._prev_buttons - buttons
        self._prev_buttons = buttons

        controls = stick_to_movement(*state.left_stick, self.tuning)
        controls.update(control for button, control in HOLD_BINDINGS.items() if button in buttons)

        look_y = state.right_stick[1]
        if look_y < -LOOK_THRESHOLD:
            controls.add("lookUp")
        elif look_y > LOOK_THRESHOLD:
            controls.add("lookDown")

        self._update_start(pressed, released, buttons, now)
        self._update_sprint(pressed, controls, now)

        self._pulses = {c: until for c, until in self._pulses.items() if now < until}
        controls.update(self._pulses)
        return controls

    def _pulse(self, control: str, now: float) -> None:
        self._pulses[control] = now + PULSE_SECONDS

    def _update_start(self, pressed, released, buttons, now: float) -> None:
        if "start" in pressed:
            self._start_down_at = now
            self._start_hold_fired = False
        elif "start" in buttons and self._start_down_at is not None and not self._start_hold_fired:
            if now - self._start_down_at >= START_HOLD_SECONDS:
                self._pulse("options", now)
                self._start_hold_fired = True
        if "start" in released:
            if self._start_down_at is not None and not self._start_hold_fired:
                self._pulse("stickerBook", now)
            self._start_down_at = None

    def _update_sprint(self, pressed, controls: set[str], now: float) -> None:
        if "l3" in pressed:
            self._sprint_armed_until = now + SPRINT_ARM_SECONDS

        if "forward" not in controls:
            self._sprint_started_at = None
            if self._sprint_armed_until is not None and now > self._sprint_armed_until:
                self._sprint_armed_until = None
            return

        if self._sprint_armed_until is not None and self._sprint_started_at is None:
            self._sprint_started_at = now
            self._sprint_armed_until = None

        if self._sprint_started_at is not None:
            step = int((now - self._sprint_started_at) / SPRINT_STEP_SECONDS)
            if step < len(_SPRINT_STEPS):
                if not _SPRINT_STEPS[step]:
                    controls.discard("forward")
            else:
                self._sprint_started_at = None
