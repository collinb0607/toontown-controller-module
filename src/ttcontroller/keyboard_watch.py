"""Notices the real keyboard being used, so the controller pauses like it does for the
mouse (one toon only: in two-toon mode the keyboard is the other toon's).

The module's own keys (SendInput) can't be told from real ones by key state, so this
listens to raw input on a thread of its own: Windows reports injected keys with no
device (hDevice is NULL), and real ones with the keyboard they came from. Raw input
only queues messages for this thread; it never holds up anyone's typing.
"""

import ctypes
import threading
from ctypes import wintypes

RIM_TYPEKEYBOARD = 1
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100
RI_KEY_BREAK = 0x01  # a key let go
WM_INPUT = 0x00FF
WM_QUIT = 0x0012


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [("usUsagePage", wintypes.USHORT), ("usUsage", wintypes.USHORT),
                ("dwFlags", wintypes.DWORD), ("hwndTarget", wintypes.HWND)]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [("dwType", wintypes.DWORD), ("dwSize", wintypes.DWORD),
                ("hDevice", wintypes.HANDLE), ("wParam", wintypes.WPARAM)]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [("MakeCode", wintypes.USHORT), ("Flags", wintypes.USHORT), ("Reserved", wintypes.USHORT),
                ("VKey", wintypes.USHORT), ("Message", wintypes.UINT), ("ExtraInformation", wintypes.ULONG)]


class RAWINPUT(ctypes.Structure):
    _fields_ = [("header", RAWINPUTHEADER), ("keyboard", RAWKEYBOARD)]


def is_real_key_press(header: RAWINPUTHEADER, keyboard: RAWKEYBOARD) -> bool:
    """A key pressed down on a real keyboard (not injected, not a release)."""
    return header.dwType == RIM_TYPEKEYBOARD and bool(header.hDevice) and not keyboard.Flags & RI_KEY_BREAK


class KeyboardWatcher:
    """take() says whether a real key was pressed since it was last asked."""

    def __init__(self):
        self._pressed = threading.Event()
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self.working = False

    def start(self) -> None:
        if self._thread is None:
            ready = threading.Event()
            self._thread = threading.Thread(target=self._run, args=(ready,), name="keyboard-watch", daemon=True)
            self._thread.start()
            ready.wait(2.0)

    def take(self) -> bool:
        if self._pressed.is_set():
            self._pressed.clear()
            return True
        return False

    def stop(self) -> None:
        if self._thread is not None and self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            self._thread.join(1.0)
        self._thread = None

    def _run(self, ready: threading.Event) -> None:
        user32 = ctypes.windll.user32
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                           ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                           wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
        user32.GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPVOID,
                                           ctypes.POINTER(wintypes.UINT), wintypes.UINT]
        user32.GetRawInputData.restype = wintypes.UINT
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        # A hidden window of a built-in class: WM_INPUT is read off the queue below.
        hwnd = user32.CreateWindowExW(0, "STATIC", None, 0, 0, 0, 0, 0, None, None, None, None)
        device = RAWINPUTDEVICE(0x01, 0x06, RIDEV_INPUTSINK, hwnd)  # generic desktop, keyboard
        self.working = bool(hwnd) and bool(user32.RegisterRawInputDevices(ctypes.byref(device), 1,
                                                                          ctypes.sizeof(device)))
        ready.set()
        if not self.working:
            return
        msg = wintypes.MSG()
        raw = RAWINPUT()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_INPUT:
                size = wintypes.UINT(ctypes.sizeof(raw))
                got = user32.GetRawInputData(msg.lParam, RID_INPUT, ctypes.byref(raw), ctypes.byref(size),
                                             ctypes.sizeof(RAWINPUTHEADER))
                if got != 0xFFFFFFFF and got >= ctypes.sizeof(RAWINPUTHEADER) and \
                        is_real_key_press(raw.header, raw.keyboard):
                    self._pressed.set()
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        user32.DestroyWindow(hwnd)
