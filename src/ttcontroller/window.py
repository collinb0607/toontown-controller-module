"""Find TTR's windows: the one in front (one toon), or one chosen window that may be in
the background (two toons, M13)."""

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path

from . import ui
from .screen import Frame, grab

TTR_PROCESS = "ttrengine64.exe"
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
_user32.GetClientRect.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.RECT))
_user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
_user32.IsWindowVisible.argtypes = (wintypes.HWND,)
_user32.IsWindow.argtypes = (wintypes.HWND,)
_user32.IsIconic.argtypes = (wintypes.HWND,)
_user32.WindowFromPoint.argtypes = (wintypes.POINT,)
_user32.WindowFromPoint.restype = wintypes.HWND
_user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
_user32.GetAncestor.restype = wintypes.HWND
_user32.SetForegroundWindow.argtypes = (wintypes.HWND,)
_user32.BringWindowToTop.argtypes = (wintypes.HWND,)
_user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
_user32.AttachThreadInput.argtypes = (wintypes.DWORD, wintypes.DWORD, wintypes.BOOL)
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD
GA_ROOT = 2
SW_RESTORE = 9
_kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
)
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)


def make_dpi_aware() -> None:
    """Use real pixels everywhere, so screen reads and clicks line up when Windows scaling isn't 100%."""
    try:
        _user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
    except AttributeError:
        pass


def _process_path(hwnd) -> Path | None:
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return None
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return None
        return Path(buf.value)
    finally:
        _kernel32.CloseHandle(handle)


def client_rect(hwnd) -> tuple[int, int, int, int]:
    """Return the window's drawable area as (left, top, width, height) in screen pixels."""
    rect = wintypes.RECT()
    _user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = wintypes.POINT(0, 0)
    _user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return origin.x, origin.y, rect.right, rect.bottom


def find_ttr_windows() -> list:
    """Return handles of all visible TTR game windows."""
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if _user32.IsWindowVisible(hwnd):
            path = _process_path(hwnd)
            if path and path.name.lower() == TTR_PROCESS:
                found.append(hwnd)
        return True

    _user32.EnumWindows(visit, 0)
    return found


class ForegroundWatcher:
    """Reports the TTR executable path while TTR is the foreground window."""

    def __init__(self):
        self._hwnd = None
        self._path: Path | None = None

    @property
    def ttr_hwnd(self):
        """The foreground TTR window from the last check, or None."""
        return self._hwnd if self._path else None

    def ttr_foreground(self) -> Path | None:
        hwnd = _user32.GetForegroundWindow()
        if hwnd != self._hwnd:
            # Only look up the process when the foreground window changes.
            self._hwnd = hwnd
            path = _process_path(hwnd) if hwnd else None
            self._path = path if path and path.name.lower() == TTR_PROCESS else None
        return self._path


PARK_ABOVE = 12  # pixels above the game area: the middle of the title bar


@dataclass
class TargetChoice:
    """Which TTR window the controller drives, set by the module's window and read by the
    loop each frame. One toon (two_toons False): the TTR window in front, real input. Two
    toons: the window `hwnd`, in front or not, posted input; with none picked yet the
    controller does nothing (it mustn't play the keyboard-and-mouse toon). Window handles
    change every time TTR starts, so the window is never saved."""
    two_toons: bool = False
    hwnd: int | None = None

    @property
    def wanted(self) -> tuple[bool, int | None]:
        return (True, self.hwnd) if self.two_toons else (False, None)


class ForegroundTarget:
    """One toon (as always): the controller drives the TTR window in front, with real input."""
    background = False

    def __init__(self, watcher: ForegroundWatcher | None = None):
        self._watch = watcher or ForegroundWatcher()
        self.hwnd = None
        self.path: Path | None = None

    def update(self) -> None:
        self.path = self._watch.ttr_foreground()
        self.hwnd = self._watch.ttr_hwnd

    @property
    def active(self) -> bool:
        return self.hwnd is not None

    @property
    def state(self) -> str:
        return "ok" if self.active else "not_front"


COVER_GRID = 5  # points per side checked for another window over the controller toon's


def covered(hwnd) -> bool:
    """Whether another window (or the edge of the screens) hides part of this one's game
    area. The module reads the game from the screen, so a covered window reads wrong.
    The module's own overlay windows let clicks through, so they never count."""
    left, top, width, height = client_rect(hwnd)
    if width <= 0 or height <= 0:
        return True
    for i in range(COVER_GRID):
        for j in range(COVER_GRID):
            x = left + round((i + 0.5) * width / COVER_GRID)
            y = top + round((j + 0.5) * height / COVER_GRID)
            under = _user32.WindowFromPoint(wintypes.POINT(x, y))
            if not under or _user32.GetAncestor(under, GA_ROOT) != hwnd:
                return True
    return False


