from test_book import replay

from ttcontroller.controller import ControllerState
from ttcontroller.mail import MailScreen
from ttcontroller.mapper import OverworldMapper
from ttcontroller.vp import read_pie_round


def test_reads_the_pie_round():
    assert replay("vp_pies_1920x1009", read_pie_round)


def test_any_icon_in_the_blue_box_counts():
    """The CJ's evidence round has the same box with another icon."""
    import json
    from pathlib import Path
    from ttcontroller import vp
    data = json.loads((Path(__file__).parent / "fixtures" / "battle" / "vp_pies_1920x1009.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    icon = vp.PIE_ICON.to_client(w, h)
    others = {vp._top(-0.0149, 0.0436).to_client(w, h), vp._top(-0.0050, 0.0436).to_client(w, h)}

    def evidence(x, y):  # the pie's cream swapped for a brown folder's color
        return (150, 110, 60) if (x, y) == icon or (x, y) in others else tuple(pixels[f"{x},{y}"])
    assert read_pie_round(w, h, evidence)

    def empty(x, y):  # just the box's blue: no icon
        return (60, 150, 240) if (x, y) == icon else tuple(pixels[f"{x},{y}"])
    assert not read_pie_round(w, h, empty)


def test_not_on_other_screens():
    for name in ("clarabelle_popup_1920x1009", "gags_hud_1920x1009", "test_1920x1009"):
        assert not replay(name, read_pie_round), name


class MailView:
    def is_visible(self, button):
        return False

    def read(self, reader):
        raise AssertionError("the mail isn't read in the pie round")


RT = ControllerState(right_trigger=1.0)
RB = ControllerState(buttons=frozenset({"rb"}))


def test_rb_throws_while_held_in_the_pie_round():
    m = OverworldMapper()
    view = MailView()
    assert "performAction" in m.update(RB, 0.0, view, pies=True)
    assert "performAction" in m.update(RB, 0.5, view, pies=True)  # held: winding up
    assert "performAction" not in m.update(ControllerState(), 0.6, view, pies=True)
    assert m.take_clicks() == [] and "friendsList" not in m.update(ControllerState(), 0.7, view, pies=True)


def test_rt_doesnt_throw_in_the_pie_round():
    m = OverworldMapper()
    assert "performAction" not in m.update(RT, 0.0, MailView(), pies=True)
    assert "performAction" not in m.update(ControllerState(), 0.6, MailView(), pies=True)


def test_rt_is_mail_again_outside_the_round():
    class View(MailView):
        def read(self, reader):
            return MailScreen()

    m = OverworldMapper()
    assert "performAction" not in m.update(RT, 0.0, View())
