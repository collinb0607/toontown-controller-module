"""The module's own small window (ToontownControllerModule.exe): runs the module while
it's open and shows what it's doing, with a button that opens the settings window.

The module's loop runs on a thread here, and stops cleanly when the window closes (so the
cursor comes back and held keys are let go). The settings window opens as its own process,
because both read the controller through pygame. Only one copy runs at a time.

Two toons (M13) is switched on here, and here the controller's TTR window is picked, each
session (window handles change every time TTR starts). The loop reads the choice from a
shared TargetChoice.
"""

import argparse
import base64
import ctypes
import json
import subprocess
import sys
import threading
import traceback
from pathlib import Path

from .app_icon import app_pixmap, use_app_icon
from .config import CONFIG_DIR, CONFIG_FILE
from .screen import grab
from .settings_model import SettingsStore
from .settings_window import DARK, LIGHT, Art, Toggle, is_dark, label, stylesheet
from .window import TargetChoice, client_rect, ttr_windows

from PySide6.QtCore import QByteArray, QObject, QSize, Qt, QTimer, Signal  # noqa: E402
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QImage, QPixmap, QTextCursor  # noqa: E402
from PySide6.QtWidgets import (QApplication, QDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,  # noqa: E402
                               QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSizePolicy,
                               QSystemTrayIcon, QToolButton,
                               QVBoxLayout, QWidget)

TITLE = "Toontown Controller"
SETTINGS_TITLE = "Toontown Controller Settings"
LOG_FILE = CONFIG_DIR / "ttcontroller.log"  # this session's log, for bug reports
# Where the window was when it closed, and whether the log was open, so it comes back the
# same way (the user, Nov 9). Its own file: config.json is the user's settings.
PLACE_FILE = CONFIG_DIR / "window.json"
_MUTEX = "Local\\ToontownControllerModule"
_LOG_LINES = 500  # kept in the window

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_user32 = ctypes.WinDLL("user32")
_user32.FindWindowW.restype = ctypes.c_void_p
_user32.FindWindowW.argtypes = (ctypes.c_wchar_p, ctypes.c_wchar_p)
_user32.SetForegroundWindow.argtypes = (ctypes.c_void_p,)
_user32.ShowWindow.argtypes = (ctypes.c_void_p, ctypes.c_int)
SW_RESTORE = 9
# A second copy started while this one hides in the tray sets this event; the running
# copy sees it and shows its window (FindWindow can't bring back a window Qt hid).
_SHOW_EVENT = "Local\\ToontownControllerModuleShow"
_kernel32.CreateEventW.restype = ctypes.c_void_p
_kernel32.CreateEventW.argtypes = (ctypes.c_void_p, ctypes.c_bool, ctypes.c_bool, ctypes.c_wchar_p)
_kernel32.OpenEventW.restype = ctypes.c_void_p
_kernel32.OpenEventW.argtypes = (ctypes.c_uint32, ctypes.c_bool, ctypes.c_wchar_p)
_kernel32.SetEvent.argtypes = (ctypes.c_void_p,)
_kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
_kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
EVENT_MODIFY_STATE = 0x0002
WAIT_OBJECT_0 = 0
ERROR_ALREADY_EXISTS = 183
CREATE_NO_WINDOW = 0x08000000


def bring_to_front(title: str) -> bool:
    hwnd = _user32.FindWindowW(None, title)
    if not hwnd:
        return False
    _user32.ShowWindow(hwnd, SW_RESTORE)
    _user32.SetForegroundWindow(hwnd)
    return True


TARGET_STATUS = {  # two toons: the controller toon's window, when it can't be played
    "unpicked": ("Pick the controller's toon", "Press Pick… and choose the TTR window the controller plays.", "wait"),
    "gone": ("Controller toon's window closed", "Press Pick… to choose another TTR window.", "off"),
    "minimized": ("Controller toon minimized", "Restore its TTR window to keep playing.", "wait"),
    "covered": ("Controller toon covered", "Something is over its TTR window. Move the windows apart.", "wait"),
}


def status_text(controller: str | None, focused: bool, mouse_paused: bool,
                target: str | None = None) -> tuple[str, str, str]:
    """(headline, detail, tone) for the status: tone is "ok", "wait" or "off". target: the
    controller toon's window's state in two-toon mode, None in one-toon mode."""
    if not controller:
        return "No controller", "Plug one in, or press its Xbox button to wake it.", "off"
    if target in TARGET_STATUS:
        return TARGET_STATUS[target]
    if target is not None:
        return "Playing", "The controller is driving its TTR window, in front or not.", "ok"
    if not focused:
        return "Waiting for TTR", "The controller works while Toontown Rewritten is in front.", "wait"
    if mouse_paused:
        return "Paused for the mouse", "Press anything on the controller to take over again.", "wait"
    return "Playing", "The controller is driving TTR.", "ok"


