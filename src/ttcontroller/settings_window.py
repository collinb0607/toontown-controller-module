"""The settings window (M12): a Windows-style settings app over config.json.

Pages: General (controller, hints, movement, hold time), Controls (remapping each of the
seven tables, press and hold), Hints (with a preview drawn by the real hint drawer),
Game options (with an Advanced section) and About. It follows Windows' dark or light
theme. Every change is saved at once (settings_model.SettingsStore); the running
module reloads config.json by itself, so nothing needs restarting.

It reads the controller too (the Test row, and listening for a button to move a binding
to). The module pauses while TTR isn't in front, so presses here never reach the game.
"""

import os
import sys
from importlib.metadata import PackageNotFoundError, version

import numpy as np

from .config import CONFIG_DIR, CONFIG_FILE, Config
from .controller import ControllerReader, connected_names
from .hint_draw import RING_STEPS, Drawer, find_sheet
from .hints import BADGE, COVER, Badge, Bar
from .mapper import controller_buttons
from .settings_model import (ACTION_HELP, BUTTON_LABELS, BUTTON_SPRITES, TABLES, SettingsStore, Table,
                             action_choices, action_label, bindings_of, clear, move, with_action)
from .ui import UIPoint

from PySide6.QtCore import QObject, QRectF, Qt, QTimer, QUrl, Signal  # noqa: E402
from PySide6.QtGui import (QColor, QDesktopServices, QFont, QGuiApplication, QIcon, QImage, QPainter,  # noqa: E402
                           QPen, QPixmap)
from PySide6.QtWidgets import (QAbstractButton, QApplication, QComboBox, QDialog, QFrame, QGridLayout,  # noqa: E402
                               QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton,
                               QScrollArea, QSizePolicy, QSlider, QStackedWidget, QTabBar, QToolButton,
                               QVBoxLayout, QWidget)

REPO = "https://github.com/collinb0607/toontown-controller-module"

DARK = {"bg": "#202020", "card": "#2b2b2b", "border": "#2b2b2b", "text": "#f3f3f3", "sub": "#c5c5c5",
        "accent": "#60cdff", "accent_text": "#000000", "input": "#373737", "input_border": "#4a4a4a",
        "nav": "#2d2d2d", "hover": "#323232", "sep": "#3a3a3a", "danger": "#ff99a4", "ok": "#6ccb5f",
        "muted": "#9a9a9a", "well": "#1c1c1c"}
LIGHT = {"bg": "#f3f3f3", "card": "#fbfbfb", "border": "#e5e5e5", "text": "#1b1b1b", "sub": "#5f5f5f",
         "accent": "#005fb8", "accent_text": "#ffffff", "input": "#ffffff", "input_border": "#d1d1d1",
         "nav": "#e9e9e9", "hover": "#f0f0f0", "sep": "#e5e5e5", "danger": "#c42b1c", "ok": "#0f7b0f",
         "muted": "#8a8a8a", "well": "#e9e9e9"}


def is_dark() -> bool:
    try:
        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except AttributeError:
        return True


def stylesheet(t: dict) -> str:
    return f"""
    QWidget {{ color: {t['text']}; font-family: 'Segoe UI Variable Text', 'Segoe UI'; font-size: 10pt; }}
    QMainWindow, QWidget#root, QWidget#page, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {t['bg']}; }}
    QScrollArea {{ border: none; }}
    QFrame[card="true"] {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 8px; }}
    QFrame[card="true"] QLabel {{ background: transparent; }}
    QLabel[sub="true"] {{ color: {t['sub']}; font-size: 9pt; }}
    QLabel[h1="true"] {{ font-size: 20pt; font-weight: 600; }}
    QLabel[h2="true"] {{ font-weight: 600; color: {t['sub']}; padding-top: 10px; }}
    QLabel[muted="true"] {{ color: {t['muted']}; }}
    QLabel[banner="true"] {{ background: {t['danger']}; color: #000; border-radius: 6px; padding: 8px 12px; }}
    QListWidget#nav {{ background: {t['bg']}; border: none; outline: none; }}
    QListWidget#nav::item {{ padding: 8px 12px; border-radius: 5px; margin: 1px 0; }}
    QListWidget#nav::item:hover {{ background: {t['hover']}; }}
    QListWidget#nav::item:selected {{ background: {t['nav']}; color: {t['text']}; border-left: 3px solid {t['accent']}; }}
    QComboBox {{ background: {t['input']}; border: 1px solid {t['input_border']}; border-radius: 5px; padding: 5px 10px; min-height: 20px; }}
    QComboBox QAbstractItemView {{ background: {t['input']}; border: 1px solid {t['input_border']}; selection-background-color: {t['nav']}; selection-color: {t['text']}; }}
    QComboBox[unset="true"] {{ color: {t['muted']}; }}
    QPushButton {{ background: {t['input']}; border: 1px solid {t['input_border']}; border-radius: 5px; padding: 6px 16px; }}
    QPushButton:hover {{ background: {t['hover']}; }}
    QPushButton[accent="true"] {{ background: {t['accent']}; color: {t['accent_text']}; border-color: {t['accent']}; font-weight: 600; }}
    QPushButton[danger="true"] {{ color: {t['danger']}; }}
    QPushButton[link="true"], QToolButton[link="true"] {{ background: transparent; border: none; color: {t['accent']}; padding: 4px 6px; }}
    QPushButton[link="true"]:hover {{ text-decoration: underline; }}
    QPushButton#expander {{ background: transparent; border: none; border-radius: 8px; padding: 0; }}
    QPushButton#expander:hover {{ background: {t['hover']}; }}
    QPushButton#expander QLabel {{ background: transparent; }}
    QSlider::groove:horizontal {{ height: 4px; background: {t['input_border']}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {t['accent']}; border: 4px solid {t['input']}; width: 12px; height: 12px; margin: -8px 0; border-radius: 10px; }}
    QTabBar::tab {{ background: transparent; border: none; border-bottom: 3px solid transparent; padding: 7px 14px; color: {t['sub']}; }}
    QTabBar::tab:selected {{ color: {t['text']}; font-weight: 600; border-bottom: 3px solid {t['accent']}; }}
    QTabBar::tab:hover {{ color: {t['text']}; }}
    QDialog {{ background: {t['card']}; }}
    QFrame[footer="true"] {{ background: {t['bg']}; border: none; }}
    QFrame[sep="true"] {{ background: {t['sep']}; max-height: 1px; min-height: 1px; border: none; }}
    """


