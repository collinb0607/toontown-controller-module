"""A glowing frame drawn around whatever the module is hovering, like a console game's
selection highlight, for screens where the hover is hard to see with the cursor hidden.

The frame is a small borderless window on top of TTR. It never takes focus, mouse
clicks go straight through it, and it's excluded from screen capture, so the
module's own pixel reading (screen.py) never sees it.
"""

import ctypes
import math
import time
from ctypes import wintypes

import numpy as np

# Gold, with a soft glow outside the outline.
COLOR = (255, 214, 64)
THICKNESS = 0.004  # the outline, in units of the window's shorter side (see ui.py)
GLOW = 0.006  # how far the glow reaches past the outline
RADIUS = 0.010  # the corners' rounding


# The pointer (Make-a-Toon): a gold triangle left of the item, pointing at it, that
# gently grows and shrinks.
POINTER_SIZE = 0.032  # its length, in units of the window's shorter side
POINTER_GAP = 0.006  # between its tip and the item
POINTER_PULSE = 0.15  # grows and shrinks this much either way
POINTER_PERIOD = 0.9  # seconds a pulse takes
POINTER_STEPS = 12  # sizes drawn per pulse (each is cached)
POINTER_OUTLINE = (70, 45, 0)


def pointer_image(length: int, color: tuple[int, int, int] = COLOR) -> np.ndarray:
    """A right-pointing triangle `length` long (and 1.2 times that tall), gold with a dark
    outline, its tip at the image's right middle, as premultiplied BGRA rows."""
    pad = 2
    s = float(length)
    h, w = int(math.ceil(1.2 * s)) + 2 * pad, int(math.ceil(s)) + 2 * pad
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    corners = ((pad, pad), (pad + s, pad + 0.6 * s), (pad, pad + 1.2 * s))

    def inside(a, b):  # distance inside the edge from a to b (clockwise on screen)
        (ax, ay), (bx, by) = a, b
        nx, ny = -(by - ay), bx - ax
        return ((xs - ax) * nx + (ys - ay) * ny) / math.hypot(nx, ny)

    depth = np.minimum.reduce([inside(corners[i], corners[(i + 1) % 3]) for i in range(3)])
    alpha = np.clip(depth + 0.5, 0, 1)
    outline = max(1.5, s / 12)
    fill = np.clip(depth + 0.5 - outline, 0, 1)[..., None]
    rgb = np.array(POINTER_OUTLINE, np.float32) * (1 - fill) + np.array(color, np.float32) * fill
    image = np.empty((h, w, 4), np.uint8)
    image[..., [2, 1, 0]] = np.round(rgb * alpha[..., None])
    image[..., 3] = np.round(alpha * 255)
    return image


def pointer_scale(t: float) -> float:
    """How big the pointer is at time t (seconds), stepped so each size is drawn once."""
    step = round((t / POINTER_PERIOD) % 1 * POINTER_STEPS) % POINTER_STEPS
    return 1 + POINTER_PULSE * math.sin(2 * math.pi * step / POINTER_STEPS)


def frame_pad(thickness: int, glow: int) -> int:
    """How far the frame's image reaches past the item on each side."""
    return (thickness + 1) // 2 + glow


def frame_image(width: int, height: int, thickness: int, glow: int, radius: int,
                color: tuple[int, int, int] = COLOR) -> np.ndarray:
    """A frame on the edge of a width x height item (the outline straddles it), as
    premultiplied BGRA rows (what layered windows take). The image is bigger than the
    item by half the thickness plus the glow on each side."""
    half = thickness / 2
    pad = frame_pad(thickness, glow)
    h, w = height + 2 * pad, width + 2 * pad
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    # Distance outside the item's rounded rectangle (negative inside).
    r = min(radius, width / 2, height / 2)
    cx, cy = w / 2, h / 2
    qx = np.abs(xs - cx) - (width / 2 - r)
    qy = np.abs(ys - cy) - (height / 2 - r)
    outside = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0) - r
    line = np.clip(half + 0.5 - np.abs(outside), 0, 1)  # antialiased band centered on the edge
    beyond = np.clip(outside - half, 0, None)
    halo = np.where(outside > half, 0.55 * np.exp(-((beyond / max(glow, 1) * 2.2) ** 2)), 0)
    alpha = np.maximum(line, halo)
    image = np.empty((h, w, 4), np.uint8)
    for channel, value in zip((2, 1, 0), color):  # BGR
        image[..., channel] = np.round(alpha * value)
    image[..., 3] = np.round(alpha * 255)
    return image


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32")
_kernel32 = ctypes.WinDLL("kernel32")

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOPMOST = 0x00080000, 0x00000020, 0x00000008
WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x00000080, 0x08000000
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
ULW_ALPHA = 0x2
AC_SRC_OVER, AC_SRC_ALPHA = 0x00, 0x01
WDA_EXCLUDEFROMCAPTURE = 0x11
PM_REMOVE = 0x1
HWND_TOPMOST = -1
SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x2, 0x1, 0x10

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


