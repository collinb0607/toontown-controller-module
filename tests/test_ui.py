import os
import re
from pathlib import Path

import pytest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from ttcontroller.ui import FRIENDS_CLOSE, UIPoint, is_visible  # noqa: E402

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


def test_anchors():
    assert UIPoint("left", 0.1, 0.5).to_client(1000, 500) == (50, 250)
    assert UIPoint("center", 0.1, 0.5).to_client(1000, 500) == (550, 250)
    assert UIPoint("right", -0.1, 0.5).to_client(1000, 500) == (950, 250)


@pytest.mark.parametrize("path,w,h,x0,y0", fixtures("friends_open"))
def test_friends_close_detected(path, w, h, x0, y0):
    assert is_visible(FRIENDS_CLOSE, w, h, pixel_reader(path, x0, y0))


@pytest.mark.parametrize("path,w,h,x0,y0", fixtures("friends_closed"))
def test_friends_close_not_detected(path, w, h, x0, y0):
    assert not is_visible(FRIENDS_CLOSE, w, h, pixel_reader(path, x0, y0))
