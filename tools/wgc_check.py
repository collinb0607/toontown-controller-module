"""Can the module read TTR with Windows Graphics Capture instead of copying the screen?

Usage: PYTHONPATH=src .venv/Scripts/python.exe tools/wgc_check.py

If it can, the overlay no longer has to hide from screen capture, so OBS records it.
Needs `pip install windows-capture` in the venv. Have one TTR window open (in game is
best, standing somewhere with things moving), and follow the prompts in this console.

Checks, in order:
  1. Speed: how many frames a second arrive, and what one copy costs.
  2. Match: the captured window, cut to its client area, against today's screen copy (BitBlt).
  3. Flash: you watch TTR with and without the capture running.
  4. Border: whether a yellow (or any) border shows round TTR while it's captured.
  5. Covered: you put this console over part of TTR; the capture should still show TTR.
Pictures go in captures/ (gitignored): wgc_uncovered.png, wgc_covered.png, bitblt_covered.png.
"""

import ctypes
import threading
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np

from ttcontroller.screen import grab
from ttcontroller.window import client_rect, make_dpi_aware, ttr_windows

try:
    from windows_capture import WindowsCapture
except ImportError:
    raise SystemExit("Install it first: .venv/Scripts/python.exe -m pip install windows-capture")

CAPTURES = Path(__file__).resolve().parent.parent / "captures"

_user32 = ctypes.WinDLL("user32")
_user32.GetForegroundWindow.restype = wintypes.HWND
_dwmapi = ctypes.WinDLL("dwmapi")
DWMWA_EXTENDED_FRAME_BOUNDS = 9


def frame_bounds(hwnd) -> tuple[int, int, int, int]:
    """The window's visible bounds (what Windows Graphics Capture copies), in screen pixels."""
    rect = wintypes.RECT()
    _dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS,
                                  ctypes.byref(rect), ctypes.sizeof(rect))
    return rect.left, rect.top, rect.right, rect.bottom


class Latest:
    """Keeps a copy of the newest captured frame, and counts them."""

    def __init__(self):
        self.lock = threading.Lock()
        self.image = None  # (height, width, 4) BGRA
        self.count = 0
        self.copy_ms: list[float] = []
        self.closed = False

    def take(self):
        with self.lock:
            return None if self.image is None else self.image.copy()


def start_capture(hwnd, border):
    latest = Latest()
    capture = WindowsCapture(cursor_capture=False, draw_border=border, window_hwnd=hwnd)

    @capture.event
    def on_frame_arrived(frame, control):
        t = time.perf_counter()
        image = np.array(frame.frame_buffer)  # the buffer is only valid during the callback
        with latest.lock:
            latest.image = image
            latest.count += 1
            latest.copy_ms.append((time.perf_counter() - t) * 1000)

    @capture.event
    def on_closed():
        latest.closed = True

    return capture.start_free_threaded(), latest


def save(image_bgra, name):
    import cv2
    CAPTURES.mkdir(exist_ok=True)
    path = CAPTURES / name
    cv2.imwrite(str(path), image_bgra[..., :3])
    print(f"   saved {path}")


def ask(question) -> str:
    return input(f"{question} ").strip().lower()


