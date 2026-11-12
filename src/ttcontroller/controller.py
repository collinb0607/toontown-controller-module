"""Read a controller through SDL2 (pygame-ce): Xbox, PlayStation, Switch, Steam and others.

SDL's game controller layer reports every pad in the Xbox layout: "a" is the bottom face
button (Cross on a PlayStation pad), "lb" the left bumper (L1, L). Nintendo pads go by their
labels instead (the user, Nov 11): a Switch's A (on the right) is "a", B "b", X "x", Y "y".
So bindings work the same on all of them; only the button pictures and names differ
(`family_of` says which set a pad gets).
"""

import ctypes
import os
from dataclasses import dataclass

# Must be set before SDL starts: TTR has focus, not us, and SDL drops
# controller input for unfocused apps by default.
os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# Nintendo pads by their labels (SDL's default, set here so nothing else changes it): the
# Switch's A does what A does on an Xbox pad, though it sits where Xbox's B is; X and Y the
# same (the user, Nov 11). hint_draw cuts the Switch sheet to match.
os.environ.setdefault("SDL_GAMECONTROLLER_USE_BUTTON_LABELS", "1")
# The Steam Controller read directly (off in SDL by default). Without Steam running, it's
# otherwise a mouse and keyboard ("lizard mode"), which would keep pausing the controller.
os.environ.setdefault("SDL_JOYSTICK_HIDAPI_STEAM", "1")

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
    "ls": pygame.CONTROLLER_BUTTON_LEFTSTICK,
    "rs": pygame.CONTROLLER_BUTTON_RIGHTSTICK,
    "lb": pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
    "rb": pygame.CONTROLLER_BUTTON_RIGHTSHOULDER,
    "dpad_up": pygame.CONTROLLER_BUTTON_DPAD_UP,
    "dpad_down": pygame.CONTROLLER_BUTTON_DPAD_DOWN,
    "dpad_left": pygame.CONTROLLER_BUTTON_DPAD_LEFT,
    "dpad_right": pygame.CONTROLLER_BUTTON_DPAD_RIGHT,
}

_AXIS_MAX = 32767.0

# Which button pictures a controller gets (hint_draw.FAMILIES).
# SDL_GameControllerType (SDL 2.x): 1 Xbox 360, 2 Xbox One, 3 PS3, 4 PS4, 5 Switch Pro,
# 6 virtual, 7 PS5, 8 Luna, 9 Stadia, 10 Shield, 11-13 Joy-Cons (left, right, pair).
_SDL_TYPES = {1: "xbox", 2: "xbox", 3: "playstation", 4: "playstation", 5: "switch", 7: "playstation",
              11: "switch", 12: "switch", 13: "switch"}
_SONY, _NINTENDO, _VALVE = 0x054C, 0x057E, 0x28DE
_STEAM_VIRTUAL = 0x11FF  # Steam Input's virtual pad: it stands for any controller
_NAME_WORDS = (("steam controller", "steam"), ("steam deck", "steam"),
               ("dualsense", "playstation"), ("dualshock", "playstation"), ("playstation", "playstation"),
               ("ps5", "playstation"), ("ps4", "playstation"), ("ps3", "playstation"),
               ("nintendo", "switch"), ("switch", "switch"), ("joy-con", "switch"))


def family_of(sdl_type: int = 0, vendor: int = 0, product: int = 0, name: str = "") -> str:
    """Which button pictures a controller gets: "xbox", "playstation", "switch" or "steam".
    Valve's own hardware first (SDL 2 has no Steam type), then SDL's type, which knows
    third-party PlayStation pads and what's behind Steam's virtual pad, then the vendor
    and the name. Anything else is drawn as an Xbox pad, the layout SDL reports."""
    if vendor == _VALVE and product != _STEAM_VIRTUAL:
        return "steam"
    if sdl_type in _SDL_TYPES:
        return _SDL_TYPES[sdl_type]
    if vendor == _SONY:
        return "playstation"
    if vendor == _NINTENDO:
        return "switch"
    lowered = (name or "").lower()
    for words, family in _NAME_WORDS:
        if words in lowered:
            return family
    return "xbox"


_sdl_lib = None


