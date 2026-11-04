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


# --- M4.2: teammates, toon targets, trunk ---

@pytest.mark.parametrize("name,xs", [
    ("battle_teammates_1920x1009", [-0.093]),
    ("battle_teammates_397x911", [-0.06]),
    ("battle_teammates_2_1448x415", [-0.093]),
    ("battle_teammates_2_216x826", [-0.06]),
    ("battle_teammates_3_1920x1009", [-0.242, 0.034]),
    ("battle_teammates_3_673x907", [-0.171, 0.034]),
    ("battle_teammates_4_1283x307", [-0.343, -0.091, 0.16]),
    ("battle_teammates_4_1920x1009", [-0.343, -0.091, 0.16]),
    ("battle_teammates_4_673x907", [-0.246, -0.06, 0.128]),
    ("battle_gags_1920x1009", []),  # solo
])
def test_teammate_choices(name, xs):
    """Teammates who picked a gag, left to right. Your own "?" circle is skipped."""
    screen = replay(name)
    assert screen.kind == "picker"
    assert [round(t.x, 3) for t in screen.teammates] == xs


@pytest.mark.parametrize("name,count", [
    ("battle_target_toons_2_1920x1009", 1), ("battle_target_toons_2_406x885", 1),
    ("battle_target_toons_3_1273x318", 2), ("battle_target_toons_3_393x879", 2),
    ("battle_target_toons_4_1920x1009", 3), ("battle_target_toons_4_1283x307", 3),
])
def test_toon_targets(name, count):
    screen = replay(name)
    assert screen.kind == "target"
    assert len(screen.targets) == count


@pytest.mark.parametrize("name", ["battle_trunk_after_pinkslips_1920x1009", "battle_trunk_after_remotes_1920x1009"])
def test_trunk_items_lead_to_cog_choice(name):
    assert len(replay(name).targets) == 1


def content(screen):
    return [i.name for i in screen.items if not i.tab]


@pytest.mark.parametrize("name", ["battle_trunk_1920x1009", "battle_trunk_1433x531"])
def test_trunk_sos_cards(name):
    screen = replay(name)
    assert screen.tab == "SOS"
    assert len(content(screen)) == 8


def test_trunk_skips_unavailable_and_cut_off_sos_cards():
    assert content(replay("battle_trunk_sos_more_1920x1009")) == [
        "SOS card 1 at -0.17", "SOS card 1 at 0.01", "SOS card 3 at -0.17", "SOS card 3 at 0.01", "SOS card 4 at -0.17"]


@pytest.mark.parametrize("name", ["battle_trunk_remotes_1920x1009", "battle_trunk_remotes_hover_single_1920x1009"])
def test_trunk_remotes(name):
    screen = replay(name)
    assert screen.tab == "remotes"
    assert content(screen) == ["healing remote 1"]


@pytest.mark.parametrize("name", ["battle_trunk_doodle_1920x1009", "battle_trunk_doodle_hover_1920x1009"])
def test_trunk_doodle(name):
    screen = replay(name)
    assert screen.tab == "doodle"
    assert content(screen) == [f"doodle trick {i}" for i in range(1, 6)]


def test_lb_toggles_teammate_hover():
    screen = replay("battle_teammates_4_1920x1009")
    m = BattleMapper()
    m.update(frozenset(), 0.0, screen)
    assert press(m, screen, 1.0, "lb")[-1].point == screen.teammates[0]
    assert press(m, screen, 2.0, "dpad_right")[-1].point == screen.teammates[1]
    assert press(m, screen, 3.0, "ls_right")[-1].point == screen.teammates[2]
    assert press(m, screen, 4.0, "dpad_right")[-1].point == screen.teammates[2]  # stays at the end
    assert press(m, screen, 5.0, "dpad_up") == []
    assert press(m, screen, 6.0, "lb")[-1].point == cell(4, 3)  # back to your gags
    assert press(m, screen, 7.0, "dpad_right")[-1].point == cell(4, 4)
    press(m, screen, 8.0, "lb")
    assert [c.kind for c in press(m, screen, 9.0, "a")] == ["hover"]  # A leaves too, without clicking
    assert [c.kind for c in press(m, screen, 10.0, "a")] == ["click"]