def _version() -> str:
    try:
        return version("toontown-controller-module")
    except PackageNotFoundError:
        return "dev"


# ---- art --------------------------------------------------------------------------------
class Art:
    """Button sprites from the Xbox sheet as QPixmaps, and hint pieces from the real drawer."""

    def __init__(self):
        import pygame
        pygame.init()
        sheet = find_sheet(CONFIG_DIR)
        self.drawer = Drawer(sheet) if sheet else None
        self._cache: dict = {}

    def pixmap(self, sprite: str, height: float, dim: bool = False) -> QPixmap:
        ratio = QGuiApplication.primaryScreen().devicePixelRatio() if QGuiApplication.primaryScreen() else 1.0
        key = (sprite, round(height), dim, ratio)
        found = self._cache.get(key)
        if found is not None:
            return found
        if self.drawer is None:
            pm = QPixmap(1, 1)
            pm.fill(Qt.transparent)
        else:
            import pygame
            surf = self.drawer.sprites.get(sprite, height * ratio)
            data = pygame.image.tobytes(surf, "RGBA")
            img = QImage(data, surf.get_width(), surf.get_height(), QImage.Format_RGBA8888).copy()
            if dim:
                faded = QImage(img.size(), QImage.Format_ARGB32_Premultiplied)
                faded.fill(Qt.transparent)
                p = QPainter(faded)
                p.setOpacity(0.35)
                p.drawImage(0, 0, img)
                p.end()
                img = faded
            pm = QPixmap.fromImage(img)
            pm.setDevicePixelRatio(ratio)
        self._cache[key] = pm
        return pm

    def piece(self, hint, scale: float, ring: int = 0) -> QImage | None:
        """A hint drawn as the overlay draws it in a 1920x1009 window, as a QImage."""
        if self.drawer is None:
            return None
        drawn = self.drawer._draw_one(hint, 1920, 1009, scale, 0, ring)
        if drawn is None:
            return None
        bgra = np.ascontiguousarray(drawn[0])
        h, w = bgra.shape[:2]
        return QImage(bgra.data, w, h, w * 4, QImage.Format_ARGB32_Premultiplied).copy()


# ---- the controller -----------------------------------------------------------------------
class Pad(QObject):
    """Polls the controller: `buttons` (held, as the module names them) and `name`."""
    buttons_changed = Signal(frozenset)
    name_changed = Signal(str)

    def __init__(self, preferred: str, threshold: float):
        super().__init__()
        self.reader = ControllerReader(preferred)
        self.threshold = threshold
        self.buttons: frozenset[str] = frozenset()
        self.name = ""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def _tick(self) -> None:
        state = self.reader.poll()
        name = self.reader.name or ""
        if name != self.name:
            self.name = name
            self.name_changed.emit(name)
        buttons = controller_buttons(state, self.threshold) if state is not None else frozenset()
        if buttons != self.buttons:
            self.buttons = buttons
            self.buttons_changed.emit(buttons)

    def close(self) -> None:
        self._timer.stop()
        self.reader.close()


# ---- small widgets ----------------------------------------------------------------------------
class Toggle(QAbstractButton):
    def __init__(self, theme, name: str):
        super().__init__()
        self._theme = theme
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(40, 20)
        self.setAccessibleName(name)

    def paintEvent(self, event) -> None:
        t = self._theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        if on:
            p.setPen(QColor(t["accent"]))
            p.setBrush(QColor(t["accent"]))
        else:
            p.setPen(QPen(QColor(t["sub"]), 1))
            p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, 39, 19), 9.5, 9.5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t["accent_text"] if on else t["sub"]))
        p.drawEllipse(QRectF(23 if on else 5, 4, 12, 12))


class Spinner(QWidget):
    def __init__(self, theme):
        super().__init__()
        self._theme = theme
        self._angle = 0
        self.setFixedSize(56, 56)
        timer = QTimer(self)
        timer.timeout.connect(self._step)
        timer.start(16)

    def _step(self) -> None:
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, event) -> None:
        t = self._theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(4, 4, 48, 48)
        p.setPen(QPen(QColor(t["sep"]), 4))
        p.drawEllipse(r)
        pen = QPen(QColor(t["accent"]), 4)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(r, -self._angle * 16, 90 * 16)


