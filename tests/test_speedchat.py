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
    ("speedchat_hover_1920x1009", [(137, 19, 5), (335, 10, None)]),  # GOODBYE
    # PLACES > DISTRICT > SPECIFIC, each overlapping the one before.
    ("speedchat_deep_1920x1009", [(137, 19, 11), (335, 17, 1), (452, 6, 0), (609, 15, None)]),
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
    assert press(m, screen, 2.0, "ls_down")[-1].point == top.rows[0]


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
