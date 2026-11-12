"""Build ToontownController.exe, the module packaged with its own icon.

    .venv/Scripts/python.exe -m pip install -e .[build]
    .venv/Scripts/python.exe tools/build_exe.py

Double-clicking it works too: it runs itself again with the project's .venv Python (the
one with PySide6 and PyInstaller) and keeps its window open at the end.

Writes input_sprites/icon.ico from icon.png (16 to 256 px, for Windows), then runs
PyInstaller: dist/ToontownController/ToontownController.exe, a windowed exe that opens
the module window (and Settings, as itself with --settings). The whole folder is what
gets shared: the exe needs the _internal folder beside it.
"""

import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPRITES = ROOT / "input_sprites"
ICON_PNG = SPRITES / "icon.png"
ICON_ICO = SPRITES / "icon.ico"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def write_ico() -> None:
    """A multi-size .ico whose entries are PNGs (Windows Vista and later read those)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    full = QImage(str(ICON_PNG))
    if full.isNull():
        raise SystemExit(f"Can't read {ICON_PNG}")
    images = []
    for size in SIZES:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        full.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation).save(buffer, "PNG")
        images.append((size, bytes(data)))
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for size, png in images:
        side = 0 if size >= 256 else size  # 0 means 256
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset)
        blobs += png
        offset += len(png)
    ICON_ICO.write_bytes(header + entries + blobs)
    print(f"Wrote {ICON_ICO} ({', '.join(str(s) for s in SIZES)} px)")


def build() -> None:
    entry = ROOT / "build" / "exe_entry.py"
    entry.parent.mkdir(exist_ok=True)
    entry.write_text("from ttcontroller.launcher import main\n\nmain()\n", encoding="utf-8")
    sep = os.pathsep
    command = [
        sys.executable, "-m", "PyInstaller", str(entry),
        "--name", "ToontownController",
        "--windowed", "--onedir", "--noconfirm", "--clean",
        "--icon", str(ICON_ICO),
        "--paths", str(ROOT / "src"),
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "pyinstaller"),
        "--specpath", str(ROOT / "build"),
        # Beside the package's modules, where app_icon and hint_draw look when packaged.
        "--add-data", f"{ICON_PNG}{sep}ttcontroller",
        # Each controller's button pictures (hint_draw.SHEET_NAMES).
        *[arg for family in ("xbox", "playstation", "switch", "steam")
          for arg in ("--add-data", f"{SPRITES / f'{family}-spritesheet.png'}{sep}ttcontroller")],
        "--add-data", f"{SPRITES / 'all_input.png'}{sep}ttcontroller",  # the name keyboard's keys
        "--collect-submodules", "ttcontroller",
    ]
    subprocess.run(command, check=True, cwd=ROOT)
    print(f"Built {ROOT / 'dist' / 'ToontownController' / 'ToontownController.exe'}")


VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def _in_venv() -> bool:
    return Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()


def _double_clicked() -> bool:
    # Explorer's console has no PROMPT (a terminal's cmd or PowerShell session sets one).
    return os.name == "nt" and "PROMPT" not in os.environ and "--no-pause" not in sys.argv


if __name__ == "__main__":
    if not _in_venv() and VENV_PYTHON.exists():
        # Windows' own Python (a double-click) has no PySide6 or PyInstaller: use the venv's.
        code = subprocess.run([str(VENV_PYTHON), __file__, *sys.argv[1:], "--no-pause"]).returncode
        if _double_clicked():
            input("Press Enter to close.")
        sys.exit(code)
    try:
        write_ico()
        if "--icon-only" not in sys.argv:
            build()
    except Exception as error:
        print(f"Build failed: {error}")
        # PyInstaller's own "Access is denied" shows above: the old exe is still running.
        print("If it says Access is denied, close ToontownController.exe and build again.")
        if _double_clicked():
            input("Press Enter to close.")
        sys.exit(1)
    if _double_clicked():
        input("Press Enter to close.")