def test_rb_is_left_for_the_friends_list():
    assert "rb" not in BattleMapper().buttons


def test_lb_does_nothing_when_solo():
    m = BattleMapper()
    m.update(frozenset(), 0.0, PICKER)
    assert press(m, PICKER, 1.0, "lb") == []


def test_trunk_navigation():
    sos = replay("battle_trunk_1920x1009")
    m = BattleMapper()
    assert [c.name for c in m.update(frozenset(), 0.0, sos)] == ["SOS card 1 at -0.04"]
    assert press(m, sos, 1.0, "dpad_right")[-1].name == "SOS card 2 at -0.04"
    assert press(m, sos, 2.0, "dpad_down")[-1].name == "SOS card 2 at 0.14"
    press(m, sos, 3.0, "dpad_left")
    assert press(m, sos, 4.0, "dpad_left")[-1].name == "tab doodle"  # into the tab list, level with the card
    assert press(m, sos, 5.0, "dpad_up")[-1].name == "tab remotes"
    assert [(c.kind, c.name) for c in press(m, sos, 6.0, "a")] == [("click", "tab remotes")]
    remotes = replay("battle_trunk_remotes_1920x1009")
    assert [c.name for c in m.update(frozenset(), 7.0, remotes)] == ["tab remotes"]  # stays on the tabs
    assert press(m, remotes, 8.0, "dpad_right")[-1].name == "healing remote 1"
    assert [c.point for c in press(m, remotes, 9.0, "b")] == [TRUNK]


def test_sos_scrolls_past_the_last_visible_card():
    sos = replay("battle_trunk_1920x1009")
    m = BattleMapper()
    m.update(frozenset(), 0.0, sos)
    press(m, sos, 1.0, "dpad_down")
    cmds = press(m, sos, 2.0, "dpad_down")
    assert [(c.kind, c.notches) for c in cmds] == [("scroll", -battle.SOS_SCROLL_NOTCHES)]
    # Not quite a row: the bottom row moved up to -0.01, the next one is still cut off.
    def cards(*ys):
        return BattleScreen("trunk", tab="SOS", items=tuple(
            battle.Item(f"SOS card 1 at {y:.2f}", battle._center(battle._SOS_CALL_XS[0], y)) for y in ys))
    assert [(c.kind, c.notches) for c in m.update(frozenset(), 3.0, cards(-0.01))] == [("scroll", -1)]
    # One more notch brings the next row fully into view: highlight it.
    assert [c.name for c in m.update(frozenset(), 4.0, cards(-0.025, 0.155))] == ["SOS card 1 at 0.15"]
    assert m._scrolling is None


def test_sos_scroll_stops_at_the_end_of_the_list():
    sos = replay("battle_trunk_1920x1009")
    m = BattleMapper()
    m.update(frozenset(), 0.0, sos)
    press(m, sos, 1.0, "dpad_down")
    press(m, sos, 2.0, "dpad_down")
    # Nothing moved: stay on the same card without more scrolling.
    assert [c.name for c in m.update(frozenset(), 3.0, sos)] == ["SOS card 1 at 0.14"]


def test_sos_scroll_gives_up_after_the_extra_notches():
    sos = replay("battle_trunk_1920x1009")
    m = BattleMapper()
    m.update(frozenset(), 0.0, sos)
    press(m, sos, 1.0, "dpad_down")
    press(m, sos, 2.0, "dpad_down")
    # A row of only unavailable cards scrolls in: no usable card turns up.
    top = BattleScreen("trunk", tab="SOS", items=tuple(i for i in sos.items if i.tab or "-0.04" in i.name))
    t = 3.0
    for _ in range(battle.SOS_EXTRA_NOTCHES):
        assert [c.kind for c in m.update(frozenset(), t, top)] == ["scroll"]
        t += 1.0
    assert [c.name for c in m.update(frozenset(), t, top)] == ["SOS card 1 at -0.04"]


def circle(x):
    return battle._center(x, 0.412)


