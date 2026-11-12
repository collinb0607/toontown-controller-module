"""M14: Make-a-Toon's on-screen keyboard for typing a name."""

from dataclasses import replace

import pytest
from test_makeatoon import names, press, read

from ttcontroller import name_keyboard as nk
from ttcontroller.makeatoon import MakeAToonMapper
from ttcontroller.name_keyboard import CLEAR_PRESSES, NameKeyboard
from ttcontroller.output import WM_CHAR, WM_KEYDOWN, WM_KEYUP, PostedKeys, type_text

CLEAR = "\b" * CLEAR_PRESSES


def test_first_letter_of_each_word_is_a_capital():
    k = NameKeyboard()
    assert k.capital and k.letter == "Q"
    assert k.type_letter() == "Q"
    assert not k.capital and k.letter == "q"
    k.type_letter()
    assert k.space() and k.capital and k.letter == "Q"
    assert not k.space()  # no double spaces
    k.type_letter()
    assert k.text == "Qq Q"
    assert k.delete() and k.capital and k.text == "Qq "
    k.delete(), k.delete(), k.delete()
    assert k.text == "" and k.capital and not k.delete() and not k.space()  # no leading space


def test_moving_round_the_staggered_rows():
    k = NameKeyboard()
    assert not k.move("left") and not k.move("up")
    for _ in range(4):
        k.move("right")
    assert k.letter == "T"
    k.move("down")  # straight down: the rows line up
    assert k.letter == "G"
    k.move("down")
    assert k.letter == "V"
    assert not k.move("down")
    k.move("up"), k.move("up")
    assert k.letter == "T"
    for _ in range(9):
        k.move("right")
    assert k.letter == "P" and not k.move("right")
    k.move("down"), k.move("down")
    assert k.letter == "M"  # the last key of the shorter rows
    k.row, k.col = 0, 0
    k.move("down")
    assert k.letter == "A"


def typing_screen(m, at=0.0):
    """On the Name step, then Type-A-Name: returns the Name step, Type-A-Name (its box
    empty), the same with text in the box, and the commands on arriving."""
    name = read("make_a_toon_5_1920x1009")
    typing = read("make_a_toon_5_type_name_1920x1009")
    assert typing.box_empty
    m.update(frozenset(), at, name)
    return name, typing, replace(typing, box_empty=False), m.update(frozenset(), at + 1.0, typing)


def test_type_a_name_opens_the_keyboard_on_an_empty_box():
    m = MakeAToonMapper()
    _, typing, _, out = typing_screen(m)
    assert out == []  # nothing sent: the box is read
    assert m.showing_keyboard(typing) and m.keyboard.letter == "Q"


def test_typing_a_name():
    m = MakeAToonMapper()
    _, _, typed_in, _ = typing_screen(m)
    t = 2.0
    typed = []
    for buttons in (["dpad_down", "dpad_right", "dpad_right", "dpad_right", "dpad_right"], ["a"],  # G
                    ["dpad_left", "dpad_left", "dpad_left", "dpad_left"], ["a"], ["y"], ["y"], ["a"], ["x"], ["a"]):
        for b in buttons:
            typed += press(m, typed_in, b, at=t)
            t += 1.0
    assert names(typed) == [("type", "G"), ("type", "a"), ("type", " "), ("type", "A"), ("type", ""),
                            ("type", "A")]
    assert m.keyboard.text == "Ga A" and not m.keyboard.capital


def test_text_already_in_the_box_is_kept_as_mid_word():
    # Half typed on the real keyboard, or before the mouse paused the controller.
    m = MakeAToonMapper()
    name = read("make_a_toon_5_1920x1009")
    _, typing, typed_in, _ = typing_screen(MakeAToonMapper())
    m.update(frozenset(), 0.0, name)
    assert m.update(frozenset(), 1.0, typed_in) == []  # nothing cleared
    assert m.showing_keyboard(typed_in) and m.keyboard.letter == "q"
    assert names(press(m, typed_in, "a", at=2.0)) == [("type", "q")]
    # Deleting goes on into the earlier text (unseen), until the box reads empty.
    for t in (3.0, 4.0, 5.0):
        assert names(press(m, typed_in, "x", at=t)) == [("type", "")]
    m.update(frozenset(), 5.1, typing)  # too soon after a key to trust
    assert not m.keyboard.capital
    m.update(frozenset(), 6.0, typing)
    assert m.keyboard.capital and press(m, typing, "x", at=7.0) == []


def test_a_mouse_pause_reads_the_box_again():
    m = MakeAToonMapper()
    _, typing, typed_in, _ = typing_screen(m)
    press(m, typed_in, "a", at=2.0)
    press(m, typed_in, "y", at=3.0)
    assert m.keyboard.capital
    m.reset_buttons()  # the mouse took over
    m.update(frozenset(), 4.0, typed_in)
    assert m.keyboard.prefix and m.keyboard.letter == "q"
    m.reset_buttons()
    m.update(frozenset(), 5.0, typing)  # cleared with the mouse and keyboard meanwhile
    assert m.keyboard.empty and m.keyboard.letter == "Q"


