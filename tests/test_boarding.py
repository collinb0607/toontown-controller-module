import pytest
from test_book import replay

from ttcontroller import boarding as bg
from ttcontroller import friends as fr
from ttcontroller.boarding import BoardingMapper, BoardingScreen, read_boarding
from ttcontroller.friends import FriendsMapper, read_friends


@pytest.mark.parametrize("name,kind,members,start", [
    ("boarding_groups_1920x1009", "closed", 0, False),
    ("boarding_groups_hover_1920x1009", "closed", 0, False),  # the tab hovered: lighter blue
    ("boarding_groups_invited_1920x1009", "closed", 0, False),
    ("boarding_groups_empty_1920x1009", "open", 0, True),
    ("boarding_groups_in_a_group_1920x1009", "open", 1, False),
    ("boarding_groups_hover_a_toon_1920x1009", "open", 2, False),  # the second name hovered (yellow)
    ("boarding_groups_kick_1920x1009", "open", 2, False),
    ("clarabelle_popup_1920x1009", None, 0, False),
])
def test_reads_the_panel(name, kind, members, start):
    screen = replay(name, read_boarding)
    assert screen.kind == kind and len(screen.members) == members and (screen.start is not None) == start


def test_member_rows():
    screen = replay("boarding_groups_kick_1920x1009", read_boarding)
    assert [m.to_client(1920, 1009) for m in screen.members] == [(105, 436), (105, 471)]


def step(m, screen, *buttons, at):
    """A press and release, at frame times a tenth of a second apart (as the app calls it,
    so it isn't taken for a resume): `at` counts presses, not seconds."""
    t = at * 0.2
    out = m.update(frozenset(buttons), t, screen)
    return out + m.update(frozenset(), t + 0.1, screen)


def names(commands):
    return [(c.kind, c.name) for c in commands]


def test_right_stick_opens_and_closes():
    m = BoardingMapper()
    closed = replay("boarding_groups_1920x1009", read_boarding)
    assert m.buttons(closed) == {"rs_right"}
    out = step(m, closed, "rs_right", at=0.0)
    assert names(out) == [("click", "open boarding group")] and out[0].point == bg.TAB
    opened = replay("boarding_groups_in_a_group_1920x1009", read_boarding)
    assert "a" not in m.buttons(opened)  # nothing hovered yet: A still jumps
    assert names(step(m, opened, "rs_left", at=1.0)) == [("click", "close boarding group")]


def test_dpad_hovers_members_and_a_opens_their_panel():
    m = BoardingMapper()
    screen = replay("boarding_groups_kick_1920x1009", read_boarding)
    m.update(frozenset(), 0.0, screen)
    assert not m.hovering(screen)
    assert names(step(m, screen, "dpad_down", at=1.0)) == [("hover", "boarding group 1")]
    assert names(step(m, screen, "dpad_down", at=2.0)) == [("hover", "boarding group 2")]
    assert names(step(m, screen, "dpad_down", at=3.0)) == [("hover", "boarding group 2")]  # the last one
    assert "a" in m.buttons(screen) and m.hovering(screen)
    out = step(m, screen, "a", at=4.0)
    assert names(out) == [("click", "boarding member 2")] and out[0].point.to_client(1920, 1009) == (105, 471)


def test_start_a_group_is_hovered_as_soon_as_it_opens():
    m = BoardingMapper()
    closed = replay("boarding_groups_1920x1009", read_boarding)
    screen = replay("boarding_groups_empty_1920x1009", read_boarding)
    m.update(frozenset(), 0.0, closed)
    out = m.update(frozenset(), 0.1, screen)  # just opened: A starts a group straight away
    assert names(out) == [("hover", "boarding group 1")] and out[0].point == screen.start
    assert "a" in m.buttons(screen)
    out = step(m, screen, "a", at=1.0)
    assert names(out) == [("click", "start a group")] and out[0].point == screen.start


def test_holding_b_leaves():
    m = BoardingMapper()
    screen = replay("boarding_groups_in_a_group_1920x1009", read_boarding)
    for t in (0.0, 0.1, 0.2, 0.3):
        assert m.update(frozenset({"b"}), t, screen) == []  # a tap isn't enough
    m.update(frozenset({"b"}), 0.4, screen)
    out = m.update(frozenset({"b"}), 0.5, screen)
    assert names(out) == [("click", "leave boarding group")] and out[0].point == screen.leave
    assert m.update(frozenset({"b"}), 0.6, screen) == []  # once per hold
    # Nothing to leave with no group.
    empty = replay("boarding_groups_empty_1920x1009", read_boarding)
    m2 = BoardingMapper()
    out = []
    for t in range(8):
        out += m2.update(frozenset({"b"}), t * 0.1, empty)
    assert "leave boarding group" not in [c.name for c in out]