def _sdl():
    """pygame's own SDL2 library, for what pygame doesn't wrap (the controller's type and
    vendor), or None. It must be the copy pygame loaded (the packaged exe has two), so it
    shares pygame's state: the loaded module first, then pygame's file; `device_family`
    checks it against pygame's controller count."""
    global _sdl_lib
    if _sdl_lib is None:
        _sdl_lib = False
        loaded = None
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetModuleHandleW.argtypes = [ctypes.c_wchar_p]
            kernel32.GetModuleHandleW.restype = ctypes.c_void_p
            loaded = kernel32.GetModuleHandleW("SDL2.dll")
        except (OSError, AttributeError):
            pass
        names = ([("SDL2.dll", loaded)] if loaded else []) + [
            (os.path.join(os.path.dirname(pygame.__file__), "SDL2.dll"), None)]
        for name, handle in names:
            try:
                lib = ctypes.CDLL(name, handle=handle)
                lib.SDL_GameControllerTypeForIndex.argtypes = [ctypes.c_int]
                lib.SDL_GameControllerTypeForIndex.restype = ctypes.c_int
                lib.SDL_JoystickGetDeviceVendor.argtypes = [ctypes.c_int]
                lib.SDL_JoystickGetDeviceVendor.restype = ctypes.c_uint16
                lib.SDL_JoystickGetDeviceProduct.argtypes = [ctypes.c_int]
                lib.SDL_JoystickGetDeviceProduct.restype = ctypes.c_uint16
                lib.SDL_NumJoysticks.restype = ctypes.c_int
            except (OSError, AttributeError):
                continue
            _sdl_lib = lib
            break
    return _sdl_lib or None


def device_family(index: int, name: str = "") -> str:
    """The family of the controller at SDL device index `index` (SDL must be started)."""
    lib = _sdl()
    sdl_type = vendor = product = 0
    if lib is not None and lib.SDL_NumJoysticks() == sdl_controller.get_count():
        sdl_type = lib.SDL_GameControllerTypeForIndex(index)
        vendor = lib.SDL_JoystickGetDeviceVendor(index)
        product = lib.SDL_JoystickGetDeviceProduct(index)
    return family_of(sdl_type, vendor, product, name)


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


def connected_names() -> list[str]:
    """The names of the controllers plugged in now (starting SDL if needed). Each is opened
    to read its name and left open: pygame hands back the same object for a controller
    that's already open, so closing it here would close the reader's too."""
    if not sdl_controller.get_init():
        pygame.init()
        sdl_controller.init()
    names = []
    for index in range(sdl_controller.get_count()):
        if sdl_controller.is_controller(index):
            names.append(sdl_controller.Controller(index).name or f"Controller {index + 1}")
    return names


class ControllerReader:
    """Opens a connected controller and handles plugging/unplugging. With `preferred`
    set (a controller's name, from the settings window), that one is opened when it's
    plugged in; otherwise, or when it isn't, the first one."""

    def __init__(self, preferred: str = ""):
        pygame.init()
        sdl_controller.init()
        self._pad = None
        self.preferred = preferred
        # The open controller's button pictures (hint_draw.FAMILIES), or None with none open.
        self.family: str | None = None

    def set_preferred(self, preferred: str) -> None:
        """Switch to another preferred controller, reopening if that changes which one."""
        if preferred == self.preferred:
            return
        self.preferred = preferred
        if self._pad is not None:
            self._pad.quit()
            self._pad = None
            self.family = None

    @property
    def name(self) -> str | None:
        return self._pad.name if self._pad else None

    def poll(self) -> ControllerState | None:
        """Process SDL events and return the current state, or None if no controller."""
        for event in pygame.event.get():
            if event.type == pygame.CONTROLLERDEVICEREMOVED and self._pad and not self._pad.attached():
                self._pad.quit()
                self._pad = None
                self.family = None
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
        indexes = [i for i in range(sdl_controller.get_count()) if sdl_controller.is_controller(i)]
        if self.preferred:
            named = [i for i in indexes if sdl_controller.Controller(i).name == self.preferred]
            indexes = named + [i for i in indexes if i not in named]
        if indexes:
            self._pad = sdl_controller.Controller(indexes[0])
            try:
                self.family = device_family(indexes[0], self._pad.name or "")
            except Exception:  # noqa: BLE001 (the pictures mustn't stop the controller)
                self.family = family_of(name=self._pad.name or "")

    def close(self) -> None:
        if self._pad:
            self._pad.quit()
        pygame.quit()
