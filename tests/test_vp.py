from test_book import replay

from ttcontroller.controller import ControllerState
from ttcontroller.mail import MailScreen
from ttcontroller.mapper import OverworldMapper
from ttcontroller.vp import read_pie_round


def test_reads_the_pie_round():
    assert replay("vp_pies_1920x1009", read_pie_round)


def test_not_on_other_screens():
    for name in ("clarabelle_popup_1920x1009", "gags_hud_1920x1009", "test_1920x1009"):
        assert not replay(name, read_pie_round), name


class MailView:
    def is_visible(self, button):
        return False

    def read(self, reader):
        raise AssertionError("the mail isn't read in the pie round")


RT = ControllerState(right_trigger=1.0)


def test_rt_throws_while_held_in_the_pie_round():
    m = OverworldMapper()
    view = MailView()
    assert "performAction" in m.update(RT, 0.0, view, pies=True)
    assert "performAction" in m.update(RT, 0.5, view, pies=True)  # held: winding up
    assert "performAction" not in m.update(ControllerState(), 0.6, view, pies=True)
    assert m.take_clicks() == []


def test_rt_is_mail_again_outside_the_round():
    class View(MailView):
        def read(self, reader):
            return MailScreen()

    m = OverworldMapper()
    assert "performAction" not in m.update(RT, 0.0, View())