def test_closing_forgets_the_hover():
    m = BoardingMapper()
    opened = replay("boarding_groups_in_a_group_1920x1009", read_boarding)
    step(m, opened, "dpad_down", at=0.0)
    assert m.item == 0
    m.update(frozenset(), 0.6, BoardingScreen("closed"))  # put away
    m.update(frozenset(), 0.7, opened)
    assert m.item is None


def test_coming_back_from_something_else_carries_on():
    # A member's toon panel (or the gags, a dialog) had the controls: the panel's still out,
    # so the D-pad works there again, back on the same member, without reopening it.
    m = BoardingMapper()
    screen = replay("boarding_groups_kick_1920x1009", read_boarding)
    step(m, screen, "dpad_down", at=0)
    step(m, screen, "dpad_down", at=1)
    m.update(frozenset({"a"}), 0.4, screen)  # A opens their panel; the friends list takes over
    # ... a while later, the toon's panel closed (A was let go meanwhile):
    out = m.update(frozenset(), 5.0, screen)
    assert names(out) == [("hover", "boarding group 2")]
    assert names(m.update(frozenset({"dpad_up"}), 5.1, screen)) == [("hover", "boarding group 1")]
    # Covered for a moment (not read at all) doesn't put it away either.
    m.update(frozenset(), 5.2, BoardingScreen())
    m.update(frozenset(), 5.3, screen)
    assert m.item == 0


def test_start_a_group_again_after_something_else():
    m = BoardingMapper()
    screen = replay("boarding_groups_empty_1920x1009", read_boarding)
    m.update(frozenset(), 0.0, screen)
    out = m.update(frozenset(), 3.0, screen)  # back from the gags or a toon's panel
    assert names(out) == [("hover", "boarding group 1")] and out[0].point == screen.start
    # A held from before the gap isn't a fresh press; a new one is.
    m.update(frozenset({"a"}), 3.1, screen)
    m2 = BoardingMapper()
    m2.update(frozenset({"a"}), 0.0, screen)
    assert "start a group" not in [c.name for c in m2.update(frozenset({"a"}), 3.0, screen)]


# The toon panel's Boarding Group section, and the invite popups.

def test_toon_panel_invite_and_kick_join_the_list():
    for name in ("boarding_groups_invite_1920x1009", "boarding_groups_kick_1920x1009"):
        screen = replay(name, read_friends)
        assert screen.kind == "panel" and screen.boarding
        # Last, below Toon Details: the order they're in going down.
        assert fr.panel_buttons(screen)[-2:] == (fr.PANEL_BUTTONS[-1], (fr.BOARDING, "invite or kick"))
    assert not replay("friends_detail_1920x1009", read_friends).boarding
    m = FriendsMapper()
    screen = replay("boarding_groups_invite_1920x1009", read_friends)
    m.update(frozenset(), 0.0, screen)
    for t in range(1, 7):
        m.update(frozenset({"dpad_down"}), float(t), screen)
        m.update(frozenset(), t + 0.05, screen)
    out = m.update(frozenset({"a"}), 8.0, screen)
    assert [(c.kind, c.point) for c in out] == [("click", fr.BOARDING)]


def test_invite_popups():
    invited = replay("boarding_groups_invited_1920x1009", read_friends)
    assert invited.popup == "friend request"  # OK and No, like a friend request
    assert invited.yes.to_client(1920, 1009) == (1145, 189) and invited.no.to_client(1920, 1009) == (1228, 189)
    inviting = replay("boarding_groups_inviting_1920x1009", read_friends)
    assert inviting.popup == "cancel" and inviting.yes is None
    assert inviting.no.to_client(1920, 1009) == (1186, 186)


def test_declined_popup_a_or_b_ok():
    screen = replay("boarding_groups_declined_1920x1009", read_friends)
    assert screen.popup == "OK" and screen.yes == screen.no
    assert screen.yes.to_client(1920, 1009) == (1186, 185)
    for button in ("a", "b"):
        m = FriendsMapper()
        m.update(frozenset(), 0.0, screen)
        out = m.update(frozenset({button}), 1.0, screen)
        assert [(c.kind, c.point) for c in out] == [("click", screen.yes)]


