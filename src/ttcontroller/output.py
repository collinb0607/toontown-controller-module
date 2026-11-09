"""Send keyboard and mouse input to the game: real input with Windows SendInput (one
toon, the TTR window in front), or window messages posted to one TTR window that may be
in the background (two toons, M13)."""

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
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120
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
_user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_user32.ScreenToClient.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))


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


def _send_mouse(flags: int, dx: int = 0, dy: int = 0, data: int = 0) -> None:
    event = INPUT(type=INPUT_MOUSE, u=_INPUTUNION(mi=MOUSEINPUT(dx, dy, data, flags, 0, 0)))
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


def wheel(notches: int) -> None:
    """Turn the mouse wheel: positive scrolls up, negative down. Each notch is
    its own event, since games may count events rather than the distance."""
    for _ in range(abs(notches)):
        _send_mouse(MOUSEEVENTF_WHEEL, data=WHEEL_DELTA if notches > 0 else -WHEEL_DELTA)


def cursor_pos() -> tuple[int, int]:
    point = wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y


_MOUSE_BUTTONS = (0x01, 0x02, 0x04)  # VK_LBUTTON, VK_RBUTTON, VK_MBUTTON


def mouse_button_down() -> bool:
    """Whether a mouse button is held (by anyone: the module's own clicks count too)."""
    return any(_user32.GetAsyncKeyState(vk) & 0x8000 for vk in _MOUSE_BUTTONS)


