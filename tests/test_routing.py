"""Which screen owns the controller (routing.route) and how the small screens walking
around share the buttons (routing.share)."""

from dataclasses import replace
from types import SimpleNamespace as S

from ttcontroller import ui
from ttcontroller.pipeline import Reads
from ttcontroller.routing import FREE_ORDER, route, share

OPEN = S(is_open=True)
DIALOG = (ui.UIPoint("center", 0.1, 0.1), ui.UIPoint("center", -0.1, 0.1))


def reads(**screens) -> Reads:
    return replace(Reads(), **screens)


def test_nothing_open_walks_freely():
    r = route(Reads(), battle_recent=False, shop_recent=False)
    assert r.free and r.walk and r.mode == "free" and r.holder is None and not r.menu


def test_options_is_over_everything():
    r = route(reads(options=S(kind="gameplay")), battle_recent=True, shop_recent=True)
    assert r.options and not r.battle and not r.shop and not r.walk and not r.free
    assert r.mode == "options" and r.holder == "options"


def test_speedchat_opens_over_a_battle():
    r = route(reads(speedchat=OPEN), battle_recent=True, shop_recent=False)
    assert r.battle and r.speedchat and r.menu and r.mode == "speedchat"
    assert not r.walk  # the left stick never walks in battle


def test_speedchat_comes_before_the_friends_list_and_both_over_the_book():
    r = route(reads(speedchat=OPEN, friends=S(kind="list"), book=OPEN), battle_recent=False, shop_recent=False)
    assert r.speedchat and not r.friends and not r.book and r.mode == "speedchat"
    r = route(reads(friends=S(kind="list"), book=OPEN), battle_recent=False, shop_recent=False)
    assert r.friends and not r.book and r.holder == "friends"


def test_a_conversation_pauses_under_a_menu():
    r = route(reads(npc=S(kind="tasks"), speedchat=OPEN), battle_recent=False, shop_recent=False)
    assert r.npc_open and not r.npc and r.speedchat
    assert not r.walk and not r.free  # choosing a task: no walking


def test_the_start_up_screen_still_walks_toon_selection_doesnt():
    assert route(reads(pregame=S(kind="startup")), battle_recent=False, shop_recent=False).walk
    assert not route(reads(pregame=S(kind="select")), battle_recent=False, shop_recent=False).walk


def test_fishing_gives_way_to_its_popups_and_golf_to_the_book():
    assert route(reads(fishing=S(kind="dock")), battle_recent=False, shop_recent=False).fishing
    assert not route(reads(fishing=S(kind="dock"), stray_dialog=DIALOG), battle_recent=False, shop_recent=False).fishing
    assert route(reads(golf=OPEN), battle_recent=False, shop_recent=False).golf
    assert not route(reads(golf=OPEN, book=OPEN), battle_recent=False, shop_recent=False).golf


def test_the_shop_waits_for_a_battle():
    r = route(Reads(), battle_recent=True, shop_recent=True)
    assert r.battle and not r.shop


def test_a_dialog_takes_its_buttons_before_the_screens_behind_it():
    # The HUD's trunk takes A too: with a dialog up, only the dialog's A clicks.
    shares = share([("dialog", frozenset({"a", "b"})), ("hud", frozenset({"a", "ls", "dpad_up"}))])
    assert shares == {"dialog": {"a", "b"}, "hud": {"ls", "dpad_up"}}


def test_screens_that_dont_overlap_keep_all_their_buttons():
    shares = share([("garden", frozenset({"x", "y"})), ("facility", frozenset({"lb"}))])
    assert shares == {"garden": {"x", "y"}, "facility": {"lb"}}


def test_the_dialog_comes_first():
    assert FREE_ORDER[0] == "dialog"
