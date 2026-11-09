"""M13, two toons: posted input, the chosen window, the overlay above it, and the module
window's switch and picker."""

import json
import os

import numpy as np
import pytest

from ttcontroller.output import (MK_LBUTTON, POSTED_STEPS, WM_KEYDOWN, WM_KEYUP, WM_LBUTTONDOWN, WM_LBUTTONUP,
                                 WM_MBUTTONDOWN, WM_MBUTTONUP, WM_MOUSEWHEEL, MouseClicker, PostedKeys, PostedMouse,
                                 key_lparam)
from ttcontroller.window import BoundTarget, TargetChoice, TTRView, describe_windows


class Posts(list):
    def __call__(self, hwnd, msg, wparam, lparam):
        self.append((msg, wparam, lparam))


def posted_clicker(posts):
    mouse = PostedMouse(1, post=posts, to_client=lambda x, y: (x - 100, y - 50))
    return MouseClicker(mouse.move, mouse.button, mouse.get_pos, mouse.wheel, steps=POSTED_STEPS, restores=False)


def run(clicker, posts, seconds=1.0):
    """Steps the clicker every 10 ms; returns when each message was first posted."""
    times = {}
    for i in range(round(seconds * 100)):
        before = len(posts)
        clicker.update(i * 0.01)
        for msg, _, _ in posts[before:]:
            times.setdefault(msg, i * 0.01)
    return times


def test_a_posted_hover_is_a_middle_press_in_client_pixels():
    posts = Posts()
    mouse = PostedMouse(1, post=posts, to_client=lambda x, y: (x - 100, y - 50))
    mouse.move(300, 250)
    assert [m for m, _, _ in posts] == [WM_MBUTTONDOWN, WM_MBUTTONUP]
    assert posts[0][2] == (200 << 16) | 200
    assert mouse.get_pos() == (300, 250)


def test_a_posted_click_is_paced_and_leaves_the_pointer_on_it():
    posts = Posts()
    clicker = posted_clicker(posts)
    clicker.click(400, 300)  # restore=True by default: nothing to put back when posted
    times = run(clicker, posts)
    assert times[WM_LBUTTONDOWN] - times[WM_MBUTTONDOWN] >= 0.05 - 1e-9
    assert times[WM_LBUTTONUP] - times[WM_LBUTTONDOWN] >= 0.08 - 1e-9
    assert [m for m, _, _ in posts] == [WM_MBUTTONDOWN, WM_MBUTTONUP, WM_LBUTTONDOWN, WM_LBUTTONUP]
    assert all(lp == (250 << 16) | 300 for _, _, lp in posts)
    assert not clicker.busy


def test_real_clicks_keep_their_quick_steps():
    moves = []
    clicker = MouseClicker(lambda x, y: moves.append(("move", x, y)), lambda d: moves.append(("button", d)),
                           lambda: (5, 5), lambda n: None)
    clicker.click(10, 20)
    for i in range(4):
        clicker.update(i * 0.03 + 1e-6)
    assert moves == [("move", 10, 20), ("button", True), ("button", False), ("move", 5, 5)]


def test_posted_keys_carry_scan_codes_and_release_flags():
    posts = Posts()
    keys_out = PostedKeys(1, post=posts)
    keys_out("w", True)
    keys_out("w", False)
    (down, vk, lp_down), (up, _, lp_up) = posts
    assert (down, up, vk) == (WM_KEYDOWN, WM_KEYUP, ord("W"))
    assert lp_down & 0xFF0000 and not lp_down >> 30 & 1
    assert lp_up >> 30 & 1 and lp_up >> 31 & 1


def test_extended_keys_say_so():
    assert key_lparam("arrow_up", True) >> 24 & 1
    assert not key_lparam("w", True) >> 24 & 1


def test_a_held_button_is_let_go_on_release():
    posts = Posts()
    clicker = posted_clicker(posts)
    clicker.hold(400, 300)
    run(clicker, posts, 0.3)
    assert posts[-1][0] == WM_LBUTTONDOWN and clicker.holding
    clicker.release()
    assert posts[-1][0] == WM_LBUTTONUP and not clicker.holding


def test_a_drag_keeps_the_left_button_flagged_while_it_moves():
    posts = Posts()
    clicker = posted_clicker(posts)
    clicker.drag(400, 300, 600, 300)
    run(clicker, posts)
    kinds = [m for m, _, _ in posts]
    down, up = kinds.index(WM_LBUTTONDOWN), kinds.index(WM_LBUTTONUP)
    moves = [(m, w) for m, w, _ in posts[down + 1:up] if m == WM_MBUTTONDOWN]
    assert len(moves) == 2 and all(w & MK_LBUTTON for _, w in moves)
    assert posts[up][2] == (250 << 16) | 500  # let go at the end, in client pixels


def test_the_wheel_is_posted_in_screen_pixels_one_notch_each():
    posts = Posts()
    clicker = posted_clicker(posts)
    clicker.scroll(400, 300, -3)
    run(clicker, posts)
    wheels = [(w, lp) for m, w, lp in posts if m == WM_MOUSEWHEEL]
    assert len(wheels) == 3
    assert all(w >> 16 == (-120) & 0xFFFF and lp == (300 << 16) | 400 for w, lp in wheels)


def test_nothing_is_posted_before_the_pointer_is_anywhere():
    posts = Posts()
    mouse = PostedMouse(1, post=posts, to_client=lambda x, y: (x, y))
    mouse.button(False)
    mouse.wheel(2)
    assert posts == []


