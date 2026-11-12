import pytest

from ttcontroller import hints as H
from ttcontroller.battle import BattleScreen
from ttcontroller.book import BookScreen
from ttcontroller.config import parse
from ttcontroller.friends import FriendsScreen
from ttcontroller.garden import GardenScreen
from ttcontroller.makeatoon import MakeAToonScreen
from ttcontroller.npc import NpcScreen
from ttcontroller.pregame import PregameScreen
from ttcontroller.shop import ShopScreen
from ttcontroller.ui import UIPoint


def _center(x, y):
    return UIPoint("center", x, y, "center")


def sprites(hints):
    return [h.sprite for h in hints if isinstance(h, H.Badge)]


def bars(hints):
    return [tuple(text for _, text in h.items) for h in hints if isinstance(h, H.Bar)]


def covers(hints):
    return [h.sprite for h in hints if isinstance(h, H.Badge) and h.cover]


def test_walking_badges_and_bar():
    hints = H.hints_for(H.Context())
    assert sprites(hints) == ["VIEW", "RB", "START"]
    assert bars(hints) == [("Walk", "Jump", "Gags", "Tasks", "Map", "Unite")]


def test_walking_bar_has_its_own_setting():
    hints = H.hints_for(H.Context(walking_bar=False))
    assert sprites(hints) == ["VIEW", "RB", "START"]
    assert bars(hints) == []


def test_gardening_panel_drops_the_walking_bar():
    garden = GardenScreen(top=UIPoint("left", 0.065, 0.23), bottom=UIPoint("left", 0.065, 0.33))
    hints = H.hints_for(H.Context(garden=garden))
    assert sprites(hints) == ["VIEW", "RB", "START", "Y", "X"]
    assert bars(hints) == []


def test_a_dialog_nothing_owns_is_covered():
    ok, cancel = _center(-0.05, 0.12), _center(0.05, 0.12)
    hints = H.hints_for(H.Context(dialog=(ok, cancel)))
    assert covers(hints) == ["A", "B"]
    assert [h.at for h in hints] == [ok, cancel]


def test_a_lone_cancel_is_covered_by_b():
    alone = _center(0.0, 0.1)
    assert covers(H.hints_for(H.Context(dialog=(alone, alone)))) == ["B"]


def test_hop_off_badge_is_big():
    hints = H.hints_for(H.Context(hop_off=UIPoint("center", 0.0, 0.063, "top")))
    (badge,) = hints
    assert badge.sprite == "B" and badge.size == pytest.approx(H.BADGE * 2)


def test_ceo_leave_bar_charges_with_a_and_no_ring():
    hints = H.hints_for(H.Context(leave=_center(0.52, 0.4)))
    assert covers(hints) == ["B"]
    (bar,) = [h for h in hints if isinstance(h, H.Bar)]
    assert bar.items == (("L", "Turn"), ("A", "Charge"))
    assert not any(h.hold for h in hints if isinstance(h, H.Badge))


def test_battle_picker():
    hints = H.hints_for(H.Context(mode="battle", battle=BattleScreen("picker")))
    assert sprites(hints) == ["VIEW", "RB", "Y", "B", "X"]  # speedchat and friends work in battle too
    assert [h.hold for h in hints if isinstance(h, H.Badge)] == [False, False, False, True, False]
    assert bars(hints) == [("Move", "Select", "Teammates")]


def test_battle_trunk_closes_on_x_only():
    hints = H.hints_for(H.Context(mode="battle", battle=BattleScreen("trunk")))
    assert "B" not in sprites(hints)
    assert all("Close" not in b for b in bars(hints))


def test_battle_target_has_no_bar():
    hints = H.hints_for(H.Context(mode="battle", battle=BattleScreen("target")))
    assert sprites(hints) == ["B"] and bars(hints) == []


def test_battle_run_prompt_is_covered():
    assert covers(H.hints_for(H.Context(mode="battle", battle=BattleScreen("confirm_run")))) == ["A", "B"]


def test_shop_delete_mode_changes_the_bar():
    hints = H.hints_for(H.Context(mode="shop", shop=ShopScreen("shop", delete_mode=True)))
    assert bars(hints) == [("Move", "Delete one", "Delete all")]


def test_shop_after_trolley():
    hints = H.hints_for(H.Context(mode="shop", shop=ShopScreen("shop", trolley=True)))
    assert sprites(hints) == ["X", "B", "RT"]


def test_speedchat_has_no_hints():
    assert H.hints_for(H.Context(mode="speedchat")) == ()


def test_friends_list_bar_only_quick_keys():
    hints = H.hints_for(H.Context(mode="friends", friends=FriendsScreen("list")))
    assert bars(hints) == [("Go To", "Whisper")]


