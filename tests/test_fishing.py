"""M14: fishing on a dock."""

import json
from pathlib import Path

import pytest

from ttcontroller import hints
from ttcontroller.dialog import find_cancel_alone
from ttcontroller.fishing import (CARD_KEEP, CARD_RELEASE, CAST, EXIT, BOTTOM, FIRST_PULL, MIN_PULL, REACH, SPEED, FishingMapper,
                                  FishingScreen, move_pull, read_fishing)

FIXTURES = Path(__file__).parent / "fixtures" / "battle"
DOCK = FishingScreen("dock", can_cast=True)
GREEN = FishingScreen("dock", can_cast=True, casting=True)  # Cast grabbed
CARD = FishingScreen("card", can_cast=True)


def pixels(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    seen = data["pixels"]
    return w, h, lambda x, y: tuple(seen[f"{x},{y}"])


@pytest.mark.parametrize("name, kind, casting", [
    ("fishing_idle_1920x1009", "dock", False),
    ("fishing_waiting_for_bite_1920x1009", "dock", False),
    ("fishing_casting_1920x1009", "dock", True),
    ("fishing_caught_fish_1920x1009", "card", False),
    ("fishing_caught_fish_2_1920x1009", "card", False),  # not a new species (its card read as an NPC bubble)
])
def test_the_dock_and_the_catch_card(name, kind, casting):
    screen = read_fishing(*pixels(name))
    assert screen.kind == kind and screen.can_cast and screen.casting == casting


@pytest.mark.parametrize("name", ["fishing_bucket_full_popup_1920x1009", "fishing_out_of_beans_1920x1009"])
def test_the_popups_are_one_button_dialogs(name):
    # The dock's buttons are hidden; the generic one-button dialog takes them (A or B: Exit).
    w, h, get_pixel = pixels(name)
    assert read_fishing(w, h, get_pixel).kind is None
    exit_button = find_cancel_alone(w, h, get_pixel)
    assert exit_button is not None and abs(exit_button.to_client(w, h)[0] - 960) < 10


def test_other_screens_are_not_fishing():
    # Minnie's Melodyland's pink pavement once read as the dock's red X (the user, Nov 12).
    for name in ("gardening_hud_1_1920x1009", "shop_1920x1009", "shop_empty_throw_slots_1920x1009",
                 "street_melodyland_pink_1920x1009"):
        w, h, get_pixel = pixels(name)
        assert read_fishing(w, h, get_pixel).kind is None


def kinds(commands):
    return [(c.kind, c.point) for c in commands]


def test_holding_a_casts_and_the_stick_moves_the_pull():
    m = FishingMapper()
    assert kinds(m.update(frozenset({"a"}), (0.0, 0.0), 0.0, DOCK)) == [("hold", CAST)]
    assert m.holding and not m.grabbed
    assert m.update(frozenset({"a"}), (-1.0, 0.0), 0.05, GREEN) == []  # too soon after the press
    first = m.update(frozenset({"a"}), (-1.0, 0.0), 0.1, GREEN)  # green: grabbed, the pull starts
    assert kinds(first) == [("hover", CAST.offset(*FIRST_PULL))]  # straight back to start
    # Full tilt left for a tenth of a second moves the pull left by a tenth of SPEED.
    moved = m.update(frozenset({"a"}), (-1.0, 0.0), 0.2, GREEN)
    x, y = m.pull
    assert abs(x + SPEED * 0.1) < 1e-9 and y == FIRST_PULL[1]
    assert [c.kind for c in moved] == ["hover"]
    # Let go of the stick: the pull stays where it is.
    assert m.update(frozenset({"a"}), (0.0, 0.0), 0.3, GREEN) == [] and m.pull == (x, y)
    let_go = m.update(frozenset(), (0.0, 0.0), 0.4, GREEN)
    assert [c.kind for c in let_go] == ["release"] and not m.holding
    # The next cast starts where this one was let go.
    m.update(frozenset({"a"}), (0.0, 0.0), 0.5, DOCK)
    assert kinds(m.update(frozenset({"a"}), (0.0, 0.0), 0.6, GREEN)) == [("hover", CAST.offset(x, y))]


def test_a_press_cast_missed_is_pressed_again():
    m = FishingMapper()
    m.update(frozenset({"a"}), (0.0, 0.0), 0.0, DOCK)
    assert m.update(frozenset({"a"}), (0.0, 0.0), 0.3, DOCK) == []  # still waiting for green
    again = m.update(frozenset({"a"}), (0.0, 0.0), 0.55, DOCK)
    assert [c.kind for c in again] == ["release", "hold"]
    assert kinds(m.update(frozenset({"a"}), (0.0, 0.0), 0.7, GREEN)) == [("hover", CAST.offset(*FIRST_PULL))]


def test_with_no_green_ever_it_pulls_after_three_presses():
    m = FishingMapper()
    seen = []
    for i in range(30):
        seen += [c.kind for c in m.update(frozenset({"a"}), (0.0, 0.0), i * 0.1, DOCK)]
    assert seen.count("hold") == 3 and seen[-1] == "hover" and m.grabbed


def test_a_held_before_cast_shows_grabs_when_it_does():
    m = FishingMapper()
    hidden = FishingScreen("dock", can_cast=False)
    assert m.update(frozenset({"a"}), (0.0, 0.0), 0.0, hidden) == []
    assert kinds(m.update(frozenset({"a"}), (0.0, 0.0), 0.1, DOCK)) == [("hold", CAST)]


def test_the_pull_stops_at_its_longest_and_at_the_cast_button():
    pull = FIRST_PULL
    for _ in range(100):
        pull = move_pull(pull, (1.0, 0.3), 0.05)
    assert abs((pull[0] ** 2 + pull[1] ** 2) ** 0.5 - REACH) < 1e-9
    for _ in range(100):
        pull = move_pull(pull, (0.0, 1.0), 0.05)
    assert pull[1] == BOTTOM  # straight back stops short of the window's bottom edge
    for _ in range(100):
        pull = move_pull(pull, (0.0, -1.0), 0.05)
    assert pull[1] == 0.0  # never forward of the button


def test_small_tilts_dont_move_the_pull():
    assert move_pull(FIRST_PULL, (0.1, 0.1), 1.0) == FIRST_PULL
    m = FishingMapper()
    m.update(frozenset({"a"}), (0.0, 0.0), 0.0, DOCK)
    m.update(frozenset({"a"}), (0.0, 0.0), 0.1, GREEN)
    assert m.update(frozenset({"a"}), (0.0, 0.25), 0.11, GREEN) == []  # a tiny move: not sent yet


def test_no_cast_without_the_cast_button():
    m = FishingMapper()
    assert m.update(frozenset({"a"}), (0.0, 0.0), 0.0, FishingScreen("dock", can_cast=False)) == []
    assert not m.holding


def test_b_leaves_the_dock():
    m = FishingMapper()
    assert kinds(m.update(frozenset({"b"}), (0.0, 0.0), 0.0, DOCK)) == [("click", EXIT)]
    assert m.update(frozenset({"b"}), (0.0, 0.0), 0.1, DOCK) == []  # once per press


def test_the_catch_card():
    m = FishingMapper()
    assert kinds(m.update(frozenset({"x"}), (0.0, 0.0), 0.0, CARD)) == [("click", CARD_KEEP)]
    m.update(frozenset(), (0.0, 0.0), 0.1, CARD)
    assert kinds(m.update(frozenset({"b"}), (0.0, 0.0), 0.2, CARD)) == [("click", CARD_RELEASE)]  # not Exit
    m.update(frozenset(), (0.0, 0.0), 0.3, CARD)
    # A casts again straight away with the card up.
    assert kinds(m.update(frozenset({"a"}), (0.0, 0.0), 0.4, CARD)) == [("hold", CAST)]
    assert kinds(m.update(frozenset({"a"}), (0.0, 0.0), 0.5, FishingScreen("card", True, True))) == [
        ("hover", CAST.offset(*FIRST_PULL))]
    assert FishingMapper.buttons(CARD) == {"a", "b", "x", "ls"} and FishingMapper.buttons(DOCK) == {"a", "b", "ls"}


def test_ls_switches_to_the_stick_being_the_aim_and_back():
    m = FishingMapper()
    m.update(frozenset({"ls"}), (0.0, 0.0), 0.0, DOCK)
    assert m.method == "stick" and m.take_switch() and not m.take_switch()
    m.update(frozenset({"a"}), (0.0, 0.0), 0.1, DOCK)
    # At rest: the shortest cast, straight forward.
    assert kinds(m.update(frozenset({"a"}), (0.0, 0.0), 0.2, GREEN)) == [("hover", CAST.offset(0.0, MIN_PULL))]
    # The stick's tilt is the pull: full left is the longest pull left, straight away.
    assert kinds(m.update(frozenset({"a"}), (-1.0, 0.0), 0.21, GREEN)) == [("hover", CAST.offset(-REACH, 0.0))]
    # Switched back mid-cast: the stick moves the aim from where it is.
    m.update(frozenset({"a", "ls"}), (0.0, 0.0), 0.22, GREEN)
    assert m.method == "move" and m.pull == (-REACH, 0.0)
    assert m.update(frozenset({"a"}), (0.0, 0.0), 0.3, GREEN) == []  # stick let go: it stays


def test_the_cast_setting():
    from ttcontroller.config import parse
    assert parse({"fishing_cast": "stick"})[0].fishing_cast == "stick"
    config, warnings = parse({"fishing_cast": "sideways"})
    assert config.fishing_cast == "move" and warnings


def test_a_cast_is_let_go_when_the_dock_goes():
    m = FishingMapper()
    m.update(frozenset({"a"}), (0.0, 0.0), 0.0, DOCK)
    assert [c.kind for c in m.update(frozenset({"a"}), (0.0, 0.0), 0.1, FishingScreen())] == ["release"]
    assert not m.holding
    # A still held from before doesn't start another cast.
    assert m.update(frozenset({"a"}), (0.0, 0.0), 0.2, DOCK) == []


def test_reset_ignores_buttons_still_held():
    m = FishingMapper()
    m.reset()
    assert m.update(frozenset({"a"}), (0.0, 0.0), 0.0, DOCK) == []
    m.update(frozenset(), (0.0, 0.0), 0.1, DOCK)
    assert m.update(frozenset({"a"}), (0.0, 0.0), 0.2, DOCK)[0].kind == "hold"




def test_fishing_hints():
    dock = hints.hints_for(hints.Context(mode="fishing", fishing=DOCK))
    sprites = [h.sprite for h in dock if isinstance(h, hints.Badge)]
    assert sprites == ["B", "A"] and any(isinstance(h, hints.Bar) for h in dock)
    card = hints.hints_for(hints.Context(mode="fishing", fishing=CARD))
    covers = {(h.sprite, h.at) for h in card if isinstance(h, hints.Badge) and h.cover}
    assert covers == {("X", CARD_KEEP), ("B", CARD_RELEASE)}
    assert any(isinstance(h, hints.Badge) and h.sprite == "A" and h.at != CARD_KEEP for h in card)
