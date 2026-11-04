"""Send keyboard and mouse input to the game with Windows SendInput."""

import ctypes
from collections import deque
from collections.abc import Callable, Iterable
from ctypes import wintypes

from . import keys

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_VIRTUALDESK = 0x4000
MOUSEEVENTF_ABSOLUTE = 0x8000
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79
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
_user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
_user32.GetSystemMetrics.argtypes = (ctypes.c_int,)


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


def _send_mouse(flags: int, dx: int = 0, dy: int = 0) -> None:
    event = INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=MOUSEINPUT(dx, dy, 0, flags, 0, 0)))
    _user32.SendInput(1, ctypes.byref(event), ctypes.sizeof(INPUT))


def move_mouse(x: int, y: int) -> None:
    """Move the cursor to a screen pixel (works across multiple monitors)."""
    left = _user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = _user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = _user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = _user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    # Absolute moves use 0..65535 across the whole virtual desktop.
    dx = round((x - left) * 65535 / max(1, width - 1))
    dy = round((y - top) * 65535 / max(1, height - 1))
    _send_mouse(MOUSEEVENTF_MOVE | MOUSEEVENTF_ABSOLUTE | MOUSEEVENTF_VIRTUALDESK, dx, dy)


def left_button(down: bool) -> None:
    _send_mouse(MOUSEEVENTF_LEFTDOWN if down else MOUSEEVENTF_LEFTUP)


def cursor_pos() -> tuple[int, int]:
    point = wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


class MouseClicker:
    """Clicks a screen point and then puts the cursor back where it was.

    The steps are spread over a few frames so the game sees the cursor arrive
    on the button before the click, like a real mouse.
    """

    STEP_SECONDS = 0.03

    def __init__(self, move=move_mouse, button=left_button, get_pos=cursor_pos):
        self._move, self._button, self._get_pos = move, button, get_pos
        self._queue: deque[tuple[int, int]] = deque()
        self._step = 0
        self._next_at = 0.0
        self._target: tuple[int, int] | None = None
        self._restore: tuple[int, int] | None = None

    def click(self, x: int, y: int) -> None:
        self._queue.append((x, y))

    @property
    def busy(self) -> bool:
        return self._target is not None or bool(self._queue)

    def update(self, now: float) -> None:
        if self._target is None:
            if not self._queue:
                return
            self._target = self._queue.popleft()
            self._restore = self._get_pos()
            self._step = 0
            self._next_at = now
        if now < self._next_at:
            return

        if self._step == 0:
            self._move(*self._target)
        elif self._step == 1:
            self._button(True)
        elif self._step == 2:
            self._button(False)
        else:
            self._move(*self._restore)
            self._target = None
            return
        self._step += 1
        self._next_at = now + self.STEP_SECONDS


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
