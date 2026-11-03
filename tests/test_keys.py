import pytest

from ttcontroller.keys import KeyCombo, is_extended, is_modifier, parse_combo, vk_code


def test_plain_key():
    assert parse_combo("w") == KeyCombo((), "w")


def test_modifier_combo():
    assert parse_combo("shift-escape") == KeyCombo(("shift",), "escape")
    assert parse_combo("shift-escape").names == ("shift", "escape")


def test_underscore_names_are_not_split():
    assert parse_combo("page_down") == KeyCombo((), "page_down")


def test_minus_key():
    assert parse_combo("-") == KeyCombo((), "-")
    assert parse_combo("shift--") == KeyCombo(("shift",), "-")


def test_modifier_alone_is_a_key():
    assert parse_combo("shift") == KeyCombo((), "shift")


def test_unknown_key_raises():
    with pytest.raises(ValueError):
        parse_combo("mouse1")


def test_codes():
    assert vk_code("w") == ord("W")
    assert vk_code("f8") == 0x77
    assert vk_code("space") == 0x20
    assert is_extended("delete") and not is_extended("w")
    assert is_modifier("shift") and is_modifier("rcontrol") and not is_modifier("r")
