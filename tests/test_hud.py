from test_book import replay

from ttcontroller.book import GAG_SIZE
from ttcontroller.hud import TO_GAGS, TO_TRUNK, HudMapper, HudScreen, read_hud
from ttcontroller.mapper import OverworldMapper
from ttcontroller.controller import ControllerState

SIZE = (1920, 1009)


def at(point):
    return point.to_client(*SIZE)


def near(point, x, y, tolerance=4):
    px, py = at(point)
    return abs(px - x) <= tolerance and abs(py - y) <= tolerance


def test_reads_each_hud():
    gags = replay("gags_hud_1920x1009", read_hud)
    assert gags.kind == "gags"
    assert sum(map(sum, gags.gags)) == 42  # every track but Trap
    assert not any(gags.gags[1])
    trunk = replay("trunk_hud_1920x1009", read_hud)
    assert trunk.kind == "trunk" and trunk.trunk.tab == "SOS"
    assert sum(i.name.startswith("SOS card") for i in trunk.trunk.items) == 8
    # Filtered to Toon-Up, in a sunny playground.
    filtered = replay("trunk_hud_2_1920x1009", read_hud)
    assert filtered.kind == "trunk" and filtered.trunk.tab == "SOS"
    tasks = replay("tasks_hud_1920x1009", read_hud)
    assert tasks.kind == "tasks" and all(t is not None for t in tasks.tasks)


def test_nothing_on_a_plain_screen():
    assert read_hud(1920, 1009, lambda x, y: (90, 70, 50)) == HudScreen()


def press(m, screen, button, now):
    commands = m.update(frozenset({button}), now, screen)
    m.update(frozenset(), now + 0.05, screen)
    return commands


def test_gags_start_with_nothing_hovered_then_the_cupcake():
    screen = replay("gags_hud_1920x1009", read_hud)
    m = HudMapper()
    assert m.update(frozenset(), 0.0, screen) == []
    commands = press(m, screen, "dpad_right", 1.0)
    assert len(commands) == 1 and commands[0].kind == "hover" and commands[0].size == GAG_SIZE
    assert near(commands[0].point, 775, 492)  # Throw's first gag, on the HUD
    commands = press(m, screen, "dpad_right", 2.0)
    assert near(commands[0].point, 862, 492)


def test_the_right_stick_switches_gags_and_trunk():
    gags = replay("gags_hud_1920x1009", read_hud)
    trunk = replay("trunk_hud_1920x1009", read_hud)
    m = HudMapper()
    assert [c.point for c in press(m, gags, "rs_left", 0.0)] == []
    assert [(c.kind, c.point) for c in press(m, gags, "rs_right", 1.0)] == [("click", TO_TRUNK)]
    assert near(TO_TRUNK, 1370, 446)
    clicks = lambda commands: [(c.kind, c.point) for c in commands if c.kind == "click"]
    assert clicks(press(m, trunk, "rs_right", 2.0)) == []
    assert clicks(press(m, trunk, "rs_left", 3.0)) == [("click", TO_GAGS)]
    assert near(TO_GAGS, 557, 426)


def test_tasks_hover_each_scroll():
    screen = replay("tasks_hud_1920x1009", read_hud)
    m = HudMapper()
    m.update(frozenset(), 0.0, screen)
    first = press(m, screen, "dpad_down", 1.0)
    assert near(first[0].point, 733, 356)  # the top-left scroll, lifted
    second = press(m, screen, "dpad_right", 2.0)
    assert near(second[0].point, 1190, 356)
    third = press(m, screen, "dpad_down", 3.0)
    assert near(third[0].point, 1190, 659)


def test_the_trunk_hovers_like_the_books_and_a_clicks():
    screen = replay("trunk_hud_1920x1009", read_hud)
    m = HudMapper()
    shown = m.update(frozenset(), 0.0, screen)
    assert shown and shown[0].kind == "hover"  # as the book's Trunk tab does
    assert {"a", "ls", "rs_up", "rs_down", "dpad_up", "rs_left"} <= m.buttons(screen)  # SOS cards scroll
    hover = press(m, screen, "dpad_down", 1.0)
    assert hover and hover[0].kind == "hover" and hover[0].point != shown[0].point
    click = press(m, screen, "a", 2.0)
    assert click and click[0].kind == "click" and click[0].point == hover[0].point


def test_ls_cycles_the_sos_filter_on_the_trunk():
    screen = replay("trunk_hud_1920x1009", read_hud)
    m = HudMapper()
    m.update(frozenset(), 0.0, screen)
    commands = press(m, screen, "ls", 1.0)
    assert [c.name for c in commands if c.kind == "click"] == ["SOS filter", "filter Restock"]  # the next after All


def test_gags_and_tasks_leave_the_right_stick_looking_up_and_down():
    screen = replay("gags_hud_1920x1009", read_hud)
    assert not {"rs_up", "rs_down", "a", "ls"} & HudMapper().buttons(screen)  # LS still sprints
    assert HudMapper().buttons(HudScreen()) == frozenset()


def test_the_overworld_mapper_says_which_huds_are_toggled_up():
    m = OverworldMapper(toggle_show=True)
    m.update(ControllerState(buttons=frozenset({"y"})), 0.0)
    m.update(ControllerState(), 0.1)
    assert m.shown == {"showGags"}
    m.update(ControllerState(buttons=frozenset({"y"})), 0.2)
    m.update(ControllerState(), 0.3)
    assert m.shown == frozenset()


def test_a_scrolled_trunk_hud_is_not_the_battle_waiting_screen():
    # Its white SOS cards cover every spot the waiting screen is told by.
    from ttcontroller.battle import read_screen
    assert replay("trunk_hud_bug_1920x1009", read_screen).kind is None
    screen = replay("trunk_hud_bug_1920x1009", read_hud)
    assert screen.kind == "trunk" and screen.trunk.can_scroll == (True, True)
