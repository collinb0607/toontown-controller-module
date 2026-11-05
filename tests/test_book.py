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


def test_gags_tab_reads_the_gags_you_have():
    screen = replay("book_gags_1920x1009")
    assert screen.trunk is None and screen.gags is not None
    assert [any(row) for row in screen.gags] == [True, False, True, True, True, True, True]  # no Trap
    assert all(screen.gags[4])  # Throw


@pytest.mark.parametrize("name,tab,cards", [
    ("book_gags_sos_1920x1009", "SOS", 8), ("book_trunk_1920x1009", "SOS", 8),
    ("book_gags_sos_scrolled_1920x1009", "SOS", 4),  # rows cut off at the edges don't count
    ("book_gags_remote_controls_1920x1009", "remotes", 0), ("book_gags_doodle_1920x1009", "doodle", 0),
])
def test_trunk_tab_reads_like_the_battle_trunk(name, tab, cards):
    screen = replay(name)
    assert screen.gags is None and screen.trunk.tab == tab
    assert sum(i.name.startswith("SOS card") for i in screen.trunk.items) == cards


def test_every_remote_can_be_hovered_even_ones_you_dont_have():
    screen = replay("book_gags_remote_controls_1920x1009")  # only one healing remote is owned
    remotes = sorted(b.to_book(i.point).to_client(1920, 1009) for i in screen.trunk.items if not i.tab and "remote" in i.name)
    assert len(remotes) == 6
    assert (805, 488) in remotes  # the one you have, where it shows


def test_trunk_cards_are_where_they_show_in_the_book():
    screen = replay("book_gags_sos_1920x1009")
    centers = sorted(b.to_book(i.point).to_client(1920, 1009) for i in screen.trunk.items
                     if i.name.startswith("SOS card"))
    assert centers[:2] == [(824, 298), (824, 460)]


def test_trunk_filter_list():
    screen = replay("book_gags_sos_filter_1920x1009")
    assert screen.trunk.filter_open
    assert sum(i.name.startswith("filter ") for i in screen.trunk.items) == 10


def gags_screen(owned=None):
    owned = owned or tuple(tuple(r != 1 for _ in range(7)) for r in range(7))
    return BookScreen(tuple(b._center(0.46, 0.04 * i) for i in range(4)), 3, "gags", gags=owned)


def test_gags_start_on_nothing_then_the_cupcake():
    mapper = BookMapper()
    assert mapper.update(frozenset(), 0.0, gags_screen()) == []
    assert not mapper.hovering(gags_screen())  # so the cursor parks
    [hover] = press(mapper, "ls_right", 1.0, gags_screen())
    assert hover.point == b.gag_point(*b.CUPCAKE) and hover.size == b.GAG_SIZE
    assert mapper.hovering(gags_screen())
    [hover] = press(mapper, "dpad_right", 2.0, gags_screen())
    assert hover.point == b.gag_point(4, 1)
    # Up from Lure skips the empty Trap row.
    press(mapper, "dpad_up", 3.0, gags_screen())
    press(mapper, "dpad_up", 4.0, gags_screen())
    [hover] = press(mapper, "dpad_up", 5.0, gags_screen())
    assert hover.point == b.gag_point(0, 1)
    assert not press(mapper, "a", 6.0, gags_screen())  # nothing to click
    # Back to nothing after leaving the tab.
    mapper.update(frozenset(), 7.0, BookScreen(gags_screen().tabs, 3, "gags"))
    [hover] = press(mapper, "dpad_down", 8.0, gags_screen())
    assert hover.point == b.gag_point(*b.CUPCAKE)


def test_trunk_tab_moves_with_the_battle_mapper_in_book_places():
    screen = replay("book_gags_sos_1920x1009")
    mapper = BookMapper()
    commands = mapper.update(frozenset(), 0.0, screen)
    assert commands and all(c.kind == "hover" for c in commands)
    first = commands[-1]
    assert first.size is not None
    # Points are the book's: inside the book's trunk panel, not the battle's.
    x, y = first.point.to_client(1920, 1009)
    assert 570 < x < 1360 and 140 < y < 600
    # B isn't the trunk's: it still closes the book.
    press(mapper, "b", 1.0, screen)
    assert mapper.take_taps() == ["stickerBook"]


