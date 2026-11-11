"""Overworld mapping: controller state in, TTR controls to hold out.

The mapper is declarative: every frame it returns the full set of TTR controls
(names from settings.json, e.g. "forward", "jump") that should be held right now.
The output layer diffs that against what is already held, so a key can never
get stuck down.

Bindings map a button to an action. An action is either a TTR control name
(held while the button is held) or one of the special actions below.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from . import ui
from .ceo import read_leave
from .elevator import read_hop_off
from .silly import read_silly, toggle as silly_toggle
from .mail import read_mail
from .bindings import Bindings, ButtonActions, stick_buttons
from .controller import ControllerState
from .movement import MovementTuning, stick_to_movement


class ScreenView(Protocol):
    def is_visible(self, button: ui.Button) -> bool: ...

    def read(self, reader: Callable[..., Any]) -> Any: ...


# Actions that do more than hold a TTR key.
SPECIAL_ACTIONS = {
    "sprint": "turn auto-sprint on or off (when on, every run starts with a sprint)",
    "friendsList": "open the friends list, or close it if it's open; in the VP's pie round and the CJ's "
                   "evidence round, throw (TTR's performAction, held while the button is)",
    "back": "close whatever is open (speedchat, then a whisper, then the friends list); at the CEO, leave a seltzer bottle or golf ball, and at the CFO, a crane; in an elevator or golf kart, Hop off",
    "speedchat": "open speedchat, or close it if it's open",
    "unite": "open speedchat at the UNITE! menu, on Toon-Up (works in battle too)",
    "mail": "close Clarabelle's mail popup, or click her icon if there's no popup (only "
            "while walking around, with nothing else open). A tap: it fires when let go of, since holding it "
            "is the Silly Meter",
    "sillyMeter": "hold: open the Silly Meter (top right), or close it if it's open",
}


# With toggle_hud on, these TTR controls stay held from one press to the
# next instead of only while the button is held.
TOGGLE_CONTROLS = frozenset({"showMap", "showTasks", "showGags"})


def default_bindings() -> Bindings:
    return Bindings(
        press={
            "a": "jump",
            "b": "back",
            "ls": "sprint",
            "rs": "cameraNext",
            "rb": "friendsList",
            "y": "showGags",
            "x": "showTasks",
            "dpad_up": "showMap",
            "start": "stickerBook",
            "view": "speedchat",
            "lt": "unite",
            "rt": "mail",
            "rs_up": "lookUp",
            "rs_down": "lookDown",
        },
        # Holding RT: the Silly Meter (a tap, let go of before the hold, is still Clarabelle's mail).
        hold={"start": "options", "rt": "sillyMeter"},
    )


@dataclass
class Timing:
    # Holding a button with a hold action this long triggers it.
    hold_seconds: float = 0.5
    # Sprint is a fresh double-tap of forward, even if forward is already held:
    # release, tap, release, then hold. Each of the first three steps lasts this long.
    sprint_step_seconds: float = 0.06
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
                 timing: Timing | None = None, auto_sprint: bool = False, toggle_show: bool = False):
        self.bindings = bindings or default_bindings()
        self.tuning = tuning
        self.timing = timing or Timing()
        # When on, each run (a full tilt forward, not a walk) starts with a sprint.
        self.auto_sprint = auto_sprint
        self._sprint_toggled = False
        # Map, tasks and gags: a press shows them and the next press hides them.
        self.toggles = TOGGLE_CONTROLS if toggle_show else frozenset()
        self._actions = ButtonActions(self.bindings, self.timing.hold_seconds,
                                      is_oneshot=lambda action: action in SPECIAL_ACTIONS or action in self.toggles)
        self.reset()

    def reset(self, ignore_held: bool = False) -> None:
        self._actions.reset(ignore_held)
        self._pulses: dict[str, float] = {}
        self._clicks: list[ui.Button] = []
        self._unite = False
        self._was_running = False
        self._sprint_started_at: float | None = None
        self._toggled: set[str] = set()  # toggle controls shown right now
        self._free = True
        self._pies = False

    @property
    def shown(self) -> frozenset[str]:
        """The toggle controls shown right now (showGags, showTasks, showMap)."""
        return frozenset(self._toggled)

    def take_sprint_toggle(self) -> bool:
        """Whether auto-sprint was turned on or off since the last call."""
        toggled, self._sprint_toggled = self._sprint_toggled, False
        return toggled

    def take_unite(self) -> bool:
        """Whether the unite hotkey was pressed since the last call."""
        unite, self._unite = self._unite, False
        return unite

    def take_clicks(self) -> list[ui.Button]:
        """On-screen buttons to click, requested since the last call."""
        clicks, self._clicks = self._clicks, []
        return clicks

    def update(self, state: ControllerState, now: float, screen: ScreenView | None = None,
               blocked: frozenset[str] = frozenset(), movement: bool = True, free: bool = True,
               pies: bool = False) -> set[str]:
        """blocked: buttons another mode is using right now. movement: whether the left stick walks.
        free: walking around with nothing else open (no battle, book, menu or conversation).
        pies: the VP's pie round or the CJ's evidence round is on (the friends list button throws instead)."""
        self._free = free
        self._pies = pies
        buttons = controller_buttons(state, self.timing.stick_button_threshold) - blocked
        controls = stick_to_movement(*state.left_stick, self.tuning) if movement else set()

        held, fired = self._actions.update(buttons, now)
        controls |= held
        if pies and any(self.bindings.press.get(b) == "friendsList" for b in buttons):
            # TTR throws on the key, and winds up while it's held. On RB, the friends list's
            # button, since a bumper is easier to press over and over than RT (the user,
            # Nov 10); the list can't open in a boss round anyway.
            controls.add("performAction")
        for action in fired:
            if pies and action == "friendsList":
                continue
            self._run(action, now, screen)
        # A shown map, tasks or gags goes away when another mode takes its button
        # (a battle, the book), as it would if the button were let go.
        self._toggled = {c for c in self._toggled
                         if not any(self.bindings.press.get(b) == c for b in blocked)}
        controls |= self._toggled

        self._update_sprint(controls, now)
        self._pulses = {c: until for c, until in self._pulses.items() if now < until}
        controls.update(self._pulses)
        return controls

    def _run(self, action: str, now: float, screen: ScreenView | None) -> None:
        """Do a one-shot action: a special action, or a quick tap of a TTR control."""
        if action == "sprint":
            self.auto_sprint = not self.auto_sprint
            self._sprint_toggled = True
            # Turned on mid-run: sprint now.
            self._was_running = False
        elif action == "back" and screen is not None and screen.is_visible(ui.SPEEDCHAT_MENU):
            self._clicks.append(ui.SPEEDCHAT)
        elif (action == "back" and screen is not None and screen.is_visible(ui.WHISPER_CLOSE)
              and screen.is_visible(ui.WHISPER_BAR)):
            self._clicks.append(ui.WHISPER_CLOSE)  # stop whispering
        elif action == "back" and self._free and screen is not None and (leave := screen.read(read_leave)):
            # The CEO's seltzer bottle or golf ball, or the CFO's crane: its X leave button (read on the press).
            self._clicks.append(ui.Button("leave", leave))
        elif action == "back" and self._free and screen is not None and (hop := screen.read(read_hop_off)):
            # In an elevator or a golf kart: Hop off (read on the press; speedchat closes first, above).
            self._clicks.append(ui.Button("hop off", hop))
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
        elif action == "sillyMeter":
            # Open the Silly Meter, or close it if it's open (only while walking around).
            if self._free and not self._pies and screen is not None:
                for command in silly_toggle(screen.read(read_silly)):
                    self._clicks.append(ui.Button(command.name, command.point))
        elif action == "mail":
            # Read only on the press: the popup's size follows its message, so it's searched for.
            if self._free and not self._pies and screen is not None:
                mail = screen.read(read_mail)
                if mail.close is not None:
                    self._clicks.append(ui.Button("mail popup close", mail.close))
                elif mail.icon is not None:
                    self._clicks.append(ui.Button("clarabelle", mail.icon))
        elif action in self.toggles:
            self._toggled ^= {action}
        else:
            self._pulse(action, now)

    def tap(self, control: str, now: float) -> None:
        """Tap a TTR control on behalf of another mode (e.g. the book key to close the book)."""
        self._pulse(control, now)

    def _pulse(self, control: str, now: float) -> None:
        self._pulses[control] = now + PULSE_SECONDS

    def _update_sprint(self, controls: set[str], now: float) -> None:
        running = "forward" in controls and "walk" not in controls
        if running and not self._was_running and self.auto_sprint:
            self._sprint_started_at = now
        self._was_running = running
        if not running:
            self._sprint_started_at = None
            return

        if self._sprint_started_at is not None:
            step = int((now - self._sprint_started_at) / self.timing.sprint_step_seconds)
            if step < len(_SPRINT_STEPS):
                if not _SPRINT_STEPS[step]:
                    controls.discard("forward")
            else:
                self._sprint_started_at = None
