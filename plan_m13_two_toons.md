# M13: Two toons on one machine

Two Toontown Rewritten windows open at once. One is played with keyboard and mouse, in
front like any game. The other is played with the controller **in the background**: it
never takes focus, never moves the real cursor, and never hides it. Part of 1.0 (moved in
Nov 8, 2026, the user). Two controllers driving two toons stays after 1.0.

Status: done and tested in game (Nov 8, 2026); see plan.md's Progress entry. Phase 0 passed, but PrintWindow flashes TTR, so Phase 2 changed (see there). The user's answers: hints always on in the controller toon's window, the window always picked by the user, no console option. Findings so far are in plan.md under
"Two-toon findings" (Nov 5) and in `tools/background_input_test.py`, `_2.py` and
`background_battle_test.py`.

## How it works

Today the module drives TTR with real input. SendInput keys go to whichever window is in
front, the real cursor is the hover, and the screen is read by copying what's on the
monitor. None of that works for a window in the background, so two-toon mode swaps four
pieces and keeps everything else: every reader, mapper, hint and binding.

| Piece | Today (one toon) | Two-toon mode (controller toon) |
|---|---|---|
| Which window | the TTR window in front | a TTR window you pick, in front or not |
| Keys | SendInput (scan codes) | `PostMessage` WM_KEYDOWN/UP to that window |
| Mouse | real cursor: move, click, wheel | posted: hover = middle-button press/release; click = paced left down/up; wheel posted |
| Reading the screen | BitBlt from the screen | BitBlt from the screen too: PrintWindow flashes TTR (Nov 8), so the window must be uncovered; covered, it pauses |
| Overlay (hints, frame, golf aim) | topmost windows | owned by that TTR window, just above it, never over the other toon |
| Cursor hiding, mouse pause | on | off: the real cursor belongs to the keyboard-and-mouse toon |
| When it's active | while TTR is in front | while that window exists and isn't minimized |

One-toon mode stays exactly as it is today. The mode is chosen at start or from the
module's window, and the rest of the loop doesn't know which one it's in.

What we know works when posted to a background TTR (Nov 5):
- Key taps: 5 of 5.
- Held keys walk, with one key-down or with repeats.
- Clicks on simple buttons: 10 of 10 when paced (move, 50 ms, down, 80 ms, up), but only
  2 of 10 when instant.
- A middle or right button press moves TTR's pointer (hover) without clicking.
- A posted WM_MOUSEMOVE does nothing, however it's sent.
- In battle, a hover and then a paced click picked a gag.

## Phase 0: experiments (with the user, two TTR windows open)

The design above depends on these. Each one has a fallback, listed in Risks. Run them
first, write the results into plan.md's findings, and adjust the phases before building.

| # | Check | Pass when | If it fails |
|---|---|---|---|
| E1 | Two windows: the user types and walks in the front window while keys are posted to the back one | each toon only does its own input | stop: two-toon mode can't work |
| E2 | The real mouse moving over the back window | its hover doesn't follow the real mouse | the controller toon's hover jumps when the mouse passes over it; tell the user to keep the windows apart |
| E3 | The back window keeps drawing (frames per second, read from a spinning or moving thing) | 20+ fps | longer settle times in two-toon mode |
| E4 | `PrintWindow(PW_RENDERFULLCONTENT)` of the back window while the front one covers half of it | the covered half reads right; time under 25 ms at 1920x1009 | Windows.Graphics.Capture, else the windows must not overlap (the module warns) |
| E5 | Held left button: the book's scroll triangles (held_scroll) and kart turning | scrolls fast and turns while held, stops on release | click repeatedly instead of holding |
| E6 | Posted mouse wheel (WM_MOUSEWHEEL) on the Options keybind list and the SOS cards | scrolls one notch per message | click the scroll triangles instead |
| E7 | Typing: letters posted as WM_KEYDOWN/UP into Make-a-Toon's name box and the "delete" box | each letter appears once, in the right case | post WM_CHAR instead |
| E8 | Shift-Escape (TTR Options) and other modifier keys | Options opens | post WM_SYSKEYDOWN, or a shift state flag |
| E9 | The middle-button hover everywhere a hover is used: book pages, toon selection, Make-a-Toon, Options, the shop, gag info cards, the calendar | the hover shows and nothing else happens | a right-button hover where the middle one misbehaves |
| E10 | Dragging a slider (Options volume) | the knob follows | Options sliders use the D-pad steps only in two-toon mode |
| E11 | Picking a cog target in battle, and the book's page tabs | works like a click | longer pacing |
| E12 | Where TTR's custom cursor shows in the back window after a posted hover | noted, for the user to judge | park the pointer in a corner when idle |

