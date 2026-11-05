"""Read Toontown Rewritten's settings.json (keybinds, controller and display options)."""

import json
from dataclasses import dataclass
from pathlib import Path

from .keys import KeyCombo, parse_combo

DEFAULT_TTR_DIR = Path(r"C:\Program Files (x86)\Toontown Rewritten")
SETTINGS_FILE = "settings.json"

# Classic Toontown defaults, used only when settings.json is missing or lacks a control.
DEFAULT_CONTROLS = {
    "forward": "arrow_up",
    "reverse": "arrow_down",
    "left": "arrow_left",
    "right": "arrow_right",
    "jump": "control",
    "walk": "shift",
    "showGags": "home",
    "showTasks": "end",
    "showMap": "alt",
    "stickerBook": "f8",
    "friendsList": "f7",
    "options": "shift-escape",
    "exitActivity": "escape",
    "performAction": "delete",
    "cameraNext": "tab",
    "cameraPrev": "shift-tab",
    "lookUp": "page_up",
    "lookDown": "page_down",
    "chat": "t",
    "screenshot": "f9",
}


@dataclass(frozen=True)
class TTRSettings:
    controls: dict[str, KeyCombo]
    native_controller_enabled: bool = False
    display_mode: str = "window"
    custom_cursor: bool = False

    def combo(self, control: str) -> KeyCombo:
        return self.controls[control]


def parse(data: dict) -> TTRSettings:
    raw = {**DEFAULT_CONTROLS, **data.get("controls", {})}
    controls = {}
    for name, text in raw.items():
        if not isinstance(text, str):
            # "controls" also holds options like "auto-jump": false.
            continue
        try:
            controls[name] = parse_combo(text)
        except ValueError:
            # Unknown key names (e.g. mouse buttons) are skipped rather than fatal.
            if name in DEFAULT_CONTROLS:
                controls[name] = parse_combo(DEFAULT_CONTROLS[name])
    return TTRSettings(
        controls=controls,
        native_controller_enabled=bool(data.get("controller", {}).get("controller-enabled", False)),
        display_mode=data.get("video", {}).get("display-mode", "window"),
        custom_cursor=bool(data.get("video", {}).get("enable-cursor", False)),
    )


def load(path: Path) -> TTRSettings:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return parse(data)


def set_custom_cursor(path: Path, on: bool) -> bool:
    """Turn TTR's custom cursor (video.enable-cursor, which has no switch in TTR's Options)
    on or off, keeping the rest of settings.json as it is. TTR reads it when it starts.
    Returns whether the file was written."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(data, dict):
        return False
    video = data.setdefault("video", {})
    if not isinstance(video, dict):
        return False
    video["enable-cursor"] = on
    try:
        path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    except OSError:
        return False
    return True


class SettingsWatcher:
    """Reloads settings.json when it changes on disk (e.g. after rebinding in game)."""

    def __init__(self, ttr_dir: Path):
        self.path = ttr_dir / SETTINGS_FILE
        self._mtime: float | None = None
        self.settings = self._reload()

    def set_dir(self, ttr_dir: Path) -> None:
        if ttr_dir / SETTINGS_FILE != self.path:
            self.path = ttr_dir / SETTINGS_FILE
            self._mtime = None

    def check(self) -> TTRSettings | None:
        """Return new settings if the file changed since the last check, else None."""
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            mtime = None
        if mtime == self._mtime:
            return None
        self.settings = self._reload()
        return self.settings

    def _reload(self) -> TTRSettings:
        try:
            self._mtime = self.path.stat().st_mtime
        except OSError:
            self._mtime = None
        return load(self.path)
