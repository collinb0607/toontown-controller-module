import json
from pathlib import Path

import pytest

from ttcontroller import friends as f, ui
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



def test_holding_at_the_end_of_the_list_holds_the_triangle_down():
    m = FriendsMapper()
    screen = full_list()
    m.update(frozenset(), 0.0, screen)
    up = frozenset({"dpad_up"})
    assert [c.kind for c in m.update(up, 1.0, screen)] == ["click", "hover"]
    [hold] = m.update(up, 1.45, screen)
    assert hold.kind == "hold" and hold.point == f.SCROLL_UP
    assert m.update(up, 2.0, screen) == []
    release, hover = m.update(frozenset(), 3.0, screen)
    assert release.kind == "release" and (hover.kind, hover.point) == ("hover", screen.rows[0])


def test_reads_go_tos_teleport_popup_over_the_panel():
    screen = replay("friends_teleport_popup_1920x1009")
    assert screen.kind == "popup" and screen.popup == "yes/no"
    yes, no = (p.to_client(1920, 1009) for p in (screen.yes, screen.no))
    assert abs(yes[0] - 1334) <= 3 and abs(yes[1] - 250) <= 3
    assert abs(no[0] - 1485) <= 3 and abs(no[1] - 251) <= 3


def test_reads_the_plus_one_invite_over_the_panel():
    # Invite on the Boarding Group section for a +1: a centered Yes/No.
    screen = replay("boarding_groups_plus_one_invite_popup_1920x1009")
    assert screen.kind == "popup" and screen.popup == "yes/no"
    yes, no = (p.to_client(1920, 1009) for p in (screen.yes, screen.no))
    assert abs(yes[0] - 904) <= 4 and abs(yes[1] - 643) <= 4
    assert abs(no[0] - 1014) <= 4 and abs(no[1] - 643) <= 4


@pytest.mark.parametrize("button,answer", [("a", "yes"), ("b", "no")])
def test_teleport_popup_a_yes_b_no_then_back_to_go_to(button, answer):
    m = FriendsMapper()
    panel = FriendsScreen("panel")
    popup = FriendsScreen("popup", yes=f._right(-0.58, 0.25), no=f._right(-0.43, 0.25), popup="yes/no")
    m.update(frozenset(), 0.0, panel)
    press(m, panel, 1.0, "dpad_down")
    press(m, panel, 2.0, "a")  # Go To
    assert m.update(frozenset(), 3.0, popup) == []  # nothing hovered over the popup
    assert press(m, popup, 4.0, "dpad_down") == []
    clicked = press(m, popup, 5.0, button)
    assert [c.point for c in clicked] == [popup.yes if answer == "yes" else popup.no]
    assert [c.point for c in m.update(frozenset(), 6.0, panel)] == [f.GO_TO]


def test_reads_a_whisper_open_over_the_toon_panel():
    screen = replay("friends_whisper_popup_1920x1009")
    assert screen.kind == "panel" and screen.whisper
    assert not replay("friends_detail_1920x1009").whisper


def test_b_ends_the_whisper_first_and_stays_on_the_same_button():
    m = FriendsMapper()
    screen = FriendsScreen("panel", whisper=True)
    m.update(frozenset(), 0.0, screen)
    press(m, screen, 1.0, "dpad_down")
    press(m, screen, 2.0, "dpad_down")
    assert [c.point for c in press(m, screen, 3.0, "b")] == [ui.WHISPER_CLOSE.center, f.WHISPER]
    assert [c.point for c in press(m, FriendsScreen("panel"), 4.0, "b")] == [f.PANEL_CLOSE]


def test_b_ends_the_whisper_over_the_list_too():
    m = FriendsMapper()
    screen = FriendsScreen("list", rows=(f._row(0), f._row(1)), whisper=True)
    m.update(frozenset(), 0.0, screen)
    assert [c.point for c in press(m, screen, 1.0, "b")] == [ui.WHISPER_CLOSE.center, f._row(0)]


@pytest.mark.parametrize("name,popup,yes,no", [
    ("friends_friends_popup_1920x1009", "already friends", (1298, 153), (1398, 225)),  # Stop, Cancel
    ("friends_friends_popup_confirmation_1920x1009", "yes/no", (1322, 224), (1474, 225)),
])
def test_reads_the_unfriend_popups(name, popup, yes, no):
    screen = replay(name)
    assert screen.kind == "popup" and screen.popup == popup
    for point, (x, y) in ((screen.yes, yes), (screen.no, no)):
        px, py = point.to_client(1920, 1009)
        assert abs(px - x) <= 3 and abs(py - y) <= 3


def test_unfriending_a_stops_then_a_confirms_and_b_backs_out_to_friends():
    m = FriendsMapper()
    panel = FriendsScreen("panel")
    stop = FriendsScreen("popup", yes=f._right(-0.6, 0.15), no=f._right(-0.5, 0.22), popup="already friends")
    sure = FriendsScreen("popup", yes=f._right(-0.58, 0.22), no=f._right(-0.43, 0.22), popup="yes/no")
    m.update(frozenset(), 0.0, panel)
    assert [c.point for c in press(m, panel, 1.0, "a")] == [f.FRIEND]
    m.update(frozenset(), 2.0, stop)
    assert [c.point for c in press(m, stop, 3.0, "a")] == [stop.yes]  # Stop being Toon friends
    m.update(frozenset(), 4.0, sure)
    assert [c.point for c in press(m, sure, 5.0, "b")] == [sure.no]  # No
    assert [c.point for c in m.update(frozenset(), 6.0, panel)] == [f.FRIEND]
    press(m, panel, 7.0, "a")
    m.update(frozenset(), 8.0, stop)
    assert [c.point for c in press(m, stop, 9.0, "b")] == [stop.no]  # Cancel
    assert [c.point for c in m.update(frozenset(), 10.0, panel)] == [f.FRIEND]