The experiment script, `tools/two_toon_check.py`, reuses round two's helpers. Each check
says what to set up, posts the input, and then either reads the pixels to judge the result
or asks the user y/n. Results go to `captures/two_toon_check/` (screenshots, local only)
and a summary is printed at the end.

```python
"""M13 phase 0: what a background TTR window takes, checked one at a time.

Usage: python tools/two_toon_check.py [E1 E4 ...]   (no arguments runs them all)

Set up: two TTR windows logged in, side by side. Click the one you'll play with keyboard
and mouse; the other is the "back" window the checks post to.
"""

import argparse
import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from background_input_test import WM_KEYDOWN, WM_KEYUP, key_lparam, post_click, post_key
from ttcontroller import keys
from ttcontroller.window import TTRView, client_rect, find_ttr_windows, make_dpi_aware

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_gdi32 = ctypes.WinDLL("gdi32")
WM_MBUTTONDOWN, WM_MBUTTONUP, WM_LBUTTONDOWN, WM_LBUTTONUP = 0x0207, 0x0208, 0x0201, 0x0202
WM_MOUSEWHEEL, WM_CHAR = 0x020A, 0x0102
MK_LBUTTON, MK_MBUTTON = 0x0001, 0x0010
PW_CLIENTONLY, PW_RENDERFULLCONTENT = 0x1, 0x2
OUT = Path("captures/two_toon_check")
results: dict[str, str] = {}


def where(x: int, y: int) -> int:
    return (y << 16) | (x & 0xFFFF)


def hover(hwnd, x: int, y: int) -> None:
    _user32.PostMessageW(hwnd, WM_MBUTTONDOWN, MK_MBUTTON, where(x, y))
    _user32.PostMessageW(hwnd, WM_MBUTTONUP, 0, where(x, y))


def ask(question: str) -> bool:
    return input(f"  {question} [y/n] ").strip().lower().startswith("y")


def print_window(hwnd):
    """The client area through PrintWindow: (seconds, Frame-like bytes) or None."""
    _, _, w, h = client_rect(hwnd)
    hdc = _user32.GetDC(hwnd)
    mem = _gdi32.CreateCompatibleDC(hdc)
    bmp = _gdi32.CreateCompatibleBitmap(hdc, w, h)
    _gdi32.SelectObject(mem, bmp)
    start = time.perf_counter()
    ok = _user32.PrintWindow(hwnd, mem, PW_CLIENTONLY | PW_RENDERFULLCONTENT)
    took = time.perf_counter() - start
    # ... GetDIBits into a buffer as screen.grab does, save a PNG to OUT, clean up ...
    return took if ok else None


def e1_two_windows(front, back) -> None:
    print("E1: keep playing in the front window (walk, type in chat) for 10 seconds.")
    input("  Press Enter, then click the front window and play...")
    vk = keys.vk_code("w")
    end = time.monotonic() + 10
    while time.monotonic() < end:  # walk the back toon in bursts meanwhile
        _user32.PostMessageW(back, WM_KEYDOWN, vk, key_lparam(vk, False))
        time.sleep(1.0)
        _user32.PostMessageW(back, WM_KEYUP, vk, key_lparam(vk, True))
        time.sleep(1.0)
    results["E1"] = "pass" if ask("Did each toon only do its own thing?") else "FAIL"


def e4_print_window(front, back) -> None:
    print("E4: drag the front window so it covers about half of the back one.")
    input("  Press Enter when it does...")
    times = [print_window(back) for _ in range(10)]
    ok = all(t is not None for t in times)
    results["E4"] = (f"{'pass' if ok else 'FAIL'}: {1000 * sum(t or 0 for t in times) / 10:.1f} ms average; "
                     f"check {OUT} shows the covered half")

# e2 ... e12 follow the same pattern: set up, post, read pixels or ask, record.


def main() -> None:
    make_dpi_aware()
    parser = argparse.ArgumentParser()
    parser.add_argument("checks", nargs="*")
    args = parser.parse_args()
    windows = find_ttr_windows()
    if len(windows) != 2:
        raise SystemExit(f"Open exactly two TTR windows ({len(windows)} found).")
    input("Click the front (keyboard-and-mouse) window, then come back here and press Enter... ")
    # The front one is the one that was in front most recently: ask the user to confirm.
    ...
    OUT.mkdir(parents=True, exist_ok=True)
    for name, check in CHECKS.items():
        if not args.checks or name in args.checks:
            check(front, back)
    for name, result in results.items():
        print(f"{name}: {result}")
```