class BoundTarget:
    """Two toons: the controller drives one chosen TTR window, in front or not, with posted
    input. state: "ok", "minimized" (TTR doesn't draw then), "covered", "gone" or
    "unpicked" (hwnd None: two toons on, no window picked yet)."""
    background = True

    def __init__(self, hwnd, is_window=None, is_minimized=None, is_covered=None):
        self.hwnd = hwnd
        self._is_window = is_window or (lambda h: bool(_user32.IsWindow(h)))
        self._is_minimized = is_minimized or (lambda h: bool(_user32.IsIconic(h)))
        self._is_covered = is_covered or covered
        self.path = _process_path(hwnd) if hwnd and self._is_window(hwnd) else None
        self.state = "ok"

    def update(self) -> None:
        if self.hwnd is None:
            self.state = "unpicked"
        elif not self._is_window(self.hwnd):
            self.state = "gone"
        elif self._is_minimized(self.hwnd):
            self.state = "minimized"
        elif self._is_covered(self.hwnd):
            self.state = "covered"
        else:
            self.state = "ok"

    @property
    def active(self) -> bool:
        return self.state == "ok"


def describe_windows(rects: dict[int, tuple[int, int, int, int]], front=None) -> dict[int, str]:
    """A name for each TTR window by where it is, for picking one: "Left", "Right", or
    "1st from the left"... for more than two; "(in front)" on the one in front."""
    order = sorted(rects, key=lambda h: (rects[h][0] + rects[h][2] / 2, rects[h][1]))
    names = {}
    for n, hwnd in enumerate(order):
        if len(order) == 1:
            name = "TTR"
        elif len(order) == 2:
            name = ("Left", "Right")[n]
        else:
            name = f"{n + 1}{'st' if n == 0 else 'nd' if n == 1 else 'rd' if n == 2 else 'th'} from the left"
        names[hwnd] = name + (" (in front)" if hwnd == front else "")
    return names


def ttr_windows() -> list[tuple[int, str]]:
    """(handle, name) for every TTR window, left to right."""
    rects = {hwnd: client_rect(hwnd) for hwnd in find_ttr_windows()}
    names = describe_windows(rects, _user32.GetForegroundWindow())
    return [(hwnd, names[hwnd]) for hwnd in sorted(rects, key=lambda h: (rects[h][0], rects[h][1]))]


def focus_window(hwnd) -> bool:
    """Bring a window to the front and give it the keyboard (restoring it if minimized).
    Windows only lets the process in front do that, so this thread borrows the front
    window's input for the moment. True if it's in front now."""
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, SW_RESTORE)
    front = _user32.GetForegroundWindow()
    theirs = _user32.GetWindowThreadProcessId(front, None) if front else 0
    mine = _kernel32.GetCurrentThreadId()
    attached = bool(theirs and theirs != mine and _user32.AttachThreadInput(mine, theirs, True))
    try:
        _user32.BringWindowToTop(hwnd)
        _user32.SetForegroundWindow(hwnd)
    finally:
        if attached:
            _user32.AttachThreadInput(mine, theirs, False)
    return _user32.GetForegroundWindow() == hwnd


class TTRView:
    """Reads and locates TTR's on-screen buttons in one game window. background: the
    controller drives it with posted input (two toons), so there's no real cursor to park."""

    def __init__(self, hwnd, background: bool = False):
        self.hwnd = hwnd
        self.background = background

    def snapshot(self) -> Frame:
        """Copy the game area, so its pixels can be read in client coordinates."""
        return grab(*client_rect(self.hwnd))

    def is_visible(self, button: ui.Button) -> bool:
        frame = self.snapshot()
        return ui.is_visible(button, frame.width, frame.height, frame.get_pixel)

    def read(self, reader):
        """Run a screen reader (width, height, get_pixel) on a fresh snapshot."""
        frame = self.snapshot()
        return reader(frame.width, frame.height, frame.get_pixel)

    def park_spot(self) -> tuple[int, int] | None:
        """Where to leave the cursor when nothing needs hovering: on the title bar, just
        above the game area, where Windows draws the cursor instead of TTR (so it can be
        hidden even with TTR's custom cursor). None if there's no title bar showing, or in
        two-toon mode (the real cursor is the other toon's, and TTR doesn't draw its pointer
        in a window that isn't in front)."""
        if self.background:
            return None
        left, top, width, _ = client_rect(self.hwnd)
        y = top - PARK_ABOVE
        return (left + width // 2, y) if y >= 0 else None

    def to_screen(self, point: ui.UIPoint) -> tuple[int, int]:
        left, top, width, height = client_rect(self.hwnd)
        x, y = point.to_client(width, height)
        return left + x, top + y
