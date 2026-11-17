"""app.run end to end in a dry run, with the controller, the TTR window, its capture and
TTR's Local API faked: the loop reads a recorded battle on its reading thread, hands the
controller to the battle and carries out its hovers, and stops cleanly. (Nothing is sent:
a dry run only logs.)"""

import threading

import pytest

from ttcontroller import app, ttr_api, window_capture
from ttcontroller.controller import ControllerState
from ttcontroller.window import TargetChoice
from test_pipeline import fixture_frame

HWND = 4242
FRAME = fixture_frame("battle_gags_1920x1009")


class FakeReader:
    """The controller: nothing held, then the D-pad right for a moment, then nothing."""
    name, family = "Fake Pad", "xbox"

    def __init__(self, preferred=""):
        self.polls = 0
        self.press_from: int | None = None

    def poll(self):
        self.polls += 1
        held = self.press_from is not None and self.press_from <= self.polls < self.press_from + 10
        return ControllerState(buttons=frozenset({"dpad_right"}) if held else frozenset())

    def rumble(self, *_):
        return True

    def set_preferred(self, preferred):
        pass

    def close(self):
        pass


class FakeToon:
    def __init__(self, *args, **kwargs):
        self.info = ttr_api.ToonInfo()

    def start(self):
        pass

    def stop(self):
        pass

    def follow(self, pid):
        pass

    def changes(self):
        return []


class FakeKeyboard:
    working = True

    def start(self):
        pass

    def take(self):
        return False

    def stop(self):
        pass


class FakeTarget:
    background, state, active, path = True, "ok", True, None

    def __init__(self, hwnd):
        self.hwnd = hwnd

    def update(self):
        pass


class FakeView:
    reads = []

    def __init__(self, hwnd, background=False):
        self.hwnd, self.background = hwnd, background

    def snapshot(self):
        FakeView.reads.append(threading.current_thread().name)
        return FRAME

    def to_screen(self, point):
        return point.to_client(FRAME.width, FRAME.height)

    def is_visible(self, button):
        return False

    def read(self, reader):
        return reader(FRAME.width, FRAME.height, FRAME.get_pixel)

    def park_spot(self):
        return None


@pytest.fixture
def faked(tmp_path, monkeypatch):
    real_watcher = app.module_config.ConfigWatcher
    monkeypatch.setattr(app.module_config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(app.module_config, "ConfigWatcher", lambda: real_watcher(tmp_path / "config.json"))
    monkeypatch.setattr(window_capture, "supported", lambda: False)
    monkeypatch.setattr(app, "ControllerReader", FakeReader)
    monkeypatch.setattr(app, "ToonWatcher", FakeToon)
    monkeypatch.setattr(app, "KeyboardWatcher", FakeKeyboard)
    monkeypatch.setattr(app, "BoundTarget", FakeTarget)
    monkeypatch.setattr(app, "TTRView", FakeView)
    monkeypatch.setattr(app, "window_pid", lambda hwnd: 0)
    FakeView.reads = []
    lines: list[str] = []
    monkeypatch.setattr(app, "log_sinks", [lines.append])
    monkeypatch.setattr(app.sys, "stdout", None)  # quiet
    return tmp_path, lines


def test_the_loop_reads_a_battle_and_drives_it(faked):
    tmp_path, lines = faked
    stop = threading.Event()
    readers = []
    real_reader = app.ControllerReader

    def make_reader(preferred=""):
        readers.append(real_reader(preferred))
        return readers[-1]

    app.ControllerReader = make_reader
    try:
        def watch():
            for _ in range(600):
                if any("Battle screen: picker" in line for line in lines) and readers:
                    if readers[0].press_from is None:
                        readers[0].press_from = readers[0].polls + 5
                    if any(line.startswith("[") and "Hover" in line for line in lines):
                        break
                threading.Event().wait(0.01)
            stop.set()

        watcher = threading.Thread(target=watch)
        watcher.start()
        errors = []
        try:
            app.run(ttr_dir=tmp_path, dry_run=True, stop=stop, choice=TargetChoice(two_toons=True, hwnd=HWND))
        except Exception as e:  # noqa: BLE001
            errors.append(e)
        watcher.join()
    finally:
        app.ControllerReader = real_reader
    assert not errors, errors
    text = "\n".join(lines)
    assert "Battle screen: picker" in text
    assert "Hover" in text  # the D-pad moved the battle's hover (logged, not moved: a dry run)
    assert FakeView.reads and set(FakeView.reads) == {"screen-reads"}  # read off the loop's thread
    assert not any("reader failed" in line for line in lines)