class StickDot(QWidget):
    """A stick's circle with its deadzone in the middle."""

    def __init__(self, theme):
        super().__init__()
        self._theme = theme
        self.deadzone = 0.25
        self.setFixedSize(52, 52)

    def paintEvent(self, event) -> None:
        t = self._theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(t["input_border"]), 2))
        p.drawEllipse(QRectF(2, 2, 48, 48))
        accent = QColor(t["accent"])
        fill = QColor(accent)
        fill.setAlpha(70)
        p.setPen(QPen(accent, 1))
        p.setBrush(fill)
        r = 23 * self.deadzone
        p.drawEllipse(QRectF(26 - r, 26 - r, 2 * r, 2 * r))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t["text"]))
        p.drawEllipse(QRectF(32, 15, 8, 8))


def label(text: str = "", **props) -> QLabel:
    w = QLabel(text)
    w.setWordWrap(props.pop("wrap", False))
    for k, v in props.items():
        w.setProperty(k, v)
    return w


def card(title: str, desc: str = "", *controls: QWidget, buddy: QWidget | None = None) -> QFrame:
    frame = QFrame()
    frame.setProperty("card", True)
    row = QHBoxLayout(frame)
    row.setContentsMargins(18, 12, 18, 12)
    row.setSpacing(16)
    text = QVBoxLayout()
    text.setSpacing(2)
    t = label(title)
    t.setStyleSheet("font-weight: 500;")
    if buddy is not None:
        t.setBuddy(buddy)
    text.addWidget(t)
    if desc:
        d = label(desc, sub=True, wrap=True)
        text.addWidget(d)
        frame.desc = d
    row.addLayout(text, 1)
    for c in controls:
        row.addWidget(c, 0, Qt.AlignVCenter)
    return frame


def page(title: str) -> tuple[QScrollArea, QVBoxLayout]:
    inner = QWidget()
    inner.setObjectName("page")
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(20, 22, 36, 28)
    lay.setSpacing(6)
    lay.addWidget(label(title, h1=True))
    lay.addSpacing(8)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setWidget(inner)
    return scroll, lay


class Slider:
    """A slider row: integer steps mapped to a value, saved shortly after it settles."""

    def __init__(self, title: str, desc: str, lo: float, hi: float, step: float, fmt, save, extra=None):
        self.lo, self.step, self.fmt, self._save = lo, step, fmt, save
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, round((hi - lo) / step))
        self.slider.setFixedWidth(200)
        self.slider.setAccessibleName(title)
        self.value_label = label()
        self.value_label.setFixedWidth(52)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(lambda: self._save(self.value))
        self.slider.valueChanged.connect(self._moved)
        self.changed = None  # called with the value as it moves (previews)
        controls = ([extra] if extra is not None else []) + [self.slider, self.value_label]
        self.card = card(title, desc, *controls, buddy=self.slider)

    @property
    def value(self) -> float:
        return round(self.lo + self.slider.value() * self.step, 4)

    def set(self, value: float) -> None:
        self.slider.blockSignals(True)
        self.slider.setValue(round((value - self.lo) / self.step))
        self.slider.blockSignals(False)
        self.value_label.setText(self.fmt(self.value))
        if self.changed:
            self.changed(self.value)

    def _moved(self) -> None:
        self.value_label.setText(self.fmt(self.value))
        if self.changed:
            self.changed(self.value)
        self._timer.start()


class Switch:
    """A toggle row with its On/Off text."""

    def __init__(self, theme, title: str, desc: str, save):
        self.toggle = Toggle(theme, title)
        self.state = label()
        self.toggle.toggled.connect(self._toggled)
        self._save = save
        self.card = card(title, desc, self.state, self.toggle)

    def _toggled(self, on: bool) -> None:
        self.state.setText("On" if on else "Off")
        self._save(on)

    def set(self, on: bool) -> None:
        self.toggle.blockSignals(True)
        self.toggle.setChecked(on)
        self.toggle.blockSignals(False)
        self.state.setText("On" if on else "Off")
        self.toggle.update()


# ---- moving a binding (C3) ---------------------------------------------------------------------
class MoveDialog(QDialog):
    """Listens for the button that should do what `source` does now."""

    def __init__(self, parent, window, table: Table, source: str):
        super().__init__(parent)
        self.window_ = window
        self.table, self.source = table, source
        self.target: str | None = None
        self.cleared = False
        b = bindings_of(window.store.config, table)
        what = describe(table, b, source)
        self.setWindowTitle("Move a button")
        self.setModal(True)
        self.setMinimumWidth(460)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        body = QVBoxLayout()
        body.setContentsMargins(24, 22, 24, 20)
        body.setSpacing(12)
        title = label(f"Move {BUTTON_LABELS.get(source, source)}")
        title.setStyleSheet("font-size: 15pt; font-weight: 600;")
        body.addWidget(title)
        body.addWidget(label(f"Press the button that should do {what}. For a stick, push it the way you want.",
                             wrap=True))
        well = QFrame()
        well.setStyleSheet(f"background: {window.theme['well']}; border-radius: 6px;")
        wl = QHBoxLayout(well)
        wl.setContentsMargins(18, 14, 18, 14)
        wl.setSpacing(16)
        wl.addWidget(Spinner(lambda: window.theme))
        texts = QVBoxLayout()
        texts.addWidget(label("Listening…"))
        now = QHBoxLayout()
        now.setSpacing(6)
        now.addWidget(label("Now:", sub=True))
        icon = QLabel()
        icon.setPixmap(window.art.pixmap(BUTTON_SPRITES.get(source, "A"), 18))
        now.addWidget(icon)
        now.addWidget(label(BUTTON_LABELS.get(source, source), sub=True))
        now.addStretch(1)
        texts.addLayout(now)
        wl.addLayout(texts, 1)
        body.addWidget(well)
        body.addWidget(label("Presses here never reach TTR.", sub=True))
        lay.addLayout(body)
        footer = QFrame()
        footer.setProperty("footer", True)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(24, 14, 24, 14)
        fl.addStretch(1)
        clear_button = QPushButton("Clear (Not set)")
        clear_button.clicked.connect(self._clear)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        fl.addWidget(clear_button)
        fl.addWidget(cancel)
        lay.addWidget(footer)
        self._held = window.pad.buttons  # held when it opened: ignored until let go
        window.pad.buttons_changed.connect(self._buttons)

    def _clear(self) -> None:
        self.cleared = True
        self.accept()

    def _buttons(self, buttons: frozenset) -> None:
        if not self.isActiveWindow():
            return
        self._held &= buttons
        new = [b for b in self.table.buttons if b in buttons - self._held]  # in the table's row order
        if new:
            self.target = new[0]
            self.accept()

    def done(self, result: int) -> None:
        try:
            self.window_.pad.buttons_changed.disconnect(self._buttons)
        except (RuntimeError, TypeError):
            pass
        super().done(result)