@pytest.mark.parametrize("name,popup,yes,no", [
    ("friends_friends_popup_ending_1920x1009", "OK", (1398, 224), (1398, 224)),  # A or B: OK
    ("friends_friend_requester_popup_1920x1009", "cancel", None, (1398, 225)),  # only B: Cancel
    ("friends_friend_request_popup_1920x1009", "friend request", (1144, 177), (1228, 177)),  # OK, No
])
def test_reads_the_other_friend_popups(name, popup, yes, no):
    screen = replay(name)
    assert screen.kind == "popup" and screen.popup == popup
    for point, expected in ((screen.yes, yes), (screen.no, no)):
        if expected is None:
            assert point is None
            continue
        px, py = point.to_client(1920, 1009)
        assert abs(px - expected[0]) <= 3 and abs(py - expected[1]) <= 3


def test_a_does_nothing_on_a_cancel_only_popup():
    m = FriendsMapper()
    popup = FriendsScreen("popup", no=f._right(-0.5, 0.22), popup="cancel")
    m.update(frozenset(), 0.0, popup)
    assert press(m, popup, 1.0, "a") == []
    assert [c.point for c in press(m, popup, 2.0, "b")] == [popup.no]


def test_a_or_b_clicks_ok_on_an_ok_only_popup():
    for button in ("a", "b"):
        m = FriendsMapper()
        popup = FriendsScreen("popup", yes=f._right(-0.5, 0.22), no=f._right(-0.5, 0.22), popup="OK")
        m.update(frozenset(), 0.0, popup)
        assert [c.point for c in press(m, popup, 1.0, button)] == [popup.yes]


def replay_dialogs(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    return read_friends(w, h, lambda x, y: tuple(pixels[f"{x},{y}"]), dialogs=True)


@pytest.mark.parametrize("name,yes,no,reasons", [
    ("friends_ignore_1920x1009", (904, 634), (1015, 638), 0),  # Ignore, Cancel
    ("friends_stop_ignoring_1920x1009", (858, 604), (1060, 604), 0),  # Stop Ignoring, Cancel
    ("friends_ignore_a_friend_1920x1009", None, (959, 619), 0),  # Cancel only
    ("friends_report_reason_1920x1009", None, (959, 780), 5),  # five reasons, Cancel
])
def test_reads_ignore_and_report_dialogs(name, yes, no, reasons):
    screen = replay_dialogs(name)
    assert screen.kind == "popup" and screen.popup == "dialog"
    for point, expected in ((screen.yes, yes), (screen.no, no)):
        if expected is None:
            assert point is None
            continue
        px, py = point.to_client(1920, 1009)
        assert abs(px - expected[0]) <= 3 and abs(py - expected[1]) <= 3
    assert len(screen.options) == reasons
    # Not looked for unless Ignore or Report was just pressed (other dialogs look the same).
    assert replay(name).kind is None


def test_report_reasons_start_unhovered_then_d_pad_and_a():
    m = FriendsMapper()
    reasons = tuple(f._right(-0.95, 0.4 + 0.06 * i) for i in range(5))
    popup = FriendsScreen("popup", no=f._right(-0.95, 0.8), popup="dialog", options=reasons)
    assert m.update(frozenset(), 0.0, popup) == []
    assert press(m, popup, 1.0, "a") == []  # nothing hovered yet
    assert [c.point for c in press(m, popup, 2.0, "dpad_down")] == [reasons[0]]
    assert [c.point for c in press(m, popup, 3.0, "dpad_down")] == [reasons[1]]
    assert [c.point for c in press(m, popup, 4.0, "dpad_up")] == [reasons[0]]
    assert [c.point for c in press(m, popup, 5.0, "a")] == [reasons[0]]
    assert m.expects_dialog(5.5)  # a confirm may follow
    m.update(frozenset(), 6.0, popup)
    assert [c.point for c in press(m, popup, 7.0, "b")] == [popup.no]


def test_ignore_opens_the_dialog_gate_and_it_closes_again():
    m = FriendsMapper()
    panel = FriendsScreen("panel")
    m.update(frozenset(), 0.0, panel)
    assert not m.expects_dialog(0.0)
    for t in (1.0, 2.0, 3.0):
        press(m, panel, t, "dpad_down")  # to Ignore
    assert [c.point for c in press(m, panel, 4.0, "a")] == [f.IGNORE]
    assert m.expects_dialog(4.5)
    assert not m.expects_dialog(10.0)


@pytest.mark.parametrize("name,rows", [
    ("friends_all_1920x1009", [195, 216, 240, 260, 284, 303, 326, 346]),  # 8, about 21.6 px apart
    ("friends_list_bug_1920x1009", [196, 213, 228]),  # closer together, the first hovered (yellow)
    ("friends_online_1920x1009", [195, 218, 235]),  # Brig's g touches Princess Isla: split
])
def test_each_name_is_found_where_it_is(name, rows):
    screen = replay(name)
    assert screen.kind == "list"
    found = [r.to_client(1920, 1009)[1] for r in screen.rows]
    assert len(found) == len(rows) and all(abs(a - b) <= 2 for a, b in zip(found, rows)), found