def test_doodle_tricks_click_their_blue_button():
    screen = replay("book_gags_doodle_1920x1009")
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, screen)
    press(mapper, "dpad_down", 1.0, screen)
    [click] = press(mapper, "a", 2.0, screen)
    # The blue button at the trick's left end (1020 to 1085 across), not the colored bar.
    assert click.kind == "click" and click.name.startswith("doodle trick")
    x, y = click.point.to_client(1920, 1009)
    assert 1025 < x < 1080


def test_right_stick_scrolls_the_sos_cards():
    screen = replay("book_gags_sos_1920x1009")  # at the top: can scroll down only
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, screen)
    [scroll] = press(mapper, "rs_down", 1.0, screen)
    assert scroll.kind == "scroll" and scroll.notches == -1
    x, y = scroll.point.to_client(1920, 1009)
    assert 740 < x < 1290 and 220 < y < 560  # over the list
    def scrolls(button, t, s):
        return [c for c in press(mapper, button, t, s) if c.kind == "scroll"]

    assert not scrolls("rs_up", 2.0, screen)  # already at the top
    [scroll] = scrolls("rs_up", 3.0, replay("book_gags_sos_scrolled_1920x1009"))
    assert scroll.notches == 1


@pytest.mark.parametrize("button", ["lb", "rb", "lt", "rt", "b", "start"])
def test_leaving_the_page_drops_the_highlight(button):
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, gags_screen())
    press(mapper, "dpad_right", 1.0, gags_screen())
    assert not mapper.take_left_page()  # moving around the page keeps it
    press(mapper, button, 2.0, gags_screen())
    assert mapper.take_left_page() and not mapper.take_left_page()


def test_after_scrolling_the_card_under_the_cursor_is_highlighted():
    top = replay("book_gags_sos_1920x1009")
    scrolled = replay("book_gags_sos_scrolled_1920x1009")
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, top)
    press(mapper, "rs_down", 1.0, top)
    assert mapper.update(frozenset(), 1.1, scrolled) == []  # still moving
    [hover] = mapper.update(frozenset(), 1.3, scrolled)
    assert hover.kind == "hover" and hover.name.startswith("SOS card") and hover.size is not None
    assert mapper._trunk.trunk_item.name == hover.name  # moving on starts from it


@pytest.mark.parametrize("name", ["book_toontasks_1920x1009", "book_toontasks_hover_1920x1009"])
def test_toontasks_page(name):
    screen = replay(name)
    assert screen.page == "toontasks"
    assert len(screen.tasks) == 4 and all(t is not None for t in screen.tasks)
    # Only the just-for-fun task has a trash can.
    assert screen.tasks[0] not in (None, False) and screen.tasks[1:] == (False, False, False)
    x, y = screen.tasks[0].to_client(1920, 1009)
    assert 880 < x < 910 and 225 < y < 270


def test_toontasks_delete_confirm():
    assert replay("book_toontasks_delete_popup_1920x1009").dialog is not None


def tasks_screen(tasks):
    return BookScreen(tuple(b._center(0.46, 0.04 * i) for i in range(5)), 4, "toontasks", tasks=tasks)


def test_toontasks_hover_and_delete():
    trash = b._center(-0.06, -0.25)
    screen = tasks_screen((trash, False, None, False))  # the third scroll is blank
    mapper = BookMapper()
    assert mapper.update(frozenset(), 0.0, screen) == [] and not mapper.hovering(screen)
    [hover] = press(mapper, "ls_down", 1.0, screen)
    assert hover.name == "task 1" and hover.size is None  # no frame here
    assert [c.point for c in press(mapper, "x", 2.0, screen) if c.kind == "click"] == [trash]
    hover = [c for c in press(mapper, "dpad_right", 3.0, screen) if c.kind == "hover"][-1]
    assert hover.name == "task 2"
    assert not [c for c in press(mapper, "x", 4.0, screen) if c.kind == "click"]  # no trash can
    [hover] = [c for c in press(mapper, "dpad_down", 5.0, screen) if c.kind == "hover"]
    assert hover.name == "task 4"
    assert not [c for c in press(mapper, "dpad_left", 6.0, screen) if c.kind == "hover" and c.name == "task 3"]


