"""Hold LB + RB and press D-pad left or right: the TTR window to the left or right comes
to the front, for playing several toons in turn with one controller (one-toon mode only;
the user, Nov 9). combo.ButtonCombo reads the buttons; this is the order. Windows are
ordered by where they are on screen, left to right (then top to bottom), and the order
wraps around; with two windows either direction swaps them. Not shown in any hint (the
user's ask).
"""


def next_window(windows: list, current, step: int):
    """The window `step` along from `current` in `windows` (in screen order), wrapping
    around. The first one if `current` isn't among them."""
    if not windows:
        return None
    if current not in windows:
        return windows[0]
    return windows[(windows.index(current) + step) % len(windows)]
