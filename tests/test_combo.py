from ttcontroller.combo import ButtonCombo
from ttcontroller.controller import ControllerState


def press(*buttons):
    return ControllerState(buttons=frozenset(buttons))


def test_both_bumpers_together_are_held_back_and_a_screenshot_when_let_go():
    combo = ButtonCombo()
    state, shot, _ = combo.update(press("lb", "a"), 0.0)
    assert not shot and state.buttons == {"a"}  # waiting to see if RB follows; others pass
    state, shot, _ = combo.update(press("lb", "rb"), 0.05)
    assert not shot and state.buttons == set()
    for t in (0.2, 0.5, 1.0):
        state, shot, _ = combo.update(press("lb", "rb"), t)
        assert not shot and state.buttons == set()
    # Letting go of one and pressing it again isn't another combo or a lone press.
    combo.update(press("lb"), 1.1)
    state, shot, _ = combo.update(press("lb"), 1.5)
    assert not shot and state.buttons == set()
    # Both let go: the screenshot, once.
    state, shot, _ = combo.update(press(), 2.0)
    assert shot
    assert not combo.update(press(), 2.1)[1]
    # A fresh press goes through again after the moment.
    combo.update(press("rb"), 3.0)
    state, _, _ = combo.update(press("rb"), 3.2)
    assert state.buttons == {"rb"}


def test_the_d_pad_while_both_are_held_switches_windows_instead():
    combo = ButtonCombo()
    combo.update(press("lb", "rb"), 0.0)
    state, shot, step = combo.update(press("lb", "rb", "dpad_right"), 0.1)
    assert step == 1 and state.buttons == set()  # the D-pad doesn't reach the screen
    assert combo.update(press("lb", "rb", "dpad_right"), 0.2)[2] == 0  # once per press
    state, _, step = combo.update(press("lb", "rb", "dpad_left"), 0.3)
    assert step == -1
    combo.update(press("lb", "rb", "dpad_up"), 0.35)
    assert combo.update(press("lb", "rb", "dpad_up"), 0.36)[0].buttons == {"dpad_up"}  # up/down pass
    # Bumpers let go while the D-pad is still down: it stays out until let go; no screenshot.
    combo.update(press("lb", "rb", "dpad_left"), 0.37)
    state, shot, _ = combo.update(press("dpad_left"), 0.4)
    assert not shot and "dpad_left" not in state.buttons
    combo.update(press(), 0.5)
    assert combo.update(press("dpad_left"), 0.6)[0].buttons == {"dpad_left"}


def test_the_d_pad_alone_or_with_one_bumper_is_untouched():
    combo = ButtonCombo()
    state, _, step = combo.update(press("dpad_right"), 0.0)
    assert step == 0 and state.buttons == {"dpad_right"}
    combo.update(press(), 0.1)
    combo.update(press("lb"), 0.2)
    state, _, step = combo.update(press("lb", "dpad_right"), 0.4)
    assert step == 0 and state.buttons == {"lb", "dpad_right"}


def test_a_lone_bumper_goes_through_just_late():
    combo = ButtonCombo()
    state, _, _ = combo.update(press("lb"), 0.0)
    assert state.buttons == set()
    state, shot, _ = combo.update(press("lb"), 0.15)
    assert not shot and state.buttons == {"lb"}
    # The other pressed well after isn't a combo.
    combo.update(press("lb", "rb"), 1.0)
    state, shot, _ = combo.update(press("lb", "rb"), 1.2)
    assert not shot and state.buttons == {"lb", "rb"}
    assert not combo.update(press(), 1.3)[1]


def test_a_quick_tap_still_counts():
    # Let go inside the moment: passed on as it's let go, for one frame.
    combo = ButtonCombo()
    state, _, _ = combo.update(press("rb"), 0.0)
    assert state.buttons == set()
    state, shot, _ = combo.update(press(), 0.05)
    assert not shot and state.buttons == {"rb"}
    state, _, _ = combo.update(press(), 0.07)
    assert state.buttons == set()