def test_toontask_x_clicks_its_trash_can():
    trash = b._center(-0.06, -0.25)
    screen = tasks_screen((trash, False, False, False))
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, screen)
    press(mapper, "dpad_down", 1.0, screen)
    [click] = [c for c in press(mapper, "x", 2.0, screen) if c.kind == "click"]
    assert click.point == trash


def test_cancelling_a_task_delete_goes_back_to_that_task():
    trash = b._center(0.17, -0.25)
    screen = tasks_screen((False, trash, False, False))
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, screen)
    press(mapper, "dpad_down", 1.0, screen)
    press(mapper, "dpad_right", 2.0, screen)  # task 2
    press(mapper, "x", 3.0, screen)
    dialog = BookScreen(dialog=(b._center(-0.05, 0.1), b._center(0.05, 0.1)))
    mapper.update(frozenset(), 4.0, dialog)
    press(mapper, "b", 5.0, dialog)
    [hover] = mapper.update(frozenset(), 6.0, screen)
    assert hover.name == "task 2"


def test_the_book_takes_the_trunks_buttons_too():
    # LS is the SOS filter on the Trunk tab, so it mustn't also toggle sprint.
    assert "ls" in BookMapper().buttons


def test_resistance_rank_pages_turn_with_left_and_right():
    assert replay("book_resistance_rank_1920x1009").page == "resistance rank"
    rank = BookScreen(tuple(b._center(0.46, 0.04 * i) for i in range(6)), 5, "resistance rank")
    mapper = BookMapper()
    assert mapper.update(frozenset(), 0.0, rank) == []  # just to look at
    [click] = press(mapper, "dpad_right", 1.0, rank)
    assert click.kind == "click" and click.point == b.RANK_PAGE_ARROWS["right"]
    [click] = press(mapper, "ls_left", 2.0, rank)
    assert click.point == b.RANK_PAGE_ARROWS["left"]
    assert not press(mapper, "dpad_up", 3.0, rank)


SUMMON_COGS = ((3, 0), (4, 0), (5, 0), (1, 1), (2, 2), (2, 3), (4, 3))


@pytest.mark.parametrize("name,cogs", [
    ("book_cog_gallery_1920x1009", SUMMON_COGS),
    ("book_cog_gallery_summon_hover_1920x1009", SUMMON_COGS),  # the hovered button turns light blue
    ("book_cog_gallery_some_missing_1920x1009", ()),  # nothing to summon, even on gold (maxed) cogs
])
def test_cog_gallery_summon_buttons(name, cogs):
    screen = replay(name)
    assert screen.page == "cog gallery" and screen.summon_cogs == cogs


@pytest.mark.parametrize("name", ["book_cog_gallery_summon_popup_1920x1009",
                                  "book_cog_gallery_summon_popup_hover_1920x1009"])
def test_issue_a_cog_summons_popup(name):
    screen = replay(name)
    assert screen.is_open and screen.hovers
    # Summon a Cog Invasion is dark teal (unavailable), so it can't be hovered.
    assert [p.to_client(1920, 1009) for p in screen.summons] == [(1110, 226), (1110, 290)]


def gallery(cogs=SUMMON_COGS):
    return BookScreen(tuple(b._center(0.46, 0.04 * i) for i in range(7)), 6, "cog gallery", summon_cogs=cogs)


