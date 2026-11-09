"""The module's own small window (ToontownControllerModule.exe): runs the module while
it's open and shows what it's doing, with a button that opens the settings window.

The module's loop runs on a thread here, and stops cleanly when the window closes (so the
cursor comes back and held keys are let go). The settings window opens as its own process,
because both read the controller through pygame. Only one copy runs at a time.
"""

import argparse
import ctypes
import subprocess
import sys
import threading
import traceback
from pathlib import Path

from .config import CONFIG_DIR
from .settings_window import DARK, LIGHT, Art, is_dark, stylesheet

from PySide6.QtCore import QObject, Qt, Signal  # noqa: E402
from PySide6.QtGui import QGuiApplication, QIcon, QTextCursor  # noqa: E402
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,  # noqa: E402
                               QPlainTextEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget)

TITLE = "Toontown Controller"
SETTINGS_TITLE = "Toontown Controller Settings"
LOG_FILE = CONFIG_DIR / "ttcontroller.log"  # this session's log, for bug reports
_MUTEX = "Local\\ToontownControllerModule"
_LOG_LINES = 500  # kept in the window

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32 = ctypes.WinDLL("user32")
_user32.FindWindowW.restype = ctypes.c_void_p
_user32.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
_user32.SetForegroundWindow.argtypes = (ctypes.c_void_p,)
_user32.ShowWindow.argtypes = (ctypes.c_void_p, ctypes.c_int)
SW_RESTORE = 9
ERROR_ALREADY_EXISTS = 183
CREATE_NO_WINDOW = 0x08000000


def bring_to_front(title: str) -> bool:
    hwnd = _user32.FindWindowW(None, title)
    if not hwnd:
        return False
    _user32.ShowWindow(hwnd, SW_RESTORE)
    _user32.SetForegroundWindow(hwnd)
    return True


def status_text(controller: str | None, focused: bool, mouse_paused: bool) -> tuple[str, str, str]:
    """(headline, detail, tone) for the status: tone is "ok", "wait" or "off"."""
    if not controller:
        return "No controller", "Plug one in, or press its Xbox button to wake it.", "off"
    if not focused:
        return "Waiting for TTR", "The controller works while Toontown Rewritten is in front.", "wait"
    if mouse_paused:
        return "Paused for the mouse", "Press anything on the controller to take over again.", "wait"
    return "Playing", "The controller is driving TTR.", "ok"


class _Bridge(QObject):
    """Carries the module thread's news to the window's thread."""
    line = Signal(str)
    status = Signal(object, bool, bool)
    stopped = Signal(str)  # "" when it stopped because the window asked


