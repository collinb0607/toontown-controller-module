import json
from pathlib import Path

import pytest

from ttcontroller import battle
from ttcontroller.battle import (
    RUN, RUN_NO, RUN_YES, TARGET_BACK, TRUNK, WAITING_BACK, BattleMapper, BattleScreen, cell, move, nearest_usable, read_screen,
)

FIXTURES = Path(__file__).parent / "fixtures" / "battle"


def replay(name):
    """Read a recorded screen: only the pixels the reader sampled when it was recorded."""
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    return read_screen(w, h, lambda x, y: tuple(pixels[f"{x},{y}"]))


def grid(*rows):
    return tuple(tuple(ch == "B" for ch in row) for row in rows)


# Checked by eye against the screenshots. Rows: Toon-Up, Trap, Lure, Sound, Throw, Squirt, Drop.
SOLO_LURE_USABLE = grid(".......", ".......", "...BBBB", "B..BBBB", "...BBBB", "...BBBB", "...BBBB")
SOLO_LURE_GRAYED = grid(".......", ".......", ".......", "B..BBBB", "...BBBB", "...BBBB", "...BBBB")
WITH_TEAMMATE = grid("...BBBB", ".......", "...BBBB", "B..BBBB", "...BBBB", "...BBBB", "...BBBB")
SECOND_TOON = grid(".......", ".BB....", "..BB...", "...BB..", "...BBB.", "...BB..", ".......")
SECOND_TOON_LATER = grid(".......", ".......", ".......", "...BB..", "...BBB.", "...BB..", ".......")


@pytest.mark.parametrize("name,usable", [
    ("battle_gags_1920x1009", SOLO_LURE_USABLE),
    ("battle_gags_1552x578", SOLO_LURE_GRAYED),
    ("battle_gags_435x817", SOLO_LURE_GRAYED),
    ("battle_gags_hover_1920x1009", SOLO_LURE_GRAYED),
    ("battle_gags_hover_1082x464", SOLO_LURE_GRAYED),
    ("battle_gags_hover_435x817", SOLO_LURE_GRAYED),
    ("battle_teammates_1920x1009", WITH_TEAMMATE),
    ("battle_teammates_1071x374", WITH_TEAMMATE),
    ("battle_teammates_397x911", WITH_TEAMMATE),
    ("battle_empty_gag_1920x1009", SECOND_TOON),
    ("battle_empty_gag_1324x554", SECOND_TOON),
    ("battle_empty_gag_570x852", SECOND_TOON_LATER),
])
def test_gag_picker(name, usable):
    screen = replay(name)
    assert screen.kind == "picker"
    assert screen.usable == usable


@pytest.mark.parametrize("name", ["battle_target_cogs_1920x1009", "battle_target_cogs_1071x374",
                                  "battle_target_cogs_316x652"])
def test_two_cog_targets(name):
    screen = replay(name)
    assert screen.kind == "target"
    assert [round(t.x, 2) for t in screen.targets] == [-0.11, 0.11]


@pytest.mark.parametrize("name", ["battle_waiting_1920x1009", "battle_waiting_1082x464", "battle_waiting_316x652"])
def test_waiting(name):
    assert replay(name).kind == "waiting"


@pytest.mark.parametrize("name", ["battle_trunk_1920x1009", "battle_trunk_1433x531", "battle_trunk_216x826"])
def test_trunk(name):
    assert replay(name).kind == "trunk"


@pytest.mark.parametrize("name", ["battle_run_confirm_1904x993", "battle_run_confirm_1433x531",
                                  "battle_run_confirm_814x888"])
def test_run_confirm(name):
    assert replay(name).kind == "confirm_run"


@pytest.mark.parametrize("name", ["test_1920x1009", "speedchat_1920x1009", "options_1920x1009"])
def test_no_battle(name):
    assert replay(name).kind is None


# --- Navigation ---

def test_left_right_skip_unusable():
    usable = SOLO_LURE_GRAYED
    assert move(usable, (3, 0), "right") == (3, 3)  # skips the two grayed Sound gags
    assert move(usable, (3, 3), "left") == (3, 0)
    assert move(usable, (3, 6), "right") == (3, 6)  # edge: stays put


def test_up_down_skip_tracks_with_nothing_usable():
    usable = SOLO_LURE_GRAYED
    assert move(usable, (3, 4), "up") == (3, 4)  # nothing usable above Sound
    assert move(usable, (3, 0), "down") == (4, 3)  # closest usable Throw gag
    assert move(usable, (6, 5), "up") == (5, 5)


def test_nearest_usable_prefers_same_track():
    assert nearest_usable(SOLO_LURE_GRAYED, (4, 3)) == (4, 3)
    assert nearest_usable(SOLO_LURE_GRAYED, (4, 0)) == (4, 3)
    assert nearest_usable(SOLO_LURE_GRAYED, (2, 5)) == (3, 5)
    assert nearest_usable(grid(*["......."] * 7), (0, 0)) is None


# --- Mapper flow ---

PICKER = BattleScreen("picker", usable=SOLO_LURE_GRAYED)
TARGETS = BattleScreen("target", targets=(battle._center(-0.11, -0.0788), battle._center(0.11, -0.0788)))
WAITING = BattleScreen("waiting")


