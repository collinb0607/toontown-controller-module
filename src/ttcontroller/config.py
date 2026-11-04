"""The module's own settings: bindings, stick tuning and timing.

Stored as JSON in %APPDATA%\\ToontownControllerModule\\config.json. The file is
created with the defaults on first run and can be edited by hand; changes are
picked up while the module is running.
"""

import json
import os
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

from .battle import BATTLE_ACTIONS, default_battle_bindings
from .bindings import STICK_BUTTONS, Bindings
from .controller import BUTTONS
from .mapper import SPECIAL_ACTIONS, Timing, default_bindings
from .movement import MovementTuning
from .shop import SHOP_ACTIONS, default_shop_bindings

CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "ToontownControllerModule"
CONFIG_FILE = CONFIG_DIR / "config.json"

VALID_BUTTONS = (*BUTTONS, *STICK_BUTTONS)

HELP = {
    "buttons": ", ".join(VALID_BUTTONS),
    "actions": "Any TTR control from TTR's Options > Controls (e.g. jump, showGags, stickerBook, options), "
               "or one of: " + "; ".join(f"{name} = {desc}" for name, desc in SPECIAL_ACTIONS.items()),
    "press": "Button -> action. TTR controls are held while the button is held. "
             "Set a button to null to unbind it.",
    "hold": "Button -> action after holding it for timing.hold_seconds. "
            "A button with a hold action sends its press action as a tap when released early.",
    "battle": "Bindings used while a battle panel is showing. Buttons not bound here keep their "
              "overworld action (e.g. speedchat), except that the left stick never walks in battle. "
              "Actions: " + "; ".join(f"{name} = {desc}" for name, desc in BATTLE_ACTIONS.items()),
    "shop": "Bindings used in the gag shop, the same way. "
            "Actions: " + "; ".join(f"{name} = {desc}" for name, desc in SHOP_ACTIONS.items()),
}


@dataclass
class Config:
    bindings: Bindings = field(default_factory=default_bindings)
    battle: Bindings = field(default_factory=default_battle_bindings)
    shop: Bindings = field(default_factory=default_shop_bindings)
    movement: MovementTuning = field(default_factory=MovementTuning)
    timing: Timing = field(default_factory=Timing)


def to_json(config: Config) -> dict:
    return {
        "_help": HELP,
        "bindings": {
            "press": config.bindings.press,
            "hold": config.bindings.hold,
            "battle": {"press": config.battle.press, "hold": config.battle.hold},
            "shop": {"press": config.shop.press, "hold": config.shop.hold},
        },
        "movement": asdict(config.movement),
        "timing": asdict(config.timing),
    }


def _merge_bindings(defaults: dict[str, str], user: dict, warnings: list[str], table: str) -> dict[str, str]:
    merged = dict(defaults)
    for button, action in user.items():
        if button not in VALID_BUTTONS:
            warnings.append(f"bindings.{table}: unknown button {button!r} (ignored)")
        elif action is None:
            merged.pop(button, None)
        elif not isinstance(action, str):
            warnings.append(f"bindings.{table}.{button}: action must be a name or null (ignored)")
        else:
            merged[button] = action
    return merged


def _merge_numbers(default, user: dict, warnings: list[str], section: str):
    changes = {}
    for f in fields(default):
        if f.name not in user:
            continue
        value = user[f.name]
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            changes[f.name] = float(value)
        else:
            warnings.append(f"{section}.{f.name}: must be a non-negative number (using {getattr(default, f.name)})")
    return replace(default, **changes)


def parse(data: dict) -> tuple[Config, list[str]]:
    """Build a Config from JSON data, falling back to defaults for anything missing or invalid."""
    warnings: list[str] = []
    defaults = Config()
    bindings = data.get("bindings", {})
    battle = bindings.get("battle", {})
    shop = bindings.get("shop", {})
    config = Config(
        bindings=Bindings(
            press=_merge_bindings(defaults.bindings.press, bindings.get("press", {}), warnings, "press"),
            hold=_merge_bindings(defaults.bindings.hold, bindings.get("hold", {}), warnings, "hold"),
        ),
        battle=Bindings(
            press=_merge_bindings(defaults.battle.press, battle.get("press", {}), warnings, "battle.press"),
            hold=_merge_bindings(defaults.battle.hold, battle.get("hold", {}), warnings, "battle.hold"),
        ),
        shop=Bindings(
            press=_merge_bindings(defaults.shop.press, shop.get("press", {}), warnings, "shop.press"),
            hold=_merge_bindings(defaults.shop.hold, shop.get("hold", {}), warnings, "shop.hold"),
        ),
        movement=_merge_numbers(defaults.movement, data.get("movement", {}), warnings, "movement"),
        timing=_merge_numbers(defaults.timing, data.get("timing", {}), warnings, "timing"),
    )
    return config, warnings


def load(path: Path = CONFIG_FILE) -> tuple[Config, list[str]]:
    """Load the config, creating it with defaults if it doesn't exist yet."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(to_json(Config()), indent=2), encoding="utf-8")
        return Config(), []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        # Don't overwrite a file the user is in the middle of editing.
        return Config(), [f"couldn't read {path.name} ({e}); using defaults"]
    if not isinstance(data, dict):
        return Config(), [f"{path.name} should contain a JSON object; using defaults"]
    return parse(data)


def unknown_actions(config: Config, ttr_controls) -> list[str]:
    """Bindings whose action is neither a special action nor a TTR control."""
    problems = []
    for table, bindings in (("press", config.bindings.press), ("hold", config.bindings.hold)):
        for button, action in bindings.items():
            if action not in SPECIAL_ACTIONS and action not in ttr_controls:
                problems.append(f"bindings.{table}.{button}: unknown action {action!r}")
    for table, bindings in (("battle.press", config.battle.press), ("battle.hold", config.battle.hold)):
        for button, action in bindings.items():
            if action not in BATTLE_ACTIONS:
                problems.append(f"bindings.{table}.{button}: unknown battle action {action!r}")
    for table, bindings in (("shop.press", config.shop.press), ("shop.hold", config.shop.hold)):
        for button, action in bindings.items():
            if action not in SHOP_ACTIONS:
                problems.append(f"bindings.{table}.{button}: unknown shop action {action!r}")
    return problems


class ConfigWatcher:
    """Reloads config.json when it changes on disk."""

    def __init__(self, path: Path = CONFIG_FILE):
        self.path = path
        self.config, self.warnings = load(path)
        self._mtime = self._stat()

    def _stat(self) -> float | None:
        try:
            return self.path.stat().st_mtime
        except OSError:
            return None

    def check(self) -> Config | None:
        """Return the new config if the file changed since the last check, else None."""
        mtime = self._stat()
        if mtime == self._mtime:
            return None
        self._mtime = mtime
        self.config, self.warnings = load(self.path)
        self._mtime = self._stat()
        return self.config
