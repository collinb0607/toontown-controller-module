import pytest
from test_book import replay

from ttcontroller import ui
from ttcontroller.controller import ControllerState
from ttcontroller.elevator import HOP_OFF, read_hop_off
from ttcontroller.mapper import OverworldMapper


@pytest.mark.parametrize("name", [
    "elevator_cog_building_1920x1009", "elevator_cog_building_2_1660x614", "elevator_cog_building_3_515x880",
    "elevator_ceo_1920x1009", "elevator_cog_golf_kart_1920x1009",
    "elevator_golf_kart_1920x1009",  # red, with cream letters
])
def test_finds_hop_off(name):
    assert replay(name, read_hop_off) == HOP_OFF


def test_not_on_other_screens():
    assert replay("clarabelle_popup_1920x1009", read_hop_off) is None
    assert read_hop_off(1920, 1009, lambda x, y: (150, 150, 150)) is None  # plain gray: no letters or rim


class View:
    def __init__(self, hop, speedchat=False):
        self.hop = hop
        self.speedchat = speedchat

    def is_visible(self, button):
        return self.speedchat and button == ui.SPEEDCHAT_MENU

    def read(self, reader):
        return self.hop if reader is read_hop_off else None


def b(m, view, free=True, at=0.0):
    m.update(ControllerState(buttons=frozenset({"b"})), at, view, free=free)
    m.update(ControllerState(), at + 0.1, view, free=free)
    return [c.name for c in m.take_clicks()]


def test_b_hops_off():
    hop = replay("elevator_cog_building_1920x1009", read_hop_off)
    assert b(OverworldMapper(), View(hop)) == ["hop off"]
    assert b(OverworldMapper(), View(None)) == []
    assert b(OverworldMapper(), View(hop), free=False) == []


def test_b_closes_speedchat_first():
    m = OverworldMapper()
    hop = replay("elevator_cog_building_1920x1009", read_hop_off)
    assert b(m, View(hop, speedchat=True)) == [ui.SPEEDCHAT.name]
    assert b(m, View(hop), at=1.0) == ["hop off"]
