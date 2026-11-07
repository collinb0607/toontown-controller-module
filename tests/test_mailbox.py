import pytest

from test_book import replay

from ttcontroller import mailbox as mb
from ttcontroller.mailbox import MailboxMapper, MailboxScreen, read_mailbox


@pytest.mark.parametrize("name", ["mailbox_popup_1920x1009", "mailbox_popup_hover_1_1920x1009",
                                  "mailbox_popup_hover_2_1920x1009"])
def test_reads_the_open_mailbox(name):
    assert replay(name, read_mailbox).is_open


@pytest.mark.parametrize("name", ["estate_popup_1920x1009", "gardening_hud_1_1920x1009", "test_1920x1009",
                                  "shop_1920x1009", "book_options_1920x1009"])
def test_other_screens_arent_the_mailbox(name):
    assert not replay(name, read_mailbox).is_open


@pytest.mark.parametrize("button,point", [("dpad_left", mb.LEFT), ("dpad_right", mb.RIGHT), ("a", mb.TAKE),
                                          ("x", mb.DISCARD), ("b", mb.CLOSE)])
def test_buttons(button, point):
    m = MailboxMapper()
    screen = MailboxScreen(True)
    assert [c.point for c in m.update(frozenset({button}), 0.0, screen)] == [point]
    assert m.update(frozenset({button}), 0.1, screen) == []  # held: once (the arrows repeat later)


def test_nothing_when_closed():
    assert MailboxMapper().update(frozenset({"a"}), 0.0, MailboxScreen()) == []