class MouseClicker:
    """Moves and clicks the mouse for on-screen buttons.

    click() clicks a point and, by default, puts the cursor back where it was.
    hover() just parks the cursor on a point (the battle highlight).
    scroll() parks the cursor on a point and turns the mouse wheel there.
    hold() presses the button on a point and keeps it down until release() (for
    buttons that act while held, like turning the kart).
    The steps are spread over a few frames so the game sees the cursor arrive
    on the button before the click, like a real mouse.
    """

    STEP_SECONDS = 0.03

    def __init__(self, move=move_mouse, button=left_button, get_pos=cursor_pos, wheel=wheel,
                 steps: tuple[float, float, float] = (STEP_SECONDS,) * 3, restores: bool = True):
        self._move, self._button, self._get_pos, self._wheel = move, button, get_pos, wheel
        # Seconds to wait after the move, after the press, and after anything later. Posted
        # clicks need (0.05, 0.08, 0.03): TTR misses quicker ones (Nov 5 findings).
        self._steps = steps
        # Whether a click puts the cursor back. Posted input has no cursor of the user's to
        # put back, so it leaves TTR's pointer on what it clicked.
        self._restores = restores
        # (x, y, click, restore, wheel notches, seconds to wait first)
        self._queue: deque[tuple[int, int, bool, bool, int, float]] = deque()
        self._step = 0
        self._next_at = 0.0
        self._job: tuple[int, int, bool, bool, int, float] | None = None
        self._restore_to: tuple[int, int] | None = None
        self.moved_to: tuple[int, int] | None = None  # where the module last put the cursor
        self.holding = False  # the button is held down by hold()

    def click(self, x: int, y: int, restore: bool = True, delay: float = 0.0) -> None:
        """delay waits after the previous step, e.g. for a menu the last click opens."""
        self._queue.append((x, y, True, restore and self._restores, 0, delay))

    def scroll(self, x: int, y: int, notches: int) -> None:
        self._queue.append((x, y, False, False, notches, 0.0))

    def hold(self, x: int, y: int) -> None:
        self._queue.append((x, y, "hold", False, 0, 0.0))

    def drag(self, x: int, y: int, to_x: int, to_y: int) -> None:
        """Press on a point, move to another with the button down, and let go there (a
        slider's knob). Queued like a click, so it happens in order with the rest."""
        self._queue.append((x, y, "drag", (to_x, to_y), 0, 0.0))

    def release(self) -> None:
        """Let go of a hold(), straight away (also safe when nothing is held)."""
        self._queue = deque(job for job in self._queue if job[2] != "hold")
        if self._job is not None and self._job[2] == "hold":
            self._job = None
        if self.holding:
            self._button(False)
            self.holding = False

    def hover(self, x: int, y: int) -> None:
        # A newer hover replaces any hover still waiting, so fast stick input doesn't lag behind.
        if self._queue and not self._queue[-1][2] and not self._queue[-1][4]:
            self._queue.pop()
        self._queue.append((x, y, False, False, 0, 0.0))

    @property
    def busy(self) -> bool:
        return self._job is not None or bool(self._queue) or self.holding

    def update(self, now: float) -> None:
        if self._job is None:
            if not self._queue:
                return
            self._job = self._queue.popleft()
            self._restore_to = self._get_pos() if self._job[3] is True else None
            self._step = 0
            self._next_at = now + self._job[5]
        if now < self._next_at:
            return

        x, y, click, _, notches, _ = self._job
        if click == "drag":
            # Onto the knob, press, halfway, the rest of the way, let go.
            to_x, to_y = self._job[3]
            if self._step == 1:
                self._button(True)
            elif self._step == 4:
                self._button(False)
                self._job = None
                return
            else:
                spot = {0: (x, y), 2: ((x + to_x) // 2, (y + to_y) // 2), 3: (to_x, to_y)}[self._step]
                self._move(*spot)
                self.moved_to = spot
            self._step += 1
            self._next_at = now + self._steps[min(self._step - 1, 2)]
            return
        if click == "hold" and self._step == 1:
            self._button(True)
            self.holding = True
            self._job = None
            return
        if self._step == 0:
            self._move(x, y)
            self.moved_to = (x, y)
            if not click and not notches:
                self._job = None
                return
        elif notches:
            self._wheel(notches)
            self._job = None
            return
        elif self._step == 1:
            self._button(True)
        elif self._step == 2:
            self._button(False)
            if self._restore_to is None:
                self._job = None
                return
        else:
            self._move(*self._restore_to)
            self.moved_to = self._restore_to
            self._job = None
            return
        self._step += 1
        self._next_at = now + self._steps[min(self._step - 1, 2)]


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


# ---- Posted input: one TTR window, in front or not (two toons, M13) -----------------------
# TTR takes posted keys, clicks, wheel turns and drags, but ignores a posted WM_MOUSEMOVE:
# a middle-button press and release moves its pointer instead, without clicking anything
# (M13 phase 0, Nov 8). TTR doesn't draw its pointer in a window that isn't in front.

WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MOUSEWHEEL = 0x0201, 0x0202, 0x0207, 0x0208, 0x020A
MK_LBUTTON, MK_MBUTTON = 0x0001, 0x0010
POSTED_STEPS = (0.05, 0.08, 0.03)  # after the move, after the press, after the rest


def _post(hwnd, msg: int, wparam: int, lparam: int) -> None:
    _user32.PostMessageW(hwnd, msg, wparam, lparam)


def key_lparam(name: str, down: bool) -> int:
    """A key message's lParam, as a real keyboard's: repeat count 1, the scan code, the
    extended-key flag, and on release the was-down and released flags."""
    value = 1 | (_user32.MapVirtualKeyW(keys.vk_code(name), MAPVK_VK_TO_VSC) << 16)
    if keys.is_extended(name):
        value |= 1 << 24
    if not down:
        value |= (1 << 30) | (1 << 31)
    return value


def _xy(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


class PostedKeys:
    """Keys for one window, posted: called like send_key(name, down)."""

    def __init__(self, hwnd, post=_post, lparam=key_lparam):
        self.hwnd, self._post, self._lparam = hwnd, post, lparam

    def __call__(self, name: str, down: bool) -> None:
        self._post(self.hwnd, WM_KEYDOWN if down else WM_KEYUP, keys.vk_code(name), self._lparam(name, down))


class PostedMouse:
    """MouseClicker's move, button, get_pos and wheel for one window, posted. Points come
    in screen pixels, as the rest of the module works in them, and are posted in the
    window's client pixels (the wheel takes screen pixels, as Windows sends it)."""

    def __init__(self, hwnd, post=_post, to_client=None):
        self.hwnd, self._post = hwnd, post
        self._to_client = to_client or self._screen_to_client
        self._at: tuple[int, int] | None = None  # the screen point TTR's pointer was last put on
        self._down = False  # the left button, as posted

    def _screen_to_client(self, x: int, y: int) -> tuple[int, int]:
        point = wintypes.POINT(x, y)
        _user32.ScreenToClient(self.hwnd, ctypes.byref(point))
        return point.x, point.y

    def _where(self) -> int:
        return _xy(*self._to_client(*self._at))

    def move(self, x: int, y: int) -> None:
        self._at = (x, y)
        held = MK_LBUTTON if self._down else 0  # mid-drag the left button stays down
        self._post(self.hwnd, WM_MBUTTONDOWN, MK_MBUTTON | held, self._where())
        self._post(self.hwnd, WM_MBUTTONUP, held, self._where())

    def button(self, down: bool) -> None:
        if self._at is None or down == self._down and not down:
            self._down = down
            return  # nothing pressed yet, or a release with nothing held
        self._down = down
        self._post(self.hwnd, WM_LBUTTONDOWN if down else WM_LBUTTONUP, MK_LBUTTON if down else 0, self._where())

    def wheel(self, notches: int) -> None:
        if self._at is None:
            return
        delta = WHEEL_DELTA if notches > 0 else -WHEEL_DELTA
        for _ in range(abs(notches)):
            self._post(self.hwnd, WM_MOUSEWHEEL, (delta & 0xFFFF) << 16, _xy(*self._at))

    def get_pos(self) -> tuple[int, int]:
        return self._at or (0, 0)


def posted_output(hwnd, send_wrap=None) -> tuple[KeyboardOutput, MouseClicker, PostedKeys]:
    """Keys and mouse for one TTR window, posted. send_wrap(send) can wrap the key sender
    (the debug log). Returns the KeyboardOutput, the MouseClicker and the key sender."""
    send = PostedKeys(hwnd)
    mouse = PostedMouse(hwnd)
    wrapped = send_wrap(send) if send_wrap else send
    return (KeyboardOutput(wrapped),
            MouseClicker(mouse.move, mouse.button, mouse.get_pos, mouse.wheel, steps=POSTED_STEPS, restores=False),
            wrapped)