## Phase 1: a posted output

`output.py` already lets `MouseClicker` and `KeyboardOutput` take their move, button,
wheel, position and send functions. So a posted output is two small classes beside the
real ones, plus one pacing setting.

```python
# output.py

WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP, WM_CHAR = 0x0100, 0x0101, 0x0104, 0x0105, 0x0102
WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MOUSEWHEEL = 0x0201, 0x0202, 0x0207, 0x0208, 0x020A
MK_LBUTTON, MK_MBUTTON = 0x0001, 0x0010
_user32.PostMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
_user32.ScreenToClient.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.POINT))


def _key_lparam(name: str, down: bool) -> int:
    scan = _user32.MapVirtualKeyW(keys.vk_code(name), MAPVK_VK_TO_VSC)
    value = 1 | (scan << 16)
    if keys.is_extended(name):
        value |= 1 << 24
    if not down:
        value |= (1 << 30) | (1 << 31)
    return value


class PostedKeys:
    """Keys for one window, posted: the same (name, down) calls as send_key."""

    def __init__(self, hwnd, post=_user32.PostMessageW):
        self.hwnd, self._post = hwnd, post

    def __call__(self, name: str, down: bool) -> None:
        self._post(self.hwnd, WM_KEYDOWN if down else WM_KEYUP, keys.vk_code(name), _key_lparam(name, down))

    def type(self, text: str) -> None:
        # E7 decides: keydown/up per letter (as now), or WM_CHAR.
        for letter in text:
            self(letter, True)
            self(letter, False)


class PostedMouse:
    """MouseClicker's move/button/wheel/get_pos for one window, posted. Points come in
    screen pixels, as the module already works in them, and are posted in the window's
    client pixels. TTR ignores a posted move, so a move is a middle-button press and
    release there, which moves TTR's pointer without clicking (Nov 5 findings)."""

    def __init__(self, hwnd, post=_user32.PostMessageW, to_client=None):
        self.hwnd, self._post = hwnd, post
        self._to_client = to_client or self._screen_to_client
        self._at: tuple[int, int] | None = None  # screen point last hovered
        self._down = False

    def _screen_to_client(self, x: int, y: int) -> tuple[int, int]:
        point = wintypes.POINT(x, y)
        _user32.ScreenToClient(self.hwnd, ctypes.byref(point))
        return point.x, point.y

    def _lparam(self) -> int:
        x, y = self._to_client(*self._at)
        return ((y & 0xFFFF) << 16) | (x & 0xFFFF)

    def move(self, x: int, y: int) -> None:
        if (x, y) == self._at:
            return  # a click's "put it back" step: nothing to do
        self._at = (x, y)
        held = MK_LBUTTON if self._down else 0
        self._post(self.hwnd, WM_MBUTTONDOWN, MK_MBUTTON | held, self._lparam())
        self._post(self.hwnd, WM_MBUTTONUP, held, self._lparam())

    def button(self, down: bool) -> None:
        if self._at is None:
            return
        self._down = down
        self._post(self.hwnd, WM_LBUTTONDOWN if down else WM_LBUTTONUP, MK_LBUTTON if down else 0, self._lparam())

    def wheel(self, notches: int) -> None:
        if self._at is None:
            return
        x, y = self._at  # WM_MOUSEWHEEL takes screen coordinates
        delta = WHEEL_DELTA if notches > 0 else -WHEEL_DELTA
        for _ in range(abs(notches)):
            self._post(self.hwnd, WM_MOUSEWHEEL, (delta & 0xFFFF) << 16, ((y & 0xFFFF) << 16) | (x & 0xFFFF))

    def get_pos(self) -> tuple[int, int]:
        return self._at or (0, 0)
```