def test_cog_gallery_suits_on_the_right_stick():
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, gallery())
    for t, (button, suit) in enumerate((("rs_up", "up"), ("rs_left", "left"), ("rs_right", "right"),
                                        ("rs_down", "down")), start=1):
        clicks = [c for c in press(mapper, button, float(t), gallery()) if c.kind == "click"]
        assert [c.point for c in clicks] == [b.SUIT_ICONS[suit]]


def test_cog_gallery_summons_and_back():
    mapper = BookMapper()
    assert mapper.update(frozenset(), 0.0, gallery()) == [] and not mapper.hovering(gallery())
    [hover] = press(mapper, "dpad_down", 1.0, gallery())
    assert hover.point == b.summon_button((3, 0))
    [hover] = press(mapper, "dpad_right", 2.0, gallery())
    assert hover.point == b.summon_button((4, 0))
    [click] = press(mapper, "a", 3.0, gallery())
    assert click.kind == "click" and click.point == b.summon_button((4, 0))
    # The popup: starts on its top button, up/down move, B closes it.
    popup = BookScreen(summons_open=True,
                       summons=(b._center(0.15, -0.28), b._center(0.15, -0.22), b._center(0.15, -0.15)))
    [hover] = mapper.update(frozenset(), 4.0, popup)
    assert hover.point == popup.summons[0]
    [hover] = press(mapper, "dpad_down", 5.0, popup)
    assert hover.point == popup.summons[1]
    assert not press(mapper, "lb", 6.0, popup) and not mapper.take_taps()
    [close] = press(mapper, "b", 7.0, popup)
    assert close.point == b.SUMMONS_CLOSE and not mapper.take_taps()
    # Back on the gallery, on the same cog's button.
    [hover] = mapper.update(frozenset(), 8.0, gallery())
    assert hover.point == b.summon_button((4, 0))


def test_summons_confirm_and_message():
    confirm = replay("book_cog_gallery_summon_popup_confirmation_1920x1009")
    assert confirm.dialog is not None  # Yes/No
    message = replay("book_cog_gallery_summon_popup_message_1920x1009")
    assert message.is_open and message.summons_open and message.summons == ()


def test_declining_a_summons_goes_back_to_the_one_picked_and_the_message_closes_with_b():
    popup = BookScreen(summons_open=True,
                       summons=(b._center(0.15, -0.28), b._center(0.15, -0.22), b._center(0.15, -0.15)))
    mapper = BookMapper()
    mapper.update(frozenset(), 0.0, gallery())
    press(mapper, "dpad_down", 1.0, gallery())
    press(mapper, "a", 2.0, gallery())
    mapper.update(frozenset(), 3.0, popup)
    press(mapper, "dpad_down", 4.0, popup)
    press(mapper, "a", 5.0, popup)  # the second summons
    dialog = BookScreen(dialog=(b._center(-0.05, 0.13), b._center(0.05, 0.13)))
    [hover] = mapper.update(frozenset(), 6.0, dialog)
    assert hover.point == dialog.dialog[0]  # Yes
    [no] = press(mapper, "b", 7.0, dialog)
    assert no.point == dialog.dialog[1]
    [hover] = mapper.update(frozenset(), 8.0, popup)
    assert hover.point == popup.summons[1]  # the one picked, not the top one
    # Confirmed: the message, closed with B, back to the gallery on the same cog.
    press(mapper, "a", 9.0, popup)
    mapper.update(frozenset(), 10.0, dialog)
    press(mapper, "a", 11.0, dialog)
    message = BookScreen(summons_open=True)
    assert mapper.update(frozenset(), 12.0, message) == []
    [close] = press(mapper, "b", 13.0, message)
    assert close.point == b.SUMMONS_CLOSE and not mapper.take_taps()
    [hover] = mapper.update(frozenset(), 14.0, gallery())
    assert hover.point == b.summon_button((3, 0))


def test_the_summons_message_closes_with_a_too():
    mapper = BookMapper()
    message = BookScreen(summons_open=True)
    mapper.update(frozenset(), 0.0, message)
    [close] = press(mapper, "a", 1.0, message)
    assert close.point == b.SUMMONS_CLOSE
