"""Experiment, round two: the harder kinds of background input.

Usage: python tools/background_input_test_2.py [--delay SECONDS]

Round one (background_input_test.py) found TTR takes a key tap and a click posted to
it while another window is in front. This checks what the module needs beyond that,
measuring each from the window's pixels:

1. walking: the forward key held for a second (one key-down, then again with key
   repeats like a real held key), compared with how much the scene changes standing
   still; then walking back;
2. hovering: opens speedchat with a click, rests the mouse on its rows and checks a
   submenu opens (speedchat submenus, gag info and calendar popups all open on hover);
3. rapid clicks: toggles speedchat ten times quickly, checking after each, both with
   round one's paced clicks and with instant ones (the module's old window clicks were
   instant, and TTR missed some);
4. two windows: if a second TTR is open, opens and closes the friends list in each.

Set up: TTR in the overworld, standing somewhere open (room to walk a few steps), with
speedchat and the friends list closed, fully visible on screen. Run this, then keep
another window in front. The real cursor is never moved.
"""

import argparse
import ctypes
import time
from ctypes import wintypes

from background_input_test import (WM_KEYDOWN, WM_KEYUP, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MOUSEMOVE,
                                   MK_LBUTTON, key_lparam, list_open, post_click, post_key)
from ttcontroller import keys, ttr_settings, ui
from ttcontroller.speedchat import read_speedchat
from ttcontroller.window import TTRView, client_rect, find_ttr_windows, make_dpi_aware

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

REPEAT_SECONDS = 0.033  # how often Windows repeats a held key


def _where(x: int, y: int) -> int:
    return (y << 16) | (x & 0xFFFF)


def hold_key(hwnd, vk: int, seconds: float, repeats: bool) -> None:
    _user32.PostMessageW(hwnd, WM_KEYDOWN, vk, key_lparam(vk, False))
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        time.sleep(REPEAT_SECONDS)
        if repeats:
            # A repeat: the key was already down (bit 30).
            _user32.PostMessageW(hwnd, WM_KEYDOWN, vk, key_lparam(vk, False) | (1 << 30))
    _user32.PostMessageW(hwnd, WM_KEYUP, vk, key_lparam(vk, True))


def instant_click(hwnd, x: int, y: int) -> None:
    where = _where(x, y)
    _user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, where)
    _user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, where)
    _user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, where)


def hover(hwnd, x: int, y: int) -> None:
    _user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, _where(x, y))


def scene(view: TTRView) -> list:
    """A grid of pixels over the middle of the window, where the world shows."""
    frame = view.snapshot()
    w, h = frame.width, frame.height
    return [frame.get_pixel(round(w * (0.2 + 0.6 * i / 39)), round(h * (0.25 + 0.5 * j / 19)))
            for i in range(40) for j in range(20)]


def change(a: list, b: list) -> float:
    return sum(abs(p - q) for pa, pb in zip(a, b) for p, q in zip(pa, pb)) / (3 * len(a))


def speedchat_menus(view: TTRView) -> int:
    frame = view.snapshot()
    return len(read_speedchat(frame.width, frame.height, frame.get_pixel).menus)


def control_vk(settings, control: str) -> int | None:
    combo = settings.combo(control)
    return keys.vk_code(combo.key) if not combo.modifiers else None


def test_walking(hwnd, view, settings) -> None:
    print("\n1. Walking")
    forward, reverse = control_vk(settings, "forward"), control_vk(settings, "reverse")
    if forward is None or reverse is None:
        print("  skipped: forward or reverse has a modifier key")
        return
    before = scene(view)
    time.sleep(1.0)
    still = change(before, scene(view))
    print(f"  standing still for 1 s, the scene changes by {still:.1f}")
    for repeats in (False, True):
        before = scene(view)
        hold_key(hwnd, forward, 1.0, repeats)
        time.sleep(0.2)
        moved = change(before, scene(view))
        walked = moved > 3 * still + 4
        print(f"  forward held 1 s ({'with repeats' if repeats else 'one key-down'}): changes by {moved:.1f}"
              f" -> {'WALKED' if walked else 'did not walk'}")
        hold_key(hwnd, reverse, 1.0, repeats)  # back to where it was
        time.sleep(0.5)


