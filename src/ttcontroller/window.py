"""Find out whether the Toontown Rewritten window is the active (foreground) window."""

import ctypes
from ctypes import wintypes
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


class TTRView:
    """Reads and locates TTR's on-screen buttons in one game window."""

    def __init__(self, hwnd):
        self.hwnd = hwnd

    def snapshot(self) -> Frame:
        """Copy the game area, so its pixels can be read in client coordinates."""
        return grab(*client_rect(self.hwnd))

    def is_visible(self, button: ui.Button) -> bool:
        frame = self.snapshot()
        return ui.is_visible(button, frame.width, frame.height, frame.get_pixel)

    def park_spot(self) -> tuple[int, int] | None:
        """Where to leave the cursor when nothing needs hovering: on the title bar, just
        above the game area, where Windows draws the cursor instead of TTR (so it can be
        hidden even with TTR's custom cursor). None if there's no title bar showing."""
        left, top, width, _ = client_rect(self.hwnd)
        y = top - PARK_ABOVE
        return (left + width // 2, y) if y >= 0 else None

    def to_screen(self, point: ui.UIPoint) -> tuple[int, int]:
        left, top, width, height = client_rect(self.hwnd)
        x, y = point.to_client(width, height)
        return left + x, top + y
