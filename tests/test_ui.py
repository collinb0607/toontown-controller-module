import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from ttcontroller.ui import FRIENDS_CLOSE, SPEEDCHAT, SPEEDCHAT_MENU, UIPoint, is_visible  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
# Fixtures are small crops of real captures: <label>_<W>x<H>_at_<x0>_<y0>.png
NAME = re.compile(r"(?P<label>\w+?)_(?P<w>\d+)x(?P<h>\d+)_at_(?P<x0>\d+)_(?P<y0>\d+)\.png")


def fixtures(label):
    params = []
    for path in sorted(FIXTURES.glob(f"{label}_*.png")):
        m = NAME.fullmatch(path.name)
        params.append(pytest.param(path, int(m["w"]), int(m["h"]), int(m["x0"]), int(m["y0"]), id=path.stem))
    return params


def pixel_reader(path, x0, y0):
    img = pygame.image.load(str(path))
    return lambda x, y: tuple(img.get_at((x - x0, y - y0)))[:3]


def test_speedchat_button_position_at_two_sizes():
    # Measured centers of the green button in real captures.
    assert abs(SPEEDCHAT.center.to_client(1920, 1009)[0] - 102) <= 2
    assert abs(SPEEDCHAT.center.to_client(1533, 711)[0] - 72) <= 2


def test_anchors():
    assert UIPoint("left", 0.1, 0.5).to_client(1000, 500) == (50, 250)
    assert UIPoint("center", 0.1, 0.5).to_client(1000, 500) == (550, 250)
    assert UIPoint("right", -0.1, 0.5).to_client(1000, 500) == (950, 250)


def test_tall_window_scales_by_width():
    assert UIPoint("left", 0.1, 0.05).to_client(500, 800) == (50, 25)
    assert UIPoint("left", 0.1, -0.5, "center").to_client(500, 800) == (50, 150)


DETECTORS = [(FRIENDS_CLOSE, "friends"), (SPEEDCHAT_MENU, "speedchat")]


@pytest.mark.parametrize("path,w,h,x0,y0,button", [
    (*p.values, button) for button, prefix in DETECTORS for p in fixtures(f"{prefix}_open")
])
def test_detected_when_open(path, w, h, x0, y0, button):
    assert is_visible(button, w, h, pixel_reader(path, x0, y0))


@pytest.mark.parametrize("path,w,h,x0,y0,button", [
    (*p.values, button) for button, prefix in DETECTORS for p in fixtures(f"{prefix}_closed")
])
def test_not_detected_when_closed(path, w, h, x0, y0, button):
    assert not is_visible(button, w, h, pixel_reader(path, x0, y0))


def test_every_detector_has_fixtures():
    for _, prefix in DETECTORS:
        assert fixtures(f"{prefix}_open") and fixtures(f"{prefix}_closed")