def test_friends_panel_has_no_bar():
    hints = H.hints_for(H.Context(mode="friends", friends=FriendsScreen("panel")))
    assert sprites(hints) == ["X", "Y", "B"] and bars(hints) == []


def test_friends_ok_popup_is_covered_by_a():
    ok = _center(0.3, -0.2)
    hints = H.hints_for(H.Context(mode="friends", friends=FriendsScreen("popup", yes=ok, no=ok, popup="OK")))
    assert covers(hints) == ["A"]


def test_dialogue_arrow_is_covered_by_a():
    hints = H.hints_for(H.Context(mode="npc", npc=NpcScreen("dialogue", button=_center(0.38, -0.25))))
    assert covers(hints) == ["A"]


def test_book_has_no_bar_and_navigation_outside():
    hints = H.hints_for(H.Context(mode="book", book=BookScreen(page="map", go_home=True)))
    assert sprites(hints) == ["LB", "RB", "B", "Y"]
    assert bars(hints) == []


def test_book_top_tabs_get_lt_and_rt_past_their_ends():
    tabs = (_center(-0.115, -0.455), _center(0.117, -0.455))
    hints = H.hints_for(H.Context(mode="book", book=BookScreen(page="gags", top_tabs=tabs)))
    lt, rt = [h for h in hints if h.sprite in ("LT", "RT")]
    assert lt.at.x < tabs[0].x and rt.at.x > tabs[1].x
    assert lt.at.y == rt.at.y


def test_cog_gallery_suit_icons_get_the_right_stick():
    from ttcontroller.book import SUIT_ICONS
    hints = H.hints_for(H.Context(mode="book", book=BookScreen(page="cog gallery")))
    suits = [h for h in hints if h.sprite.startswith("R:")]
    assert [h.sprite for h in suits] == ["R:u", "R:l", "R:r", "R:d"]
    for h, icon in zip(suits, SUIT_ICONS.values()):
        assert h.at.y == pytest.approx(icon.y) and h.at.x < icon.x


def test_book_dialog_only_covers():
    dialog = (_center(-0.05, 0.1), _center(0.05, 0.1))
    hints = H.hints_for(H.Context(mode="book", book=BookScreen(page="toontasks", dialog=dialog)))
    assert covers(hints) == ["A", "B"] and len(hints) == 2


def test_snapshot_arrows_mirror():
    book = BookScreen(page="snapshots", snapshot_arrows=("left", "right"))
    dl, dr = [h for h in H.hints_for(H.Context(mode="book", book=book)) if h.sprite in ("DL", "DR")]
    assert dl.at.y == dr.at.y
    from ttcontroller.book import SNAPSHOT_ARROWS
    assert dl.at.x < SNAPSHOT_ARROWS["left"].x and dr.at.x > SNAPSHOT_ARROWS["right"].x


def test_startup_quit_and_options():
    hints = H.hints_for(H.Context(mode="pregame", pregame=PregameScreen("startup")))
    assert sprites(hints) == ["B", "START"] and bars(hints) == []
    assert hints[0].hold


def test_toon_selection_badges_only_on_the_hovered_toon():
    screen = PregameScreen("toons", trash=(True,) * 6, names=(True, False, False, False, False, False))
    assert sprites(H.hints_for(H.Context(mode="pregame", pregame=screen, toon_slot=0))) == ["B", "START", "X", "Y"]
    assert sprites(H.hints_for(H.Context(mode="pregame", pregame=screen, toon_slot=1))) == ["B", "START", "X"]


def test_type_delete_is_covered_by_y():
    assert covers(H.hints_for(H.Context(mode="pregame", pregame=PregameScreen("type")))) == ["Y", "B"]


def test_make_a_toon_b_only_on_the_style_step():
    style = H.hints_for(H.Context(mode="mat", mat=MakeAToonScreen("style")))
    assert "B" in sprites(style)
    for kind in ("type", "color", "clothes", "name"):
        assert "B" not in sprites(H.hints_for(H.Context(mode="mat", mat=MakeAToonScreen(kind)))), kind


def test_make_a_toon_back_and_next_mirror():
    from ttcontroller.makeatoon import BACK, NEXT
    hints = H.hints_for(H.Context(mode="mat", mat=MakeAToonScreen("type", back=BACK, next=NEXT)))
    lb, rb = [h for h in hints if h.sprite in ("LB", "RB")]
    assert lb.at.y == pytest.approx(rb.at.y)
    assert lb.at.x < BACK.x and rb.at.x > NEXT.x
    assert bars(hints) == []


