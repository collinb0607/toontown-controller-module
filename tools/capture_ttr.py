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

from ttcontroller.screen import grab  # noqa: E402
from ttcontroller.window import ForegroundWatcher, client_rect, find_ttr_windows, make_dpi_aware  # noqa: E402

user32 = ctypes.WinDLL("user32")
user32.GetForegroundWindow.restype = wintypes.HWND


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="what's on screen, e.g. friends_list")
    parser.add_argument("--delay", type=float, default=3.0, help="seconds to wait so you can click into TTR")
    args = parser.parse_args()

    make_dpi_aware()
    print(f"Capturing in {args.delay:g} seconds. Click into the TTR window now...")
    time.sleep(args.delay)

    windows = find_ttr_windows()
    if not windows:
        raise SystemExit("No TTR window found.")
    foreground = user32.GetForegroundWindow()
    hwnd = foreground if ForegroundWatcher().ttr_foreground() and foreground in windows else windows[0]

    left, top, width, height = client_rect(hwnd)
    frame = grab(left, top, width, height)
    surface = pygame.image.frombuffer(frame._bgra, (width, height), "BGRA")
    out_dir = Path(__file__).resolve().parent.parent / "captures"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"{args.name}_{width}x{height}.png"
    pygame.image.save(surface, str(path))
    print(f"Saved {path} ({width}x{height} game area at screen position {left},{top})")


if __name__ == "__main__":
    main()