THUMB_WIDTH = 240


def thumbnail(hwnd) -> QPixmap | None:
    """A small picture of a TTR window, copied from the screen (copying the window itself
    makes TTR flash)."""
    left, top, width, height = client_rect(hwnd)
    if width <= 0 or height <= 0:
        return None
    frame = grab(left, top, width, height)
    image = QImage(frame._bgra, width, height, width * 4, QImage.Format_RGB32)
    return QPixmap.fromImage(image.scaledToWidth(THUMB_WIDTH, Qt.SmoothTransformation))


class PickDialog(QDialog):
    """One tile per TTR window, with a picture and where it is; click one to choose it."""

    def __init__(self, parent=None, windows=None, thumb=thumbnail):
        super().__init__(parent)
        self.setWindowTitle("Pick the controller's toon")
        self.setModal(True)
        self.chosen: tuple[int, str] | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)
        windows = ttr_windows() if windows is None else windows
        if not windows:
            lay.addWidget(label("No TTR windows are open. Open them, log in, then press Pick… again.", wrap=True))
        else:
            lay.addWidget(label("Which TTR window does the controller play? The other one is yours, "
                                "with keyboard and mouse.", wrap=True))
            row = QHBoxLayout()
            row.setSpacing(12)
            self.tiles: list[QToolButton] = []
            for hwnd, name in windows:
                tile = QToolButton()
                tile.setText(name)
                tile.setAccessibleName(f"{name} TTR window")
                tile.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                tile.setCursor(Qt.PointingHandCursor)
                picture = thumb(hwnd)
                if picture is not None:
                    tile.setIcon(QIcon(picture))
                    tile.setIconSize(QSize(picture.width(), picture.height()))
                tile.clicked.connect(lambda _=False, h=hwnd, n=name: self._choose(h, n))
                row.addWidget(tile)
                self.tiles.append(tile)
            lay.addLayout(row)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(cancel)
        lay.addLayout(bottom)

    def _choose(self, hwnd: int, name: str) -> None:
        self.chosen = (hwnd, name)
        self.accept()


class _Bridge(QObject):
    """Carries the module thread's news to the window's thread."""
    line = Signal(str)
    status = Signal(object, bool, bool, object)
    stopped = Signal(str)  # "" when it stopped because the window asked


def help_mark(text: str) -> QLabel:
    """A small ? whose hover tooltip is `text`."""
    mark = QLabel("?")
    mark.setProperty("help", True)
    mark.setFixedSize(16, 16)
    mark.setAlignment(Qt.AlignCenter)
    mark.setToolTip(text)
    mark.setAccessibleName(text)
    return mark


class CompactSwitch:
    """One line: the name, a ? with the description, then On/Off and the toggle."""

    def __init__(self, theme, title: str, desc: str, save):
        self.toggle = Toggle(theme, title)
        self.toggle.setToolTip(desc)
        self.state = label()
        self.toggle.toggled.connect(self._toggled)
        self._save = save
        self.card = QWidget()
        row = QHBoxLayout(self.card)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.addWidget(label(title))
        row.addWidget(help_mark(desc))
        row.addStretch(1)
        row.addWidget(self.state)
        row.addSpacing(6)
        row.addWidget(self.toggle)

    def _toggled(self, on: bool) -> None:
        self.state.setText("On" if on else "Off")
        self._save(on)

    def set(self, on: bool) -> None:
        self.toggle.blockSignals(True)
        self.toggle.setChecked(on)
        self.toggle.blockSignals(False)
        self.state.setText("On" if on else "Off")
        self.toggle.update()


COMING_SOON = "Corporate Clash is coming soon."


class GameSwitch:
    """Rewritten or Corporate Clash: locked on Rewritten for now, and does nothing."""

    def __init__(self, theme):
        self.toggle = Toggle(theme, "Game: Rewritten or Corporate Clash")
        self.toggle.setEnabled(False)
        self.card = QWidget()
        self.card.setToolTip(COMING_SOON)
        row = QHBoxLayout(self.card)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        # Kept together (the user: wide gaps looked odd), the space after them.
        row.addWidget(label("Rewritten"))
        row.addSpacing(4)
        row.addWidget(self.toggle)
        row.addSpacing(4)
        clash = label("Corporate Clash")
        clash.setProperty("sub", True)
        row.addWidget(clash)
        row.addWidget(help_mark(COMING_SOON))
        row.addStretch(1)


