"""Copy part of the screen into memory so many pixels can be read quickly."""

import ctypes
from ctypes import wintypes

import numpy as np

RGB = tuple[int, int, int]

_user32 = ctypes.WinDLL("user32")
_gdi32 = ctypes.WinDLL("gdi32")
# Handles are 64-bit, so every function that takes or returns one needs explicit types.
_user32.GetDC.argtypes = (wintypes.HWND,)
_user32.GetDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
_gdi32.CreateCompatibleDC.argtypes = (wintypes.HDC,)
_gdi32.CreateCompatibleDC.restype = wintypes.HDC
_gdi32.CreateCompatibleBitmap.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int)
_gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
_gdi32.SelectObject.argtypes = (wintypes.HDC, wintypes.HGDIOBJ)
_gdi32.SelectObject.restype = wintypes.HGDIOBJ
_gdi32.BitBlt.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                          wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD)
_gdi32.GetDIBits.argtypes = (wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                             ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT)
_gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)
_gdi32.DeleteDC.argtypes = (wintypes.HDC,)
SRCCOPY = 0x00CC0020


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
    ]


class Frame:
    """A snapshot of a screen region. Pixels outside it read as black."""

    def __init__(self, width: int, height: int, bgra: bytes):
        self.width, self.height, self._bgra = width, height, bgra

    def get_pixel(self, x: int, y: int) -> RGB:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return (0, 0, 0)
        i = (y * self.width + x) * 4
        b, g, r = self._bgra[i:i + 3]
        return r, g, b

    def rgb(self) -> np.ndarray:
        """The whole snapshot as an RGB array (rows, columns, 3), for searching all of it."""
        bgra = np.frombuffer(self._bgra, dtype=np.uint8).reshape(self.height, self.width, 4)
        return bgra[..., 2::-1]


def grab(left: int, top: int, width: int, height: int) -> Frame:
    """Copy a region of the screen (in screen pixels) into a Frame."""
    screen_dc = _user32.GetDC(None)
    mem_dc = _gdi32.CreateCompatibleDC(screen_dc)
    bitmap = _gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    try:
        _gdi32.SelectObject(mem_dc, bitmap)
        _gdi32.BitBlt(mem_dc, 0, 0, width, height, screen_dc, left, top, SRCCOPY)
        # Negative height asks for top-down rows; 32-bit pixels come back as BGRA.
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        buffer = ctypes.create_string_buffer(width * height * 4)
        _gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(header), 0)
    finally:
        _gdi32.DeleteObject(bitmap)
        _gdi32.DeleteDC(mem_dc)
        _user32.ReleaseDC(None, screen_dc)
    return Frame(width, height, buffer.raw)
