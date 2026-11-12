from test_book import replay

from ttcontroller.ceo import read_leave
from ttcontroller.controller import ControllerState
from ttcontroller.mapper import OverworldMapper


def test_finds_the_leave_button_at_each_size():
    for name, (w, h), (x, y) in (("ceo_golfing_1920x1009", (1920, 1009), (1490, 914)),
                                 ("ceo_seltzer_1920x1009", (1920, 1009), (1490, 914)),
                                 ("ceo_golfing_2_1577x535", (1577, 535), (1069, 484)),
                                 ("ceo_seltzer_5_1637x533", (1637, 533), (1098, 483)),
                                 # Tall: only a sliver shows at the right edge, so that's clicked.
                                 ("ceo_golfing_3_388x812", (388, 812), (386, 563))):
        point = replay(name, read_leave)
        px, py = point.to_client(w, h)
        assert abs(px - x) <= 2 and abs(py - y) <= 2, name


def test_not_on_other_screens():
    assert replay("clarabelle_popup_1920x1009", read_leave) is None
    assert read_leave(1920, 1009, lambda x, y: (90, 70, 50)) is None


class View:
    def __init__(self, leave):
        self.leave = leave

    def is_visible(self, button):
        return False

    def read(self, reader):
        return self.leave if reader is read_leave else None


def b(m, view, free=True):
    m.update(ControllerState(buttons=frozenset({"b"})), 0.0, view, free=free)
    m.update(ControllerState(), 0.1, view, free=free)
    return [c.center for c in m.take_clicks()]


def test_b_clicks_leave():
    point = replay("ceo_seltzer_1920x1009", read_leave)
    assert b(OverworldMapper(), View(point)) == [point]
    assert b(OverworldMapper(), View(None)) == []
    assert b(OverworldMapper(), View(point), free=False) == []


def test_a_hovered_leave_button_is_yellow():
    # Leave Crane, hovered, as in the CFO video still: yellow in the same place.
    w, h = 1920, 1009
    from ttcontroller.ceo import LEAVE
    cx, cy = LEAVE.to_client(w, h)

    def pixel(x, y):
        if (x - cx) ** 2 + (y - cy) ** 2 <= 30 ** 2:
            return (240, 200, 40)
        if abs(y - (cy + 62)) <= 2 and abs(x - cx) < 80 and x % 7 < 3:
            return (255, 255, 255)  # "Leave Crane"
        return (40, 40, 40)

    point = read_leave(w, h, pixel)
    assert point is not None and point.to_client(w, h) == (cx, cy)


def test_leave_crane_hovered_in_game():
    point = replay("cfo_crane_hover_3024x1710", read_leave)
    px, py = point.to_client(3024, 1710)
    assert abs(px - 2409) <= 3 and abs(py - 1548) <= 3


def test_a_darker_red_counts():
    # The CFO's Leave Crane is a darker red than the CEO's (the user): (140, 55, 60) or so.
    w, h = 1920, 1009
    from ttcontroller.ceo import LEAVE
    cx, cy = LEAVE.to_client(w, h)

    def pixel(x, y):
        if (x - cx) ** 2 + (y - cy) ** 2 <= 30 ** 2:
            return (140, 55, 60)
        if abs(y - (cy + 62)) <= 2 and abs(x - cx) < 80 and x % 7 < 3:
            return (255, 255, 255)
        return (40, 40, 40)

    assert read_leave(w, h, pixel) is not None
    assert read_leave(w, h, lambda x, y: (200, 120, 40) if (x - cx) ** 2 + (y - cy) ** 2 <= 900
                      else (255, 255, 255) if abs(y - (cy + 62)) <= 2 and x % 7 < 3 else (40, 40, 40)) is None  # orange


def test_b_doesnt_look_for_leave_outside_cashbot_and_bossbot_hq():
    point = replay("ceo_seltzer_1920x1009", read_leave)
    m = OverworldMapper()
    m.leave_possible = False  # TTR's Local API: somewhere else
    assert b(m, View(point)) == []