`MouseClicker` gains per-step pacing, because posted clicks need the slower findings
pacing:

```python
class MouseClicker:
    def __init__(self, move=move_mouse, button=left_button, get_pos=cursor_pos, wheel=wheel,
                 steps: tuple[float, float, float] = (0.03, 0.03, 0.03)):
        # Seconds after the move, after the press, after the release. Posted clicks need
        # (0.05, 0.08, 0.03): TTR misses instant ones (Nov 5 findings).
        self._steps = steps
        ...
    # update(): `self._next_at = now + self._steps[min(self._step, 2)]` in place of STEP_SECONDS


def posted_output(hwnd) -> tuple[KeyboardOutput, MouseClicker, PostedKeys]:
    keys_out = PostedKeys(hwnd)
    mouse = PostedMouse(hwnd)
    return (KeyboardOutput(keys_out),
            MouseClicker(mouse.move, mouse.button, mouse.get_pos, mouse.wheel, steps=(0.05, 0.08, 0.03)),
            keys_out)
```

`output.release_all()` and `clicker.release()` work as they do now: the posted ones post
the key-up and button-up messages.

## Phase 2: reading a window that isn't in front

**Changed Nov 8:** PrintWindow makes TTR flash (tools/flash_check.py), with or without full content. The screen copy doesn't, so the module keeps BitBlt and `BoundTarget` reports "covered" when another window is over the controller toon's (sampled with WindowFromPoint); the toon pauses until it's uncovered. The code below is kept for the record; `grab_window` stays in screen.py for the tools only.

`TTRView` takes a capture function, and `screen.py` gains a window capture.

```python
# screen.py
PW_CLIENTONLY, PW_RENDERFULLCONTENT = 0x1, 0x2


def grab_window(hwnd, width: int, height: int) -> Frame | None:
    """Copy one window's client area even while other windows cover it (DWM keeps its
    picture). None if Windows couldn't (then the caller falls back to grab())."""
    window_dc = _user32.GetDC(hwnd)
    mem_dc = _gdi32.CreateCompatibleDC(window_dc)
    bitmap = _gdi32.CreateCompatibleBitmap(window_dc, width, height)
    try:
        _gdi32.SelectObject(mem_dc, bitmap)
        if not _user32.PrintWindow(hwnd, mem_dc, PW_CLIENTONLY | PW_RENDERFULLCONTENT):
            return None
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        buffer = ctypes.create_string_buffer(width * height * 4)
        _gdi32.GetDIBits(mem_dc, bitmap, 0, height, buffer, ctypes.byref(header), 0)
    finally:
        _gdi32.DeleteObject(bitmap)
        _gdi32.DeleteDC(mem_dc)
        _user32.ReleaseDC(hwnd, window_dc)
    return Frame(width, height, buffer.raw)


# window.py
class TTRView:
    def __init__(self, hwnd, background: bool = False):
        self.hwnd, self.background = hwnd, background

    def snapshot(self) -> Frame:
        left, top, width, height = client_rect(self.hwnd)
        if self.background:
            frame = grab_window(self.hwnd, width, height)
            if frame is not None:
                return frame
        return grab(left, top, width, height)

    def park_spot(self):
        if self.background:
            return None  # no real cursor to park (E12 may choose a corner hover instead)
        ...
```

E4 decides whether PrintWindow is good enough. If it's too slow or comes back black, the
fallback is Windows.Graphics.Capture, through the `windows-capture` package, which is
another dependency. If that fails too, two-toon mode needs the back window uncovered.
`Target` then reports "covered" by comparing window rectangles, and the module window says
so.

## Phase 3: which window the controller drives

A target replaces `ForegroundWatcher` in the loop. The one-toon target is today's
behavior, wrapped. The two-toon target is bound to one window handle.

