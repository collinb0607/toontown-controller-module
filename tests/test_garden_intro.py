"""The first-time gardening introduction's pages."""

import json
from pathlib import Path

import pytest

from ttcontroller import hints
from ttcontroller.garden_intro import DONE, NEXT, PREVIOUS, GardenIntro, GardenIntroMapper, read_garden_intro

FIXTURES = Path(__file__).parent / "fixtures" / "battle"


def pixels(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    seen = data["pixels"]
    return w, h, lambda x, y: tuple(seen[f"{x},{y}"])


@pytest.mark.parametrize("name, previous, next_, done", [
    ("gardening_intro_958x484", False, True, False),  # Gardening: the first page
    ("gardening_intro_2_958x484", True, True, False),  # Flowers
    ("gardening_intro_3_958x484", True, True, False),  # Trees
    ("gardening_intro_4_958x484", True, True, False),  # How-To
    ("gardening_intro_5_958x484", True, False, True),  # Statues: the last, with Done
])
def test_each_page(name, previous, next_, done):
    assert read_garden_intro(*pixels(name)) == GardenIntro(True, previous, next_, done)


def test_other_screens_are_not_the_intro():
    for name in ("gardening_hud_1_1920x1009", "fishing_caught_fish_1920x1009", "shop_1920x1009"):
        assert not read_garden_intro(*pixels(name)).is_open


FIRST, MIDDLE, LAST = GardenIntro(True, False, True, False), GardenIntro(True, True, True, False), GardenIntro(True, True, False, True)


def press(m, screen, button, now):
    out = m.update(frozenset({button}), now, screen)
    m.update(frozenset(), now + 0.05, screen)
    return [(c.kind, c.point) for c in out]


def test_a_turns_the_page_then_is_done():
    m = GardenIntroMapper()
    assert press(m, FIRST, "a", 0.0) == [("click", NEXT)]
    assert press(m, LAST, "a", 0.1) == [("click", DONE)]


def test_b_and_the_d_pad():
    m = GardenIntroMapper()
    assert press(m, FIRST, "b", 0.0) == []  # nothing before the first page
    assert press(m, MIDDLE, "b", 0.1) == [("click", PREVIOUS)]
    assert press(m, MIDDLE, "dpad_left", 0.2) == [("click", PREVIOUS)]
    assert press(m, MIDDLE, "dpad_right", 0.3) == [("click", NEXT)]
    assert press(m, LAST, "dpad_right", 0.4) == []  # Done is A's


def test_held_through_a_reset_does_nothing():
    m = GardenIntroMapper()
    m.reset_buttons()
    assert m.update(frozenset({"a"}), 0.0, FIRST) == []


def test_intro_hints():
    first = hints.hints_for(hints.Context(garden_intro=FIRST))
    assert [(h.sprite, h.at) for h in first] == [("A", NEXT.offset(-34 / 1009, -30 / 1009))]
    last = hints.hints_for(hints.Context(garden_intro=LAST))
    assert [h.sprite for h in last] == ["B", "A"]
