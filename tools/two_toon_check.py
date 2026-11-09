"""M13 phase 0: what a background TTR window takes, checked one at a time.

Usage: python tools/two_toon_check.py [E1 E4 ...]   (no arguments runs them all)

Set up: two TTR windows logged in, side by side. When asked, click the one you'll play
with keyboard and mouse (the "front" window); the other is the "back" window every check
posts to. Keep this console where you can see it: most checks ask you to set the back
window up, then type y or n. Answer "s" to skip a check.

Some checks ask you to point at something in the back window: rest the real mouse on it
(don't click), press Enter here, then move the mouse off the back window before the
countdown ends. Screenshots of each step go to captures/two_toon_check/ (local only).
"""

import argparse
import ctypes
import os
import time
from ctypes import wintypes
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from background_input_test import key_lparam  # noqa: E402
from ttcontroller import keys, ttr_settings, ui  # noqa: E402
from ttcontroller.options import read_options  # noqa: E402
from ttcontroller.screen import grab, grab_window  # noqa: E402
from ttcontroller.speedchat import read_speedchat  # noqa: E402
from ttcontroller.window import client_rect, find_ttr_windows, make_dpi_aware  # noqa: E402

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.ScreenToClient.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))
_user32.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
_user32.ClientToScreen.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))

WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP, WM_CHAR = 0x0100, 0x0101, 0x0104, 0x0105, 0x0102
WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0201, 0x0202
WM_RBUTTONDOWN, WM_RBUTTONUP = 0x0204, 0x0205
WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MOUSEWHEEL = 0x0207, 0x0208, 0x020A
MK_LBUTTON, MK_RBUTTON, MK_MBUTTON = 0x0001, 0x0002, 0x0010
WHEEL_DELTA = 120
OUT = Path(__file__).resolve().parent.parent / "captures" / "two_toon_check"
results: dict[str, str] = {}


class Skip(Exception):
    pass


# --- posting ---------------------------------------------------------------------------

def where(x: int, y: int) -> int:
    return ((y & 0xFFFF) << 16) | (x & 0xFFFF)


def hover(hwnd, x: int, y: int, button: str = "middle", holding_left: bool = False) -> None:
    """Move TTR's pointer to client x,y: a middle (or right) press and release."""
    held = MK_LBUTTON if holding_left else 0
    down, up, flag = ((WM_MBUTTONDOWN, WM_MBUTTONUP, MK_MBUTTON) if button == "middle"
                      else (WM_RBUTTONDOWN, WM_RBUTTONUP, MK_RBUTTON))
    _user32.PostMessageW(hwnd, down, flag | held, where(x, y))
    _user32.PostMessageW(hwnd, up, held, where(x, y))


def left(hwnd, x: int, y: int, down: bool) -> None:
    _user32.PostMessageW(hwnd, WM_LBUTTONDOWN if down else WM_LBUTTONUP, MK_LBUTTON if down else 0, where(x, y))


def paced_click(hwnd, x: int, y: int) -> None:
    """The findings' pacing: hover, 50 ms, down, 80 ms, up."""
    hover(hwnd, x, y)
    time.sleep(0.05)
    left(hwnd, x, y, True)
    time.sleep(0.08)
    left(hwnd, x, y, False)


def key(hwnd, name: str, down: bool, system: bool = False) -> None:
    vk = keys.vk_code(name)
    lparam = key_lparam(vk, not down)
    if keys.is_extended(name):
        lparam |= 1 << 24
    if system:
        lparam |= 1 << 29
        msg = WM_SYSKEYDOWN if down else WM_SYSKEYUP
    else:
        msg = WM_KEYDOWN if down else WM_KEYUP
    _user32.PostMessageW(hwnd, msg, vk, lparam)


def tap(hwnd, name: str) -> None:
    key(hwnd, name, True)
    time.sleep(0.06)
    key(hwnd, name, False)


# --- reading and asking ----------------------------------------------------------------