class ModuleWindow(QMainWindow):
    def __init__(self, ttr_dir: Path | None = None, dry_run: bool = False, debug: bool = False,
                 start: bool = True, config_path: Path = CONFIG_FILE, pick_dialog=PickDialog,
                 place_path: Path = PLACE_FILE, tray: bool = True):
        super().__init__()
        self.setWindowTitle(TITLE)
        art = Art()
        self._settings: subprocess.Popen | None = None
        self._bridge = _Bridge()
        self._bridge.line.connect(self._add_line)
        self._bridge.status.connect(self._show_status)
        self._bridge.stopped.connect(self._on_stopped)
        self._stop = threading.Event()
        self._tone = "off"
        self.theme = DARK if is_dark() else LIGHT
        self.store = SettingsStore(config_path)
        self._config_mtime = self._mtime()
        self.choice = TargetChoice(two_toons=self.store.config.two_toons)
        self._picked_name = ""
        self._target_state: str | None = None
        self._pick_dialog = pick_dialog
        self._flash = None  # the Identify frame, while it shows

        root = QWidget(objectName="root")
        lay = QVBoxLayout(root)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(app_pixmap(32) or art.pixmap("A", 28))
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

        # Compact switches, each with a ? whose hover says what it does (the user, Nov 10):
        # Two toons (M13), then which game, locked to Rewritten until Corporate Clash comes.
        switches = QFrame()
        switches.setProperty("card", True)
        sl = QVBoxLayout(switches)
        sl.setContentsMargins(14, 8, 14, 8)
        sl.setSpacing(6)
        self.two = CompactSwitch(lambda: self.theme, "Two toons",
                                 "One toon on keyboard and mouse, another on the controller.", self._set_two_toons)
        self.two.set(self.choice.two_toons)
        sl.addWidget(self.two.card)
        self.game = GameSwitch(lambda: self.theme)
        sl.addWidget(self.game.card)
        lay.addWidget(switches)
        self.pick_row = QFrame()
        self.pick_row.setProperty("card", True)
        pr = QHBoxLayout(self.pick_row)
        pr.setContentsMargins(14, 8, 14, 8)
        pr.setSpacing(8)
        self.picked = QLabel("")
        self.picked.setProperty("sub", True)
        self.picked.setWordWrap(True)
        pr.addWidget(self.picked, 1)
        self.pick_button = QPushButton("Pick…")
        self.pick_button.clicked.connect(self.pick)
        pr.addWidget(self.pick_button)
        self.identify_button = QPushButton("Identify")
        self.identify_button.setToolTip("Flash a frame around the controller toon's window")
        self.identify_button.clicked.connect(self.identify)
        pr.addWidget(self.identify_button)
        lay.addWidget(self.pick_row)
        self._show_pick_row()

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
        self._place_path = place_path
        self._restore_place()

        self._log_file = None
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            self._log_file = open(LOG_FILE, "w", encoding="utf-8")
        except OSError:
            pass
        self._thread = threading.Thread(target=self._run, args=(ttr_dir, dry_run, debug), daemon=True)
        if start:
            self._thread.start()
        # Close to tray: an icon in the notification area while the window is hidden.
        self._quitting = False
        self._tray_told = False  # the "still running" notice, shown on the first close only
        self.tray = self._make_tray() if tray and QSystemTrayIcon.isSystemTrayAvailable() else None
        self._show_event = _kernel32.CreateEventW(None, False, False, _SHOW_EVENT) if tray else None
        self._show_timer = QTimer(self)
        self._show_timer.timeout.connect(self._check_show_event)
        self._show_timer.start(300)
        # The settings window can switch two toons too: follow config.json.
        self._config_timer = QTimer(self)
        self._config_timer.timeout.connect(self._check_config)
        self._config_timer.start(1000)
        if self.choice.two_toons and start:
            QTimer.singleShot(300, self.pick)  # always asked: the window changes every session

    # ---- the module ----------------------------------------------------------------------
    def _run(self, ttr_dir, dry_run, debug) -> None:
        from . import app
        app.log_sinks.append(self._sink)
        try:
            app.run(ttr_dir=ttr_dir, dry_run=dry_run, debug=debug, stop=self._stop,
                    on_status=lambda *s: self._bridge.status.emit(*s), choice=self.choice)
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

    def _show_status(self, controller, focused: bool, mouse_paused: bool, target=None) -> None:
        self._target_state = target
        self._show_pick_row()
        headline, detail, tone = status_text(controller, focused, mouse_paused, target)
        self.headline.setText(headline)
        self.detail.setText(detail)
        if self.tray is not None:
            self.tray.setToolTip(f"{TITLE}: {headline}")
        self.controller.setText(f"Controller: {controller}" if controller else "")
        self.controller.setVisible(bool(controller))
        self._tone = tone
        self._paint_dot()
        # The detail may wrap onto more or fewer lines; its new height is only known once
        # Qt has handled the text change, so fit after that.
        QTimer.singleShot(0, self._fit)

    def _on_stopped(self, error: str) -> None:
        if not error:
            return
        self.headline.setText("Stopped")
        self.detail.setText(f"Something went wrong: {error}. The log has the details; restart to try again.")
        self.controller.hide()
        self._tone = "error"
        self._paint_dot()
        self.log_button.setChecked(True)

    # ---- two toons -----------------------------------------------------------------------
    def _set_two_toons(self, on: bool, save: bool = True) -> None:
        if save and self.store.writable:
            self.store.set("two_toons", on)
            self._config_mtime = self._mtime()
        self.choice.hwnd = None
        self._picked_name = ""
        self.choice.two_toons = on
        self._show_pick_row()
        if on:
            self.pick()

    def pick(self) -> None:
        if not self.choice.two_toons:
            return
        dialog = self._pick_dialog(self)
        if dialog.exec() and dialog.chosen is not None:
            self.choice.hwnd, self._picked_name = dialog.chosen
        self._show_pick_row()

    def identify(self) -> None:
        """A gold frame around the controller toon's window for a moment."""
        if self.choice.hwnd is None:
            return
        from .overlay import Highlighter
        left, top, width, height = client_rect(self.choice.hwnd)
        if self._flash is None:
            self._flash = Highlighter()
        self._flash.show((left, top, width, height), min(width, height))
        QTimer.singleShot(1500, self._end_flash)

    def _end_flash(self) -> None:
        if self._flash is not None:
            self._flash.close()
            self._flash = None

    def _show_pick_row(self) -> None:
        on = self.choice.two_toons
        self.pick_row.setVisible(on)
        if self.choice.hwnd is None:
            text = "Controller toon: not picked yet"
        elif self._target_state == "gone":
            text = "Controller toon: its window closed"
        else:
            text = f"Controller toon: the {self._picked_name.replace(' (in front)', '').lower()} TTR window"
        self.picked.setText(text)
        self.identify_button.setEnabled(self.choice.hwnd is not None and self._target_state != "gone")
        if hasattr(self, "log_view"):
            self._fit()

    def _mtime(self) -> float | None:
        try:
            return self.store.path.stat().st_mtime
        except OSError:
            return None

    def _check_config(self) -> None:
        mtime = self._mtime()
        if mtime == self._config_mtime:
            return
        self._config_mtime = mtime
        self.store.reload()
        on = self.store.config.two_toons
        if on != self.choice.two_toons:
            self.two.set(on)
            self._set_two_toons(on, save=False)

    # ---- settings ------------------------------------------------------------------------
    def open_settings(self) -> None:
        if self._settings is not None and self._settings.poll() is None and bring_to_front(SETTINGS_TITLE):
            return
        if getattr(sys, "frozen", False):
            # The packaged ToontownController.exe opens Settings as itself (see main).
            command = [sys.executable, "--settings"]
        else:
            python = Path(sys.executable)
            windowed = python.with_name("pythonw.exe")
            exe = windowed if windowed.exists() else python
            command = [str(exe), "-m", "ttcontroller", "--settings"]
        self._settings = subprocess.Popen(command, creationflags=CREATE_NO_WINDOW)

    # ---- look ------------------------------------------------------------------------------
    def apply_theme(self) -> None:
        self.theme = DARK if is_dark() else LIGHT
        t = self.theme
        self.setStyleSheet(stylesheet(t) + f"""
            QLabel[title="true"] {{ font-size: 12pt; font-weight: 600; }}
            QLabel[headline="true"] {{ font-weight: 600; }}
            QLabel[help="true"] {{ color: {t['sub']}; border: 1px solid {t['sub']}; border-radius: 8px; font-size: 8pt; font-weight: 600; }}
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
            # Wrapped text needs its height worked out at the window's width.
            layout = self.centralWidget().layout()
            layout.invalidate()  # it keeps the last answer otherwise, from before the text changed
            height = layout.totalHeightForWidth(360) if layout.hasHeightForWidth() else self.sizeHint().height()
            self.setMinimumSize(0, 0)
            self.setFixedSize(360, max(height, self.sizeHint().height()))

    def _restore_place(self) -> None:
        """Back where it was when it last closed. Qt moves it onto a screen that's still
        there if that monitor is gone."""
        try:
            place = json.loads(self._place_path.read_text(encoding="utf-8"))
            geometry = base64.b64decode(place["geometry"])
        except (OSError, ValueError, KeyError, TypeError):
            return
        if place.get("log"):
            self.log_button.setChecked(True)
        self._tray_told = bool(place.get("tray_told"))
        self.restoreGeometry(QByteArray(geometry))

    def _save_place(self) -> None:
        place = {"geometry": base64.b64encode(bytes(self.saveGeometry())).decode("ascii"),
                 "log": self.log_button.isChecked(), "tray_told": self._tray_told}
        try:
            self._place_path.parent.mkdir(parents=True, exist_ok=True)
            self._place_path.write_text(json.dumps(place), encoding="utf-8")
        except OSError:
            pass

    # ---- the tray -------------------------------------------------------------------------
    def _make_tray(self) -> QSystemTrayIcon:
        tray = QSystemTrayIcon(QApplication.windowIcon(), self)
        tray.setToolTip(TITLE)
        menu = QMenu(self)
        for text, slot in (("Open", self.show_window), ("Settings", self.open_settings), ("Quit", self.quit)):
            action = QAction(text, menu)
            action.triggered.connect(slot)
            menu.addAction(action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_clicked)
        tray.show()
        return tray

    def _tray_clicked(self, reason) -> None:
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.show_window()

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _check_show_event(self) -> None:
        if self._show_event and _kernel32.WaitForSingleObject(self._show_event, 0) == WAIT_OBJECT_0:
            self.show_window()

    def quit(self) -> None:
        """Really stop (the tray's Quit): the controller and the window."""
        self._quitting = True
        self.close()

    def closeEvent(self, event) -> None:
        if not self._quitting and self.tray is not None and self.store.config.close_to_tray:
            # Hide, keep running (the user, Nov 10). The first time, say where it went.
            self._save_place()
            event.ignore()
            self.hide()
            if not self._tray_told:
                self._tray_told = True
                self._save_place()
                self.tray.showMessage(TITLE, "Still running in the notification area. "
                                      "Right-click its icon to quit.", QApplication.windowIcon(), 4000)
            return
        self._save_place()
        self._show_timer.stop()
        if self._show_event:
            _kernel32.CloseHandle(self._show_event)
            self._show_event = None
        self._config_timer.stop()
        self._end_flash()
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._log_file is not None:
            self._log_file.close()
        super().closeEvent(event)
        if self.tray is not None:
            self.tray.hide()
            QApplication.quit()  # nothing keeps running once the window really closes


def main() -> None:
    parser = argparse.ArgumentParser(prog="ToontownControllerModule", description="Controller support for Toontown Rewritten.")
    parser.add_argument("--ttr-dir", type=Path, help="TTR install folder (default: detected from the running game)")
    parser.add_argument("--dry-run", action="store_true", help="print keys instead of sending them")
    parser.add_argument("--debug", action="store_true", help="log button presses and every key sent")
    parser.add_argument("--settings", action="store_true", help="open the settings window instead")
    args = parser.parse_args()
    if args.settings:
        # The packaged exe's Settings button runs it again with this (one exe, two windows).
        from .settings_window import main as settings
        settings()
        return

    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName(TITLE)
    use_app_icon(app)
    # One copy at a time: a second one would fight the first over the keys and cursor.
    mutex = _kernel32.CreateMutexW(None, False, _MUTEX)
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        # The running copy may be hidden in the tray: ask it to show its window.
        show = _kernel32.OpenEventW(EVENT_MODIFY_STATE, False, _SHOW_EVENT)
        if show:
            _kernel32.SetEvent(show)
            _kernel32.CloseHandle(show)
        elif not bring_to_front(TITLE):
            QMessageBox.information(None, TITLE, "Toontown Controller is already running.")
        return
    # Hidden in the tray isn't closed: only the window's real close (or Quit) ends it.
    app.setQuitOnLastWindowClosed(False)
    window = ModuleWindow(ttr_dir=args.ttr_dir, dry_run=args.dry_run, debug=args.debug)
    window.show()
    code = app.exec()
    _kernel32.CloseHandle(mutex)
    sys.exit(code)


if __name__ == "__main__":
    main()
