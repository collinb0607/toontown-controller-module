"""Send keyboard input to the game with Windows SendInput."""

import ctypes
from collections.abc import Callable, Iterable
from ctypes import wintypes

from . import keys

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VK_TO_VSC = 0

ULONG_PTR = wintypes.WPARAM


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
_user32.SendInput.restype = wintypes.UINT
_user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
_user32.MapVirtualKeyW.restype = wintypes.UINT


def send_key(name: str, down: bool) -> None:
    """Press or release one key, sent by scan code like a physical keyboard."""
    scan = _user32.MapVirtualKeyW(keys.vk_code(name), MAPVK_VK_TO_VSC)
    flags = KEYEVENTF_SCANCODE
    if keys.is_extended(name):
        flags |= KEYEVENTF_EXTENDEDKEY
    if not down:
        flags |= KEYEVENTF_KEYUP
    event = INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(0, scan, flags, 0, 0)))
    _user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))


class KeyboardOutput:
    """Keeps the set of held keys in sync with what the mapper wants held."""

    def __init__(self, send: Callable[[str, bool], None] = send_key):
        self._send = send
        self.held: set[str] = set()

    def sync(self, desired: Iterable[str]) -> None:
        desired = set(desired)
        # Release regular keys before modifiers, and press modifiers before
        # regular keys, so combos like shift-escape arrive in the right order.
        for name in sorted(self.held - desired, key=keys.is_modifier):
            self._send(name, False)
        for name in sorted(desired - self.held, key=lambda n: not keys.is_modifier(n)):
            self._send(name, True)
        self.held = desired

    def release_all(self) -> None:
        self.sync(())
