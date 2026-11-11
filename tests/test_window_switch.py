"""Hold LB + RB and press D-pad left/right: the TTR window to that side (one toon). The
buttons are combo.ButtonCombo's (tests/test_combo.py); this is the order."""

from ttcontroller.window_switch import next_window


def test_the_order_wraps_around():
    windows = [1, 2, 3]  # left to right
    assert next_window(windows, 1, 1) == 2
    assert next_window(windows, 3, 1) == 1
    assert next_window(windows, 1, -1) == 3
    assert next_window([1, 2], 1, -1) == next_window([1, 2], 1, 1) == 2  # two: either way swaps
    assert next_window(windows, 99, 1) == 1  # the one in front isn't TTR: the first
    assert next_window([], 1, 1) is None