_user32.DefWindowProcW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_user32.DefWindowProcW.restype = ctypes.c_ssize_t
_user32.CreateWindowExW.argtypes = (wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID)
_user32.CreateWindowExW.restype = wintypes.HWND
_user32.UpdateLayeredWindow.argtypes = (wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                        ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                        wintypes.COLORREF, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD)
_user32.SetWindowDisplayAffinity.argtypes = (wintypes.HWND, wintypes.DWORD)
_user32.SetWindowPos.argtypes = (wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, wintypes.UINT)
_user32.ShowWindow.argtypes = (wintypes.HWND, ctypes.c_int)
_user32.BeginDeferWindowPos.argtypes = (ctypes.c_int,)
_user32.BeginDeferWindowPos.restype = wintypes.HANDLE
_user32.DeferWindowPos.argtypes = (wintypes.HANDLE, wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, wintypes.UINT)
_user32.DeferWindowPos.restype = wintypes.HANDLE
_user32.EndDeferWindowPos.argtypes = (wintypes.HANDLE,)
_user32.DestroyWindow.argtypes = (wintypes.HWND,)
_user32.GetDC.argtypes = (wintypes.HWND,)
_user32.GetDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
_user32.PeekMessageW.argtypes = (ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
                                 wintypes.UINT)
_user32.TranslateMessage.argtypes = (ctypes.POINTER(wintypes.MSG),)
_user32.DispatchMessageW.argtypes = (ctypes.POINTER(wintypes.MSG),)
_gdi32.CreateCompatibleDC.argtypes = (wintypes.HDC,)
_gdi32.CreateCompatibleDC.restype = wintypes.HDC
_gdi32.CreateDIBSection.argtypes = (wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                    wintypes.HANDLE, wintypes.DWORD)
_gdi32.CreateDIBSection.restype = wintypes.HBITMAP
_gdi32.SelectObject.argtypes = (wintypes.HDC, wintypes.HGDIOBJ)
_gdi32.SelectObject.restype = wintypes.HGDIOBJ
_gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)
_gdi32.DeleteDC.argtypes = (wintypes.HDC,)
_kernel32.GetModuleHandleW.restype = wintypes.HMODULE


@WNDPROC
def _wndproc(hwnd, message, wparam, lparam):
    return _user32.DefWindowProcW(hwnd, message, wparam, lparam)


_CLASS = "TTControllerHighlight"
_registered = False


def _register() -> None:
    global _registered
    if not _registered:
        wc = WNDCLASSW(lpfnWndProc=_wndproc, hInstance=_kernel32.GetModuleHandleW(None), lpszClassName=_CLASS)
        _user32.RegisterClassW(ctypes.byref(wc))
        _registered = True