def test_emptied_on_the_real_keyboard_starts_over():
    m = MakeAToonMapper()
    _, typing, typed_in, _ = typing_screen(m)
    press(m, typed_in, "a", at=2.0)
    m.update(frozenset(), 3.0, typed_in)
    assert not m.keyboard.capital
    m.update(frozenset(), 4.0, typing)
    assert m.keyboard.capital and m.keyboard.text == ""


def test_start_closes_and_submits_and_a_no_keeps_the_name():
    m = MakeAToonMapper()
    _, typing, typed_in, _ = typing_screen(m)
    press(m, typed_in, "a", at=2.0)
    press(m, typed_in, "y", at=2.5)
    out = press(m, typed_in, "start", at=3.0)
    assert names(out) == [("click", "submit")] and out[0].point == typing.buttons[0]
    assert not m.showing_keyboard(typed_in)
    confirm = read("make_a_toon_5_type_name_confirm_1920x1009")
    m.update(frozenset(), 4.0, confirm)
    press(m, confirm, "b", at=5.0)  # No
    assert m.update(frozenset(), 6.0, typed_in) == []  # back with the name kept
    assert m.showing_keyboard(typed_in) and m.keyboard.text == "Q " and m.keyboard.capital


def test_b_clears_the_name_and_goes_back_to_the_lists():
    m = MakeAToonMapper()
    _, typing, typed_in, _ = typing_screen(m)
    press(m, typed_in, "a", at=2.0)
    press(m, typed_in, "a", at=3.0)
    out = press(m, typed_in, "b", at=4.0)
    assert names(out) == [("type", CLEAR), ("click", "pick-a-name")] and out[1].point == typing.buttons[1]
    assert m.keyboard.empty and not m.showing_keyboard(typing)


def test_closed_by_start_a_direction_opens_it_again():
    m = MakeAToonMapper()
    _, typing, _, _ = typing_screen(m)
    press(m, typing, "start", at=4.0)
    # Closed (Submit with nothing typed does nothing): Type-A-Name's own buttons again.
    assert names(press(m, typing, "a", at=5.0)) == [("click", "submit")]
    assert press(m, typing, "dpad_up", at=6.0) == [] and m.showing_keyboard(typing)
    assert names(press(m, typing, "a", at=7.0)) == [("type", "Q")]


def test_nothing_else_while_typing():
    m = MakeAToonMapper()
    _, typing, _, _ = typing_screen(m)
    for i, b in enumerate(("lb", "rb", "rt", "rs_left")):
        assert press(m, typing, b, at=2.0 + i) == [], b


def test_reads_text_in_the_box():
    import json
    from test_book import FIXTURES
    from ttcontroller.makeatoon import read_make_a_toon
    data = json.loads((FIXTURES / "make_a_toon_5_type_name_1920x1009.json").read_text())
    pixels = {k: tuple(v) for k, v in data["pixels"].items()}
    assert read_make_a_toon(1920, 1009, lambda x, y: pixels[f"{x},{y}"]).box_empty
    pixels["700,374"] = (20, 20, 20)  # a letter's stroke
    assert not read_make_a_toon(1920, 1009, lambda x, y: pixels[f"{x},{y}"]).box_empty


def test_type_text_holds_shift_for_capitals():
    sent = []
    type_text(lambda name, down: sent.append((name, down)), "Ab \b")
    assert sent == [("shift", True), ("a", True), ("a", False), ("shift", False), ("b", True), ("b", False),
                    ("space", True), ("space", False), ("backspace", True), ("backspace", False)]


def test_posted_capitals_go_as_characters():
    posts = []
    send = PostedKeys(1, post=lambda hwnd, msg, w, l: posts.append((msg, w)))
    type_text(send, "Ab")
    assert posts == [(WM_KEYDOWN, 0x10), (WM_CHAR, ord("A")), (WM_KEYUP, 0x10),
                     (WM_KEYDOWN, ord("B")), (WM_KEYUP, ord("B"))]


@pytest.mark.parametrize("unit", [1009, 534])
def test_drawing(unit):
    sheet = nk.find_sheet()
    if sheet is None:
        pytest.skip("no input_sprites/all_input.png")
    k = NameKeyboard(text="Ga")
    from ttcontroller.hint_draw import find_sheet as button_sheet
    image = nk.KeyboardDrawer(sheet, button_sheet()).image(k, unit)
    assert image.shape == (round(nk.PANEL_SIZE[1] * unit), round(nk.PANEL_SIZE[0] * unit), 4)
    assert image[unit // 20, image.shape[1] // 2, 3] == 255  # solid