def describe(table: Table, b, button: str) -> str:
    press, hold = b.press.get(button), b.hold.get(button)
    if press and hold:
        return f"{action_label(table, press)} (hold: {action_label(table, hold)})"
    if hold:
        return f"hold: {action_label(table, hold)}"
    return action_label(table, press) if press else "nothing"


# ---- pages ---------------------------------------------------------------------------------
class SettingsWindow(QMainWindow):
    def __init__(self, store: SettingsStore | None = None, art: Art | None = None, pad: Pad | None = None):
        super().__init__()
        self.store = store or SettingsStore()
        self.art = art or Art()
        self.pad = pad or Pad(self.store.config.controller, self.store.config.timing.stick_button_threshold)
        self.theme = DARK if is_dark() else LIGHT
        self.setWindowTitle("Toontown Controller Settings")
        self.setWindowIcon(QIcon(self.art.pixmap("A", 64)))
        self.resize(1100, 780)
        self.setMinimumSize(860, 560)
        self._refreshers = []
        self._table = TABLES[0]

        root = QWidget()
        root.setObjectName("root")
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        side = QVBoxLayout()
        side.setContentsMargins(10, 18, 10, 18)
        brand = QHBoxLayout()
        brand.setContentsMargins(12, 6, 12, 14)
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(self.art.pixmap("A", 22))
        brand.addWidget(logo)
        name = label("Toontown Controller")
        name.setStyleSheet("font-size: 9pt; font-weight: 600;")
        brand.addWidget(name)
        brand.addStretch(1)
        side.addLayout(brand)
        self.nav = QListWidget()
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(240)
        self.nav.setAccessibleName("Settings sections")
        for title in ("General", "Controls", "Hints", "Game options", "About"):
            self.nav.addItem(title)
        side.addWidget(self.nav, 1)
        outer.addLayout(side)
        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        self.banner = label(wrap=True, banner=True)
        self.banner.setVisible(False)
        right.addWidget(self.banner)
        self.pages = QStackedWidget()
        right.addWidget(self.pages, 1)
        outer.addLayout(right, 1)
        self.setCentralWidget(root)

        for build in (self._general, self._controls, self._hints, self._options, self._about):
            self.pages.addWidget(build())
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)

        self.pad.buttons_changed.connect(self._light_test)
        self.pad.name_changed.connect(lambda _: self._refresh_pads())
        self._mtime = self._stat()
        watch = QTimer(self)
        watch.timeout.connect(self._watch_file)
        watch.start(1000)
        pads = QTimer(self)
        pads.timeout.connect(self._refresh_pads)
        pads.start(2000)
        try:
            QGuiApplication.styleHints().colorSchemeChanged.connect(lambda _: self.apply_theme())
        except AttributeError:
            pass
        self.apply_theme()
        self.refresh()

    # ---- plumbing ---------------------------------------------------------------------
    def apply_theme(self) -> None:
        self.theme = DARK if is_dark() else LIGHT
        self.setStyleSheet(stylesheet(self.theme))
        for w in self.findChildren(QWidget):
            w.update()

    def _stat(self):
        try:
            return CONFIG_FILE.stat().st_mtime if self.store.path == CONFIG_FILE else self.store.path.stat().st_mtime
        except OSError:
            return None

    def _watch_file(self) -> None:
        """Pick up changes made elsewhere (the module saving auto-sprint, a hand edit)."""
        mtime = self._stat()
        if mtime != self._mtime:
            self._mtime = mtime
            self.store.reload()
            self.refresh()

    def saved(self) -> None:
        self._mtime = self._stat()
        self.refresh()

    def save(self, key: str, value, section: str | None = None) -> None:
        self.store.set(key, value, section)
        if key == "stick_button_threshold":
            self.pad.threshold = value
        if key == "controller":
            self.pad.reader.set_preferred(value)
        self.saved()

    def refresh(self) -> None:
        self.banner.setVisible(not self.store.writable)
        self.banner.setText(self.store.error or "")
        for f in self._refreshers:
            f()

    # ---- General ------------------------------------------------------------------------
    def _general(self) -> QWidget:
        scroll, lay = page("General")
        c = lambda: self.store.config  # noqa: E731
        lay.addWidget(label("Controller", h2=True))
        self.pad_combo = QComboBox()
        self.pad_combo.setFixedWidth(280)
        self.pad_combo.setAccessibleName("Controller")
        self.pad_combo.activated.connect(lambda i: self.save("controller", self.pad_combo.itemData(i) or ""))
        self.pad_card = card("Controller", " ", self.pad_combo, buddy=self.pad_combo)
        lay.addWidget(self.pad_card)
        test = QFrame()
        test.setProperty("card", True)
        tl = QHBoxLayout(test)
        tl.setContentsMargins(18, 10, 18, 10)
        tl.setSpacing(12)
        tl.addWidget(label("Test", sub=True))
        tl.addSpacing(40)
        self.test_icons = {}
        for sprite in ("A", "B", "X", "Y", "LB", "RB", "LT", "RT", "VIEW", "START", "D4", "L", "R"):
            icon = QLabel()
            icon.setAccessibleName(sprite)
            tl.addWidget(icon)
            self.test_icons[sprite] = icon
        tl.addStretch(1)
        lay.addWidget(test)

        lay.addWidget(label("Hints", h2=True))
        show = Switch(lambda: self.theme, "Show hints",
                      "Button pictures on TTR’s buttons while you use the controller.", lambda v: self.save("hints", v))
        bar = Switch(lambda: self.theme, "Walking bar", "The small bar beside the laff meter while walking around.",
                     lambda v: self.save("hints_walking_bar", v))
        preview = QLabel()
        preview.setFixedSize(round(1009 * BADGE * 2.0) + 14, round(1009 * BADGE * 2.0) + 8)  # fits 200%
        preview.setAlignment(Qt.AlignCenter)
        size = Slider("Hint size", "How big the button pictures are drawn in game.", 0.5, 2.0, 0.05,
                      lambda v: f"{round(v * 100)}%", lambda v: self.save("hints_scale", v), extra=preview)
        size.changed = lambda v: (preview.setStyleSheet(f"background: {self.theme['well']}; border-radius: 6px;"),
                                  preview.setPixmap(self.art.pixmap("A", 1009 * BADGE * v)))
        for w in (show.card, bar.card, size.card):
            lay.addWidget(w)

        lay.addWidget(label("Movement", h2=True))
        dot = StickDot(lambda: self.theme)
        dz = Slider("Left stick deadzone", "How far the stick tilts before your toon moves.", 0.05, 0.6, 0.01,
                    lambda v: f"{round(v * 100)}%", lambda v: self.save("deadzone", v, "movement"), extra=dot)
        dz.changed = lambda v: (setattr(dot, "deadzone", v), dot.update())
        walk = Slider("Walk below", "A light tilt walks; past this it runs.", 0.3, 1.0, 0.01,
                      lambda v: f"{round(v * 100)}%", lambda v: self.save("walk_threshold", v, "movement"))
        sprint = Switch(lambda: self.theme, "Auto-sprint",
                        "Every run starts with a sprint. The sprint button turns this on and off.",
                        lambda v: self.save("auto_sprint", v))
        for w in (dz.card, walk.card, sprint.card):
            lay.addWidget(w)

        lay.addWidget(label("Buttons", h2=True))
        hold = Slider("Hold time", "How long a hold takes (Silly Meter, Run, Quit). The hint rings fill in this time.",
                      0.2, 1.5, 0.05, lambda v: f"{v:g} s", lambda v: self.save("hold_seconds", v, "timing"))
        lay.addWidget(hold.card)
        remap = QPushButton("Remap buttons  ›")
        remap.setProperty("link", True)
        remap.clicked.connect(lambda: self.nav.setCurrentRow(1))
        lay.addWidget(card("Remap buttons", "Walking, Battle, Gag Shop, NPC chat, SpeedChat, Friends, Book", remap))
        lay.addStretch(1)

        def refresh():
            show.set(c().hints)
            bar.set(c().hints_walking_bar)
            size.set(c().hints_scale)
            dz.set(c().movement.deadzone)
            walk.set(c().movement.walk_threshold)
            sprint.set(c().auto_sprint)
            hold.set(c().timing.hold_seconds)
            self._refresh_pads()
            self._light_test(self.pad.buttons)
        self._refreshers.append(refresh)
        return scroll

    def _refresh_pads(self) -> None:
        names = connected_names()
        preferred = self.store.config.controller
        items = [("First one plugged in", "")] + [(n, n) for n in dict.fromkeys(names)]
        if preferred and preferred not in names:
            items.append((f"{preferred} (not plugged in)", preferred))
        current = [(self.pad_combo.itemText(i), self.pad_combo.itemData(i)) for i in range(self.pad_combo.count())]
        if current != items:
            self.pad_combo.blockSignals(True)
            self.pad_combo.clear()
            for text, data in items:
                self.pad_combo.addItem(text, data)
            self.pad_combo.blockSignals(False)
        self.pad_combo.setCurrentIndex(max(0, [d for _, d in items].index(preferred) if preferred in
                                           [d for _, d in items] else 0))
        status = (f"Connected: {self.pad.name}. Press any button to test it." if self.pad.name else
                  "No controller connected. Press the Xbox button to wake it.")
        self.pad_card.desc.setText(status)

    def _light_test(self, buttons: frozenset) -> None:
        lit = {"A": "a", "B": "b", "X": "x", "Y": "y", "LB": "lb", "RB": "rb", "LT": "lt", "RT": "rt",
               "VIEW": "view", "START": "start"}
        for sprite, icon in self.test_icons.items():
            if sprite == "D4":
                on = any(b.startswith("dpad_") for b in buttons)
            elif sprite == "L":
                on = any(b == "ls" or b.startswith("ls_") for b in buttons)
            elif sprite == "R":
                on = any(b == "rs" or b.startswith("rs_") for b in buttons)
            else:
                on = lit[sprite] in buttons
            icon.setPixmap(self.art.pixmap(sprite, 26, dim=not on))

    # ---- Controls ----------------------------------------------------------------------
    def _controls(self) -> QWidget:
        scroll, lay = page("Controls")
        self.tabs = QTabBar()
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setAccessibleName("Where the buttons apply")
        for t in TABLES:
            self.tabs.addTab(t.title)
        lay.addWidget(self.tabs)
        sep = QFrame()
        sep.setProperty("sep", True)
        lay.addWidget(sep)
        self.table_note = label(wrap=True, sub=True)
        lay.addWidget(self.table_note)
        lay.addSpacing(4)
        self.grid_card = QFrame()
        self.grid_card.setProperty("card", True)
        self.grid = QGridLayout(self.grid_card)
        self.grid.setContentsMargins(18, 8, 18, 8)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(4)
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnStretch(2, 1)
        lay.addWidget(self.grid_card)
        foot = QHBoxLayout()
        self.restore_table_button = QPushButton()
        self.restore_table_button.clicked.connect(self._restore_table)
        foot.addWidget(self.restore_table_button)
        foot.addStretch(1)
        foot.addWidget(label("Saved as you go. The game picks it up right away.", sub=True))
        lay.addSpacing(8)
        lay.addLayout(foot)
        lay.addStretch(1)
        self.tabs.currentChanged.connect(lambda i: (setattr(self, "_table", TABLES[i]), self._fill_grid()))
        self._refreshers.append(self._fill_grid)
        return scroll

    def _fill_grid(self) -> None:
        table = self._table
        b = bindings_of(self.store.config, table)
        self.table_note.setText(table.note + " A hold happens after "
                                f"{self.store.config.timing.hold_seconds:g} s; let go sooner and it’s a press.")
        self.restore_table_button.setText(f"Restore {table.title} defaults")
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for col, text in enumerate(("Button", "Press", "Hold")):
            self.grid.addWidget(label(text, sub=True), 0, col)
        help_ = ACTION_HELP.get(table.key, {})
        for row, button in enumerate(table.buttons, start=1):
            name = QWidget()
            nl = QHBoxLayout(name)
            nl.setContentsMargins(0, 0, 0, 0)
            nl.setSpacing(10)
            icon = QLabel()
            icon.setFixedSize(40, 30)
            icon.setAlignment(Qt.AlignCenter)
            sprite = BUTTON_SPRITES[button]
            height = 20 if ":" in sprite else 22 if sprite in ("LB", "RB", "LS", "RS") else 26
            icon.setPixmap(self.art.pixmap(sprite, height))
            nl.addWidget(icon)
            nl.addWidget(label(BUTTON_LABELS[button]))
            nl.addStretch(1)
            self.grid.addWidget(name, row, 0)
            for col, hold in ((1, False), (2, True)):
                current = (b.hold if hold else b.press).get(button)
                combo = QComboBox()
                combo.setAccessibleName(f"{BUTTON_LABELS[button]} {'hold' if hold else 'press'}")
                combo.addItem("Not set", None)
                for action, text in action_choices(table, current):
                    combo.addItem(text, action)
                    if action in help_:
                        combo.setItemData(combo.count() - 1, help_[action], Qt.ToolTipRole)
                combo.setCurrentIndex(max(0, combo.findData(current)) if current else 0)
                combo.setProperty("unset", current is None)
                combo.setMinimumWidth(120)
                combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                combo.activated.connect(lambda i, c=combo, bt=button, h=hold: self._set_action(bt, c.itemData(i), h))
                self.grid.addWidget(combo, row, col)
            mv = QPushButton("Move…")
            mv.setProperty("link", True)
            mv.setToolTip("Move what this button does to another button")
            mv.setAccessibleName(f"Move {BUTTON_LABELS[button]}")
            mv.clicked.connect(lambda _=False, bt=button: self._move(bt))
            self.grid.addWidget(mv, row, 3)

    def _set_action(self, button: str, action, hold: bool) -> None:
        table = self._table
        b = with_action(bindings_of(self.store.config, table), button, action, hold)
        self.store.set_bindings(table, b)
        self.saved()

    def _move(self, source: str) -> None:
        table = self._table
        dialog = MoveDialog(self, self, table, source)
        if dialog.exec() != QDialog.Accepted:
            return
        b = bindings_of(self.store.config, table)
        if dialog.cleared:
            self.store.set_bindings(table, clear(b, source))
            self.saved()
            return
        target = dialog.target
        if target is None or target == source:
            return
        moved, clash = move(b, source, target)
        if clash:
            a, t = BUTTON_LABELS[source], BUTTON_LABELS[target]
            box = QMessageBox(self)
            box.setWindowTitle("Swap buttons")
            box.setText(f"{t} already does {describe(table, b, target)}")
            box.setInformativeText(f"Swap them, so {t} does {describe(table, b, source)} and {a} does "
                                   f"{describe(table, b, target)}? Only {table.title} changes; the other "
                                   "modes keep their own buttons.")
            swap = box.addButton("Swap", QMessageBox.AcceptRole)
            swap.setProperty("accent", True)
            box.addButton("Cancel", QMessageBox.RejectRole)
            box.exec()
            if box.clickedButton() is not swap:
                return
        self.store.set_bindings(table, moved)
        self.saved()

    def _restore_table(self) -> None:
        self.store.restore_table(self._table)
        self.saved()

    # ---- Hints ---------------------------------------------------------------------------
    def _hints(self) -> QWidget:
        scroll, lay = page("Hints")
        c = lambda: self.store.config  # noqa: E731
        box = QFrame()
        box.setProperty("card", True)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(18, 14, 18, 14)
        bl.setSpacing(10)
        self.preview_title = label(sub=True)
        bl.addWidget(self.preview_title)
        self.preview = QLabel()
        self.preview.setMinimumHeight(240)
        self.preview.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        bl.addWidget(self.preview)
        bl.addWidget(label("Badges sit on TTR’s buttons, popup buttons are covered, a gold ring fills on buttons you "
                           "hold, and a few screens get a small bar.", sub=True, wrap=True))
        lay.addWidget(box)
        show = Switch(lambda: self.theme, "Show hints", "While you use the controller. They hide when you use the mouse.",
                      lambda v: self.save("hints", v))
        bar = Switch(lambda: self.theme, "Walking bar",
                     "Walk, Jump, Gags, Tasks, Map and Unite, beside the laff meter while walking around.",
                     lambda v: self.save("hints_walking_bar", v))
        size = Slider("Size", "Bigger helps on a TV or a big window.", 0.5, 2.0, 0.05,
                      lambda v: f"{round(v * 100)}%", lambda v: self.save("hints_scale", v))
        size.changed = self._draw_preview
        for w in (show.card, bar.card, size.card):
            lay.addWidget(w)
        lay.addWidget(card("Hints follow your Controls", "Move Pass to RB and the badge on Pass shows RB."))
        lay.addStretch(1)

        def refresh():
            show.set(c().hints)
            bar.set(c().hints_walking_bar)
            size.set(c().hints_scale)
        self._refreshers.append(refresh)
        return scroll

    def _draw_preview(self, scale: float) -> None:
        self.preview_title.setText(f"Preview at {round(scale * 100)}%, as in a 1920×1009 window")
        w, h = 700, 240
        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor("#3c6e3a"))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#e8d9a8"))
        p.drawRoundedRect(QRectF(30, 30, 230, 150), 12, 12)
        font = QFont("Segoe UI", 13, QFont.Bold)
        p.setFont(font)
        for y, text, color in ((62, "PASS", "#d8452e"), (118, "RUN", "#6a6a6a")):
            p.setBrush(QColor(color))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(80, y, 130, 38), 16, 16)
            p.setPen(QColor("#ffffff"))
            p.drawText(QRectF(80, y, 130, 38), Qt.AlignCenter, text)
        p.setPen(QPen(QColor("#3f9a3a"), 4))
        p.setBrush(QColor("#fffbe0"))
        p.drawRoundedRect(QRectF(330, 30, 320, 150), 14, 14)
        p.setPen(QColor("#2b2410"))
        p.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
        p.drawText(QRectF(330, 42, 320, 24), Qt.AlignCenter, "Delete this task?")
        p.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        p.drawText(QRectF(400, 150, 60, 20), Qt.AlignCenter, "OK")
        p.drawText(QRectF(520, 150, 60, 20), Qt.AlignCenter, "Cancel")
        center = UIPoint("center", 0, 0, "center")
        pieces = [
            (Badge("Y", center), (84, 64), 0),
            (Badge("B", center, hold=True), (84, 120), round(RING_STEPS * 0.6)),
            (Badge("A", center, COVER, cover=True), (430, 118), 0),
            (Badge("B", center, COVER, cover=True), (550, 118), 0),
            (Bar((("D4", "Move"), ("A", "Select"), ("LB", "Teammates")), center), (330, 212), 0),
        ]
        for hint, (x, y), ring in pieces:
            piece = self.art.piece(hint, scale, ring)
            if piece is not None:
                p.drawImage(round(x - piece.width() / 2), round(y - piece.height() / 2), piece)
        p.end()
        self.preview.setPixmap(QPixmap.fromImage(img))

    # ---- Game options -------------------------------------------------------------------
    def _options(self) -> QWidget:
        scroll, lay = page("Game options")
        c = lambda: self.store.config  # noqa: E731
        cursor = Switch(lambda: self.theme, "Hide TTR’s cursor",
                        "Turns off TTR’s custom cursor in its settings, so the cursor can vanish while you play on "
                        "the controller. Applies the next time TTR starts.", lambda v: self.save("hide_cursor", v))
        hud = Switch(lambda: self.theme, "Map, tasks and gags stay open",
                     "One press shows them, the next hides them. Off: they show while the button is held.",
                     lambda v: self.save("toggle_hud", v))
        lay.addWidget(cursor.card)
        lay.addWidget(hud.card)
        lay.addSpacing(12)
        adv = QFrame()
        adv.setProperty("card", True)
        al = QVBoxLayout(adv)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(0)
        head = QPushButton()
        head.setObjectName("expander")
        head.setCheckable(True)
        head.setChecked(True)
        head.setAccessibleName("Advanced")
        head.setCursor(Qt.PointingHandCursor)
        head.setMinimumHeight(64)
        hrow = QHBoxLayout(head)
        hrow.setContentsMargins(18, 10, 18, 10)
        htext = QVBoxLayout()
        htext.setSpacing(2)
        htitle = label("Advanced")
        htitle.setStyleSheet("font-weight: 500;")
        htext.addWidget(htitle)
        htext.addWidget(label("Fine tuning. The defaults suit most controllers.", sub=True))
        hrow.addLayout(htext, 1)
        chevron = label("⌃")
        hrow.addWidget(chevron)
        for w in (htitle, chevron):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
        head.toggled.connect(lambda on: chevron.setText("⌃" if on else "⌄"))
        al.addWidget(head)
        inner = QWidget()
        il = QVBoxLayout(inner)
        il.setContentsMargins(16, 0, 0, 8)
        il.setSpacing(0)
        diag = Slider("Diagonals", "How wide the diagonal directions are on the left stick.", 0.2, 0.6, 0.01,
                      lambda v: f"{v:.2f}", lambda v: self.save("direction_threshold", v, "movement"))
        press = Slider("Stick press point",
                       "How far a stick tilts before it counts as a button (scrolling, D-pad stand-ins).",
                       0.2, 0.9, 0.05, lambda v: f"{round(v * 100)}%",
                       lambda v: self.save("stick_button_threshold", v, "timing"))
        tap = Slider("Sprint tap speed", "Sprint is a quick double tap of forward: the length of each tap.",
                     0.03, 0.15, 0.01, lambda v: f"{v:.2f} s", lambda v: self.save("sprint_step_seconds", v, "timing"))
        for s in (diag, press, tap):
            s.card.setProperty("card", False)
            il.addWidget(s.card)
        al.addWidget(inner)
        head.toggled.connect(inner.setVisible)
        lay.addWidget(adv)
        restore = QPushButton("Restore advanced defaults")
        restore.clicked.connect(self._restore_advanced)
        lay.addSpacing(8)
        row = QHBoxLayout()
        row.addWidget(restore)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(1)

        def refresh():
            cursor.set(c().hide_cursor)
            hud.set(c().toggle_hud)
            diag.set(c().movement.direction_threshold)
            press.set(c().timing.stick_button_threshold)
            tap.set(c().timing.sprint_step_seconds)
        self._refreshers.append(refresh)
        return scroll

    def _restore_advanced(self) -> None:
        d = Config()
        self.store.set("direction_threshold", d.movement.direction_threshold, "movement")
        self.store.set("stick_button_threshold", d.timing.stick_button_threshold, "timing")
        self.store.set("sprint_step_seconds", d.timing.sprint_step_seconds, "timing")
        self.pad.threshold = d.timing.stick_button_threshold
        self.saved()

    # ---- About --------------------------------------------------------------------------
    def _about(self) -> QWidget:
        scroll, lay = page("About")
        head = QFrame()
        head.setProperty("card", True)
        hl = QHBoxLayout(head)
        hl.setContentsMargins(18, 18, 18, 18)
        hl.setSpacing(18)
        tile = QWidget()
        tile.setFixedSize(64, 64)
        tg = QGridLayout(tile)
        tg.setContentsMargins(6, 6, 6, 6)
        tg.setSpacing(2)
        for i, s in enumerate(("Y", "B", "X", "A")):
            icon = QLabel()
            icon.setPixmap(self.art.pixmap(s, 24))
            tg.addWidget(icon, i // 2, i % 2)
        hl.addWidget(tile)
        text = QVBoxLayout()
        title = label("Toontown Controller Module")
        title.setStyleSheet("font-size: 14pt; font-weight: 600;")
        text.addWidget(title)
        text.addWidget(label(f"Version {_version()} · Xbox controller support for Toontown Rewritten", sub=True))
        hl.addLayout(text, 1)
        hl.addWidget(self._link("Project page", REPO))
        lay.addWidget(head)
        folder = QPushButton("Open folder")
        folder.clicked.connect(lambda: os.startfile(self.store.path.parent))  # noqa: S606 (Windows only)
        path = card("Settings file", str(self.store.path), folder)
        path.desc.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path.desc.setStyleSheet("font-family: Consolas, 'Cascadia Mono', monospace;")
        lay.addWidget(path)
        everything = QPushButton("Restore defaults…")
        everything.setProperty("danger", True)
        everything.clicked.connect(self._restore_everything)
        lay.addWidget(card("Restore every setting",
                           "All buttons and options back to their defaults. Your current file is backed up first "
                           f"({self.store.backup.name}).", everything))
        lay.addWidget(card("Report a problem", "Opens the project’s issue page. A screenshot from LB + RB in game helps.",
                           self._link("Open issues", REPO + "/issues")))
        lay.addSpacing(12)
        lay.addWidget(label("A fan-made tool, not made by or affiliated with Toontown Rewritten. Button pictures from "
                            "the Xbox controller sprite sheet included with the project.", sub=True, wrap=True))
        lay.addStretch(1)
        return scroll

    def _link(self, text: str, url: str) -> QPushButton:
        b = QPushButton(text)
        b.setProperty("link", True)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        return b

    def _restore_everything(self) -> None:
        answer = QMessageBox.question(self, "Restore every setting",
                                      "Put every button and option back to its default? Your current settings file "
                                      f"is backed up to {self.store.backup.name} first.")
        if answer == QMessageBox.Yes:
            self.store.restore_everything()
            self.pad.reader.set_preferred("")
            self.saved()

    def closeEvent(self, event) -> None:
        self.pad.close()
        super().closeEvent(event)


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Toontown Controller Settings")
    window = SettingsWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
