from test_book import replay

from ttcontroller.controller import ControllerState
from ttcontroller.mail import MailScreen, read_mail
from ttcontroller.mapper import OverworldMapper
from ttcontroller.ui import UIPoint


def at(point, size=(1920, 1009)):
    return point.to_client(*size)


def test_finds_the_popups_x_and_clarabelles_icon():
    screen = replay("clarabelle_popup_1920x1009", read_mail)
    assert abs(at(screen.close)[0] - 1450) <= 3 and abs(at(screen.close)[1] - 181) <= 3
    assert abs(at(screen.icon)[0] - 1712) <= 3 and abs(at(screen.icon)[1] - 60) <= 3


def test_the_icon_without_a_popup():
    screen = replay("test_1920x1009", read_mail)
    assert screen.close is None
    assert abs(at(screen.icon)[0] - 1712) <= 3 and abs(at(screen.icon)[1] - 60) <= 3


def test_the_icon_in_a_tall_window():
    screen = replay("speedchat_539x786", read_mail)
    assert screen.close is None
    x, y = at(screen.icon, (539, 786))
    assert abs(x - 429) <= 3 and abs(y - 33) <= 3


def test_nothing_on_a_plain_screen():
    assert read_mail(1920, 1009, lambda x, y: (90, 70, 50)) == MailScreen()


class FakeView:
    def __init__(self, mail):
        self.mail = mail

    def is_visible(self, button):
        return False

    def read(self, reader):
        return self.mail


CLOSE = UIPoint("right", -0.46, 0.18)
ICON = UIPoint("right", -0.21, 0.06)


def rt(m, view, now, free=True):
    m.update(ControllerState(right_trigger=1.0), now, view, free=free)
    m.update(ControllerState(), now + 0.05, view, free=free)
    return [b.center for b in m.take_clicks()]


def test_rt_closes_the_popup_then_clicks_the_icon():
    m = OverworldMapper()
    assert rt(m, FakeView(MailScreen(close=CLOSE, icon=ICON)), 0.0) == [CLOSE]
    assert rt(m, FakeView(MailScreen(icon=ICON)), 1.0) == [ICON]
    assert rt(m, FakeView(MailScreen()), 2.0) == []


def test_rt_does_nothing_while_something_else_is_open():
    m = OverworldMapper()
    assert rt(m, FakeView(MailScreen(close=CLOSE, icon=ICON)), 0.0, free=False) == []
