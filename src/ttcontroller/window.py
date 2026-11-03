"""Find out whether the Toontown Rewritten window is the active (foreground) window."""

import ctypes
from ctypes import wintypes
from pathlib import Path

TTR_PROCESS = "ttrengine64.exe"
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
_kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.QueryFullProcessImageNameW.argtypes = (
    wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
)
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)


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


class ForegroundWatcher:
    """Reports the TTR executable path while TTR is the foreground window."""

    def __init__(self):
        self._hwnd = None
        self._path: Path | None = None

    def ttr_foreground(self) -> Path | None:
        hwnd = _user32.GetForegroundWindow()
        if hwnd != self._hwnd:
            # Only look up the process when the foreground window changes.
            self._hwnd = hwnd
            path = _process_path(hwnd) if hwnd else None
            self._path = path if path and path.name.lower() == TTR_PROCESS else None
        return self._path
