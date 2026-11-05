import json
from pathlib import Path

import pytest

from ttcontroller import book as b
from ttcontroller.book import BookMapper, BookScreen, read_book, read_pages

FIXTURES = Path(__file__).parent / "fixtures" / "battle"


def replay(name, reader=read_book):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    return reader(w, h, lambda x, y: tuple(pixels[f"{x},{y}"]))


@pytest.mark.parametrize("name,page", [
    ("book_trunk_1920x1009", "gags"), ("book_gags_1915x1006", "gags"),
    # The page beside the tabs is shaded nearly tab gray here.
    ("book_cog_gallery_1920x1009", "cog gallery"),
])
def test_reads_every_page_by_its_icon(name, page):
    assert replay(name, read_pages) == list(b.PAGES)
    screen = replay(name)
    assert len(screen.tabs) == 14
    assert screen.page == page


@pytest.mark.parametrize("name,current", [("book_gags_1915x1006", 0), ("book_trunk_1920x1009", 1)])
def test_reads_the_top_tabs(name, current):
    screen = replay(name)
    assert len(screen.top_tabs) == 2  # Gags and Trunk
    assert screen.top_current == current


def test_not_open_on_other_screens():
    assert not replay("friends_list_1920x1009").is_open
    assert not replay("speedchat_hello_grey_1920x1009").is_open


def test_unknown_icon():
    assert b.identify((0,) * 75) is None


def screen(current=1, top_current=None):
    top = (b._center(-0.1, -0.45), b._center(0.1, -0.45)) if top_current is not None else ()
    tabs = tuple(b._center(0.46, 0.04 * i) for i in range(4))
    return BookScreen(tabs, current, b.PAGES[current], top, top_current)


def press(mapper, button, now, s):
    commands = mapper.update(frozenset({button}), now, s)
    mapper.update(frozenset(), now + 0.01, s)
    return commands


def test_bumpers_tap_the_turn_keys():
    mapper = BookMapper()
    assert not press(mapper, "rb", 0.0, screen())
    assert not press(mapper, "rb", 0.1, screen())
    assert not press(mapper, "lb", 0.2, screen())
    assert mapper.take_taps() == ["right", "right", "left"]
    assert mapper.take_taps() == []


def test_waits_for_the_tab_to_change():
    mapper = BookMapper()
    assert press(mapper, "rt", 0.0, screen(top_current=0))
    assert not press(mapper, "rt", 0.1, screen(top_current=0))


def test_triggers_change_top_tab_without_wrapping():
    mapper = BookMapper()
    [c] = press(mapper, "rt", 0.0, screen(top_current=0))
    assert c.kind == "click" and c.point == b._center(0.1, -0.45)
    assert not press(mapper, "rt", 1.0, screen(top_current=1))
    assert not press(mapper, "lt", 2.0, screen())  # a page without top tabs


def test_b_closes_the_book():
    mapper = BookMapper()
    assert not press(mapper, "b", 0.0, screen())
    assert mapper.take_taps() == ["stickerBook"]


def test_options_page():
    screen = replay("book_options_1920x1009")
    assert screen.page == "options" and screen.hovers
    assert replay("book_options_speedchat_color_hover_1920x1009").page == "options"


def test_exit_dialog_over_the_dimmed_book():
    screen = replay("book_options_exit_confirm_1920x1009")
    assert screen.is_open and screen.dialog is not None and screen.hovers
    w, h = 1920, 1009
    assert [p.to_client(w, h) for p in screen.dialog] == [(904, 602), (1015, 602)]


def options(dialog=None):
    tabs = tuple(b._center(0.46, 0.04 * i) for i in range(4))
    if dialog:
        return BookScreen(dialog=(b._center(-0.05, 0.1), b._center(0.05, 0.1)))
    return BookScreen(tabs, 0, "options")


def test_options_buttons_and_exit_dialog():
    mapper = BookMapper()
    [hover] = mapper.update(frozenset(), 0.0, options())
    assert hover.kind == "hover" and hover.point == b.SUBMIT
    for t in (1.0, 2.0, 3.0):
        press(mapper, "dpad_down", t, options())
    assert mapper.row == 3
    [click] = press(mapper, "a", 4.0, options())
    assert click.kind == "click" and click.point == b.EXIT_TOONTOWN
    # The dialog: OK is highlighted, the bumpers do nothing, B cancels.
    [hover] = mapper.update(frozenset(), 5.0, options(dialog=True))
    assert hover.point == options(dialog=True).dialog[0]
    assert not press(mapper, "lb", 6.0, options(dialog=True)) and not mapper.take_taps()
    [cancel] = press(mapper, "b", 7.0, options(dialog=True))
    assert cancel.point == options(dialog=True).dialog[1]
    assert not mapper.take_taps()  # B cancelled the dialog, it didn't close the book
    # Back on the page, still on Exit Toontown.
    [hover] = mapper.update(frozenset(), 8.0, options())
    assert hover.point == b.EXIT_TOONTOWN


def test_speedchat_color_arrows():
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, options())
    press(mapper, "dpad_down", 1.0, options())
    click, hover = press(mapper, "dpad_right", 2.0, options())
    assert (click.kind, click.point) == ("click", b.COLOR_RIGHT)
    assert (hover.kind, hover.point) == ("hover", b.SPEEDCHAT_COLOR)
    [click, _] = press(mapper, "dpad_left", 3.0, options())
    assert click.point == b.COLOR_LEFT
    assert not press(mapper, "a", 4.0, options())


