"""Overworld mapping: controller state in, TTR controls to hold out.

The mapper is declarative: every frame it returns the full set of TTR controls
(names from settings.json, e.g. "forward", "jump") that should be held right now.
The output layer diffs that against what is already held, so a key can never
get stuck down.

Bindings map a button to an action. An action is either a TTR control name
(held while the button is held) or one of the special actions below.
"""

from dataclasses import dataclass
from typing import Protocol

from . import ui
from .bindings import Bindings, ButtonActions, stick_buttons
from .controller import ControllerState
from .movement import MovementTuning, stick_to_movement


class ScreenView(Protocol):
    def is_visible(self, button: ui.Button) -> bool: ...


# Actions that do more than hold a TTR key.
SPECIAL_ACTIONS = {
    "sprint": "double-tap forward to sprint",
    "friendsList": "open the friends list, or close it if it's open",
    "back": "close whatever is open (speedchat, then the friends list)",
    "speedchat": "open speedchat, or close it if it's open",
    "unite": "open speedchat at the UNITE! menu, on Toon-Up (works in battle too)",
}


def default_bindings() -> Bindings:
    return Bindings(
        press={
            "a": "jump",
            "b": "back",
            "l3": "sprint",
            "r3": "cameraNext",
            "rb": "friendsList",
            "y": "showGags",
            "x": "showTasks",
            "dpad_up": "showMap",
            "start": "stickerBook",
            "view": "speedchat",
            "lt": "unite",
            "rs_up": "lookUp",
            "rs_down": "lookDown",
        },
        hold={"start": "options"},
    )


@dataclass
class Timing:
    # Holding a button with a hold action this long triggers it.
    hold_seconds: float = 0.5
    # Sprint is a fresh double-tap of forward, even if forward is already held:
    # release, tap, release, then hold. Each of the first three steps lasts this long.
    sprint_step_seconds: float = 0.06
    # Clicking sprint while standing still arms it for this long.
    sprint_arm_seconds: float = 1.0
    # Stick tilt needed to count as a stick button press.
    stick_button_threshold: float = 0.5


# One-shot key presses last this long so the game sees both the press and release.
PULSE_SECONDS = 0.06
_SPRINT_STEPS = (False, True, False)


def controller_buttons(state: ControllerState, threshold: float) -> frozenset[str]:
    """Physical buttons plus both sticks' directions and the triggers as virtual buttons."""
    triggers = {name for name, pull in (("lt", state.left_trigger), ("rt", state.right_trigger)) if pull > threshold}
    return frozenset(state.buttons
                     | stick_buttons("ls", *state.left_stick, threshold)
                     | stick_buttons("rs", *state.right_stick, threshold)
                     | triggers)


class OverworldMapper:
    def __init__(self, bindings: Bindings | None = None, tuning: MovementTuning = MovementTuning(),
                 timing: Timing | None = None):
        self.bindings = bindings or default_bindings()
        self.tuning = tuning
        self.timing = timing or Timing()
        self._actions = ButtonActions(self.bindings, self.timing.hold_seconds,
                                      is_oneshot=lambda action: action in SPECIAL_ACTIONS)
        self.reset()

    def reset(self) -> None:
        self._actions.reset()
        self._pulses: dict[str, float] = {}
        self._clicks: list[ui.Button] = []
        self._unite = False
        self._sprint_armed_until: float | None = None
        self._sprint_started_at: float | None = None

    def take_unite(self) -> bool:
        """Whether the unite hotkey was pressed since the last call."""
        unite, self._unite = self._unite, False
        return unite

    def take_clicks(self) -> list[ui.Button]:
        """On-screen buttons to click, requested since the last call."""
        clicks, self._clicks = self._clicks, []
        return clicks

    def update(self, state: ControllerState, now: float, screen: ScreenView | None = None,
               blocked: frozenset[str] = frozenset(), movement: bool = True) -> set[str]:
        """blocked: buttons another mode is using right now. movement: whether the left stick walks."""
        buttons = controller_buttons(state, self.timing.stick_button_threshold) - blocked
        controls = stick_to_movement(*state.left_stick, self.tuning) if movement else set()

        held, fired = self._actions.update(buttons, now)
        controls |= held
        for action in fired:
            self._run(action, now, screen)

        self._update_sprint(controls, now)
        self._pulses = {c: until for c, until in self._pulses.items() if now < until}
        controls.update(self._pulses)
        return controls

    def _run(self, action: str, now: float, screen: ScreenView | None) -> None:
        """Do a one-shot action: a special action, or a quick tap of a TTR control."""
        if action == "sprint":
            self._sprint_armed_until = now + self.timing.sprint_arm_seconds
        elif action == "back" and screen is not None and screen.is_visible(ui.SPEEDCHAT_MENU):
            self._clicks.append(ui.SPEEDCHAT)
        elif action in ("friendsList", "back"):
            # The friends list key only opens it; closing takes a click on its X.
            # The screen is only checked on a press, since reading pixels is slow.
            if screen is not None and screen.is_visible(ui.FRIENDS_CLOSE):
                self._clicks.append(ui.FRIENDS_CLOSE)
            elif action == "friendsList":
                self._pulse("friendsList", now)
        elif action == "speedchat":
            self._clicks.append(ui.SPEEDCHAT)
        elif action == "unite":
            self._unite = True
            if screen is None or not screen.is_visible(ui.SPEEDCHAT_MENU):
                self._clicks.append(ui.SPEEDCHAT)
        else:
            self._pulse(action, now)

    def _pulse(self, control: str, now: float) -> None:
        self._pulses[control] = now + PULSE_SECONDS

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