def main() -> None:
    make_dpi_aware()
    windows = ttr_windows()
    if not windows:
        raise SystemExit("No TTR window found. Open TTR and run this again.")
    hwnd, name = windows[0]
    if len(windows) > 1:
        print(f"{len(windows)} TTR windows found; using the {name} one.")
    results = {}

    print("\n3a. Flash, without the capture: watch TTR for 6 seconds to see how it looks normally.")
    ask("   Press Enter to start...")
    time.sleep(6)

    print("\nStarting the capture (no border asked for)...")
    try:
        control, latest = start_capture(hwnd, border=False)
        border_note = "asked for no border"
    except Exception as e:  # Windows 10 can't turn the border off
        print(f"   No-border capture failed ({e}); trying with Windows' default border.")
        control, latest = start_capture(hwnd, border=None)
        border_note = "Windows' default border"
    time.sleep(1.0)
    if latest.image is None:
        control.stop()
        raise SystemExit("No frames arrived in a second. Is TTR minimized?")

    print("\n1. Speed: measuring for 5 seconds...")
    count0, t0 = latest.count, time.perf_counter()
    take_ms, convert_ms = [], []
    while time.perf_counter() - t0 < 5:
        t = time.perf_counter()
        image = latest.take()
        take_ms.append((time.perf_counter() - t) * 1000)
        t = time.perf_counter()
        image[..., :].tobytes()  # what building today's Frame from it would cost
        convert_ms.append((time.perf_counter() - t) * 1000)
        time.sleep(0.1)  # the module reads screens every 0.1 s
    fps = (latest.count - count0) / (time.perf_counter() - t0)
    with latest.lock:
        copy_ms = latest.copy_ms[-50:]
    results["frames/s"] = f"{fps:.0f}"
    results["copy in callback"] = f"{np.mean(copy_ms):.1f} ms"
    results["take + to bytes"] = f"{np.mean(take_ms) + np.mean(convert_ms):.1f} ms"
    t = time.perf_counter()
    for _ in range(5):
        grab(*client_rect(hwnd))
    results["today's BitBlt"] = f"{(time.perf_counter() - t) / 5 * 1000:.1f} ms"
    for k in ("frames/s", "copy in callback", "take + to bytes", "today's BitBlt"):
        print(f"   {k}: {results[k]}")

    print("\n2. Match against today's screen copy (TTR must be uncovered now)...")
    ask("   Make sure nothing covers TTR, then press Enter...")
    left, top, w, h = client_rect(hwnd)
    fl, ft, fr, fb = frame_bounds(hwnd)
    image = latest.take()
    blt = grab(left, top, w, h).rgb()[..., ::-1]  # BGR, like the capture
    ih, iw = image.shape[:2]
    print(f"   captured {iw}x{ih}; visible bounds {fr - fl}x{fb - ft}; client {w}x{h} at offset "
          f"{left - fl},{top - ft} in the bounds")
    # Look for the client area near where the bounds say it is (a few pixels either way).
    best = None
    for dy in range(-8, 9):
        for dx in range(-8, 9):
            x0, y0 = left - fl + dx, top - ft + dy
            if x0 < 0 or y0 < 0 or x0 + w > iw or y0 + h > ih:
                continue
            crop = image[y0:y0 + h:7, x0:x0 + w:7, :3].astype(int)
            diff = np.abs(crop - blt[::7, ::7].astype(int)).mean()
            if best is None or diff < best[0]:
                best = (diff, dx, dy, x0, y0)
    if best is None:
        print("   The client area doesn't fit in the captured frame.")
        results["match"] = "client area didn't fit"
    else:
        diff, dx, dy, x0, y0 = best
        crop = image[y0:y0 + h, x0:x0 + w]
        exact = (np.abs(crop[..., :3].astype(int) - blt.astype(int)).max(axis=2) <= 2).mean()
        results["match"] = (f"offset {x0},{y0} ({'as the bounds say' if (dx, dy) == (0, 0) else f'{dx:+},{dy:+} off'}), "
                            f"mean difference {diff:.1f}, {exact:.0%} of pixels within 2")
        print(f"   {results['match']}")
        print("   (TTR moves between the two copies, so a few percent off is normal; 0-3 mean is a match.)")
        save(crop, "wgc_uncovered.png")

    print("\n3b. Flash, with the capture running: watch TTR for 6 seconds.")
    ask("   Press Enter to start...")
    time.sleep(6)
    results["flash"] = ask("   Did TTR flash, flicker or stutter more than before? (y/n)")

    print(f"\n4. Border ({border_note}):")
    results["border"] = ask("   Is there a yellow or coloured border round TTR right now? (y/n)")

    print("\n5. Covered: drag this console (or any window) over part of TTR, leaving it there.")
    ask("   Then press Enter here (clicking the console is fine)...")
    time.sleep(0.5)
    count0 = latest.count
    time.sleep(1.0)
    results["covered frames/s"] = str(latest.count - count0)
    image = latest.take()
    left, top, w, h = client_rect(hwnd)
    if best is not None:
        save(image[y0:y0 + h, x0:x0 + w], "wgc_covered.png")
    save(grab(left, top, w, h).rgb()[..., ::-1].copy(), "bitblt_covered.png")
    print(f"   frames in a second while covered: {results['covered frames/s']}")

    control.stop()
    print("\nResults (paste these back to Claude):")
    for k, v in results.items():
        print(f"   {k}: {v}")
    print(f"   windows: {len(windows)} TTR, capture {border_note}")


if __name__ == "__main__":
    main()
