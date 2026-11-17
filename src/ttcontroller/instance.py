"""One copy of the module at a time, windowed (launcher.py) or in a console (__main__.py):
a second one would fight the first over the keys and the cursor."""

import ctypes
from ctypes import wintypes

MUTEX_NAME = "Local\\ToontownControllerModule"
ERROR_ALREADY_EXISTS = 183

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
_kernel32.CreateMutexW.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)


def claim(name: str = MUTEX_NAME) -> int | None:
    """This process's hold on being the one copy (keep it until quitting, then release()),
    or None if another copy is running."""
    handle = _kernel32.CreateMutexW(None, False, name)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        if handle:
            _kernel32.CloseHandle(handle)
        return None
    return handle


def release(handle) -> None:
    if handle:
        _kernel32.CloseHandle(handle)
