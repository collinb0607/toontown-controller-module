from ttcontroller.controller import ControllerState
from ttcontroller.mapper import OverworldMapper

FORWARD = (0.0, -1.0)


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


def test_sprint_double_taps_forward():
    m = OverworldMapper()
    frames = run_frames(m, [(state("l3", left=FORWARD), 1), (state(left=FORWARD), 30)])
    forward = ["forward" in f for f in frames]
    # down ... up ... down again
    first_up = forward.index(False)
    assert first_up > 0
    assert forward[first_up:].index(True) > 0
    assert all(forward[first_up + forward[first_up:].index(True):])


def test_sprint_armed_while_standing_then_push():
    m = OverworldMapper()
    frames = run_frames(m, [(state("l3"), 1), (state(), 20), (state(left=FORWARD), 30)])
    forward = ["forward" in f for f in frames[21:]]
    assert forward[0] and False in forward and forward[-1]


def test_sprint_arm_expires():
    m = OverworldMapper()
    frames = run_frames(m, [(state("l3"), 1), (state(), 150), (state(left=FORWARD), 30)])
    assert all("forward" in f for f in frames[151:])
