"""Reading TTR's own window picture (window_capture), so the overlay can show in recordings."""

import numpy as np
import pytest

from ttcontroller import overlay, window_capture
from ttcontroller.window_capture import WindowCapture, crop_client


def picture(width, height):
    """A BGRA picture whose pixel (x, y) is (x % 256, y % 256, 7, 255)."""
    image = np.zeros((height, width, 4), dtype=np.uint8)
    image[..., 0] = (np.arange(width) % 256)[None, :]
    image[..., 1] = (np.arange(height) % 256)[:, None]
    image[..., 2] = 7
    image[..., 3] = 255
    return image


def test_crop_client_cuts_the_game_area_below_the_title_bar():
    # The window's visible bounds start at 100,50; the game area is 23 px down (the title bar).
    frame = crop_client(picture(200, 150), (100, 50, 300, 200), (100, 73, 200, 127))
    assert (frame.width, frame.height) == (200, 127)
    assert frame.get_pixel(0, 0) == (7, 23, 0)  # get_pixel is RGB: picture's (0, 23)
    assert frame.get_pixel(199, 126) == (7, 149, 199)


def test_crop_client_refuses_a_picture_that_doesnt_match_the_window():
    image = picture(200, 150)
    assert crop_client(image, (100, 50, 320, 200), (100, 73, 200, 127)) is None  # resizing
    assert crop_client(image, (100, 50, 300, 200), (100, 73, 201, 127)) is None  # too wide
    assert crop_client(image, (100, 50, 300, 200), (90, 73, 200, 127)) is None  # off the left


class FakeSession:
    def __init__(self):
        self.on_frame = self.on_closed = None
        self.stopped = False

    def start(self, hwnd, on_frame, on_closed):
        self.on_frame, self.on_closed = on_frame, on_closed
        return self

    def stop(self):
        self.stopped = True


def test_only_frames_asked_for_are_copied():
    fake = FakeSession()
    capture = WindowCapture(1, start=fake.start)
    first = picture(4, 4)
    fake.on_frame(first)  # the first frame is always kept
    assert capture.image(wait=0) is not None and capture.image(wait=0)[0, 1, 0] == 1
    newer = picture(4, 4)
    newer[0, 0, 0] = 99
    fake.on_frame(newer)  # nobody is waiting: not copied, just noted
    assert capture.image(wait=0)[0, 0, 0] == 0  # no newer frame came in time: the last copy
    fake.on_frame(newer)  # a read is now waiting (the one above left _want set): copied
    assert capture.image(wait=0)[0, 0, 0] == 99
    newer[0, 0, 0] = 5  # the copy is the module's own, not the capture's buffer
    assert capture.image(wait=0)[0, 0, 0] == 99


def test_a_closed_window_stops_waiting():
    fake = FakeSession()
    capture = WindowCapture(1, start=fake.start)
    fake.on_closed()
    assert capture.closed and capture.image(wait=5) is None  # returns at once


@pytest.fixture
def fresh(monkeypatch):
    monkeypatch.setattr(window_capture, "_supported", True)
    monkeypatch.setattr(window_capture, "_failed", False)
    monkeypatch.setattr(window_capture, "_sessions", {})
    monkeypatch.setattr(window_capture, "_failure_handlers", [])
    yield


def test_a_session_that_cant_start_goes_back_to_the_screen(fresh, monkeypatch):
    def broken(hwnd, on_frame, on_closed):
        raise OSError("no capture here")
    monkeypatch.setattr(window_capture, "_start_session", broken)
    monkeypatch.setattr(WindowCapture.__init__, "__defaults__", (broken,))
    reasons = []
    window_capture.on_failure(reasons.append)
    assert window_capture.frame(1, (0, 0, 10, 10)) is None  # read the screen instead
    assert not window_capture.enabled() and reasons == ["OSError: no capture here"]
    assert window_capture.frame(1, (0, 0, 10, 10)) is None and len(reasons) == 1  # told once


def test_no_picture_yet_reads_black_not_the_screen(fresh, monkeypatch):
    fake = FakeSession()
    monkeypatch.setattr(WindowCapture.__init__, "__defaults__", (fake.start,))
    monkeypatch.setattr(window_capture, "FIRST_FRAME_WAIT", 0.0)
    monkeypatch.setattr(window_capture, "window_bounds", lambda hwnd: (0, 0, 10, 10))
    frame = window_capture.frame(1, (0, 0, 10, 10))
    assert frame is not None and (frame.width, frame.height) == (10, 10) and frame.get_pixel(5, 5) == (0, 0, 0)
    fake.on_frame(picture(10, 10))
    assert window_capture.frame(1, (0, 0, 10, 10)).get_pixel(3, 2) == (7, 2, 3)


def test_unused_sessions_are_stopped(fresh, monkeypatch):
    fakes = {}

    def start(hwnd, on_frame, on_closed):
        fakes[hwnd] = FakeSession()
        return fakes[hwnd]
    monkeypatch.setattr(WindowCapture.__init__, "__defaults__", (start,))
    monkeypatch.setattr(window_capture, "FIRST_FRAME_WAIT", 0.0)
    monkeypatch.setattr(window_capture, "FRAME_WAIT", 0.0)
    monkeypatch.setattr(window_capture, "window_bounds", lambda hwnd: None)
    window_capture.frame(1, (0, 0, 4, 4))
    window_capture._sessions[1].last_used -= window_capture.IDLE_STOP + 1
    window_capture.frame(2, (0, 0, 4, 4))
    assert fakes[1].stopped and set(window_capture._sessions) == {2}


def test_overlay_windows_follow_the_capture_exclusion(monkeypatch):
    monkeypatch.setattr(overlay, "_exclude", True)
    window = overlay.Highlighter()
    try:
        assert window.excluded  # hidden from capture while the module copies the screen
        overlay.set_capture_exclusion(False)
        assert not window.excluded
        later = overlay.Highlighter()
        assert not later.excluded  # new windows follow too
        later.close()
        overlay.set_capture_exclusion(True)
        assert window.excluded
    finally:
        window.close()
        overlay.set_capture_exclusion(True)