```python
# window.py
_user32.IsWindow.argtypes = (wintypes.HWND,)
_user32.IsIconic.argtypes = (wintypes.HWND,)


class ForegroundTarget:
    """One toon (today): the TTR window in front, real input."""
    background = False

    def __init__(self):
        self._watch = ForegroundWatcher()
        self.hwnd = None
        self.path: Path | None = None

    def update(self) -> None:
        self.path = self._watch.ttr_foreground()
        self.hwnd = self._watch.ttr_hwnd

    @property
    def active(self) -> bool:
        return self.hwnd is not None

    def state(self) -> str:
        return "ok" if self.active else "not_front"


class BoundTarget:
    """Two toons: one chosen TTR window, front or back, posted input."""
    background = True

    def __init__(self, hwnd):
        self.hwnd = hwnd
        self.path = _process_path(hwnd)
        self._state = "ok"

    def update(self) -> None:
        if not _user32.IsWindow(self.hwnd):
            self._state = "gone"
        elif _user32.IsIconic(self.hwnd):
            self._state = "minimized"  # TTR doesn't draw while minimized
        else:
            self._state = "ok"

    @property
    def active(self) -> bool:
        return self._state == "ok"

    def state(self) -> str:
        return self._state


def ttr_windows() -> list[tuple[int, int, str]]:
    """(hwnd, process id, a label) for every TTR window, for the picker: "TTR 1 (left)"."""
```

The module window sets the choice, and the loop reads it each frame. The choice is a
small thread-safe holder, since the loop runs on its own thread:

```python
# app.py
@dataclass
class TargetChoice:
    """What the module window asks for: None = one toon (the TTR in front), else the
    window handle the controller drives. The loop swaps its target and output when it
    changes, after letting go of every key and button on the old one."""
    hwnd: int | None = None
```

How a window gets picked (the module window, Phase 6):
- Turning on "Two toons" with exactly two TTR windows open picks the one that **isn't** in
  front. That's right in the usual case, where you're playing the other toon with the
  mouse.
- **Pick…** lists the TTR windows, each with a small thumbnail (from `grab_window`) and its
  position ("left", "right"). **Identify** flashes the gold frame around the chosen window
  for a second.
- The choice lasts while that window is open. When it closes, the status says "Controller
  toon's window closed" and the module waits. Window handles change every launch, so
  nothing is saved to config.json apart from the mode.
- On the console: `ttcontroller --two-toons` picks the window not in front when it starts.

## Phase 4: the loop

The changes in `app.run` are mostly a few names swapped. The readers, mappers and hints
don't change.

```python
def run(..., stop=None, on_status=None, choice: TargetChoice | None = None):
    target = ForegroundTarget()
    output, clicker, send = KeyboardOutput(send_key), MouseClicker(), send_key
    bound_to = None
    ...
    while not stop.is_set():
        wanted = choice.hwnd if choice is not None else None
        if wanted != bound_to:
            output.release_all()
            clicker.release()
            hider.show()
            bound_to = wanted
            if wanted is None:
                target = ForegroundTarget()
                output, clicker, send = KeyboardOutput(send_key), MouseClicker(), send_key
            else:
                target = BoundTarget(wanted)
                output, clicker, posted = posted_output(wanted)
                send = posted
            log(f"Controller drives: {'the TTR window in front' if wanted is None else f'TTR window {wanted}'}")
        target.update()
        focused = dry_run or target.active  # was: ttr_path is not None
        ttr_path = target.path
        ...
        view = TTRView(target.hwnd, background=target.background) if target.hwnd else None
        ...
        # The cursor and the mouse pause belong to the keyboard-and-mouse toon in two-toon mode:
        if not target.background:
            mouse_moved = hider.update(...)            # unchanged
            if active and (mouse_moved or ...):
                mouse_paused = True
        # Hints and the frame were gated on hider.hidden ("the controller is in use");
        # in two-toon mode the controller window is the controller's, so they always show:
        presenting = hider.hidden or target.background
```

Every `foreground.ttr_hwnd` becomes `target.hwnd`. Every `hider.hidden` gate on drawing
becomes `presenting`. `point(kind="type")` calls `send(letter, …)` instead of `send_key`.
The idle park is skipped when `view.park_spot()` is None. `on_status` gains the target's
state: "minimized", "gone" and "covered".

`hide_cursor` writes TTR's settings.json, which both toons share. In two-toon mode the
module never moves the real cursor, so it doesn't need TTR's cursor off. It leaves
`hide_cursor` alone, and the settings window says the setting affects both toons.

## Phase 5: the overlay stays with its window