def stack(windows: list) -> None:
    """Raise these overlay windows above everything in one atomic move, the first on top
    and each one just under the one before. Raising them one at a time every frame let
    overlapping hints trade places mid-frame and flicker."""
    windows = [w for w in windows if w.visible and w.hwnd]
    if not windows:
        return
    batch = _user32.BeginDeferWindowPos(len(windows))
    after = HWND_TOPMOST
    for w in windows:
        if batch:
            batch = _user32.DeferWindowPos(batch, w.hwnd, after, 0, 0, 0, 0,
                                           SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        after = w.hwnd
    if batch:
        _user32.EndDeferWindowPos(batch)


class Highlighter:
    """Shows the frame around a rectangle of the screen, or hides it."""

    def __init__(self, exclude_from_capture: bool = True):
        _register()
        self.hwnd = _user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            _CLASS, None, WS_POPUP, 0, 0, 1, 1, None, None, _kernel32.GetModuleHandleW(None), None)
        # Whether screen captures (the module's own included) leave the frame out.
        self.excluded = bool(exclude_from_capture
                             and _user32.SetWindowDisplayAffinity(self.hwnd, WDA_EXCLUDEFROMCAPTURE))
        self._shown: tuple | None = None  # (rect, unit, color) last drawn
        self._pointers: dict[int, np.ndarray] = {}  # pointer images by length
        self.visible = False

    def show(self, rect: tuple[int, int, int, int], unit: int, color: tuple[int, int, int] = COLOR) -> None:
        """rect: the item's left, top, width and height on screen. unit: the game window's
        shorter side, which the frame's thickness scales with. color: the frame's."""
        if (rect, unit, color) != self._shown:
            self._shown = (rect, unit, color)
            self._draw(rect, unit, color)
        if not self.visible:
            _user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.visible = True
        # Stay above TTR, which can be topmost-ish in fullscreen-like modes.
        _user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def show_image(self, left: int, top: int, image: np.ndarray, key, raise_it: bool = True) -> None:
        """Show a premultiplied BGRA image with its top left at (left, top) on screen
        (the golf green's aim line and crosshair). key: redrawn only when it changes.
        raise_it=False leaves the z-order to the caller (`stack`, for the hint windows)."""
        if key != self._shown:
            self._shown = key
            self._blit(left, top, image)
        if not self.visible:
            _user32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            self.visible = True
        if raise_it:
            _user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def show_pointer(self, left: int, middle: int, unit: int, now: float | None = None) -> None:
        """The pulsing pointer, pointing at an item whose left edge is at `left` and middle
        at `middle` on screen. It grows from its tip, so it never covers the item."""
        length = max(8, round(POINTER_SIZE * unit * pointer_scale(time.monotonic() if now is None else now)))
        image = self._pointers.get(length)
        if image is None:
            image = self._pointers[length] = pointer_image(length)
        h, w = image.shape[:2]
        tip = left - round(POINTER_GAP * unit)
        self.show_image(tip - w + 2, middle - h // 2, image, ("pointer", tip, middle, length))

    def hide(self) -> None:
        if self.visible:
            _user32.ShowWindow(self.hwnd, SW_HIDE)
            self.visible = False

    def pump(self) -> None:
        """Handle the window's messages; call once a frame."""
        msg = wintypes.MSG()
        while _user32.PeekMessageW(ctypes.byref(msg), self.hwnd, 0, 0, PM_REMOVE):
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

    def close(self) -> None:
        if self.hwnd:
            _user32.DestroyWindow(self.hwnd)
            self.hwnd = None

    def _draw(self, rect: tuple[int, int, int, int], unit: int, color: tuple[int, int, int] = COLOR) -> None:
        left, top, width, height = rect
        thickness = max(2, round(THICKNESS * unit))
        glow = max(3, round(GLOW * unit))
        image = frame_image(width, height, thickness, glow, max(2, round(RADIUS * unit)), color)
        pad = frame_pad(thickness, glow)
        self._blit(left - pad, top - pad, image)

    def _blit(self, left: int, top: int, image: np.ndarray) -> None:
        h, w = image.shape[:2]
        image = np.ascontiguousarray(image)
        screen_dc = _user32.GetDC(None)
        mem_dc = _gdi32.CreateCompatibleDC(screen_dc)
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        bitmap = _gdi32.CreateDIBSection(mem_dc, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
        try:
            ctypes.memmove(bits, image.ctypes.data, image.nbytes)
            old = _gdi32.SelectObject(mem_dc, bitmap)
            blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
            _user32.UpdateLayeredWindow(self.hwnd, screen_dc, ctypes.byref(wintypes.POINT(left, top)),
                                        ctypes.byref(wintypes.SIZE(w, h)), mem_dc,
                                        ctypes.byref(wintypes.POINT(0, 0)), 0, ctypes.byref(blend), ULW_ALPHA)
            _gdi32.SelectObject(mem_dc, old)
        finally:
            _gdi32.DeleteObject(bitmap)
            _gdi32.DeleteDC(mem_dc)
            _user32.ReleaseDC(None, screen_dc)