def test_sprite_buttons():
    assert H.sprite_buttons("A") == ("a",)
    assert H.sprite_buttons("DLR") == ("dpad_left", "dpad_right")
    assert H.sprite_buttons("R:ud") == ("rs_up", "rs_down")
    assert H.sprite_buttons("L") == ("ls_up", "ls_down", "ls_left", "ls_right")


def _remapped(table, press=None, hold=None):
    from ttcontroller.bindings import Bindings
    base = H.default_tables()[table]
    p = {**base.press, **(press or {})}
    h = {**base.hold, **(hold or {})}
    return {table: Bindings(press={k: v for k, v in p.items() if v}, hold={k: v for k, v in h.items() if v})}


def test_remapped_button_moves_its_badge():
    tables = _remapped("battle", press={"y": None, "rb": "pass"})
    hints = H.hints_for(H.Context(mode="battle", battle=BattleScreen("picker"), tables=tables))
    assert sprites(hints) == ["VIEW", "RB", "B", "X"]  # RB is Pass now, not the friends list


def test_remapped_hold_moves_the_ring():
    tables = _remapped("battle", hold={"b": None, "x": "run"})
    hints = H.hints_for(H.Context(mode="battle", battle=BattleScreen("picker"), tables=tables))
    held = [h for h in hints if isinstance(h, H.Badge) and h.hold]
    assert [h.sprite for h in held] == ["X"]


def test_unbound_action_drops_its_hint():
    tables = _remapped("overworld", press={"rb": None})
    assert "RB" not in sprites(H.hints_for(H.Context(tables=tables)))


def test_an_extra_button_keeps_the_default():
    tables = _remapped("overworld", press={"lb": "friendsList"})
    assert "RB" in sprites(H.hints_for(H.Context(tables=tables)))


def test_rt_on_clarabelle_and_held_rt_on_the_silly_meter():
    from ttcontroller.silly import SillyScreen
    clarabelle, gauge = UIPoint("right", -0.347, 0.057), UIPoint("right", -0.2, 0.0615)
    hints = H.hints_for(H.Context(mail_icon=clarabelle, silly=SillyScreen(icon=gauge)))
    rt = [h for h in hints if isinstance(h, H.Badge) and h.sprite == "RT"]
    assert [h.hold for h in rt] == [False, True]
    assert rt[0].at.x < clarabelle.x and rt[1].at.x < gauge.x and rt[0].at.x < rt[1].at.x
    # Neither up: no RT badge at all.
    assert "RT" not in sprites(H.hints_for(H.Context()))


def test_remapped_bar_item():
    tables = _remapped("overworld", press={"y": None, "lb": "showGags"})
    (bar,) = [h for h in H.hints_for(H.Context(tables=tables)) if isinstance(h, H.Bar)]
    assert ("LB", "Gags") in bar.items and all(len(item) == 2 for item in bar.items)


def test_remapped_directions_draw_one_stick():
    moves = {f"dpad_{d}": None for d in ("up", "down", "left", "right")}
    tables = _remapped("shop", press=moves)  # the left stick still moves
    (bar,) = [h for h in H.hints_for(H.Context(mode="shop", shop=ShopScreen("shop"), tables=tables))
              if isinstance(h, H.Bar)]
    assert bar.items[0] == ("L:udlr", "Move")
    tables = _remapped("npc", press={"dpad_up": None, "dpad_down": None, "rs_up": "up", "rs_down": "down"})
    hints = H.hints_for(H.Context(mode="npc", npc=NpcScreen("tasks", cancel=_center(0.1, 0.1)), tables=tables))
    assert bars(hints) == [("Choose", "Select")]
    (bar,) = [h for h in hints if isinstance(h, H.Bar)]
    assert bar.items[0][0] in ("L:ud", "R:ud")


def test_fixed_screens_ignore_the_tables():
    tables = _remapped("overworld", press={"b": None})
    screen = PregameScreen("startup")
    assert sprites(H.hints_for(H.Context(mode="pregame", pregame=screen, tables=tables))) == ["B", "START"]


def test_hints_settings_parse():
    config, warnings = parse({"hints": False, "hints_walking_bar": False, "hints_scale": 1.25})
    assert (config.hints, config.hints_walking_bar, config.hints_scale) == (False, False, 1.25)
    assert warnings == []
    config, warnings = parse({"hints_scale": 9})
    assert config.hints_scale == 1.0 and warnings


def test_bounce_shrinks_then_settles():
    from ttcontroller.hint_draw import BOUNCE_SECONDS, bounce
    assert bounce(-1) == 1.0 and bounce(BOUNCE_SECONDS) == 1.0
    samples = [bounce(BOUNCE_SECONDS * i / 100) for i in range(100)]
    assert min(samples) == pytest.approx(0.8, abs=0.01)
    assert 1.05 < max(samples[30:]) < 1.15
    assert abs(samples[-1] - 1.0) < 0.05


