from ttcontroller import ui
from ttcontroller.controller import ControllerState
from ttcontroller.mapper import OverworldMapper

FORWARD = (0.0, -1.0)


class FakeScreen:
    def __init__(self, *visible):
        self.visible = set(visible)

    def is_visible(self, button):
        return button in self.visible

    def read(self, reader):
        return None  # nothing found: no mail, no leave button


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


def test_b_ends_a_whisper_after_speedchat_and_before_the_friends_list():
    whisper = (ui.WHISPER_CLOSE, ui.WHISPER_BAR)
    m = OverworldMapper()
    m.update(state("b"), 0.0, FakeScreen(ui.SPEEDCHAT_MENU, *whisper))
    assert m.take_clicks() == [ui.SPEEDCHAT]
    m.update(state(), 0.1)
    m.update(state("b"), 0.2, FakeScreen(*whisper, ui.FRIENDS_CLOSE))
    assert m.take_clicks() == [ui.WHISPER_CLOSE]


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


def test_sprint_button_toggles_auto_sprint():
    m = OverworldMapper()
    assert not m.auto_sprint
    run_frames(m, [(state("ls"), 1), (state(), 1)])
    assert m.auto_sprint and m.take_sprint_toggle() and not m.take_sprint_toggle()
    run_frames(m, [(state("ls"), 1), (state(), 1)], start=1.0)
    assert not m.auto_sprint


def test_auto_sprint_double_taps_each_time_a_run_starts():
    m = OverworldMapper(auto_sprint=True)
    frames = run_frames(m, [(state(left=FORWARD), 40), (state(), 10), (state(left=FORWARD), 40)])
    forward = ["forward" in f for f in frames]
    assert presses(forward[:40]) == 2 and forward[39]  # the first run
    assert presses(forward[50:]) == 2 and forward[-1]  # and the next


def test_auto_sprint_skips_walking_but_sprints_when_walking_turns_into_a_run():
    m = OverworldMapper(auto_sprint=True)
    walk = (0.0, -0.5)  # past the deadzone, under the walk threshold
    frames = run_frames(m, [(state(left=walk), 30), (state(left=FORWARD), 40)])
    forward = ["forward" in f for f in frames]
    assert presses(forward[:30]) == 1  # just walking
    assert presses(forward[30:]) == 2 and forward[-1]


def test_auto_sprint_off_just_runs():
    m = OverworldMapper()
    frames = run_frames(m, [(state(left=FORWARD), 40)])
    assert all("forward" in f for f in frames)


def test_turning_auto_sprint_on_mid_run_sprints_right_away():
    m = OverworldMapper()
    frames = run_frames(m, [(state(left=FORWARD), 30), (state("ls", left=FORWARD), 1), (state(left=FORWARD), 30)])
    forward = ["forward" in f for f in frames[30:]]
    assert presses(forward) == 2 and forward[-1]


def test_left_trigger_is_the_unite_hotkey():
    m = OverworldMapper()
    pulled = ControllerState(left_trigger=0.9)
    m.update(pulled, 0.0, FakeScreen())
    m.update(ControllerState(), 0.05, FakeScreen())
    assert m.take_unite()
    assert m.take_clicks() == [ui.SPEEDCHAT]  # opens speedchat first
    assert not m.take_unite()
    # With speedchat already open, it just goes to UNITE!.
    m.update(pulled, 1.0, FakeScreen(ui.SPEEDCHAT_MENU))
    m.update(ControllerState(), 1.05, FakeScreen(ui.SPEEDCHAT_MENU))
    assert m.take_unite()
    assert m.take_clicks() == []


def test_map_tasks_and_gags_are_held_by_default():
    m = OverworldMapper()
    assert "showMap" in m.update(state("dpad_up"), 0.0)
    assert "showMap" not in m.update(state(), 0.1)


def test_toggle_hud_shows_on_one_press_and_hides_on_the_next():
    m = OverworldMapper(toggle_show=True)
    for button, control in (("dpad_up", "showMap"), ("x", "showTasks"), ("y", "showGags")):
        assert control in m.update(state(button), 0.0)
        assert control in m.update(state(), 0.1)  # let go: still shown
        assert control in m.update(state(), 5.0)
        assert control not in m.update(state(button), 5.1)  # pressed again: hidden
        assert control not in m.update(state(), 5.2)


def test_toggle_doesnt_change_other_held_controls():
    m = OverworldMapper(toggle_show=True)
    assert "jump" in m.update(state("a"), 0.0)
    assert "jump" not in m.update(state(), 0.1)


def test_a_toggled_control_goes_when_another_mode_takes_its_button():
    m = OverworldMapper(toggle_show=True)
    m.update(state("y"), 0.0)
    assert "showGags" in m.update(state(), 0.1)
    assert "showGags" not in m.update(state(), 0.2, blocked=frozenset({"y"}))  # a battle starts
    assert "showGags" not in m.update(state(), 0.3)