def test_waiting_hovers_teammates_but_not_your_own_choice():
    picker = BattleScreen("picker", usable=SOLO_LURE_GRAYED, teammates=(circle(-0.3),),
                          unpicked=(circle(0.0), circle(0.3)))
    m = BattleMapper()
    m.update(frozenset(), 0.0, picker)
    press(m, picker, 1.0, "a")
    # You picked (the middle circle); the right-hand teammate is still choosing.
    waiting = BattleScreen("waiting", teammates=(circle(-0.3), circle(0.0)), unpicked=(circle(0.3),))
    assert [c.point for c in m.update(frozenset(), 2.0, waiting)] == [circle(-0.3)]
    assert press(m, waiting, 3.0, "dpad_right")[-1].point == circle(-0.3)  # yours is skipped
    assert press(m, waiting, 4.0, "lb") == []  # LB does nothing here
    # The last teammate picks: now there are two to look at.
    later = BattleScreen("waiting", teammates=(circle(-0.3), circle(0.0), circle(0.3)))
    assert press(m, later, 5.0, "dpad_right")[-1].point == circle(0.3)
    assert [c.point for c in press(m, later, 6.0, "b")] == [WAITING_BACK]


def test_waiting_starts_hovering_when_the_first_teammate_picks():
    picker = BattleScreen("picker", usable=SOLO_LURE_GRAYED, unpicked=(circle(-0.1), circle(0.1)))
    m = BattleMapper()
    m.update(frozenset(), 0.0, picker)
    press(m, picker, 1.0, "a")
    alone = BattleScreen("waiting", teammates=(circle(0.1),), unpicked=(circle(-0.1),))
    assert m.update(frozenset(), 2.0, alone) == []  # only your own choice so far
    both = BattleScreen("waiting", teammates=(circle(-0.1), circle(0.1)))
    assert [c.point for c in m.update(frozenset(), 3.0, both)] == [circle(-0.1)]


def test_waiting_capture_finds_both_circles():
    screen = replay("battle_waiting_1920x1009")
    assert screen.kind == "waiting"
    assert len(screen.teammates) == 1 and len(screen.unpicked) == 1


def test_targets_wrap_and_survive_the_hovered_arrow_dropping_out():
    three = tuple(battle._center(x, battle.TOON_ARROW_ROW) for x in (-0.316, -0.1, 0.098))
    full = BattleScreen("target", targets=three)
    m = BattleMapper()
    assert [c.point for c in m.update(frozenset(), 0.0, full)] == [three[0]]
    # The lit-up arrow under the cursor isn't found on the next read.
    without_hovered = BattleScreen("target", targets=three[1:])
    assert press(m, without_hovered, 1.0, "dpad_right")[-1].point == three[1]
    assert press(m, BattleScreen("target", targets=(three[0], three[2])), 2.0, "dpad_right")[-1].point == three[2]
    assert press(m, full, 3.0, "dpad_right")[-1].point == three[0]  # wraps to the left end
    assert press(m, full, 4.0, "dpad_left")[-1].point == three[2]  # and back the other way
    assert [c.point for c in press(m, without_hovered, 5.0, "a")] == [three[2]]


def test_trunk_moves_from_a_hovered_item_missing_from_the_read():
    sos = replay("battle_trunk_1920x1009")
    m = BattleMapper()
    m.update(frozenset(), 0.0, sos)  # hovers SOS card 1 at -0.04
    missing = BattleScreen("trunk", tab="SOS", items=tuple(i for i in sos.items if i.name != "SOS card 1 at -0.04"))
    assert press(m, missing, 1.0, "dpad_right")[-1].name == "SOS card 2 at -0.04"


def test_sos_finds_every_call_button_in_a_short_row():
    """Regression: card 4's CALL was missed, so right from card 3 went nowhere."""
    sos = replay("battle_trunk_sos_five_1920x1009")
    assert len(content(sos)) == 5
    m = BattleMapper()
    m.trunk_item = next(i for i in sos.items if i.name.startswith("SOS card 3"))
    m.update(frozenset(), 0.0, sos)
    assert press(m, sos, 1.0, "dpad_right")[-1].name.startswith("SOS card 4")