class ModuleWindow(QMainWindow):
    def __init__(self, ttr_dir: Path | None = None, dry_run: bool = False, debug: bool = False,
                 start: bool = True):
        super().__init__()
        self.setWindowTitle(TITLE)
        art = Art()
        self.setWindowIcon(QIcon(art.pixmap("A", 64)))
        self._settings: subprocess.Popen | None = None
        self._bridge = _Bridge()
        self._bridge.line.connect(self._add_line)
        self._bridge.status.connect(self._show_status)
        self._bridge.stopped.connect(self._on_stopped)
        self._stop = threading.Event()
        self._tone = "off"

        root = QWidget(objectName="root")
        lay = QVBoxLayout(root)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(art.pixmap("A", 28))
        head.addWidget(logo)
        name = QLabel(TITLE)
        name.setProperty("title", True)
        head.addWidget(name)
        head.addStretch(1)
        lay.addLayout(head)

        card = QFrame()
        card.setProperty("card", True)
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 10)
        cl.setSpacing(2)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.dot = QLabel()
        self.dot.setFixedSize(10, 10)
        top.addWidget(self.dot)
        self.headline = QLabel("Starting…")
        self.headline.setProperty("headline", True)
        top.addWidget(self.headline)
        top.addStretch(1)
        cl.addLayout(top)
        self.detail = QLabel("")
        self.detail.setProperty("sub", True)
        self.detail.setWordWrap(True)
        cl.addWidget(self.detail)
        self.controller = QLabel("")
        self.controller.setProperty("sub", True)
        cl.addWidget(self.controller)
        lay.addWidget(card)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.settings_button = QPushButton("Settings")
        self.settings_button.setProperty("accent", True)
        self.settings_button.clicked.connect(self.open_settings)
        buttons.addWidget(self.settings_button)
        self.log_button = QPushButton("Show log")
        self.log_button.setCheckable(True)
        self.log_button.toggled.connect(self._toggle_log)
        buttons.addWidget(self.log_button)
        buttons.addStretch(1)
        lay.addLayout(buttons)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(_LOG_LINES)
        self.log_view.setMinimumHeight(200)
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.log_view.hide()
        lay.addWidget(self.log_view, 1)

        self.setCentralWidget(root)
        self.apply_theme()
        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self.apply_theme())
        except AttributeError:
            pass
        self._fit()

        self._log_file = None
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(LOG_FILE, "w", encoding="utf-8")
        except OSError:
            pass
        self._thread = threading.Thread(target=self._run, args=(ttr_dir, dry_run, debug), daemon=True)
        if start:
            self._thread.start()

    # ---- the module ----------------------------------------------------------------------
    def _run(self, ttr_dir, dry_run, debug) -> None:
        from . import app
        app.log_sinks.append(self._sink)
        try:
            app.run(ttr_dir=ttr_dir, dry_run=dry_run, debug=debug, stop=self._stop,
                    on_status=lambda *s: self._bridge.status.emit(*s))
            self._bridge.stopped.emit("")
        except Exception:
            text = traceback.format_exc()
            self._sink(text.rstrip())
            self._bridge.stopped.emit(text.strip().splitlines()[-1])

    def _sink(self, line: str) -> None:
        if self._log_file is not None:
            try:
                self._log_file.write(line + "\n")
                self._log_file.flush()
            except (OSError, ValueError):
                pass
        self._bridge.line.emit(line)

    def _add_line(self, line: str) -> None:
        self.log_view.appendPlainText(line)
        self.log_view.moveCursor(QTextCursor.End)

    def _show_status(self, controller, focused: bool, mouse_paused: bool) -> None:
        headline, detail, tone = status_text(controller, focused, mouse_paused)
        self.headline.setText(headline)
        self.detail.setText(detail)
        self.controller.setText(f"Controller: {controller}" if controller else "")
        self.controller.setVisible(bool(controller))
        self._tone = tone
        self._paint_dot()

    def _on_stopped(self, error: str) -> None:
        if not error:
            return
        self.headline.setText("Stopped")
        self.detail.setText(f"Something went wrong: {error}. The log has the details; restart to try again.")
        self.controller.hide()
        self._tone = "error"
        self._paint_dot()
        self.log_button.setChecked(True)

    # ---- settings ------------------------------------------------------------------------
    def open_settings(self) -> None:
        if self._settings is not None and self._settings.poll() is None and bring_to_front(SETTINGS_TITLE):
            return
        python = Path(sys.executable)
        windowed = python.with_name("pythonw.exe")
        exe = windowed if windowed.exists() else python
        self._settings = subprocess.Popen([str(exe), "-m", "ttcontroller", "--settings"],
                                          creationflags=CREATE_NO_WINDOW)

    # ---- look ------------------------------------------------------------------------------
    def apply_theme(self) -> None:
        self.theme = DARK if is_dark() else LIGHT
        t = self.theme
        self.setStyleSheet(stylesheet(t) + f"""
            QLabel[title="true"] {{ font-size: 12pt; font-weight: 600; }}
            QLabel[headline="true"] {{ font-weight: 600; }}
            QPushButton:checked {{ background: {t['nav']}; }}
            QPlainTextEdit {{ background: {t['well']}; border: 1px solid {t['border']}; border-radius: 6px; padding: 4px; font-family: Consolas, monospace; font-size: 9pt; }}
        """)
        self._paint_dot()

    def _paint_dot(self) -> None:
        t = self.theme
        color = {"ok": t["ok"], "wait": "#e8b23a", "off": t["muted"], "error": t["danger"]}[self._tone]
        self.dot.setStyleSheet(f"background: {color}; border-radius: 5px;")

    def _toggle_log(self, shown: bool) -> None:
        self.log_button.setText("Hide log" if shown else "Show log")
        self.log_view.setVisible(shown)
        self._fit()

    def _fit(self) -> None:
        if self.log_view.isVisible():
            self.setMinimumSize(360, 0)
            self.setMaximumSize(16777215, 16777215)
            self.resize(max(self.width(), 560), 420)
        else:
            self.setMinimumSize(0, 0)
            self.adjustSize()
            self.setFixedSize(360, self.sizeHint().height())

    def closeEvent(self, event) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._log_file is not None:
            self._log_file.close()
        super().closeEvent(event)


def main() -> None:
    parser = argparse.ArgumentParser(prog="ToontownControllerModule", description="Controller support for Toontown Rewritten.")
    parser.add_argument("--ttr-dir", type=Path, help="TTR install folder (default: detected from the running game)")
    parser.add_argument("--dry-run", action="store_true", help="print keys instead of sending them")
    parser.add_argument("--debug", action="store_true", help="log button presses and every key sent")
    args = parser.parse_args()

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(TITLE)
    # One copy at a time: a second one would fight the first over the keys and cursor.
    mutex = _kernel32.CreateMutexW(None, False, _MUTEX)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        if not bring_to_front(TITLE):
            QMessageBox.information(None, TITLE, "Toontown Controller is already running.")
        return
    window = ModuleWindow(ttr_dir=args.ttr_dir, dry_run=args.dry_run, debug=args.debug)
    window.show()
    code = app.exec()
    _kernel32.CloseHandle(mutex)
    sys.exit(code)


if __name__ == "__main__":
    main()
