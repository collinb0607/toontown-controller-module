import pytest
from test_book import replay

from ttcontroller import silly as s
from ttcontroller.controller import ControllerState
from ttcontroller.mail import MailScreen, read_mail
from ttcontroller.mapper import OverworldMapper
from ttcontroller.silly import SillyMapper, SillyScreen, read_silly


@pytest.mark.parametrize("name,icon,card,details", [
    ("silly_meter_1920x1009", (1717, 62), False, False),
    ("silly_meter_popup_1920x1009", None, True, False),
    ("silly_meter_details_1920x1009", None, True, True),
    ("clarabelle_popup_1920x1009", None, False, False),  # Clarabelle's icon in the same slot isn't it
    ("boarding_groups_1920x1009", None, False, False),
    ("task_turn_in_1920x1009", None, False, False),  # pale yellow wallpaper behind the slot
])
def test_reads_the_silly_meter(name, icon, card, details):
    screen = replay(name, read_silly)
    assert (screen.icon.to_client(1920, 1009) if screen.icon else None) == icon
    assert screen.card == card and screen.details == details


class View:
    def __init__(self, silly=SillyScreen(), mail=MailScreen()):
        self.silly, self.mail = silly, mail

    def is_visible(self, button):
        return False

    def read(self, reader):
        return self.silly if reader is read_silly else self.mail if reader is read_mail else None


def hold_rt(m, view, start, seconds):
    t = start
    while t < start + seconds:
        m.update(ControllerState(right_trigger=1.0), t, view)
        t += 0.05
    m.update(ControllerState(), t, view)
    return [b.name for b in m.take_clicks()]


def test_holding_rt_opens_the_silly_meter_and_a_tap_is_still_clarabelle():
    icon = replay("silly_meter_1920x1009", read_silly)
    clarabelle = MailScreen(icon=s._pt(1717, 62))
    m = OverworldMapper()
    assert hold_rt(m, View(silly=icon, mail=clarabelle), 0.0, 0.7) == ["silly meter"]  # no mail click first
    assert hold_rt(m, View(silly=icon, mail=clarabelle), 2.0, 0.1) == ["clarabelle"]  # a tap, on letting go


def test_holding_rt_again_closes_it():
    m = OverworldMapper()
    assert hold_rt(m, View(silly=replay("silly_meter_popup_1920x1009", read_silly)), 0.0, 0.7) == ["close silly meter"]
    details = replay("silly_meter_details_1920x1009", read_silly)
    assert hold_rt(m, View(silly=details), 2.0, 0.7) == ["close silly meter details", "close silly meter"]


def test_the_card():
    m = SillyMapper()
    card = replay("silly_meter_popup_1920x1009", read_silly)
    out = m.update(frozenset({"dpad_left"}), 0.0, card)
    assert [(c.kind, c.point) for c in out] == [("click", s.DETAILS_BUTTON)]
    m.update(frozenset(), 0.1, card)
    details = replay("silly_meter_details_1920x1009", read_silly)
    assert [c.point for c in m.update(frozenset({"b"}), 0.2, details)] == [s.DETAILS_X]  # the top card first
    m.update(frozenset(), 0.3, card)
    assert [c.point for c in m.update(frozenset({"b"}), 0.4, card)] == [s.CARD_X]
    assert m.update(frozenset({"dpad_left"}), 0.5, SillyScreen()) == []


def test_clarabelle_moves_a_slot_left_beside_the_silly_meter():
    # Both up: the gauge takes Clarabelle's slot, and she's one to the left.
    mail = replay("clarabelle_bug_1920x1009", read_mail)
    silly = replay("clarabelle_bug_1920x1009", read_silly)
    assert mail.icon is not None and abs(mail.icon.to_client(1920, 1009)[0] - 1575) <= 3
    assert silly.icon.to_client(1920, 1009) == (1717, 62)
    m = OverworldMapper()
    assert hold_rt(m, View(silly=silly, mail=mail), 0.0, 0.1) == ["clarabelle"]
    assert hold_rt(m, View(silly=silly, mail=mail), 2.0, 0.7) == ["silly meter"]
