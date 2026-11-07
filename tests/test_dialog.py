import json
from pathlib import Path

from ttcontroller.dialog import DialogMapper, find_ok_cancel

FIXTURES = Path(__file__).parent / "fixtures" / "battle"


def replay(name, reader):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    return reader(w, h, lambda x, y: tuple(pixels[f"{x},{y}"]))


def test_finds_the_estate_teleport_dialog():
    ok, cancel = replay("estate_popup_1920x1009", find_ok_cancel)
    ox, oy = ok.to_client(1920, 1009)
    cx, cy = cancel.to_client(1920, 1009)
    assert abs(ox - 904) <= 4 and abs(cx - 1015) <= 4 and abs(oy - 627) <= 4 and abs(cy - 627) <= 4


def test_a_clicks_ok_and_b_cancel():
    m = DialogMapper()
    dialog = ("OK", "CANCEL")
    assert [c.point for c in m.update(frozenset({"a"}), 0.0, dialog)] == ["OK"]
    assert m.update(frozenset({"a"}), 0.1, dialog) == []  # held: once
    m.update(frozenset(), 0.2, dialog)
    assert [c.point for c in m.update(frozenset({"b"}), 0.3, dialog)] == ["CANCEL"]


def test_a_held_when_the_dialog_appears_does_nothing_until_let_go():
    m = DialogMapper()
    m.reset_buttons()
    assert m.update(frozenset({"a"}), 0.0, ("OK", "CANCEL")) == []
    m.update(frozenset(), 0.1, ("OK", "CANCEL"))
    assert [c.point for c in m.update(frozenset({"a"}), 0.2, ("OK", "CANCEL"))] == ["OK"]
