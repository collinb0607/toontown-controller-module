import json
from pathlib import Path

import pytest

from ttcontroller import friends as f
from ttcontroller.friends import FriendsMapper, FriendsScreen, read_friends

FIXTURES = Path(__file__).parent / "fixtures" / "battle"


def replay(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    return read_friends(w, h, lambda x, y: tuple(pixels[f"{x},{y}"]))


@pytest.mark.parametrize("name,rows", [
    ("friends_list_1920x1009", 1), ("friends_list_1533x711", 1), ("friends_online_1920x1009", 3),
    ("friends_hover_1920x1009", 3), ("friends_all_1920x1009", 8), ("friends_scrolled_1920x1009", 8),
    ("friends_nearby_toons_1920x1009", 8), ("friends_pets_1920x1009", 0),
])
def test_list(name, rows):
    screen = replay(name)
    assert screen.kind == "list"
    assert len(screen.rows) == rows


@pytest.mark.parametrize("name,details", [
    ("friends_detail_1920x1009", False), ("friends_detail_hover_1920x1009", False),
    ("friends_detail_toon_details_hover_1920x1009", False),
    ("friends_detail_toon_details_1920x1009", True), ("friends_detail_toon_details_close_hover_1920x1009", True),
])
def test_toon_panel(name, details):
    screen = replay(name)
    assert screen.kind == "panel"
    assert screen.details == details


@pytest.mark.parametrize("name", ["test_1920x1009", "speedchat_1920x1009", "options_1920x1009"])
def test_closed(name):
    assert replay(name).kind is None


# --- Mapper ---

def press(m, screen, t, *buttons):
    out = m.update(frozenset(buttons), t, screen)
    return out + m.update(frozenset(), t + 0.01, screen)


def full_list():
    return FriendsScreen("list", rows=tuple(f._row(i) for i in range(8)))


def test_list_moves_scrolls_and_opens():
    m = FriendsMapper()
    screen = full_list()
    assert [c.point for c in m.update(frozenset(), 0.0, screen)] == [screen.rows[0]]
    # Up from the top scrolls up and stays on the top row.
    assert [(c.kind, c.point) for c in press(m, screen, 1.0, "dpad_up")] == [
        ("click", f.SCROLL_UP), ("hover", screen.rows[0])]
    for t in range(7):
        press(m, screen, 2.0 + t, "dpad_down")
    assert m.row == 7
    assert [(c.kind, c.point) for c in press(m, screen, 10.0, "dpad_down")] == [
        ("click", f.SCROLL_DOWN), ("hover", screen.rows[7])]
    assert [(c.kind, c.point) for c in press(m, screen, 11.0, "a")] == [("click", screen.rows[7])]


def test_short_list_doesnt_scroll_past_the_last_name():
    m = FriendsMapper()
    screen = FriendsScreen("list", rows=tuple(f._row(i) for i in range(3)))
    m.update(frozenset(), 0.0, screen)
    press(m, screen, 1.0, "dpad_down")
    press(m, screen, 2.0, "dpad_down")
    assert press(m, screen, 3.0, "dpad_down") == []


def test_pages_and_close():
    m = FriendsMapper()
    screen = full_list()
    m.update(frozenset(), 0.0, screen)
    assert [c.point for c in press(m, screen, 1.0, "dpad_right")] == [f.PAGE_RIGHT]
    # After the page changes, the highlight goes back to the top name.
    m.update(frozenset(), 1.5, screen)
    assert [c.point for c in press(m, screen, 2.0, "b")] == [f.LIST_CLOSE]


@pytest.mark.parametrize("button,target", [("x", f.GO_TO), ("y", f.WHISPER)])
def test_x_and_y_work_straight_from_the_list(button, target):
    m = FriendsMapper()
    screen = full_list()
    m.update(frozenset(), 0.0, screen)
    press(m, screen, 1.0, "dpad_down")
    commands = press(m, screen, 2.0, button)
    assert [(c.kind, c.point) for c in commands] == [("click", screen.rows[1]), ("click", target)]
    assert commands[1].delay == f.PANEL_OPEN_SECONDS


def test_toon_panel_buttons():
    m = FriendsMapper()
    screen = FriendsScreen("panel")
    assert [c.point for c in m.update(frozenset(), 0.0, screen)] == [f.FRIEND]
    assert press(m, screen, 1.0, "dpad_down")[-1].point == f.GO_TO
    assert [c.point for c in press(m, screen, 2.0, "y")] == [f.WHISPER]
    m.update(frozenset(), 3.0, screen)
    assert [c.point for c in press(m, screen, 4.0, "x")] == [f.GO_TO]
    m.update(frozenset(), 5.0, screen)
    assert [c.point for c in press(m, screen, 6.0, "b")] == [f.PANEL_CLOSE]


def test_b_closes_toon_details_first():
    m = FriendsMapper()
    screen = FriendsScreen("panel", details=True)
    m.update(frozenset(), 0.0, screen)
    assert [c.point for c in press(m, screen, 1.0, "b")] == [f.DETAILS_CLOSE, f.FRIEND]


def test_closing_toon_details_right_after_opening_waits_for_it():
    m = FriendsMapper()
    closed = FriendsScreen("panel")
    m.update(frozenset(), 0.0, closed)
    m.button = len(f.PANEL_BUTTONS) - 1  # Toon Details
    press(m, closed, 1.0, "a")
    [close, _] = press(m, FriendsScreen("panel", details=True), 1.1, "b")
    assert close.point == f.DETAILS_CLOSE and close.delay == pytest.approx(f.DETAILS_OPEN_SECONDS - 0.1)


def test_toon_details_close_is_clicked_again_if_it_missed():
    m = FriendsMapper()
    still_open = FriendsScreen("panel", details=True)
    m.update(frozenset(), 0.0, still_open)
    assert [c.point for c in press(m, still_open, 1.0, "b")] == [f.DETAILS_CLOSE, f.FRIEND]
    assert m.update(frozenset(), 1.2, still_open) == []
    assert [c.point for c in m.update(frozenset(), 1.6, still_open)] == [f.DETAILS_CLOSE, f.FRIEND]
    m.update(frozenset(), 2.2, still_open)  # third and last try
    assert m.update(frozenset(), 2.8, still_open) == []
    # Once it's closed, no more clicks.
    m2 = FriendsMapper()
    m2.update(frozenset(), 0.0, still_open)
    press(m2, still_open, 1.0, "b")
    assert m2.update(frozenset(), 1.6, FriendsScreen("panel")) == []
