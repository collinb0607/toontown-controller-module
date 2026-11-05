"""Experiment, round three: picking a gag in a background TTR window.

Usage: python tools/background_battle_test.py [--delay SECONDS]

Rounds one and two found that keys, paced clicks and hovering (a posted right-button
press and release; plain mouse moves are ignored) reach a TTR window that isn't in
front. This checks the battle: with the gag picker showing, it hovers a gag (a right
click), then clicks it (a paced left click), and if TTR asks which cog, hovers and
clicks the first one. It reads the battle screen after each step and saves a
screenshot of each to tools/background_battle_*.png (gitignored captures folder).

Set up: TTR in a battle with the gag picker showing, fully visible on screen. Run
this, then keep another window in front. It really picks a gag (Throw's first if you
have it). The real cursor is never moved.
"""

import argparse
import ctypes
import os
import time
from ctypes import wintypes
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import numpy as np  # noqa: E402
import pygame  # noqa: E402

from background_input_test import post_click  # noqa: E402
from ttcontroller.battle import TRACKS, cell, read_screen  # noqa: E402
from ttcontroller.window import TTRView, client_rect, find_ttr_windows, make_dpi_aware  # noqa: E402

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON = 0x0204, 0x0205, 0x0002
OUT = Path(__file__).resolve().parent.parent / "captures"
THROW = TRACKS.index("Throw")


def hover(hwnd, x: int, y: int) -> None:
    """TTR ignores posted mouse moves, but a right-button press and release moves its pointer."""
    where = (y << 16) | (x & 0xFFFF)
    _user32.PostMessageW(hwnd, WM_RBUTTONDOWN, MK_RBUTTON, where)
    time.sleep(0.05)
    _user32.PostMessageW(hwnd, WM_RBUTTONUP, 0, where)


def look(view: TTRView, name: str):
    frame = view.snapshot()
    surface = pygame.surfarray.make_surface(np.transpose(frame.rgb(), (1, 0, 2)))
    OUT.mkdir(exist_ok=True)
    pygame.image.save(surface, str(OUT / f"background_battle_{name}.png"))
    screen = read_screen(frame.width, frame.height, frame.get_pixel)
    print(f"  {name}: battle screen is {screen.kind or 'none'} (screenshot captures/background_battle_{name}.png)")
    return screen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--delay", type=float, default=5.0, help="seconds to click away first (default 5)")
    args = parser.parse_args()
    make_dpi_aware()
    time.sleep(args.delay)
    front = _user32.GetForegroundWindow()
    windows = [hwnd for hwnd in find_ttr_windows() if hwnd != front]
    if not windows:
        raise SystemExit("No TTR window in the background.")
    hwnd = windows[0]
    view = TTRView(hwnd)
    _, _, width, height = client_rect(hwnd)

    screen = look(view, "0_start")
    if screen.kind != "picker":
        raise SystemExit("The gag picker isn't showing.")
    usable = [(r, c) for r in range(len(screen.usable)) for c in range(len(screen.usable[r])) if screen.usable[r][c]]
    if not usable:
        raise SystemExit("No usable gags.")
    r, c = (THROW, 0) if screen.usable[THROW][0] else usable[0]
    gag = cell(r, c).to_client(width, height)
    print(f"Gag: {TRACKS[r]} level {c + 1} at {gag}")

    hover(hwnd, *gag)
    time.sleep(0.6)
    look(view, "1_hovered")
    post_click(hwnd, *gag)
    time.sleep(1.0)
    screen = look(view, "2_clicked")
    if screen.kind == "target" and screen.targets:
        target = screen.targets[0].to_client(width, height)
        hover(hwnd, *target)
        time.sleep(0.6)
        look(view, "3_target_hovered")
        post_click(hwnd, *target)
        time.sleep(1.0)
        screen = look(view, "4_target_clicked")
    picked = screen.kind in ("waiting", None)
    print(f"\nGag {'PICKED' if picked else 'not picked'} (now {screen.kind or 'no battle panel'}).")
    print(f"Still in front: {'yes' if _user32.GetForegroundWindow() == front else 'no (the test stole focus)'}")


if __name__ == "__main__":
    main()