The hint windows, the frame and the golf aim are topmost today, and they'd float over the
keyboard-and-mouse toon. In two-toon mode they become windows **owned** by the controller
toon's TTR window. Windows keeps owned windows above their owner, and `stack` puts them
directly above it instead of above everything.

```python
# overlay.py
GWLP_HWNDPARENT = -8
HWND_NOTOPMOST, HWND_TOP = -2, 0
GW_HWNDPREV = 3


class Highlighter:
    def attach(self, owner) -> None:
        """Owned by a TTR window (two toons) or by nothing (topmost, one toon)."""
        if owner == self.owner:
            return
        self.owner = owner
        _user32.SetWindowLongPtrW(self.hwnd, GWLP_HWNDPARENT, owner or 0)
        _user32.SetWindowPos(self.hwnd, HWND_TOPMOST if owner is None else HWND_NOTOPMOST,
                             0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def stack(windows: list, above=None) -> None:
    """Above everything (above=None), or directly above the window `above`: each one is
    put just under whatever sits above that window, so nothing else is covered."""
    windows = [w for w in windows if w.visible and w.hwnd]
    if not windows:
        return
    if above is None:
        after = HWND_TOPMOST
    else:
        ours = {w.hwnd for w in windows}
        after = _user32.GetWindow(above, GW_HWNDPREV)
        while after and after in ours:
            after = _user32.GetWindow(after, GW_HWNDPREV)
        after = after or HWND_TOP
    batch = _user32.BeginDeferWindowPos(len(windows))
    for w in windows:
        if batch:
            batch = _user32.DeferWindowPos(batch, w.hwnd, after, 0, 0, 0, 0,
                                           SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
        after = w.hwnd
    if batch:
        _user32.EndDeferWindowPos(batch)
```

The app calls `window.attach(target.hwnd if target.background else None)` on every
overlay window when the target changes, and passes `above=target.hwnd` to `stack` in
two-toon mode. The highlighter and aimer are stacked the same way there, so the order is
one rule.

The overlay windows are already left out of screen captures, so they never confuse the
readers. They're also left out of PrintWindow, which only draws TTR's own window.

## Phase 6: the module window, settings and config

- **config.json:** `two_toons: false`. Only the mode is saved; the window is picked each
  session. It gets a HELP entry and parse validation as usual, and the settings window
  gets a switch on General, under Controller.
- **The module window (`launcher.py`):**
  - A "Two toons" switch.
  - Under it: "Controller toon: TTR window (left)", with **Pick…** and **Identify**.
  - Status lines for the new states:
    - "Controller toon's window is minimized"
    - "…closed: pick another"
    - "…is covered: move the windows apart", only when the capture fallback needs it
  - It writes the choice into the `TargetChoice` it shares with the loop.
- **Pick dialog:** one tile per TTR window, each with a thumbnail and its position. Click a
  tile to choose it.
- **README:** a "Two toons" section: set up two windows, turn on Two toons, pick the
  window, what to expect (the hover shows as TTR's pointer in that window, the windows
  can overlap if E4 passes). It also gets a controls row and the shared hide_cursor note.
- **plan.md:** a Progress entry for M13 ("built, not yet tested in game"), with the
  experiment results in the findings.

## Phase 7: tests (unit, no game)

