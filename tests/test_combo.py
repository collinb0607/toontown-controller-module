from ttcontroller.combo import ButtonCombo
from ttcontroller.controller import ControllerState


def press(*buttons):
    return ControllerState(buttons=frozenset(buttons))


def test_both_bumpers_together_fire_once_and_are_held_back():
    combo = ButtonCombo()
    state, fired = combo.update(press("lb", "a"), 0.0)
    assert not fired and state.buttons == {"a"}  # waiting to see if RB follows; others pass
    state, fired = combo.update(press("lb", "rb"), 0.05)
    assert fired and state.buttons == set()
    for t in (0.2, 0.5, 1.0):
        state, fired = combo.update(press("lb", "rb"), t)
        assert not fired and state.buttons == set()
    # Letting go of one and pressing it again isn't another combo or a lone press.
    combo.update(press("lb"), 1.1)
    state, fired = combo.update(press("lb"), 1.5)
    assert not fired and state.buttons == set()
    # All let go: a fresh press goes through again after the moment.
    combo.update(press(), 2.0)
    combo.update(press("rb"), 3.0)
    state, _ = combo.update(press("rb"), 3.2)
    assert state.buttons == {"rb"}


def test_a_lone_bumper_goes_through_just_late():
    combo = ButtonCombo()
    state, _ = combo.update(press("lb"), 0.0)
    assert state.buttons == set()
    state, fired = combo.update(press("lb"), 0.15)
    assert not fired and state.buttons == {"lb"}
    # The other pressed well after isn't a combo.
    combo.update(press("lb", "rb"), 1.0)
    state, fired = combo.update(press("lb", "rb"), 1.2)
    assert not fired and state.buttons == {"lb", "rb"}


def test_a_quick_tap_still_counts():
    # Let go inside the moment: passed on as it's let go, for one frame.
    combo = ButtonCombo()
    state, _ = combo.update(press("rb"), 0.0)
    assert state.buttons == set()
    state, fired = combo.update(press(), 0.05)
    assert not fired and state.buttons == {"rb"}
    state, _ = combo.update(press(), 0.07)
    assert state.buttons == set()