def size(hwnd) -> tuple[int, int]:
    _, _, w, h = client_rect(hwnd)
    return w, h


def snap(hwnd):
    w, h = size(hwnd)
    return grab_window(hwnd, w, h)


def save(hwnd, name: str, frame=None) -> Path | None:
    frame = frame or snap(hwnd)
    if frame is None:
        return None
    path = OUT / f"{name}.png"
    pygame.image.save(pygame.image.frombuffer(frame._bgra, (frame.width, frame.height), "BGRA"), str(path))
    return path


def scene(frame) -> list:
    w, h = frame.width, frame.height
    return [frame.get_pixel(round(w * (0.2 + 0.6 * i / 39)), round(h * (0.25 + 0.5 * j / 19)))
            for i in range(40) for j in range(20)]


def change(a: list, b: list) -> float:
    return sum(abs(p - q) for pa, pb in zip(a, b) for p, q in zip(pa, pb)) / (3 * len(a))


def ask(question: str) -> bool:
    answer = input(f"  {question} [y/n/s] ").strip().lower()
    if answer.startswith("s"):
        raise Skip
    return answer.startswith("y")


def wait(prompt: str) -> None:
    if input(f"  {prompt} (Enter, or s to skip) ").strip().lower().startswith("s"):
        raise Skip


def countdown(seconds: int = 3, what: str = "Move the mouse off the back window") -> None:
    print(f"  {what}: posting in", end="", flush=True)
    for n in range(seconds, 0, -1):
        print(f" {n}", end="", flush=True)
        time.sleep(1)
    print()


def point_at(hwnd, what: str) -> tuple[int, int]:
    """The client point under the real mouse when the user presses Enter."""
    wait(f"Rest the mouse on {what} in the back window (don't click), then press Enter")
    pos = wintypes.POINT()
    _user32.GetCursorPos(ctypes.byref(pos))
    _user32.ScreenToClient(hwnd, ctypes.byref(pos))
    w, h = size(hwnd)
    if not (0 <= pos.x < w and 0 <= pos.y < h):
        print(f"  That's outside the back window ({pos.x},{pos.y}); try again.")
        return point_at(hwnd, what)
    return pos.x, pos.y


def control(name: str) -> str | None:
    """A TTR control's key, if it's a single key."""
    combo = ttr_settings.load(ttr_settings.DEFAULT_TTR_DIR / ttr_settings.SETTINGS_FILE).combo(name)
    return combo.key if not combo.modifiers else None


# --- the checks ------------------------------------------------------------------------

def e1_two_windows(front, back) -> str:
    print("E1: both toons in the overworld with room to walk. You'll play the front window for "
          "10 s (walk, open the chat box and type, don't send) while the back toon walks back and forth.")
    forward, reverse = control("forward"), control("reverse")
    if not forward or not reverse:
        return "skipped: forward or reverse has a modifier"
    wait("Press Enter, then click the front window and play")
    moved = []
    end = time.monotonic() + 10
    direction = forward
    while time.monotonic() < end:
        before = scene(snap(back))
        key(back, direction, True)
        time.sleep(1.0)
        key(back, direction, False)
        moved.append(change(before, scene(snap(back))))
        direction = reverse if direction == forward else forward
        time.sleep(0.5)
    print(f"  back window scene change per walk: {', '.join(f'{m:.0f}' for m in moved)}")
    own = ask("Did the front toon only do what you did, and the back toon only walk?")
    return f"{'pass' if own else 'FAIL'} (back scene change {min(moved):.0f} to {max(moved):.0f})"


