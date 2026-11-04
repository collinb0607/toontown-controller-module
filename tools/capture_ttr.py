"""Save a screenshot of the TTR game area, for measuring where UI buttons are.

Usage: python tools/capture_ttr.py NAME [--delay SECONDS]

Waits, then captures whichever TTR window is in front (or the first one found)
to captures/NAME_<width>x<height>.png. TTR must be visible on screen.
"""

import argparse
import ctypes
import os
import time
from ctypes import wintypes
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from ttcontroller.window import ForegroundWatcher, client_rect, find_ttr_windows  # noqa: E402

user32 = ctypes.WinDLL("user32")
gdi32 = ctypes.WinDLL("gdi32")
# Handles are 64-bit, so every function that takes or returns one needs explicit types.
user32.GetDC.argtypes = (wintypes.HWND,)
user32.GetDC.restype = wintypes.HDC
user32.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
gdi32.CreateCompatibleDC.argtypes = (wintypes.HDC,)
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleBitmap.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int)
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
gdi32.SelectObject.argtypes = (wintypes.HDC, wintypes.HGDIOBJ)
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.BitBlt.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                         wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD)
gdi32.GetDIBits.argtypes = (wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                            ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT)
gdi32.DeleteObject.argtypes = (wintypes.HGDIOBJ,)
gdi32.DeleteDC.argtypes = (wintypes.HDC,)
user32.GetForegroundWindow.restype = wintypes.HWND
SRCCOPY = 0x00CC0020


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD),
    ]


def grab(left: int, top: int, width: int, height: int) -> pygame.Surface:
    """Copy a region of the screen into a pygame surface."""
    screen_dc = user32.GetDC(None)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bitmap = gdi32.CreateCompatibleBitmap(screen_dc, width, height)
    gdi32.SelectObject(mem_dc, bitmap)
    gdi32.BitBlt(mem_dc, 0, 0, width, height, screen_dc, left, top, SRCCOPY)

    # Negative height asks for top-down rows; 32-bit pixels come back as BGRA.
    header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(header), 0)

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(mem_dc)
    user32.ReleaseDC(None, screen_dc)
    return pygame.image.frombuffer(buffer.raw, (width, height), "BGRA")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="what's on screen, e.g. friends_list")
    parser.add_argument("--delay", type=float, default=3.0, help="seconds to wait so you can click into TTR")
    args = parser.parse_args()

    print(f"Capturing in {args.delay:g} seconds. Click into the TTR window now...")
    time.sleep(args.delay)

    windows = find_ttr_windows()
    if not windows:
        raise SystemExit("No TTR window found.")
    foreground = user32.GetForegroundWindow()
    hwnd = foreground if ForegroundWatcher().ttr_foreground() and foreground in windows else windows[0]

    left, top, width, height = client_rect(hwnd)
    out_dir = Path(__file__).resolve().parent.parent / "captures"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{args.name}_{width}x{height}.png"
    pygame.image.save(grab(left, top, width, height), str(path))
    print(f"Saved {path} ({width}x{height} game area at screen position {left},{top})")


if __name__ == "__main__":
    main()