def press(m, screen, t, *buttons):
    """Press buttons at time t and release them a frame later; return all commands."""
    out = m.update(frozenset(buttons), t, screen)
    return out + m.update(frozenset(), t + 0.01, screen)


def test_picker_appears_and_hovers_remembered_gag():
    m = BattleMapper()
    cmds = m.update(frozenset(), 0.0, PICKER)
    assert [(c.kind, c.point) for c in cmds] == [("hover", cell(4, 3))]


def test_navigate_and_select():
    m = BattleMapper()
    m.update(frozenset(), 0.0, PICKER)
    cmds = press(m, PICKER, 1.0, "dpad_right")
    assert cmds[-1].kind == "hover" and cmds[-1].point == cell(4, 4)
    cmds = press(m, PICKER, 2.0, "a")
    assert [(c.kind, c.point) for c in cmds] == [("click", cell(4, 4))]


def test_selection_remembered_next_round():
    m = BattleMapper()
    m.update(frozenset(), 0.0, PICKER)
    press(m, PICKER, 1.0, "dpad_down")
    press(m, PICKER, 2.0, "a")
    m.update(frozenset(), 3.0, WAITING)
    m.update(frozenset(), 4.0, BattleScreen())
    cmds = m.update(frozenset(), 5.0, PICKER)
    assert cmds[0].point == cell(5, 3)


def test_input_ignored_while_screen_settles_after_click():
    m = BattleMapper()
    m.update(frozenset(), 0.0, PICKER)
    press(m, PICKER, 1.0, "a")
    assert press(m, PICKER, 1.05, "dpad_right") == []
    # After settling, whatever screen shows is set up fresh.
    assert m.update(frozenset(), 1.5, WAITING) == []
    assert [c.point for c in m.update(frozenset(), 2.0, PICKER)] == [cell(4, 3)]


def test_stick_repeats_while_held():
    m = BattleMapper()
    m.update(frozenset(), 0.0, PICKER)
    hovers = []
    for i in range(80):  # hold right for 0.8s
        hovers += [c.point for c in m.update(frozenset({"ls_right"}), 1.0 + i * 0.01, PICKER) if c.kind == "hover"]
    assert hovers[:3] == [cell(4, 4), cell(4, 5), cell(4, 6)]


def test_target_choice():
    m = BattleMapper()
    cmds = m.update(frozenset(), 0.0, TARGETS)
    assert cmds == [battle.PointerCommand("hover", TARGETS.targets[0], "target 1")]
    cmds = press(m, TARGETS, 1.0, "dpad_right")
    assert cmds[-1].point == TARGETS.targets[1]
    cmds = press(m, TARGETS, 2.0, "a")
    assert [(c.kind, c.point) for c in cmds] == [("click", TARGETS.targets[1])]


def test_back_buttons():
    m = BattleMapper()
    m.update(frozenset(), 0.0, TARGETS)
    assert [c.point for c in press(m, TARGETS, 1.0, "b")] == [TARGET_BACK]
    m.update(frozenset(), 2.0, WAITING)
    assert [c.point for c in press(m, WAITING, 3.0, "b")] == [WAITING_BACK]


def test_hold_b_runs_x_opens_trunk_y_passes():
    m = BattleMapper()
    m.update(frozenset(), 0.0, PICKER)
    cmds = []
    for i in range(70):
        cmds += m.update(frozenset({"b"}), 1.0 + i * 0.01, PICKER)
    cmds += m.update(frozenset(), 1.8, PICKER)
    assert [c.point for c in cmds if c.kind == "click"] == [RUN]
    assert [c.point for c in press(m, PICKER, 3.0, "x") if c.kind == "click"] == [TRUNK]
    assert [c.point for c in press(m, PICKER, 4.0, "y") if c.kind == "click"] == [battle.PASS]


CONFIRM = BattleScreen("confirm_run")


def test_run_confirm_a_yes_b_cancel():
    m = BattleMapper()
    assert [(c.kind, c.point) for c in m.update(frozenset(), 0.0, CONFIRM)] == [("hover", RUN_YES)]
    assert [c.point for c in press(m, CONFIRM, 1.0, "a")] == [RUN_YES]
    m.update(frozenset(), 2.0, CONFIRM)
    assert [c.point for c in press(m, CONFIRM, 3.0, "b") if c.kind == "click"] == [RUN_NO]


def test_holding_b_to_run_doesnt_also_cancel():
    m = BattleMapper()
    m.update(frozenset(), 0.0, PICKER)
    clicks = []
    for i in range(70):  # B held through the dialog appearing
        screen = PICKER if i < 55 else CONFIRM
        clicks += [c.point for c in m.update(frozenset({"b"}), 1.0 + i * 0.01, screen) if c.kind == "click"]
    clicks += [c.point for c in m.update(frozenset(), 1.8, CONFIRM) if c.kind == "click"]
    assert clicks == [RUN]


def test_b_closes_trunk_back_to_picker():
    m = BattleMapper()
    m.update(frozenset(), 0.0, PICKER)
    assert [c.point for c in press(m, PICKER, 1.0, "x") if c.kind == "click"] == [TRUNK]
    assert m.update(frozenset(), 1.5, BattleScreen("trunk")) == []
    assert [c.point for c in press(m, BattleScreen("trunk"), 2.0, "b")] == [TRUNK]
    assert [c.point for c in m.update(frozenset(), 2.5, PICKER)] == [cell(4, 3)]
