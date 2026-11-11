import os
import threading
import time

import pytest

from ttcontroller import launcher


def test_status_text():
    assert launcher.status_text(None, True, False)[2] == "off"
    assert launcher.status_text("Pad", False, False)[0] == "Waiting for TTR"
    assert launcher.status_text("Pad", True, True)[0] == "Paused for the mouse"
    assert launcher.status_text("Pad", True, False) == ("Playing", "The controller is driving TTR.", "ok")


def test_status_text_for_two_toons():
    assert launcher.status_text("Pad", True, False, "ok")[0] == "Playing"
    assert launcher.status_text("Pad", False, False, "covered")[0] == "Controller toon covered"
    assert launcher.status_text("Pad", False, False, "minimized")[0] == "Controller toon minimized"
    assert launcher.status_text("Pad", False, False, "gone")[2] == "off"
    assert launcher.status_text("Pad", False, False, "unpicked")[0] == "Pick the controller's toon"
    assert launcher.status_text(None, False, False, "covered")[0] == "No controller"


def test_window_runs_the_module_and_stops_it_on_close(tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PySide6.QtWidgets")
    from ttcontroller import app as module_app

    stopped = threading.Event()

    def fake_run(ttr_dir=None, dry_run=False, debug=False, stop=None, on_status=None, choice=None):
        module_app.log("Running.")
        on_status("Xbox One Controller", True, False, None)
        while not stop.is_set():
            time.sleep(0.01)
        stopped.set()

    monkeypatch.setattr(module_app, "run", fake_run)
    monkeypatch.setattr(module_app, "log_sinks", [])
    monkeypatch.setattr(launcher, "LOG_FILE", tmp_path / "ttcontroller.log")
    qt = widgets.QApplication.instance() or widgets.QApplication([])
    window = launcher.ModuleWindow(config_path=tmp_path / "config.json", place_path=tmp_path / "window.json")
    deadline = time.monotonic() + 2
    while window.headline.text() != "Playing" and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(0.01)
    assert window.headline.text() == "Playing"
    assert "Running." in window.log_view.toPlainText()
    window.close()
    assert stopped.is_set() and not window._thread.is_alive()
    assert "Running." in (tmp_path / "ttcontroller.log").read_text(encoding="utf-8")


def test_the_window_comes_back_where_it_was(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PySide6.QtWidgets")
    qt = widgets.QApplication.instance() or widgets.QApplication([])
    place = tmp_path / "window.json"
    first = launcher.ModuleWindow(start=False, config_path=tmp_path / "config.json", place_path=place)
    first.show()
    first.move(123, 234)
    first.log_button.setChecked(True)
    qt.processEvents()
    spot = first.pos()
    first.close()
    again = launcher.ModuleWindow(start=False, config_path=tmp_path / "config.json", place_path=place)
    try:
        again.show()  # the frame is only placed once shown
        qt.processEvents()
        assert again.pos() == spot and again.log_button.isChecked()
    finally:
        again.close()
    # A broken file is ignored.
    place.write_text("not json", encoding="utf-8")
    fresh = launcher.ModuleWindow(start=False, config_path=tmp_path / "config.json", place_path=place)
    fresh.close()


def test_the_app_icon_is_the_users_art():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PySide6.QtWidgets")
    qt = widgets.QApplication.instance() or widgets.QApplication([])
    from ttcontroller.app_icon import find_icon, use_app_icon

    path = find_icon()
    assert path is not None and path.name == "icon.png"
    use_app_icon(qt)
    icon = qt.windowIcon()
    assert not icon.isNull() and 16 in [s.width() for s in icon.availableSizes()]


class FakeTray:
    def __init__(self):
        self.messages, self.hidden = [], False

    def showMessage(self, *args):
        self.messages.append(args[1])

    def setToolTip(self, text):
        self.tip = text

    def hide(self):
        self.hidden = True


def _tray_window(tmp_path, monkeypatch, close_to_tray=True):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    widgets = pytest.importorskip("PySide6.QtWidgets")
    widgets.QApplication.instance() or widgets.QApplication([])
    monkeypatch.setattr(widgets.QApplication, "quit", staticmethod(lambda: None))
    path = tmp_path / "config.json"
    if not close_to_tray:
        path.write_text('{"close_to_tray": false}', encoding="utf-8")
    window = launcher.ModuleWindow(start=False, config_path=path, place_path=tmp_path / "window.json", tray=False)
    window.tray = FakeTray()
    return window


def test_closing_hides_to_the_tray_and_says_so_once(tmp_path, monkeypatch):
    window = _tray_window(tmp_path, monkeypatch)
    window.show()
    window.close()
    assert window.isHidden() and not window._stop.is_set()  # still running
    assert len(window.tray.messages) == 1
    window.show_window()
    window.close()
    assert len(window.tray.messages) == 1  # only the first time
    window.quit()
    assert window._stop.is_set() and window.tray.hidden


def test_close_to_tray_off_quits(tmp_path, monkeypatch):
    window = _tray_window(tmp_path, monkeypatch, close_to_tray=False)
    window.show()
    window.close()
    assert window._stop.is_set() and window.tray.messages == []