def e2_real_mouse(front, back) -> str:
    print("E2: the back window's speedchat gets opened and a row hovered; then you move the real "
          "mouse over the back window (don't click).")
    w, h = size(back)
    paced_click(back, *ui.SPEEDCHAT.center.to_client(w, h))
    time.sleep(0.6)
    frame = snap(back)
    menus = read_speedchat(frame.width, frame.height, frame.get_pixel).menus
    if menus:
        hover(back, *menus[0].rows[0].to_client(w, h))
        time.sleep(0.5)
    save(back, "E2_before")
    wait("Speedchat should be open with a row hovered. Press Enter, then wave the mouse over the back window for 5 s")
    time.sleep(5)
    save(back, "E2_after")
    followed = ask("Did the back window's hover or pointer follow the real mouse?")
    paced_click(back, *ui.SPEEDCHAT.center.to_client(w, h))  # close speedchat
    return "FAIL: hover follows the real mouse (README: keep the mouse off it)" if followed else "pass"


def e3_frame_rate(front, back) -> str:
    print("E3: the back toon walks forward for 2 s while its window is read as fast as possible.")
    forward = control("forward")
    if not forward:
        return "skipped: forward has a modifier"
    wait("Back toon in the overworld with room ahead; click the front window, then press Enter here")
    key(back, forward, True)
    start = time.perf_counter()
    last, reads, changes = None, 0, 0
    while time.perf_counter() - start < 2.0:
        now = scene(snap(back))
        reads += 1
        if last is not None and change(last, now) > 0.5:
            changes += 1
        last = now
    took = time.perf_counter() - start
    key(back, forward, False)
    time.sleep(0.2)
    tap(back, control("reverse") or forward)
    reads_fps, draw_fps = reads / took, changes / took
    verdict = "pass" if draw_fps >= 20 or draw_fps >= 0.9 * reads_fps else "SLOW"
    return f"{verdict}: {draw_fps:.0f} new frames/s seen ({reads_fps:.0f} reads/s, so at most that)"


def e4_print_window(front, back) -> str:
    print("E4: PrintWindow of the back window while the front one covers about half of it.")
    wait("Drag the front window so it covers about half of the back one, then press Enter")
    w, h = size(back)
    times, frames = [], []
    for _ in range(10):
        start = time.perf_counter()
        frame = grab_window(back, w, h)
        times.append(time.perf_counter() - start)
        frames.append(frame)
    if any(f is None for f in frames):
        return "FAIL: PrintWindow returned nothing"
    frame = frames[-1]
    sample = [frame.get_pixel(x, y) for x in range(0, w, 37) for y in range(0, h, 37)]
    black = sum(1 for p in sample if max(p) < 8) / len(sample)
    left_, top, _, _ = client_rect(back)
    path = save(back, "E4_printwindow", frame)
    save(back, "E4_screen_copy", grab(left_, top, w, h))
    average = 1000 * sum(times) / len(times)
    print(f"  {average:.1f} ms average at {w}x{h}, {black:.0%} black; compare {path.name} with E4_screen_copy.png")
    covered_ok = ask(f"Open {path} - does the covered half show the game (not the front window, not black)?")
    fast = average < 25
    return (f"{'pass' if covered_ok and fast else 'FAIL'}: {average:.1f} ms at {w}x{h}, "
            f"covered half {'right' if covered_ok else 'wrong'}, {black:.0%} black")


def e5_hold(front, back) -> str:
    print("E5: holding the left button on a scroll triangle (e.g. the book's Districts list), "
          "then on kart turning if you can reach it.")
    found = []
    for what in ("a scroll triangle", "a kart turn arrow (s if you can't reach one)"):
        try:
            x, y = point_at(back, what)
        except Skip:
            continue
        countdown()
        save(back, f"E5_{len(found)}_before")
        hover(back, x, y)
        time.sleep(0.05)
        left(back, x, y, True)
        time.sleep(1.5)
        save(back, f"E5_{len(found)}_held")
        left(back, x, y, False)
        time.sleep(0.5)
        save(back, f"E5_{len(found)}_after")
        found.append(f"{what.split(' (')[0]}: "
                     + ("pass" if ask("Did it keep going while held (1.5 s) and stop when let go?") else "FAIL"))
    return "; ".join(found) or "skipped"


