from ttcontroller import ui
from ttcontroller.controller import ControllerState
from ttcontroller.mapper import OverworldMapper

FORWARD = (0.0, -1.0)


class FakeScreen:
    def __init__(self, *visible):
        self.visible = set(visible)

    def is_visible(self, button):
        return button in self.visible


def state(*buttons, left=(0.0, 0.0), right=(0.0, 0.0)):
    return ControllerState(buttons=frozenset(buttons), left_stick=left, right_stick=right)


def run_frames(mapper, frames, start=0.0, step=0.01):
    """Feed (state, count) pairs at a fixed frame rate; return the controls per frame."""
    out, t = [], start
    for s, count in frames:
        for _ in range(count):
            out.append(mapper.update(s, t))
            t += step
    return out


def test_hold_binding_and_movement():
    m = OverworldMapper()
    assert m.update(state("a", left=FORWARD), 0.0) == {"jump", "forward"}
    assert m.update(state(), 0.01) == set()


def test_right_stick_looks():
    m = OverworldMapper()
    assert m.update(state(right=(0.0, -1.0)), 0.0) == {"lookUp"}


def test_rb_opens_friends_list_when_closed():
    m = OverworldMapper()
    assert "friendsList" in m.update(state("rb"), 0.0, FakeScreen())
    assert m.take_clicks() == []


def test_rb_clicks_close_when_friends_list_open():
    m = OverworldMapper()
    assert "friendsList" not in m.update(state("rb"), 0.0, FakeScreen(ui.FRIENDS_CLOSE))
    assert m.take_clicks() == [ui.FRIENDS_CLOSE]
    assert m.take_clicks() == []


def test_b_closes_friends_list_only_when_open():
    m = OverworldMapper()
    m.update(state("b"), 0.0, FakeScreen())
    assert m.take_clicks() == []
    m.update(state(), 0.01, FakeScreen())
    m.update(state("b"), 0.02, FakeScreen(ui.FRIENDS_CLOSE))
    assert m.take_clicks() == [ui.FRIENDS_CLOSE]


def test_view_clicks_speedchat_button():
    m = OverworldMapper()
    m.update(state("view"), 0.0, FakeScreen())
    assert m.take_clicks() == [ui.SPEEDCHAT]


def test_b_closes_speedchat_before_friends_list():
    m = OverworldMapper()
    m.update(state("b"), 0.0, FakeScreen(ui.SPEEDCHAT_MENU, ui.FRIENDS_CLOSE))
    assert m.take_clicks() == [ui.SPEEDCHAT]


def test_holding_rb_clicks_once():
    m = OverworldMapper()
    screen = FakeScreen(ui.FRIENDS_CLOSE)
    run = [m.update(state("rb"), t / 100, screen) for t in range(10)]
    assert run and m.take_clicks() == [ui.FRIENDS_CLOSE]


def test_start_tap_opens_sticker_book_on_release():
    m = OverworldMapper()
    frames = run_frames(m, [(state("start"), 10), (state(), 20)])
    assert not any("stickerBook" in f for f in frames[:10])
    assert "stickerBook" in frames[10]
    assert "stickerBook" not in frames[-1]
    assert not any("options" in f for f in frames)


def test_start_hold_opens_options_only():
    m = OverworldMapper()
    frames = run_frames(m, [(state("start"), 60), (state(), 20)])
    assert any("options" in f for f in frames)
    assert not any("stickerBook" in f for f in frames)


def presses(flags):
    """Count how many times forward goes from released to held."""
    return sum(1 for prev, cur in zip([False, *flags], flags) if cur and not prev)


def test_sprint_while_running_sends_fresh_double_tap():
    m = OverworldMapper()
    frames = run_frames(m, [(state(left=FORWARD), 50), (state("l3", left=FORWARD), 1), (state(left=FORWARD), 40)])
    forward = ["forward" in f for f in frames[50:]]
    assert not forward[0]  # released first, so the old long press doesn't count
    assert presses(forward) == 2
    assert forward[-1]


def test_sprint_armed_while_standing_then_push():
    m = OverworldMapper()
    frames = run_frames(m, [(state("l3"), 1), (state(), 20), (state(left=FORWARD), 40)])
    forward = ["forward" in f for f in frames[21:]]
    assert presses(forward) == 2 and forward[-1]


def test_sprint_arm_expires():
    m = OverworldMapper()
    frames = run_frames(m, [(state("l3"), 1), (state(), 150), (state(left=FORWARD), 30)])
    assert all("forward" in f for f in frames[151:])
