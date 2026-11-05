import json
from pathlib import Path

import pytest

from ttcontroller import ui
from ttcontroller.speedchat import Menu, SpeedchatMapper, SpeedchatScreen, read_speedchat

FIXTURES = Path(__file__).parent / "fixtures" / "battle"


def replay(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    return w, h, read_speedchat(w, h, lambda x, y: tuple(pixels[f"{x},{y}"]))


# (left edge, number of rows, highlighted row) of each open menu, measured by eye.
@pytest.mark.parametrize("name,menus", [
    ("speedchat_1920x1009", [(137, 19, None)]),
    ("speedchat_1552x611", [(83, 19, None)]),
    ("speedchat_539x786", [(72, 19, None)]),
    ("speedchat_phrase_hover_1920x1009", [(137, 19, 16)]),  # "Yes": no submenu
    ("speedchat_purple_1920x1009", [(138, 17, None)]),  # another speedchat color, and fewer menus
    ("speedchat_hover_1920x1009", [(137, 19, 5), (335, 10, None)]),  # GOODBYE
    # PLACES > DISTRICT > SPECIFIC, each overlapping the one before.
    ("speedchat_deep_1920x1009", [(137, 19, 11), (335, 17, 1), (452, 6, 0), (609, 15, None)]),
    # Bold letters cover most of HELLO's highlight; a gray Sellbot HQ behind.
    ("speedchat_hello_grey_1920x1009", [(137, 20, 5), (335, 9, None)]),
    # UNITE's submenus open only 0.05 in from their parent's edge.
    ("speedchat_unite_toonup_1920x1009", [(137, 20, 3), (335, 3, 0), (386, 2, None)]),
    ("speedchat_unite_gagup_1920x1009", [(137, 20, 3), (335, 3, 1), (386, 7, None)]),
    ("speedchat_unite_jellybeans_1920x1009", [(137, 20, 3), (335, 3, 2), (386, 2, None)]),
    # BATTLE > STRATEGY > I DON'T HAVE, pushed up to fit in the window.
    ("speedchat_long_1920x1009", [(137, 19, 14), (335, 9, 0), (408, 14, 2), (549, 15, None)]),
])
def test_reads_open_menus(name, menus):
    w, h, screen = replay(name)
    assert [(m.left.to_client(w, h)[0], len(m.rows), m.highlighted) for m in screen.menus] == menus


def test_rows_line_up_with_the_text():
    w, h, screen = replay("speedchat_deep_1920x1009")
    top, places, district, specific = screen.menus
    assert top.rows[0].to_client(w, h)[1] == pytest.approx(35, abs=2)  # ANIMATIONS
    assert top.rows[-1].to_client(w, h)[1] == pytest.approx(635, abs=2)  # OK
    assert places.rows[0].to_client(w, h)[1] == pytest.approx(401, abs=2)  # PLAYGROUND
    assert specific.rows[-1].to_client(w, h)[1] == pytest.approx(901, abs=2)  # Welcome Valley


@pytest.mark.parametrize("name", ["test_1920x1009", "friends_all_1920x1009", "options_1920x1009"])
def test_closed(name):
    assert not replay(name)[2].is_open


# --- Mapper ---

def menu(x, rows, highlighted=None):
    return Menu(ui.UIPoint("left", x, 0), tuple(ui.UIPoint("left", x, 0.1 * i) for i in range(rows)), highlighted)


def press(m, screen, t, *buttons):
    out = m.update(frozenset(buttons), t, screen)
    return out + m.update(frozenset(), t + 0.01, screen)


def test_opening_hovers_the_first_row_and_up_wraps():
    m = SpeedchatMapper()
    top = menu(0.1, 5)
    screen = SpeedchatScreen((top,))
    assert [c.point for c in m.update(frozenset(), 0.0, screen)] == [top.rows[0]]
    assert press(m, screen, 1.0, "dpad_up")[-1].point == top.rows[4]
    assert press(m, screen, 2.0, "dpad_down")[-1].point == top.rows[0]
    assert press(m, screen, 3.0, "ls_down") == []  # the stick still walks


def test_right_enters_a_submenu_once_it_opens_and_left_comes_back():
    m = SpeedchatMapper()
    top = menu(0.1, 5)
    m.update(frozenset(), 0.0, SpeedchatScreen((top,)))
    press(m, SpeedchatScreen((top,)), 1.0, "dpad_down")
    # Pressed before the submenu shows: it's entered when it does.
    assert press(m, SpeedchatScreen((menu(0.1, 5),)), 1.1, "dpad_right") == []
    sub = menu(0.3, 3)
    opened = SpeedchatScreen((menu(0.1, 5, highlighted=1), sub))
    assert [c.point for c in m.update(frozenset(), 1.2, opened)] == [sub.rows[0]]
    assert press(m, opened, 2.0, "dpad_down")[-1].point == sub.rows[1]
    assert press(m, opened, 3.0, "dpad_left")[-1].point == opened.menus[0].rows[1]


def test_a_says_a_phrase_and_b_backs_out_then_closes():
    m = SpeedchatMapper()
    top, sub = menu(0.1, 5, highlighted=0), menu(0.3, 3)
    screen = SpeedchatScreen((top, sub))
    m.update(frozenset(), 0.0, screen)
    assert press(m, screen, 1.0, "a")[-1].point == sub.rows[0]  # A on a submenu row opens it
    assert [(c.kind, c.point) for c in press(m, screen, 2.0, "a")] == [("click", sub.rows[0])]
    m = SpeedchatMapper()
    m.update(frozenset(), 0.0, screen)
    press(m, screen, 1.0, "dpad_right")
    assert press(m, screen, 2.0, "b")[-1].point == top.rows[0]
    assert [(c.kind, c.point) for c in press(m, screen, 3.0, "b")] == [("click", ui.SPEEDCHAT.center)]


# --- Unite hotkey ---

@pytest.mark.parametrize("name,row", [
    ("speedchat_1920x1009", 2), ("speedchat_1552x611", 2), ("speedchat_539x786", 2),
    ("speedchat_long_1920x1009", 2), ("speedchat_hello_grey_1920x1009", 3),  # BOARDING comes first in HQs
    ("speedchat_unite_toonup_1920x1009", 3),  # highlighted
    ("speedchat_purple_1920x1009", None),  # no UNITE! menu on this toon
])
def test_finds_the_unite_row(name, row):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    screen = read_speedchat(w, h, lambda x, y: tuple(pixels[f"{x},{y}"]), look_for_unite=True)
    assert screen.looked_for_unite
    assert screen.unite == row


def test_unite_hotkey_goes_to_toon_up():
    m = SpeedchatMapper()
    m.go_to_unite(0.0)
    assert m.wants_unite
    top = menu(0.1, 6)
    # Opening, before the top menu has been looked at for UNITE!: nothing yet.
    assert m.update(frozenset(), 0.1, SpeedchatScreen((top,))) == []
    looked = SpeedchatScreen((top,), unite=3, looked_for_unite=True)
    assert [c.point for c in m.update(frozenset(), 0.2, looked)] == [top.rows[3]]
    assert not m.wants_unite
    sub = menu(0.3, 3)
    opened = SpeedchatScreen((menu(0.1, 6, highlighted=3), sub))
    assert [c.point for c in m.update(frozenset(), 0.3, opened)] == [sub.rows[0]]  # Toon-Up
    assert press(m, opened, 1.0, "dpad_down")[-1].point == sub.rows[1]


def test_unite_hotkey_without_a_unite_menu_just_opens_speedchat():
    m = SpeedchatMapper()
    m.go_to_unite(0.0)
    top = menu(0.1, 6)
    assert [c.point for c in m.update(frozenset(), 0.2, SpeedchatScreen((top,), looked_for_unite=True))] == [top.rows[0]]


def test_a_light_gray_backdrop_isnt_speedchat():
    # Cog building walls in battle: light gray all the way to the window's edge, which
    # passes the margin check but isn't where the menu opens.
    from ttcontroller.speedchat import read_speedchat
    assert not read_speedchat(1920, 1009, lambda x, y: (200, 200, 205)).is_open