def test_hover(hwnd, view, width, height) -> None:
    print("\n2. Hovering")
    button = ui.SPEEDCHAT.center.to_client(width, height)
    post_click(hwnd, *button)
    time.sleep(0.6)
    frame = view.snapshot()
    menus = read_speedchat(frame.width, frame.height, frame.get_pixel).menus
    if not menus:
        print("  skipped: speedchat didn't open from a click")
        return
    opened = False
    for i, row in enumerate(menus[0].rows[:6]):
        hover(hwnd, *row.to_client(width, height))
        time.sleep(0.5)
        count = speedchat_menus(view)
        print(f"  hovering row {i + 1}: {count} menu(s) showing")
        if count >= 2:
            opened = True
            break
    print(f"  -> hover {'WORKS (a submenu opened)' if opened else 'did nothing'}")
    post_click(hwnd, *button)  # close speedchat
    time.sleep(0.6)
    if speedchat_menus(view):
        post_click(hwnd, *button)
        time.sleep(0.6)


def test_rapid_clicks(hwnd, view, width, height) -> None:
    print("\n3. Rapid clicks (toggling speedchat, 0.25 s apart)")
    button = ui.SPEEDCHAT.center.to_client(width, height)
    for name, click in (("paced", post_click), ("instant", instant_click)):
        open_ = bool(speedchat_menus(view))
        ok = 0
        for _ in range(10):
            click(hwnd, *button)
            time.sleep(0.25)
            now_open = bool(speedchat_menus(view))
            ok += now_open != open_
            open_ = now_open
        print(f"  {name} clicks: {ok}/10 toggled it")
        if open_:
            post_click(hwnd, *button)
            time.sleep(0.6)


def test_two_windows(windows, vk: int) -> None:
    print("\n4. Two windows")
    if len(windows) < 2:
        print("  skipped: only one TTR window in the background")
        return
    for n, hwnd in enumerate(windows[:2]):
        view = TTRView(hwnd)
        others = [TTRView(h) for h in windows[:2] if h != hwnd]
        post_key(hwnd, vk)
        time.sleep(1.0)
        opened, other_opened = list_open(view), any(list_open(o) for o in others)
        post_key(hwnd, vk)
        time.sleep(1.0)
        print(f"  window {n + 1}: friends key {'opened' if opened else 'did nothing'} its list; "
              f"the other window's {'ALSO opened (crossed over)' if other_opened else 'stayed closed'}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--delay", type=float, default=5.0, help="seconds to click away first (default 5)")
    args = parser.parse_args()
    make_dpi_aware()
    settings = ttr_settings.load(ttr_settings.DEFAULT_TTR_DIR / ttr_settings.SETTINGS_FILE)

    print(f"Click into another window within {args.delay:.0f} s, so TTR is in the background...")
    time.sleep(args.delay)
    front = _user32.GetForegroundWindow()
    windows = [hwnd for hwnd in find_ttr_windows() if hwnd != front]
    if not windows:
        raise SystemExit("No TTR window in the background (is TTR running, and something else in front?).")
    hwnd = windows[0]
    view = TTRView(hwnd)
    left, top, width, height = client_rect(hwnd)
    print(f"Testing TTR window {hwnd} at {left},{top} ({width}x{height}); {len(windows)} in the background.")
    if speedchat_menus(view) or list_open(view):
        raise SystemExit("Close speedchat and the friends list first.")

    test_walking(hwnd, view, settings)
    test_hover(hwnd, view, width, height)
    test_rapid_clicks(hwnd, view, width, height)
    friends = control_vk(settings, "friendsList")
    if friends is not None:
        test_two_windows(windows, friends)
    print(f"\nStill in front: {'yes' if _user32.GetForegroundWindow() == front else 'no (the test stole focus)'}")


if __name__ == "__main__":
    main()