def test_pages_without_controls_hover_nothing():
    mapper = BookMapper()
    gags = BookScreen((b._center(0.46, 0),), 0, "gags")
    assert not mapper.update(frozenset(), 0.0, gags) and not gags.hovers
    assert not press(mapper, "dpad_down", 1.0, gags)


def test_blank_page_with_four_top_tabs():
    # Gardening's Specials page is blank white (the battle reader took it for its waiting screen).
    screen = replay("book_gardening_specials_1920x1009")
    assert screen.page == "gardening"
    assert len(screen.top_tabs) == 4 and screen.top_current == 3


def test_left_stick_moves_like_the_dpad():
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, options())
    [hover] = press(mapper, "ls_down", 1.0, options())
    assert hover.point == b.SPEEDCHAT_COLOR
    click, _ = press(mapper, "ls_right", 2.0, options())
    assert click.point == b.COLOR_RIGHT


@pytest.mark.parametrize("name,chosen", [("book_districts_1920x1009", None),
                                         ("book_districts_clicked_one_1920x1009", 8)])
def test_districts_page(name, chosen):
    screen = replay(name)
    assert screen.page == "districts" and not screen.hovers
    assert len(screen.districts) == 15
    assert screen.district_current == 12 and screen.district_chosen == chosen


def test_speedchat_only_district_confirm():
    screen = replay("book_districts_speedchat_only_confirm_1920x1009")
    assert screen.dialog is not None


def districts(chosen=None, current=2):
    tabs = tuple(b._center(0.46, 0.04 * i) for i in range(4))
    names = tuple(b._center(-0.337, 0.03 * i) for i in range(4))
    return BookScreen(tabs, 1, "districts", districts=names, district_chosen=chosen, district_current=current)


def test_districts_click_up_and_down_wrapping_then_teleport():
    mapper = BookMapper()
    assert mapper.update(frozenset(), 0.0, districts()) == []  # nothing to hover
    [c] = press(mapper, "dpad_down", 1.0, districts())
    assert c.kind == "click" and c.point == districts().districts[3]
    # Straight away, before the page shows the new choice: still counts from it, and wraps.
    [c] = press(mapper, "dpad_down", 1.1, districts())
    assert c.point == districts().districts[0]
    [c] = press(mapper, "dpad_up", 1.2, districts(chosen=0))
    assert c.point == districts().districts[3]
    [c] = press(mapper, "a", 2.0, districts(chosen=3))
    assert c.kind == "click" and c.point == b.TELEPORT


def test_districts_start_from_the_current_one_each_visit():
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, districts())
    press(mapper, "dpad_down", 1.0, districts())
    mapper.update(frozenset(), 2.0, BookScreen())  # book closed
    mapper.update(frozenset(), 3.0, districts(current=1))
    [c] = press(mapper, "dpad_up", 4.0, districts(current=1))
    assert c.point == districts().districts[0]


@pytest.mark.parametrize("name,open_places,playground", [
    ("book_map_1920x1009", 12, True), ("book_hover_ttc_1920x1009", 12, True),
    # Clouds over the places not found yet; in a playground there's no Back to Playground.
    ("book_clouds_blocking_locations_1920x1009", 4, False),
])
def test_map_page(name, open_places, playground):
    screen = replay(name)
    assert screen.page == "map" and screen.hovers
    assert len(screen.places) == open_places
    assert screen.go_home and screen.back_to_playground == playground


def test_map_clouds_hide_the_places_not_found():
    names = [n for n, _ in replay("book_clouds_blocking_locations_1920x1009").places]
    assert names == ["Toontown Central", "Minnie's Melodyland", "Donald's Dreamland", "Goofy Speedway"]


def map_screen(places=b.MAP_PLACES, playground=True):
    tabs = tuple(b._center(0.46, 0.04 * i) for i in range(4))
    return BookScreen(tabs, 2, "map", places=tuple(places), go_home=True, back_to_playground=playground)


def test_map_moves_to_the_nearest_place_that_way():
    mapper = BookMapper()
    [hover] = mapper.update(frozenset(), 0.0, map_screen())
    assert hover.name == "Toontown Central"
    assert [c.name for c in press(mapper, "dpad_up", 1.0, map_screen())] == ["Minnie's Melodyland"]
    assert [c.name for c in press(mapper, "dpad_right", 2.0, map_screen())] == ["The Brrrgh"]
    assert [c.name for c in press(mapper, "ls_down", 3.0, map_screen())] == ["Donald's Dock"]
    [click] = press(mapper, "a", 4.0, map_screen())
    assert (click.kind, click.name) == ("click", "go to Donald's Dock")


def test_map_skips_clouded_places_and_stops_at_the_edge():
    places = [p for p in b.MAP_PLACES if p[0] in ("Toontown Central", "Goofy Speedway", "Donald's Dreamland")]
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, map_screen(places))
    assert [c.name for c in press(mapper, "dpad_left", 1.0, map_screen(places))] == ["Goofy Speedway"]
    assert not press(mapper, "dpad_left", 2.0, map_screen(places))  # nothing further left


def test_map_home_and_playground_buttons():
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, map_screen())
    def clicks(button, t, screen):
        return [c.point for c in press(mapper, button, t, screen) if c.kind == "click"]

    assert clicks("y", 1.0, map_screen()) == [b.GO_HOME]
    assert clicks("x", 2.0, map_screen()) == [b.BACK_TO_PLAYGROUND]
    assert clicks("x", 3.0, map_screen(playground=False)) == []
