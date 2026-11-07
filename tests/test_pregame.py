import json
from pathlib import Path

import pytest

from ttcontroller import pregame as p
from ttcontroller.pregame import PregameMapper, PregameScreen, read_pregame

FIXTURES = Path(__file__).parent / "fixtures" / "battle"


def replay(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    return read_pregame(w, h, lambda x, y: tuple(pixels[f"{x},{y}"]))


@pytest.mark.parametrize("name,kind", [
    ("startup_1920x1009", "startup"), ("toon_selection_1920x1009", "toons"), ("startup_options_1920x1009", "options"),
    ("toon_selection_delete_popup_1920x1009", "confirm"), ("toon_selection_delete_popup_2_1920x1009", "type"),
    ("friends_list_1920x1009", None), ("book_events_calendar_1920x1009", None),
])
def test_reads_the_screens(name, kind):
    screen = replay(name)
    assert screen.kind == kind
    if kind == "toons":
        assert screen.trash == (True,) * 6


def press(mapper, button, now, screen):
    commands = mapper.update(frozenset({button}), now, screen)
    return commands + mapper.update(frozenset(), now + 0.01, screen)


TOONS = PregameScreen("toons", trash=(True, True, True, False, True, True))  # slot 4 empty


def test_toon_selection_starts_top_middle_and_moves_by_card():
    m = PregameMapper()
    [hover] = m.update(frozenset(), 0.0, TOONS)
    assert hover.kind == "hover" and hover.point == p.SLOTS[1] and hover.size is None  # no frame
    assert m.update(frozenset(), 0.5, TOONS) == []
    assert [c.point for c in press(m, "dpad_right", 1.0, TOONS)] == [p.SLOTS[2]]
    assert not press(m, "dpad_right", 2.0, TOONS)  # no wrap to the next row
    assert [c.point for c in press(m, "ls_down", 3.0, TOONS)] == [p.SLOTS[5]]
    assert not press(m, "dpad_down", 4.0, TOONS)
    for t in (5.0, 6.0):
        press(m, "dpad_left", t, TOONS)
    [click] = press(m, "a", 7.0, TOONS)
    assert click.kind == "click" and click.point == p.SLOTS[3]  # an empty slot: makes a toon
    assert not press(m, "x", 8.0, TOONS)  # nothing to delete there


def test_deleting_asks_twice_and_only_y_deletes():
    m = PregameMapper()
    m.update(frozenset(), 0.0, TOONS)
    [click] = press(m, "x", 1.0, TOONS)
    assert click.point == p.TRASH[1]
    confirm = PregameScreen("confirm", dialog=(p._center(-0.05, 0.11), p._center(0.05, 0.11)))
    [hover] = m.update(frozenset(), 2.0, confirm)
    assert hover.point == confirm.dialog[0]  # OK
    # B backs out: the same toon again.
    [cancel] = press(m, "b", 3.0, confirm)
    assert cancel.point == confirm.dialog[1]
    [hover] = m.update(frozenset(), 4.0, TOONS)
    assert hover.point == p.SLOTS[1]
    # Again, OK this time, then the "type delete" dialog: A does nothing there, Y does it.
    press(m, "x", 5.0, TOONS)
    m.update(frozenset(), 6.0, confirm)
    press(m, "a", 7.0, confirm)
    typed = PregameScreen("type")
    assert m.update(frozenset(), 8.0, typed) == []
    assert not press(m, "a", 9.0, typed)
    typing, ok = press(m, "y", 10.0, typed)
    assert (typing.kind, typing.name) == ("type", "delete")
    assert ok.kind == "click" and ok.point == p.TYPE_OK and ok.delay > 0
    # Backing out of it instead: straight back to the same toon.
    m2 = PregameMapper()
    m2.update(frozenset(), 0.0, TOONS)
    press(m2, "dpad_left", 0.5, TOONS)
    press(m2, "x", 1.0, TOONS)
    m2.update(frozenset(), 2.0, confirm)
    press(m2, "a", 3.0, confirm)
    m2.update(frozenset(), 4.0, typed)
    [cancel] = press(m2, "b", 5.0, typed)
    assert cancel.point == p.TYPE_CANCEL
    [hover] = m2.update(frozenset(), 6.0, TOONS)
    assert hover.point == p.SLOTS[0]


def test_startup_start_opens_options_and_holding_b_quits():
    m = PregameMapper()
    startup = PregameScreen("startup")
    assert m.update(frozenset(), 0.0, startup) == []
    [click] = press(m, "start", 1.0, startup)
    assert click.point == p.OPTIONS
    assert not press(m, "b", 2.0, startup)  # a tap does nothing
    m.update(frozenset({"b"}), 3.0, startup)
    [click] = m.update(frozenset({"b"}), 3.6, startup)
    assert click.point == p.QUIT


def test_toon_selection_has_options_and_quit_too_and_b_closes_options():
    m = PregameMapper()
    m.update(frozenset(), 0.0, TOONS)
    press(m, "dpad_right", 0.5, TOONS)
    [click] = press(m, "start", 1.0, TOONS)
    assert click.point == p.OPTIONS
    options = PregameScreen("options")
    assert m.update(frozenset(), 2.0, options) == []
    assert not press(m, "a", 3.0, options) and not press(m, "dpad_down", 4.0, options)
    [close] = press(m, "b", 5.0, options)
    assert close.point == p.OPTIONS_CLOSE
    [hover] = m.update(frozenset(), 6.0, TOONS)
    assert hover.point == p.SLOTS[2]  # back on the same toon
    [close] = press(m, "start", 6.5, options)  # Start closes it too
    assert close.point == p.OPTIONS_CLOSE
    m.update(frozenset(), 6.9, TOONS)
    m.update(frozenset({"b"}), 7.0, TOONS)
    [click] = m.update(frozenset({"b"}), 7.6, TOONS)
    assert click.point == p.QUIT


def test_name_your_toon_button():
    screen = replay("toon_selection_name_your_toon_1920x1009")
    assert screen.names == (True, False, False, False, False, False)
    assert p.NAME_BUTTONS[0].to_client(1920, 1009) == (433, 476)
    m = PregameMapper()
    m.update(frozenset(), 0.0, screen)  # opens on the top middle toon: no button there
    assert press(m, "y", 1.0, screen) == []
    press(m, "dpad_left", 2.0, screen)
    [click] = press(m, "y", 3.0, screen)
    assert click.kind == "click" and click.point == p.NAME_BUTTONS[0] and click.name == "name toon 1"
