"""The application's icon (input_sprites/icon.png, the user's art): the module window,
the Settings window, their dialogs, and the taskbar."""

import ctypes
import os
from pathlib import Path

ICON_NAME = "icon.png"
# Its own taskbar group: without one, Windows groups the windows under pythonw.exe and
# shows Python's icon there instead of the window's.
APP_ID = "ToontownControllerModule"


def find_icon() -> Path | None:
    here = Path(__file__).resolve()
    for p in (here.parents[2] / "input_sprites" / ICON_NAME, here.parent / ICON_NAME):
        if p.exists():
            return p
    return None


def app_pixmap(size: int):
    """The icon as a QPixmap this many pixels square (the windows' header logo), or None."""
    from PySide6.QtGui import QPixmap
    from PySide6.QtCore import Qt

    path = find_icon()
    full = QPixmap(str(path)) if path is not None else None
    if full is None or full.isNull():
        return None
    return full.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def use_app_icon(app) -> None:
    """Give a QApplication the icon (every window and dialog it opens shows it) and its
    own taskbar group."""
    from PySide6.QtGui import QIcon, QPixmap
    from PySide6.QtCore import Qt

    if os.name == "nt":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
        except (AttributeError, OSError):
            pass
    path = find_icon()
    if path is None:
        return
    full = QPixmap(str(path))
    if full.isNull():
        return
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(full.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    app.setWindowIcon(icon)