@pytest.mark.parametrize("name,size,member,tab,leave,invite", [
    ("boarding_groups_resized_1502x520", (1502, 520), (54, 225), (6, 248), (140, 296), (1446, 295)),
    ("boarding_groups_resized_2_871x939", (871, 939), (91, 410), (10, 450), (235, 530), (778, 494)),
])
def test_other_window_sizes(name, size, member, tab, leave, invite):
    # Anchored to the left edge and the middle (the panel), and the right edge and top (the toon panel).
    screen = replay(name, read_boarding)
    assert screen.kind == "open" and len(screen.members) == 1
    mx, my = screen.members[0].to_client(*size)
    assert abs(mx - member[0]) <= 2 and abs(my - member[1]) <= 2
    lx, ly = screen.leave.to_client(*size)
    assert bg.TAB.to_client(*size) == tab and abs(lx - leave[0]) <= 2 and abs(ly - leave[1]) <= 4
    panel = replay(name, read_friends)
    assert panel.kind == "panel" and panel.boarding and fr.BOARDING.to_client(*size) == invite


def test_cancel_alone_dialog():
    from ttcontroller.dialog import find_cancel_alone, find_ok_cancel
    point = replay("boarding_groups_restricted_popup_1920x1009", find_cancel_alone)
    assert point is not None and abs(point.to_client(1920, 1009)[0] - 958) <= 2
    assert abs(point.to_client(1920, 1009)[1] - 645) <= 4
    # Not an OK/Cancel one, and an OK/Cancel one isn't a lone Cancel.
    assert replay("boarding_groups_restricted_popup_1920x1009", find_ok_cancel) is None
    assert replay("boarding_groups_quit_popup_1920x1009", find_cancel_alone) is None
    assert replay("clarabelle_popup_1920x1009", find_cancel_alone) is None


def test_rt_invites():
    panel = replay("boarding_groups_invite_1920x1009", read_friends)
    # On a toon's panel: straight away.
    m = FriendsMapper()
    m.update(frozenset(), 0.0, panel)
    out = m.update(frozenset({"rt"}), 1.0, panel)
    assert [(c.kind, c.point) for c in out] == [("click", fr.BOARDING)]
    # Not without the Boarding Group section.
    plain = replay("friends_detail_1920x1009", read_friends)
    m = FriendsMapper()
    m.update(frozenset(), 0.0, plain)
    assert m.update(frozenset({"rt"}), 1.0, plain) == []
    # On the list: open the toon, then Invite once their panel shows it.
    from ttcontroller.friends import FriendsScreen
    listed = FriendsScreen("list", rows=(fr._row(0),))
    m = FriendsMapper()
    m.update(frozenset(), 0.0, listed)
    out = m.update(frozenset({"rt"}), 1.0, listed)
    assert [c.name for c in out] == ["open friend 1"]
    out = m.update(frozenset(), 1.6, panel)
    assert [(c.kind, c.point) for c in out][:1] == [("click", fr.BOARDING)]
    assert fr.BOARDING not in [c.point for c in m.update(frozenset(), 2.5, panel)]  # once


@pytest.mark.parametrize("name,start,leave", [
    ("boarding_groups_empty_1920x1009", (160, 514), (272, 575)),  # a facility's: 4 toons
    ("boarding_groups_8_toons_1920x1009", (160, 489), (272, 647)),  # a boss's: 8 toons, a taller panel
])
def test_the_panel_grows_with_the_group_size(name, start, leave):
    screen = replay(name, read_boarding)
    assert screen.kind == "open" and screen.start is not None
    sx, sy = screen.start.to_client(1920, 1009)
    lx, ly = screen.leave.to_client(1920, 1009)
    assert abs(sx - start[0]) <= 2 and abs(sy - start[1]) <= 3
    assert abs(lx - leave[0]) <= 2 and abs(ly - leave[1]) <= 4


def test_leave_goes_where_the_panel_says():
    m = BoardingMapper()
    screen = replay("boarding_groups_in_a_group_1920x1009", read_boarding)
    out = []
    for t in range(8):
        out += m.update(frozenset({"b"}), t * 0.1, screen)
    [click] = [c for c in out if c.name == "leave boarding group"]
    assert click.point == screen.leave