def e6_wheel(front, back) -> str:
    print("E6: three posted wheel notches on a list (Options' keybind list, or the SOS cards).")
    x, y = point_at(back, "the list")
    countdown()
    save(back, "E6_before")
    sx, sy = to_screen(back, x, y)
    for _ in range(3):
        # WM_MOUSEWHEEL takes screen coordinates; delta in the high word of wParam.
        _user32.PostMessageW(back, WM_MOUSEWHEEL, ((-WHEEL_DELTA) & 0xFFFF) << 16, where(sx, sy))
        time.sleep(0.15)
    time.sleep(0.4)
    save(back, "E6_after")
    return "pass" if ask("Did it scroll down by three notches?") else "FAIL"


def to_screen(hwnd, x: int, y: int) -> tuple[int, int]:
    p = wintypes.POINT(x, y)
    _user32.ClientToScreen(hwnd, ctypes.byref(p))
    return p.x, p.y


def e7_typing(front, back) -> str:
    print("E7: typing into a name box: Make-a-Toon's name box, or the 'type delete' box.")
    x, y = point_at(back, "the text box")
    countdown()
    paced_click(back, x, y)
    time.sleep(0.3)
    for letter in "abc":
        key(back, letter, True)
        key(back, letter, False)
    time.sleep(0.4)
    save(back, "E7_keys")
    keys_ok = ask("Does the box show 'abc' once each (not 'aabbcc', not empty)?")
    print("  Now with WM_CHAR: 'xyz'.")
    for letter in "xyz":
        _user32.PostMessageW(back, WM_CHAR, ord(letter), 1)
    time.sleep(0.4)
    save(back, "E7_char")
    char_ok = ask("Did 'xyz' appear after it, once each?")
    return f"keydown/up {'pass' if keys_ok else 'FAIL'}; WM_CHAR {'pass' if char_ok else 'FAIL'}"


def options_open(hwnd) -> bool:
    frame = snap(hwnd)
    return read_options(frame.width, frame.height, frame.get_pixel).kind is not None


def e8_modifiers(front, back) -> str:
    print("E8: shift+escape (TTR's Options) posted to the back window.")
    wait("Back toon in the overworld with nothing open; press Enter")
    tried = []
    for way, system in (("WM_KEYDOWN", False), ("shift as WM_SYSKEYDOWN", True)):
        key(back, "shift", True, system)
        time.sleep(0.03)
        tap(back, "escape")
        time.sleep(0.03)
        key(back, "shift", False, system)
        time.sleep(1.0)
        save(back, f"E8_{'sys' if system else 'plain'}")
        opened = options_open(back) or ask("The reader didn't see Options: did it open?")
        tried.append(f"{way} {'opened Options' if opened else 'did nothing'}")
        if opened:
            wait("Close Options in the back window (with the mouse is fine), then press Enter")
            break
    return ("pass: " if "opened" in tried[0] else "FAIL (plain): ") + "; ".join(tried)


E9_SCREENS = ("a book page item (a Districts row, a page tab, a fish)", "a toon on toon selection",
              "a Make-a-Toon choice", "an Options row or tab", "a gag in the gag shop",
              "a gag in battle (its info card)", "a calendar event")


def e9_hovers(front, back) -> str:
    print("E9: a middle-button hover on each kind of screen. Set each up in the back window first; "
          "s skips one. You can quit the whole check with s at the 'Next' prompt.")
    found = []
    for n, what in enumerate(E9_SCREENS):
        try:
            x, y = point_at(back, what)
        except Skip:
            continue
        countdown()
        save(back, f"E9_{n}_before")
        hover(back, x, y)
        time.sleep(0.5)
        save(back, f"E9_{n}_middle")
        ok = ask("Did the hover show, with nothing else happening (no click, no camera move)?")
        if not ok:
            hover(back, x, y, button="right")
            time.sleep(0.5)
            save(back, f"E9_{n}_right")
            right = ask("Tried the right button: did that hover cleanly?")
            found.append(f"{what.split(' (')[0]}: middle FAIL, right {'pass' if right else 'FAIL'}")
        else:
            found.append(f"{what.split(' (')[0]}: pass")
    return "; ".join(found) or "skipped"


