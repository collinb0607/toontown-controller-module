"""Read a TTR window's own picture with Windows Graphics Capture (Nov 11, 2026).

Copying the screen (screen.grab) sees whatever is on top of TTR, the module's overlay
included, so the overlay had to hide from every screen capture, and OBS, Discord and
stream viewers never saw it. This copies only the TTR window's own picture, so nothing on
top of it is ever read, and the overlay can show in recordings. tools/wgc_check.py
(Nov 11): about 6 ms a read against 30 ms for the screen copy, the same pixels, no flash,
no yellow border.

One capture session per TTR window, started when it's first read and stopped once it
hasn't been read for a while. Frames arrive about 50 times a second; only the ones asked
for are copied. If a session can't start, capture is off for the rest of the run and the
module goes back to the screen copy (on_failure tells the overlay to hide again).
"""

import ctypes
import sys
import threading
import time
from ctypes import wintypes
from typing import Callable

import numpy as np

from .screen import Frame

FRAME_WAIT = 0.1  # how long a read waits for a newer frame before taking the last one
FIRST_FRAME_WAIT = 0.5  # a new session's first frame takes longer
IDLE_STOP = 30.0  # a window not read for this long has its session stopped
BORDERLESS_BUILD = 22000  # Windows 11: a capture without the yellow border

_dwmapi = ctypes.WinDLL("dwmapi")
_dwmapi.DwmGetWindowAttribute.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
DWMWA_EXTENDED_FRAME_BOUNDS = 9


def window_bounds(hwnd) -> tuple[int, int, int, int] | None:
    """The window's visible bounds in screen pixels (left, top, right, bottom): what Windows
    Graphics Capture copies (the title bar included, the invisible resize border not)."""
    rect = wintypes.RECT()
    if _dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rect), ctypes.sizeof(rect)):
        return None
    return rect.left, rect.top, rect.right, rect.bottom


def crop_client(image: np.ndarray, bounds, client) -> Frame | None:
    """The client area (left, top, width, height in screen pixels) cut out of a captured
    window picture (BGRA rows) whose visible bounds are `bounds`. None if the picture
    doesn't match the bounds (the window is being resized) or the area doesn't fit."""
    left, top, width, height = client
    b_left, b_top, b_right, b_bottom = bounds
    image_h, image_w = image.shape[:2]
    if (image_w, image_h) != (b_right - b_left, b_bottom - b_top) or width <= 0 or height <= 0:
        return None
    x0, y0 = left - b_left, top - b_top
    if x0 < 0 or y0 < 0 or x0 + width > image_w or y0 + height > image_h:
        return None
    return Frame(width, height, np.ascontiguousarray(image[y0:y0 + height, x0:x0 + width]).tobytes())


def _start_session(hwnd, on_frame: Callable, on_closed: Callable):
    """Start Windows Graphics Capture on one window; returns its control (with stop())."""
    from windows_capture import WindowsCapture
    capture = WindowsCapture(cursor_capture=False, draw_border=False, window_hwnd=hwnd)
    capture.frame_handler = lambda frame, control: on_frame(frame.frame_buffer)
    capture.closed_handler = on_closed
    return capture.start_free_threaded()


class WindowCapture:
    """One window's capture session, keeping a copy of the newest frame asked for."""

    def __init__(self, hwnd, start=_start_session):
        self.hwnd = hwnd
        self.closed = False
        self.last_used = time.monotonic()
        self._cond = threading.Condition()
        self._image: np.ndarray | None = None
        self._dirty = False  # a newer frame came than the copy kept
        self._want = False  # a read is waiting for the next frame
        self._control = start(hwnd, self._on_frame, self._on_closed)

    def _on_frame(self, buffer) -> None:
        # Runs on the capture's own thread; the buffer is only valid during the call.
        with self._cond:
            if self._want or self._image is None:
                self._image = np.array(buffer)
                self._want = self._dirty = False
                self._cond.notify_all()
            else:
                self._dirty = True

    def _on_closed(self) -> None:
        with self._cond:
            self.closed = True
            self._cond.notify_all()

    def image(self, wait: float = FRAME_WAIT) -> np.ndarray | None:
        """The window's picture as it is now: the kept copy if nothing has changed since,
        else the next frame (or the last copy if none comes within `wait`)."""
        self.last_used = time.monotonic()
        with self._cond:
            if self._image is None:
                wait = max(wait, FIRST_FRAME_WAIT)
            if (self._dirty or self._image is None) and not self.closed:
                self._want = True
                self._cond.wait_for(lambda: not self._want or self.closed, timeout=wait)
            return self._image

    def stop(self) -> None:
        try:
            self._control.stop()
        except Exception:  # already stopped or the window is gone
            pass
        self.closed = True


_lock = threading.Lock()
_sessions: dict[int, WindowCapture] = {}
_supported: bool | None = None
_failed = False
_failure_handlers: list[Callable[[str], None]] = []


def supported() -> bool:
    """Whether this Windows can capture a window without a border, with the package installed."""
    global _supported
    if _supported is None:
        try:
            import windows_capture  # noqa: F401
            _supported = sys.getwindowsversion().build >= BORDERLESS_BUILD
        except Exception:
            _supported = False
    return _supported


def enabled() -> bool:
    """Whether the module reads TTR through window capture (else the screen copy)."""
    return supported() and not _failed


def on_failure(handler: Callable[[str], None]) -> None:
    """Call handler(reason) once if window capture stops working for the run."""
    _failure_handlers.append(handler)


def _fail(reason: str) -> None:
    global _failed
    if _failed:
        return
    _failed = True
    for handler in _failure_handlers:
        handler(reason)


def frame(hwnd, client) -> Frame | None:
    """The client area of a TTR window from its own picture. None if window capture isn't
    in use (read the screen instead). While it is, a window with no picture to give (just
    started, resizing) reads as black, never as the screen, which has the overlay on it."""
    if not enabled():
        return None
    now = time.monotonic()
    with _lock:
        for other in [s for s in _sessions.values() if s.hwnd != hwnd and (s.closed or now - s.last_used > IDLE_STOP)]:
            other.stop()
            del _sessions[other.hwnd]
        session = _sessions.get(hwnd)
        if session is not None and session.closed:
            del _sessions[hwnd]
            session = None
        if session is None:
            try:
                session = _sessions[hwnd] = WindowCapture(hwnd)
            except Exception as e:
                _fail(f"{type(e).__name__}: {e}")
                return None
    image = session.image()
    bounds = window_bounds(hwnd)
    cropped = None if image is None or bounds is None else crop_client(image, bounds, client)
    if cropped is not None:
        return cropped
    _, _, width, height = client
    return Frame(max(width, 0), max(height, 0), bytes(max(width, 0) * max(height, 0) * 4))


def stop_all() -> None:
    with _lock:
        for session in _sessions.values():
            session.stop()
        _sessions.clear()