def _drawer():
    from ttcontroller.hint_draw import Drawer, find_sheet
    sheet = find_sheet()
    if sheet is None:
        pytest.skip("the button spritesheet is missing")
    return Drawer(sheet)


def test_pieces_draw_each_hint_and_bounce_on_press():
    drawer = _drawer()
    hints = H.hints_for(H.Context())
    pieces = drawer.pieces(hints, 1920, 1009, 0.0)
    assert len(pieces) == len(hints)
    for _, image, x, y in pieces:
        assert image.shape[2] == 4 and image[..., 3].max() == 255
    start = [p for p in pieces if getattr(p[0][0], "sprite", "") == "START"][0]
    drawer.press(frozenset({"start"}), 1.0)
    later = [p for p in drawer.pieces(hints, 1920, 1009, 1.05) if getattr(p[0][0], "sprite", "") == "START"][0]
    assert later[0] != start[0] and later[1].shape != start[1].shape  # smaller mid-bounce
    settled = [p for p in drawer.pieces(hints, 1920, 1009, 2.0) if getattr(p[0][0], "sprite", "") == "START"][0]
    assert settled[1].shape == start[1].shape


def test_hold_ring_fills_while_held():
    from ttcontroller.hint_draw import RING_STEPS
    drawer = _drawer()
    drawer.hold_seconds = 0.5
    hints = H.hints_for(H.Context(mode="battle", battle=BattleScreen("picker")))
    run = [h for h in hints if isinstance(h, H.Badge) and h.hold][0]
    ring = lambda now: [p for p in drawer.pieces(hints, 1920, 1009, now) if p[0][0] == run][0][0][-1]
    assert ring(0.0) == 0
    drawer.press(frozenset({"b"}), 1.0)
    assert 0 < ring(1.25) < RING_STEPS
    assert ring(1.6) == RING_STEPS
    drawer.press(frozenset(), 1.7)
    assert ring(1.7) == 0


def test_no_rb_badge_when_the_friends_button_is_gone():
    # A Cog HQ lobby's timer sits where the friends button was; the list can't open then.
    assert "RB" in sprites(H.hints_for(H.Context()))
    assert "RB" not in sprites(H.hints_for(H.Context(friends_button=False)))


@pytest.mark.parametrize("kind", ["picker", "trunk", "waiting"])
def test_speedchat_and_friends_badges_in_battle(kind):
    battle = H.Context(mode="battle", battle=BattleScreen(kind))
    assert {"VIEW", "RB"} <= set(sprites(H.hints_for(battle)))
    gone = H.Context(mode="battle", battle=BattleScreen(kind), friends_button=False)
    assert "RB" not in sprites(H.hints_for(gone)) and "VIEW" in sprites(H.hints_for(gone))


def test_the_friends_button_is_read():
    from test_book import replay
    from ttcontroller import ui

    def shown(name):
        return replay(name, lambda w, h, get_pixel: ui.is_visible(ui.FRIENDS_BUTTON, w, h, get_pixel))
    assert shown("test_1920x1009")
    assert not shown("timer_top_right_1920x1009")


def test_no_book_means_hold_start_for_options():
    walking = H.hints_for(H.Context())
    start = [h for h in walking if isinstance(h, H.Badge) and h.sprite == "START"]
    assert len(start) == 1 and not start[0].hold
    lobby = H.hints_for(H.Context(book_button=False))
    start = [h for h in lobby if isinstance(h, H.Badge) and h.sprite == "START"]
    assert len(start) == 1 and start[0].hold


def test_the_book_is_read():
    from test_book import replay
    from ttcontroller import ui

    def shown(name):
        return replay(name, lambda w, h, get_pixel: ui.is_visible(ui.BOOK_BUTTON, w, h, get_pixel))
    assert shown("gardening_hud_1_1920x1009")
    assert not shown("no_book_options_only_1920x1009")


def test_no_unites_drops_lt_from_the_walking_bar():
    hints = H.hints_for(H.Context(unites=False))
    assert bars(hints) == [("Walk", "Jump", "Gags", "Tasks", "Map")]


def test_boarding_go_to_leader_has_a_y_badge():
    from test_book import replay
    from ttcontroller.boarding import read_boarding
    away = H.hints_for(H.Context(boarding=replay("boarding_groups_go_to_leader", read_boarding)))
    near = H.hints_for(H.Context(boarding=replay("boarding_groups_in_a_group_1920x1009", read_boarding)))
    assert "Y" in repr(away) and "'Y'" not in repr(near)