def test_the_target_follows_the_window():
    state = {"window": True, "minimized": False, "covered": False}
    target = BoundTarget(5, is_window=lambda h: state["window"], is_minimized=lambda h: state["minimized"],
                         is_covered=lambda h: state["covered"])
    assert target.background
    target.update()
    assert target.state == "ok" and target.active
    state["covered"] = True
    target.update()
    assert target.state == "covered" and not target.active
    state["minimized"] = True
    target.update()
    assert target.state == "minimized"
    state["window"] = False
    target.update()
    assert target.state == "gone" and not target.active


def test_two_toons_with_nothing_picked_drives_nothing():
    target = BoundTarget(None, is_window=lambda h: True, is_minimized=lambda h: False, is_covered=lambda h: False)
    target.update()
    assert target.state == "unpicked" and not target.active
    assert TargetChoice(True, None).wanted == (True, None)
    assert TargetChoice(False, 7).wanted == (False, None)  # one toon ignores a leftover window


def test_windows_are_named_by_where_they_are():
    rects = {11: (1920, 23, 1920, 1009), 22: (0, 23, 1920, 1009)}
    assert describe_windows(rects, front=22) == {22: "Left (in front)", 11: "Right"}
    three = {1: (0, 0, 100, 100), 2: (200, 0, 100, 100), 3: (400, 0, 100, 100)}
    assert describe_windows(three)[3] == "3rd from the left"


def test_no_cursor_parking_in_the_background():
    assert TTRView(1, background=True).park_spot() is None


@pytest.mark.skipif(os.name != "nt", reason="Windows z-order")
def test_stack_above_a_window():
    from ttcontroller import overlay

    image = np.zeros((1, 1, 4), np.uint8)
    owner, a, b = overlay.Highlighter(), overlay.Highlighter(), overlay.Highlighter()
    try:
        owner.show_image(-32000, -32000, image, "owner")
        overlay._user32.SetWindowPos(owner.hwnd, overlay.HWND_NOTOPMOST, 0, 0, 0, 0,
                                     overlay.SWP_NOMOVE | overlay.SWP_NOSIZE | overlay.SWP_NOACTIVATE)
        for w in (a, b):
            w.attach(owner.hwnd)
            w.show_image(-32000, -32000, image, "hint", raise_it=False)
        overlay.stack([a, b], above=owner.hwnd)
        prev = lambda h: overlay._user32.GetWindow(h, overlay.GW_HWNDPREV)  # noqa: E731
        assert prev(owner.hwnd) == b.hwnd and prev(b.hwnd) == a.hwnd
        a.attach(None)
        assert a.owner is None
    finally:
        for w in (owner, a, b):
            w.close()


# ---- the module window ---------------------------------------------------------------------

@pytest.fixture
def qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PySide6.QtWidgets")
    return widgets.QApplication.instance() or widgets.QApplication([])


def test_the_picker_chooses_a_tile(qt):
    from ttcontroller.launcher import PickDialog

    dialog = PickDialog(windows=[(11, "Left (in front)"), (22, "Right")], thumb=lambda h: None)
    dialog.tiles[1].click()
    assert dialog.chosen == (22, "Right") and dialog.result() == dialog.DialogCode.Accepted


def test_the_picker_says_when_no_ttr_is_open(qt):
    from ttcontroller.launcher import PickDialog

    dialog = PickDialog(windows=[], thumb=lambda h: None)
    assert dialog.chosen is None and not hasattr(dialog, "tiles")


def test_the_two_toons_switch_asks_for_a_window_and_saves_the_mode(qt, tmp_path):
    from ttcontroller import launcher

    class FakePick:
        answer = (22, "Right")
        opened = 0

        def __init__(self, parent):
            FakePick.opened += 1
            self.chosen = FakePick.answer

        def exec(self):
            return self.chosen is not None

    path = tmp_path / "config.json"
    window = launcher.ModuleWindow(start=False, config_path=path, pick_dialog=FakePick)
    try:
        assert not window.choice.two_toons and window.pick_row.isHidden()
        window.two.toggle.click()
        assert window.choice.wanted == (True, 22) and FakePick.opened == 1
        assert json.loads(path.read_text(encoding="utf-8"))["two_toons"] is True
        assert "right" in window.picked.text()
        window._show_status("Pad", False, False, "gone")
        assert "closed" in window.picked.text() and window.headline.text() == "Controller toon's window closed"
        FakePick.answer = None  # cancelled: the old choice stays
        window.pick()
        assert window.choice.hwnd == 22
        window.two.toggle.click()
        assert window.choice.wanted == (False, None) and window.pick_row.isHidden()
        assert json.loads(path.read_text(encoding="utf-8"))["two_toons"] is False
    finally:
        window.close()


def test_the_module_window_follows_the_settings_window(qt, tmp_path):
    from ttcontroller import launcher

    class NoPick:
        def __init__(self, parent):
            self.chosen = None

        def exec(self):
            return False

    path = tmp_path / "config.json"
    window = launcher.ModuleWindow(start=False, config_path=path, pick_dialog=NoPick)
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        data["two_toons"] = True
        path.write_text(json.dumps(data), encoding="utf-8")
        window._config_mtime = -1  # as if the file changed since
        window._check_config()
        assert window.choice.wanted == (True, None) and window.two.toggle.isChecked()
        assert "not picked" in window.picked.text()
    finally:
        window.close()