```python
# tests/test_two_toons.py
from ttcontroller.output import (WM_KEYDOWN, WM_KEYUP, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_MBUTTONDOWN,
                                 WM_MBUTTONUP, MouseClicker, PostedKeys, PostedMouse)


class Posts(list):
    def __call__(self, hwnd, msg, wparam, lparam):
        self.append((msg, wparam, lparam))
        return True


def test_a_posted_hover_is_a_middle_press_in_client_pixels():
    posts = Posts()
    mouse = PostedMouse(1, post=posts, to_client=lambda x, y: (x - 100, y - 50))
    mouse.move(300, 250)
    assert [m for m, _, _ in posts] == [WM_MBUTTONDOWN, WM_MBUTTONUP]
    assert posts[0][2] == (200 << 16) | 200
    mouse.move(300, 250)  # the same spot again (a click's restore step) posts nothing
    assert len(posts) == 2


def test_a_posted_click_is_paced():
    posts = Posts()
    mouse = PostedMouse(1, post=posts, to_client=lambda x, y: (x, y))
    clicker = MouseClicker(mouse.move, mouse.button, mouse.get_pos, mouse.wheel, steps=(0.05, 0.08, 0.03))
    clicker.click(10, 20)
    times = {}
    for t in [i * 0.01 for i in range(40)]:
        before = len(posts)
        clicker.update(t)
        for msg, _, _ in posts[before:]:
            times.setdefault(msg, t)
    assert times[WM_LBUTTONDOWN] - times[WM_MBUTTONDOWN] >= 0.05
    assert times[WM_LBUTTONUP] - times[WM_LBUTTONDOWN] >= 0.08


def test_posted_keys_carry_scan_codes_and_release_flags():
    posts = Posts()
    keys_out = PostedKeys(1, post=posts)
    keys_out("w", True)
    keys_out("w", False)
    (down, vk, lp_down), (up, _, lp_up) = posts
    assert (down, up) == (WM_KEYDOWN, WM_KEYUP)
    assert lp_down & 0xFF0000 and not lp_down >> 30 & 1 and lp_up >> 30 & 1 and lp_up >> 31 & 1


def test_a_held_button_is_let_go_on_release():
    ...  # clicker.hold, then release(): ends with WM_LBUTTONUP


def test_the_target_follows_the_window():
    ...  # BoundTarget with IsWindow/IsIconic patched: ok, minimized, gone


def test_the_loop_swaps_output_when_the_choice_changes():
    ...  # app.run with a fake reader and patched targets: keys released on the old one first


def test_stack_above_a_window():
    ...  # real hidden windows, as in the z-order check on Nov 8: ours sit right above `above`
```

The launcher test gets cases for the Two toons switch, the picker, and the new status
lines. Every test must pass before the work is handed back, as always.

## Phase 8: in game (the user)

Run everything in two-toon mode, with the keyboard-and-mouse toon in front and played at
the same time:

1. Walking, jumping, sprint and camera, while the other toon walks too.
2. A battle: gags, targets, teammates, SOS cards, run.
3. The gag shop, NPC chat and tasks, SpeedChat, the friends list, Unite.
4. The shticker book: every page, including held scrolling, the calendar and the fishing
   bucket.
5. Start-up, toon selection, Make-a-Toon (typing a name) and the delete confirm.
6. TTR's Options: tabs, toggles, dropdowns, sliders (E10) and keybind lists.
7. Gardening, the mailbox, Clarabelle and the Silly Meter, boarding groups and elevators.
8. Boss rounds the user can reach: CFO cranes, CEO golf, the CJ's cannons.
9. Hints and the frame: they stay with the controller window, hide behind the
   keyboard-and-mouse window when it's dragged over, and move when the window moves.
10. Switching Two toons off and on mid-game, closing the controller window, minimizing it.

Readers that misread a background window get the usual fix: a capture from
`tools/capture_ttr.py` (which gets a `--window` option to grab the back window) and a
fixture.

## Risks and fallbacks

- **Real input leaking between windows (E1):** this is the only thing that would sink the
  milestone. Round two's "two windows" check passed for the friends list, so it's unlikely.
- **TTR throttling a background window (E3):** settle times (`_click`'s 0.25 s, the
  calendar's 0.15 s) are scaled by a `slow` factor in two-toon mode.
- **Holds, the wheel, drags (E5, E6, E10):** each has a click-only fallback, kept to
  those few spots.
- **Middle-button side effects (E9):** the right button hovers too (Nov 5); either can be
  used per screen.
- **The real cursor over the back window (E2):** if its hover follows the real mouse, the
  README says to keep the mouse off it; nothing in code can stop that.
- **Window capture (E4):** PrintWindow, then Windows.Graphics.Capture, then "keep it
  uncovered".

## Questions for the user before Phase 1

1. **Hints in the back window:** always on while two-toon mode is on, or only while the
   controller was used recently, like now?
2. **Picking the window:** is "the one not in front when you switch Two toons on" a good
   default, or should it always ask?
3. **The console:** should `ttcontroller --two-toons` exist, or is the module window enough?

## Order of work

Phase 0 (with the user), then Phases 1 to 3 together (each with unit tests), then 4 and
5, then 6. Then the user's in-game pass (Phase 8), fixes as found, docs, and the
"M13: Two toons" commit when the user says so.
