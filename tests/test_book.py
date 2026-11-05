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
