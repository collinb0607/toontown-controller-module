"""M13: which background-window step makes the back TTR window flash?

Usage: python tools/flash_check.py

Two TTR windows open. Click the front (keyboard-and-mouse) one when asked, then come back
to this console. Each step runs for 6 seconds against the back window while you watch it,
then asks whether it flashed.
"""

import ctypes
import time
from ctypes import wintypes

from ttcontroller.screen import grab, grab_window
from ttcontroller import screen
from ttcontroller.window import client_rect, find_ttr_windows, make_dpi_aware

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
WM_MBUTTONDOWN, WM_MBUTTONUP, MK_MBUTTON = 0x0207, 0x0208, 0x0010


def black_share(frame) -> float:
    if frame is None:
        return 1.0
    sample = [frame.get_pixel(x, y) for x in range(0, frame.width, 41) for y in range(0, frame.height, 41)]
    return sum(1 for p in sample if max(p) < 8) / len(sample)


def print_window(hwnd, w, h, flags):
    old = screen.PW_RENDERFULLCONTENT
    try:
        screen.PW_RENDERFULLCONTENT = flags  # grab_window ORs it with PW_CLIENTONLY
        return grab_window(hwnd, w, h)
    finally:
        screen.PW_RENDERFULLCONTENT = old


def main() -> None:
    make_dpi_aware()
    windows = find_ttr_windows()
    if len(windows) != 2:
        raise SystemExit(f"Open exactly two TTR windows ({len(windows)} found).")
    print("Click the front (keyboard-and-mouse) TTR window within 5 seconds, then come back here...")
    time.sleep(5)
    front = _user32.GetForegroundWindow()
    if front not in windows:
        raise SystemExit("A TTR window wasn't in front. Run it again and click one.")
    back = next(w for w in windows if w != front)
    left, top, w, h = client_rect(back)
    cx, cy = w // 2, h // 3

    def hover():
        where = (cy << 16) | cx
        _user32.PostMessageW(back, WM_MBUTTONDOWN, MK_MBUTTON, where)
        _user32.PostMessageW(back, WM_MBUTTONUP, 0, where)

    steps = [
        ("nothing at all (to see how it looks normally)", None, 10),
        ("posted middle-button hovers, 10 a second", hover, 10),
        ("screen copy (BitBlt, what one-toon mode uses), 10 a second", lambda: grab(left, top, w, h), 10),
        ("PrintWindow, full content, 10 a second (the module's rate)", lambda: print_window(back, w, h, 0x2), 10),
        ("PrintWindow, plain (no full content), 10 a second", lambda: print_window(back, w, h, 0x0), 10),
        ("PrintWindow, full content, as fast as it goes (like the tests)", lambda: print_window(back, w, h, 0x2), 0),
    ]
    answers = []
    for n, (what, action, rate) in enumerate(steps, 1):
        input(f"\n{n}. {what}.\n   Watch the back window, then press Enter here (don't click it)...")
        end = time.monotonic() + 6
        last = None
        count = 0
        while time.monotonic() < end:
            if action:
                last = action()
                count += 1
            time.sleep(1 / rate if rate else 0)
        note = ""
        if last is not None and hasattr(last, "get_pixel"):
            note = f" ({count} copies, {black_share(last):.0%} of the last one black)"
        flashed = input(f"   Done{note}. Did the back window flash? [y/n] ").strip().lower().startswith("y")
        answers.append(f"{n}. {what}: {'FLASHED' if flashed else 'no flash'}{note}")
    print("\nSummary (paste this back to Claude):")
    print("\n".join(answers))


if __name__ == "__main__":
    main()
