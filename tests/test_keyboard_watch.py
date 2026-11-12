"""The real keyboard pauses the controller: only real key presses count."""

from ttcontroller.keyboard_watch import RI_KEY_BREAK, RIM_TYPEKEYBOARD, RAWINPUTHEADER, RAWKEYBOARD, is_real_key_press


def key(device, flags=0, kind=RIM_TYPEKEYBOARD):
    return RAWINPUTHEADER(kind, 0, device, 0), RAWKEYBOARD(0, flags, 0, 0x41, 0, 0)


def test_a_real_key_press_counts():
    assert is_real_key_press(*key(0x1234))


def test_the_modules_own_keys_dont():
    assert not is_real_key_press(*key(None))  # SendInput's: no device


def test_releases_and_other_devices_dont():
    assert not is_real_key_press(*key(0x1234, RI_KEY_BREAK))
    assert not is_real_key_press(*key(0x1234, kind=0))  # a mouse
