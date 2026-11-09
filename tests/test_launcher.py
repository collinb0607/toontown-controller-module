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
    window = launcher.ModuleWindow(config_path=tmp_path / "config.json")
    deadline = time.monotonic() + 2
    while window.headline.text() != "Playing" and time.monotonic() < deadline:
        qt.processEvents()
        time.sleep(0.01)
    assert window.headline.text() == "Playing"
    assert "Running." in window.log_view.toPlainText()
    window.close()
    assert stopped.is_set() and not window._thread.is_alive()
    assert "Running." in (tmp_path / "ttcontroller.log").read_text(encoding="utf-8")
