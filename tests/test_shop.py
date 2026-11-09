import json
from pathlib import Path

import pytest

from ttcontroller import shop
from ttcontroller.battle import read_screen
from ttcontroller.shop import DONE, LOAD_PRESET, SAVE_PRESET, TRASH, ShopMapper, ShopScreen, cell, read_shop

FIXTURES = Path(__file__).parent / "fixtures" / "battle"


def pixels(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    seen = data["pixels"]
    return w, h, lambda x, y: tuple(seen[f"{x},{y}"])


def replay(name):
    return read_shop(*pixels(name))


def grid(*rows):
    return tuple(tuple(ch == "B" for ch in row) for row in rows)


# Checked by eye against the screenshots. Rows: Toon-Up, Trap, Lure, Sound, Throw, Squirt, Drop.
BUYABLE = grid("BBBB...", ".......", "BBBBB..", "BBBB...", "BBBBB..", "BBBB...", "BBBB...")
DELETABLE = grid("...BBB.", ".......", "...BBB.", "B..BBB.", "...BBB.", "...BBB.", "...BBB.")


@pytest.mark.parametrize("name", ["shop_1920x1009", "shop_1156x326", "shop_502x821", "shop_hover_1920x1009"])
def test_buyable_gags(name):
    screen = replay(name)
    assert screen.kind == "shop" and not screen.delete_mode
    assert screen.usable == BUYABLE


def test_pouch_full_nothing_buyable():
    assert replay("shop_full_1920x1009").usable == grid(*["......."] * 7)


def test_empty_throw_slots_are_not_delete_mode():
    # A newer toon's empty Throw slots are orange, which once read as delete mode's red:
    # the hover only moved between them, and B clicked the trash can (Nov 8).
    screen = replay("shop_empty_throw_slots_1920x1009")
    assert screen.kind == "shop" and not screen.delete_mode
    assert screen.usable == grid(".......", ".......", ".......", "BB.....", "BBBB...", "BBB....", "B......")
    full = replay("shop_full_empty_throw_slots_1920x1009")
    assert not full.delete_mode and full.usable == grid(*["......."] * 7)


@pytest.mark.parametrize("name", ["shop_delete_mode_1920x1009", "shop_delete_mode_hover_1920x1009"])
def test_delete_mode(name):
    screen = replay(name)
    assert screen.delete_mode
    assert screen.usable == DELETABLE


@pytest.mark.parametrize("name,y", [("shop_preset_save_1920x1009", 0.2027), ("shop_preset_load_1920x1009", 0.1541)])
def test_preset_dialogs(name, y):
    screen = replay(name)
    assert screen.kind == "dialog"
    assert round(screen.ok.y, 4) == y and screen.cancel.y == screen.ok.y
    # Not mistaken for the battle run prompt, which has its buttons higher up.
    assert read_screen(*pixels(name)).kind is None


@pytest.mark.parametrize("name", ["battle_gags_1920x1009", "test_1920x1009", "speedchat_1920x1009",
                                  "battle_trunk_1920x1009"])
def test_not_the_shop(name):
    assert replay(name).kind is None


# --- Mapper ---

SHOP = ShopScreen("shop", usable=BUYABLE)
DELETE = ShopScreen("shop", usable=DELETABLE, delete_mode=True)


def press(m, screen, t, *buttons):
    out = m.update(frozenset(buttons), t, screen)
    return out + m.update(frozenset(), t + 0.01, screen)


def test_opens_on_the_remembered_gag_and_buys_one():
    m = ShopMapper()
    assert [(c.kind, c.point) for c in m.update(frozenset(), 0.0, SHOP)] == [("hover", cell(4, 3))]
    assert press(m, SHOP, 1.0, "dpad_right")[-1].point == cell(4, 4)
    assert press(m, SHOP, 2.0, "dpad_right")[-1].point == cell(4, 4)  # level 6 can't be bought
    assert [(c.kind, c.point) for c in press(m, SHOP, 3.0, "a")] == [("click", cell(4, 4))]
    # Buying doesn't wait for the screen: another press buys again straight away.
    assert [c.kind for c in press(m, SHOP, 3.05, "a")] == ["click"]


def test_buy_max_clicks_until_it_cant_buy_more():
    m = ShopMapper()
    m.update(frozenset(), 0.0, SHOP)
    clicks = [c for c in press(m, SHOP, 1.0, "y") if c.kind == "click"]
    t = 1.02
    while t < 1.5:
        clicks += m.update(frozenset(), t, SHOP)
        t += 0.01
    assert len(clicks) == 5 and all(c.point == cell(4, 3) for c in clicks)  # one per 0.1s
    maxed = ShopScreen("shop", usable=BUYABLE[:4] + (tuple(c != 3 for c in range(7)),) + BUYABLE[5:])
    assert m.update(frozenset(), 2.0, maxed) == []
    assert m.update(frozenset(), 3.0, SHOP) == []  # stopped for good


def test_any_button_stops_buy_max():
    m = ShopMapper()
    m.update(frozenset(), 0.0, SHOP)
    press(m, SHOP, 1.0, "y")
    press(m, SHOP, 1.2, "dpad_up")
    assert m.update(frozenset(), 2.0, SHOP) == []


def test_x_toggles_delete_mode_and_snaps_back_to_the_same_gag():
    m = ShopMapper()
    m.update(frozenset(), 0.0, SHOP)
    press(m, SHOP, 1.0, "dpad_left")  # Throw level 3: you have none, so it can't be deleted
    assert [(c.kind, c.point) for c in press(m, SHOP, 2.0, "x")] == [("click", TRASH)]
    assert [c.point for c in m.update(frozenset(), 3.0, DELETE)] == [cell(4, 2)]
    assert press(m, DELETE, 4.0, "dpad_right")[-1].point == cell(4, 3)
    assert [(c.kind, c.point) for c in press(m, DELETE, 5.0, "a")] == [("click", cell(4, 3))]
    assert [c.point for c in press(m, DELETE, 6.0, "x")] == [TRASH]
    assert [c.point for c in m.update(frozenset(), 7.0, SHOP)] == [cell(4, 3)]


def test_b_leaves_delete_mode_then_the_shop():
    m = ShopMapper()
    m.update(frozenset(), 0.0, DELETE)
    assert [c.point for c in press(m, DELETE, 1.0, "b")] == [TRASH]
    m.update(frozenset(), 2.0, SHOP)
    assert [c.point for c in press(m, SHOP, 3.0, "b")] == [DONE]


def test_presets_and_their_dialogs():
    dialog = replay("shop_preset_save_1920x1009")
    m = ShopMapper()
    m.update(frozenset(), 0.0, SHOP)
    assert [c.point for c in press(m, SHOP, 1.0, "lb")] == [SAVE_PRESET]
    assert [(c.kind, c.point) for c in m.update(frozenset(), 2.0, dialog)] == [("hover", dialog.ok)]
    assert [c.point for c in press(m, dialog, 3.0, "a")] == [dialog.ok]
    m.update(frozenset(), 4.0, SHOP)
    assert [c.point for c in press(m, SHOP, 5.0, "rb")] == [LOAD_PRESET]
    m.update(frozenset(), 6.0, dialog)
    assert [c.point for c in press(m, dialog, 7.0, "b")] == [dialog.cancel]


def test_rb_and_lb_are_shop_buttons():
    assert {"lb", "rb", "x", "y"} <= ShopMapper().buttons
    assert shop.default_shop_bindings().press["rb"] == "load_preset"


# --- After a trolley game: Exit to Playground and Play Again instead of Done ---

@pytest.mark.parametrize("name", ["shop_trolley_1920x1009", "shop_trolley_2_1920x1009", "shop_trolley_3_1920x1009"])
def test_trolley_shop(name):
    screen = replay(name)
    assert screen.kind == "shop" and screen.trolley
    assert screen.usable == grid(*["......."] * 7)  # pouch full (80/80)


@pytest.mark.parametrize("name", ["shop_1920x1009", "shop_1156x326", "shop_502x821", "shop_done_hover_1920x1009",
                                  "shop_delete_mode_1920x1009"])
def test_the_normal_shop_isnt_the_trolley_one(name):
    assert not replay(name).trolley


TROLLEY = ShopScreen("shop", usable=BUYABLE, trolley=True)


def test_trolley_shop_b_exits_and_rt_plays_again():
    m = ShopMapper()
    m.update(frozenset(), 0.0, TROLLEY)
    assert [(c.kind, c.point) for c in press(m, TROLLEY, 1.0, "b")] == [("click", shop.EXIT)]
    m.update(frozenset(), 2.0, TROLLEY)
    assert [(c.kind, c.point) for c in press(m, TROLLEY, 3.0, "rt")] == [("click", shop.PLAY_AGAIN)]


def test_rt_does_nothing_in_the_normal_shop():
    m = ShopMapper()
    m.update(frozenset(), 0.0, SHOP)
    assert press(m, SHOP, 1.0, "rt") == []


def test_gags_carry_the_highlight_frame():
    m = ShopMapper()
    hover = m.update(frozenset(), 0.0, SHOP)[0]
    assert hover.kind == "hover" and hover.size == shop.GAG_SIZE
    assert press(m, SHOP, 1.0, "dpad_left")[-1].size == shop.GAG_SIZE
