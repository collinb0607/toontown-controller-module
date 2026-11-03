"""Read an Xbox-style controller through SDL2 (pygame-ce)."""

import os
from dataclasses import dataclass

# Must be set before SDL starts: TTR has focus, not us, and SDL drops
# controller input for unfocused apps by default.
os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402
from pygame._sdl2 import controller as sdl_controller  # noqa: E402

BUTTONS = {
    "a": pygame.CONTROLLER_BUTTON_A,
    "b": pygame.CONTROLLER_BUTTON_B,
    "x": pygame.CONTROLLER_BUTTON_X,
    "y": pygame.CONTROLLER_BUTTON_Y,
    "view": pygame.CONTROLLER_BUTTON_BACK,
    "start": pygame.CONTROLLER_BUTTON_START,
    "guide": pygame.CONTROLLER_BUTTON_GUIDE,
    "l3": pygame.CONTROLLER_BUTTON_LEFTSTICK,
    "r3": pygame.CONTROLLER_BUTTON_RIGHTSTICK,
    "lb": pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
    "rb": pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
    "dpad_up": pygame.CONTROLLER_BUTTON_DPAD_UP,
    "dpad_down": pygame.CONTROLLER_BUTTON_DPAD_DOWN,
    "dpad_left": pygame.CONTROLLER_BUTTON_DPAD_LEFT,
    "dpad_right": pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
}

_AXIS_MAX = 32767.0


@dataclass(frozen=True)
class ControllerState:
    buttons: frozenset[str] = frozenset()
    left_stick: tuple[float, float] = (0.0, 0.0)
    right_stick: tuple[float, float] = (0.0, 0.0)
    left_trigger: float = 0.0
    right_trigger: float = 0.0


NEUTRAL = ControllerState()


def _axis(pad, axis: int) -> float:
    return max(-1.0, min(1.0, pad.get_axis(axis) / _AXIS_MAX))


class ControllerReader:
    """Opens the first connected controller and handles plugging/unplugging."""

    def __init__(self):
        pygame.init()
        sdl_controller.init()
        self._pad = None

    @property
    def name(self) -> str | None:
        return self._pad.name if self._pad else None

    def poll(self) -> ControllerState | None:
        """Process SDL events and return the current state, or None if no controller."""
        for event in pygame.event.get():
            if event.type == pygame.CONTROLLERDEVICEREMOVED and self._pad and not self._pad.attached():
                self._pad.quit()
                self._pad = None
        if self._pad is None:
            self._open_first()
        if self._pad is None:
            return None

        pad = self._pad
        return ControllerState(
            buttons=frozenset(name for name, b in BUTTONS.items() if pad.get_button(b)),
            left_stick=(_axis(pad, pygame.CONTROLLER_AXIS_LEFTX), _axis(pad, pygame.CONTROLLER_AXIS_LEFTY)),
            right_stick=(_axis(pad, pygame.CONTROLLER_AXIS_RIGHTX), _axis(pad, pygame.CONTROLLER_AXIS_RIGHTY)),
            left_trigger=_axis(pad, pygame.CONTROLLER_AXIS_TRIGGERLEFT),
            right_trigger=_axis(pad, pygame.CONTROLLER_AXIS_TRIGGERRIGHT),
        )

    def _open_first(self) -> None:
        for index in range(sdl_controller.get_count()):
            if sdl_controller.is_controller(index):
                self._pad = sdl_controller.Controller(index)
                return

    def close(self) -> None:
        if self._pad:
            self._pad.quit()
        pygame.quit()
