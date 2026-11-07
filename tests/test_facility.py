import json
from pathlib import Path

from ttcontroller.facility import CLOSE, TELEPORT, FacilityMapper, FacilityScreen, read_facility

FIXTURES = Path(__file__).parent / "fixtures" / "battle"


def replay(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    return read_facility(w, h, lambda x, y: tuple(pixels[f"{x},{y}"]))


def px(point, size=(1920, 1009)):
    return point.to_client(*size)


def test_finds_cashbot_hqs_facility_nametags_in_the_margins():
    # CASHBOT VAULT, COIN MINT and BULLION MINT along the bottom; the cogs' tags beside them aren't.
    screen = replay("facility_nametags_1920x1009")
    assert [px(p) for p in screen.tags] == [(516, 889), (1182, 889), (1404, 889)]
    assert not screen.popup


def test_reads_the_teleport_popup():
    screen = replay("facility_nametags_popup_1920x1009")
    assert screen.popup and len(screen.tags) == 3
    assert replay("elevator_cog_golf_kart_1920x1009").popup  # a golf course's, in Bossbot HQ


def test_a_cogs_panel_isnt_the_popup():
    # Robber Baron's panel: the same frame, but a green health bar, not a round button.
    assert not replay("options_gameplay_toonsync_1920x1009").popup


def test_cog_and_building_tags_arent_facilities():
    # The elevator's cog tags (gray there, with orange arrows) and the street's blue buildings.
    # Cog-taken buildings' gray tags look just like a facility's and are found.
    assert [px(p) for p in replay("elevator_cog_building_1920x1009").tags] == [(294, 889)]
    assert replay("test_1626x711").tags == ()
    assert replay("gardening_hud_5_405x820").tags == ()


def press(m, button, now, screen):
    return m.update(frozenset({button}), now, screen) + m.update(frozenset(), now + 0.01, screen)


TAGS = replay("facility_nametags_1920x1009")
POPUP = replay("facility_nametags_popup_1920x1009")


def test_lb_clicks_the_first_tag_and_rb_stays_the_friends_list():
    m = FacilityMapper()
    assert m.buttons(TAGS) == {"lb"}
    assert m.buttons(FacilityScreen()) == frozenset()
    (c,) = press(m, "lb", 0.0, TAGS)
    assert (c.kind, px(c.point)) == ("click", (516, 889))


def test_with_the_popup_up_lb_and_rb_cycle_and_a_and_b_teleport_or_close():
    m = FacilityMapper()
    press(m, "lb", 0.0, TAGS)
    assert m.buttons(POPUP) == {"lb", "rb", "a", "b"}
    assert px(press(m, "rb", 1.0, POPUP)[0].point) == (1182, 889)
    assert px(press(m, "rb", 2.0, POPUP)[0].point) == (1404, 889)
    assert px(press(m, "rb", 3.0, POPUP)[0].point) == (516, 889)  # round again
    assert px(press(m, "lb", 4.0, POPUP)[0].point) == (1404, 889)
    assert press(m, "a", 5.0, POPUP)[0].point == TELEPORT
    assert press(m, "b", 6.0, POPUP)[0].point == CLOSE


def test_finds_sellbot_hqs_factories():
    # SCRAP FACTORY low in the left column (its short first line has fewer letters) and
    # STEEL FACTORY along the bottom, with Steel Factory's popup up.
    screen = replay("facility_nametags_bug_1920x1009")
    assert [px(p) for p in screen.tags] == [(111, 719), (1626, 889)]
    assert screen.popup


def test_finds_lawbot_hqs_tags_over_light_ground():
    # DA OFFICE LOBBY's tag is over a light beige ledge: its top edge is still told by the
    # box being lighter. LAWBOT COURTHOUSE is in the left column, with its popup up.
    screen = replay("facility_nametags_bug_2_1920x1009")
    assert [px(p) for p in screen.tags] == [(111, 275), (516, 889)]
    assert screen.popup
