"""Experiment: can a TTR window that isn't in front be driven by window messages?

Usage: python tools/background_input_test.py [--trials N] [--delay SECONDS]

The module sends real input (SendInput), which always goes to the window in front and
moves the one real cursor. Playing two toons, one by keyboard and mouse and one by
controller, would need the controller's input posted straight to the other window
instead. This checks whether TTR accepts that, by itself:

- keys: posts TTR's friends list key to the background window, then reads its pixels
  to see if the friends list opened;
- clicks: posts a click on the list's close X, then checks it closed.

Each trial runs two ways: plain messages, and with a fake "you're focused" message
first (games often drop input they think arrives while in the background).

Set up: TTR in the overworld with the friends list closed, fully visible on screen
(not covered by another window). Run this, then within the delay click into another
window (your other TTR, or anything else), so the TTR being tested is in the
background. The real cursor is never moved.
"""

import argparse
import ctypes
import time
from ctypes import wintypes

from ttcontroller import keys, ttr_settings
from ttcontroller.friends import LIST_CLOSE, read_friends
from ttcontroller.window import TTRView, client_rect, find_ttr_windows, make_dpi_aware

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_user32.SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

WM_ACTIVATE, WM_SETFOCUS = 0x0006, 0x0007
WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101
WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0200, 0x0201, 0x0202
MK_LBUTTON = 0x0001
WA_ACTIVE = 1
SETTLE = 1.0  # seconds for TTR to open or close the list


def key_lparam(vk: int, up: bool) -> int:
    scan = _user32.MapVirtualKeyW(vk, 0)
    value = 1 | (scan << 16)
    if up:
        value |= (1 << 30) | (1 << 31)
    return value


def post_key(hwnd, vk: int) -> None:
    _user32.PostMessageW(hwnd, WM_KEYDOWN, vk, key_lparam(vk, False))
    time.sleep(0.06)  # like the module's key pulses
    _user32.PostMessageW(hwnd, WM_KEYUP, vk, key_lparam(vk, True))


def post_click(hwnd, x: int, y: int) -> None:
    where = (y << 16) | (x & 0xFFFF)
    _user32.PostMessageW(hwnd, WM_MOUSEMOVE, 0, where)
    time.sleep(0.05)
    _user32.PostMessageW(hwnd, WM_LBUTTONDOWN, MK_LBUTTON, where)
    time.sleep(0.08)
    _user32.PostMessageW(hwnd, WM_LBUTTONUP, 0, where)


def fake_focus(hwnd) -> None:
    _user32.SendMessageW(hwnd, WM_ACTIVATE, WA_ACTIVE, 0)
    _user32.SendMessageW(hwnd, WM_SETFOCUS, 0, 0)


def list_open(view: TTRView) -> bool:
    frame = view.snapshot()
    return read_friends(frame.width, frame.height, frame.get_pixel).kind == "list"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--trials", type=int, default=5, help="tries of each way (default 5)")
    parser.add_argument("--delay", type=float, default=5.0, help="seconds to click away first (default 5)")
    args = parser.parse_args()
    make_dpi_aware()

    combo = ttr_settings.load(ttr_settings.DEFAULT_TTR_DIR / ttr_settings.SETTINGS_FILE).combo("friendsList")
    if len(combo.names) != 1:
        raise SystemExit(f"The friends list key is {'-'.join(combo.names)}; this test needs a single key.")
    vk = keys.vk_code(combo.names[0])

    print(f"Click into another window within {args.delay:.0f} s, so the TTR being tested is in the background...")
    time.sleep(args.delay)
    front = _user32.GetForegroundWindow()
    targets = [hwnd for hwnd in find_ttr_windows() if hwnd != front]
    if not targets:
        raise SystemExit("No TTR window in the background (is TTR running, and something else in front?).")
    hwnd = targets[0]
    view = TTRView(hwnd)
    left, top, width, height = client_rect(hwnd)
    print(f"Testing TTR window {hwnd} at {left},{top} ({width}x{height}); {len(targets)} in the background.")
    if list_open(view):
        raise SystemExit("Its friends list is already open: close it first.")
    close = LIST_CLOSE.to_client(width, height)

    results = {}
    for way, prepare in (("plain messages", None), ("with fake focus", fake_focus)):
        keys_ok = clicks_ok = clicks_tried = 0
        for trial in range(args.trials):
            if prepare:
                prepare(hwnd)
            post_key(hwnd, vk)
            time.sleep(SETTLE)
            opened = list_open(view)
            keys_ok += opened
            if opened:
                if prepare:
                    prepare(hwnd)
                post_click(hwnd, *close)
                time.sleep(SETTLE)
                closed = not list_open(view)
                clicks_tried += 1
                clicks_ok += closed
                if not closed:
                    post_key(hwnd, vk)  # close it with the key, for the next trial
                    time.sleep(SETTLE)
            print(f"  {way}, trial {trial + 1}: key {'opened' if opened else 'did nothing'}"
                  + (f", click {'closed it' if closed else 'did nothing'}" if opened else ""))
        results[way] = (keys_ok, clicks_ok, clicks_tried)
        if list_open(view):
            post_key(hwnd, vk)
            time.sleep(SETTLE)

    print("\nResults:")
    for way, (keys_ok, clicks_ok, clicks_tried) in results.items():
        print(f"  {way}: keys {keys_ok}/{args.trials}, clicks {clicks_ok}/{clicks_tried}")
    print(f"\nStill in front: {'yes' if _user32.GetForegroundWindow() == front else 'no (the test stole focus)'}")


if __name__ == "__main__":
    main()