def e10_slider(front, back) -> str:
    print("E10: dragging a slider knob (Options volume). The knob is pressed, then moved in steps "
          "by middle presses with the left button flagged as held.")
    x0, y0 = point_at(back, "the slider knob")
    x1, y1 = point_at(back, "where the knob should end up")
    countdown()
    save(back, "E10_before")
    hover(back, x0, y0)
    time.sleep(0.05)
    left(back, x0, y0, True)
    for i in range(1, 11):
        x, y = x0 + (x1 - x0) * i // 10, y0 + (y1 - y0) * i // 10
        hover(back, x, y, holding_left=True)
        time.sleep(0.03)
    time.sleep(0.05)
    left(back, x1, y1, False)
    time.sleep(0.4)
    save(back, "E10_after")
    return "pass" if ask("Did the knob follow to the second spot (and stay there)?") else "FAIL"


def e11_clicks(front, back) -> str:
    print("E11: paced clicks on a cog target in battle and on a book page tab.")
    found = []
    for what in ("a cog to target (after picking a gag)", "a book page tab"):
        try:
            x, y = point_at(back, what)
        except Skip:
            continue
        countdown()
        paced_click(back, x, y)
        time.sleep(0.6)
        save(back, f"E11_{len(found)}")
        found.append(f"{what.split(' (')[0]}: {'pass' if ask('Did it work like a click?') else 'FAIL'}")
    return "; ".join(found) or "skipped"


def e12_pointer(front, back) -> str:
    print("E12: where TTR's own pointer shows in the back window after a posted hover.")
    x, y = point_at(back, "any spot (an empty bit of the world is fine)")
    countdown()
    hover(back, x, y)
    time.sleep(0.5)
    save(back, "E12")
    note = input("  Where does TTR's pointer show in the back window, and does it bother you? ").strip()
    return f"noted: {note or '(no answer)'}"


CHECKS = {"E1": e1_two_windows, "E2": e2_real_mouse, "E3": e3_frame_rate, "E4": e4_print_window,
          "E5": e5_hold, "E6": e6_wheel, "E7": e7_typing, "E8": e8_modifiers, "E9": e9_hovers,
          "E10": e10_slider, "E11": e11_clicks, "E12": e12_pointer}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("checks", nargs="*", help="which checks (E1 ... E12); none runs them all")
    args = parser.parse_args()
    wanted = [c.upper() for c in args.checks]
    unknown = [c for c in wanted if c not in CHECKS]
    if unknown:
        raise SystemExit(f"Unknown check(s): {', '.join(unknown)}. Choose from {', '.join(CHECKS)}.")
    make_dpi_aware()
    windows = find_ttr_windows()
    if len(windows) != 2:
        raise SystemExit(f"Open exactly two TTR windows ({len(windows)} found).")
    print("Click the front (keyboard-and-mouse) TTR window within 5 seconds...")
    time.sleep(5)
    front = _user32.GetForegroundWindow()
    if front not in windows:
        raise SystemExit("A TTR window wasn't in front. Run it again and click one.")
    back = next(w for w in windows if w != front)
    bl, bt, bw, bh = client_rect(back)
    print(f"Front: {front}. Back: {back} at {bl},{bt} ({bw}x{bh}). Come back to this console.\n")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, check in CHECKS.items():
        if wanted and name not in wanted:
            continue
        try:
            results[name] = check(front, back)
        except Skip:
            results[name] = "skipped"
        except Exception as e:  # one broken check shouldn't lose the rest
            results[name] = f"error: {e!r}"
        print(f"  -> {name}: {results[name]}\n")
    print("Summary (paste this back to Claude):")
    for name, result in results.items():
        print(f"{name}: {result}")


if __name__ == "__main__":
    main()
