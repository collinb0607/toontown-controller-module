import math

import pytest

from test_book import replay

from ttcontroller import golf_green as gg
from ttcontroller.golf_green import GolfGreenMapper, GolfGreenScreen, aim_image, read_golf_green, stick_angle


def test_reads_the_golf_green():
    screen = replay("golf_green_video_still_1280x677", read_golf_green)
    assert screen.is_open
    x, y = screen.exit.to_client(1280, 677)
    assert abs(x - 996) <= 3 and abs(y - 594) <= 3


@pytest.mark.parametrize("name", ["test_1920x1009", "mailbox_popup_1920x1009", "gardening_hud_1_1920x1009",
                                  "battle_gags_1920x1009", "shop_1920x1009"])
def test_other_screens_arent_the_golf_green(name):
    assert not replay(name, read_golf_green).is_open


def test_the_stick_points_the_aim_within_75_degrees():
    assert stick_angle(0.0, -1.0) == pytest.approx(0)  # up
    assert stick_angle(1.0, -1.0) == pytest.approx(45)
    assert stick_angle(1.0, 0.0) == 75  # straight right: as far as it goes
    assert stick_angle(-0.3, 1.0) == -75  # pulled down: the nearer side's limit
    assert stick_angle(0.2, -0.2) is None  # barely pushed


OPEN = GolfGreenScreen(exit=gg._center(0.5258, 0.3767), how_to_play=gg._center(0.5251, 0.4483))


def test_starts_straight_up_and_the_aim_stays_when_the_stick_is_let_go():
    m = GolfGreenMapper()
    first = m.update(frozenset(), (0.0, 0.0), 0.0, OPEN)
    assert [c.point for c in first] == [gg.aim_point(0.0)]
    m.update(frozenset(), (1.0, -1.0), 0.1, OPEN)
    assert m.angle == pytest.approx(45)
    assert m.update(frozenset(), (0.0, 0.0), 0.2, OPEN) == []  # let go: no move
    assert m.angle == pytest.approx(45)


def test_d_pad_nudges_and_a_shoots_at_the_aim():
    m = GolfGreenMapper()
    m.update(frozenset(), (0.0, 0.0), 0.0, OPEN)
    m.update(frozenset({"dpad_right"}), (0.0, 0.0), 0.1, OPEN)
    assert m.angle == pytest.approx(gg.NUDGE)
    m.update(frozenset(), (0.0, 0.0), 0.2, OPEN)
    shot = m.update(frozenset({"a"}), (0.0, 0.0), 0.3, OPEN)
    assert [(c.kind, c.point) for c in shot] == [("click", gg.aim_point(gg.NUDGE))]


def test_y_how_to_play_and_holding_b_exits():
    m = GolfGreenMapper()
    m.update(frozenset(), (0.0, 0.0), 0.0, OPEN)
    assert [c.point for c in m.update(frozenset({"y"}), (0.0, 0.0), 0.1, OPEN)] == [OPEN.how_to_play]
    m.update(frozenset(), (0.0, 0.0), 0.2, OPEN)
    assert m.update(frozenset({"b"}), (0.0, 0.0), 0.3, OPEN) == []  # a tap does nothing
    assert [c.point for c in m.update(frozenset({"b"}), (0.0, 0.0), 1.0, OPEN)] == [OPEN.exit]


def test_aim_point_is_on_the_circle():
    p = gg.aim_point(90.0)
    assert p.x == pytest.approx(gg.AIM_RADIUS) and p.y == pytest.approx(gg.PIVOT.y)


@pytest.mark.parametrize("angle", [-75, 0, 40])
def test_aim_image_puts_the_crosshair_at_the_aim(angle):
    image, (ox, oy) = aim_image(300, angle, 1000)
    a = math.radians(angle)
    cx, cy = round(ox + 300 * math.sin(a)), round(oy - 300 * math.cos(a))
    assert image[cy, cx + round(0.016 * 1000 * 0.6), 3] > 200  # the ring, right of the crosshair's middle
    assert image[oy, ox, 3] < 255  # the line fades in from the launcher
