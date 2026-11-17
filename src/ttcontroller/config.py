"""The module's own settings: bindings, stick tuning and timing.

Stored as JSON in %APPDATA%\\ToontownControllerModule\\config.json. The file is
created with the defaults on first run and can be edited by hand; changes are
picked up while the module is running.
"""

import json
import os
import shutil
import time
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

from .battle import BATTLE_ACTIONS, default_battle_bindings
from .book import BOOK_ACTIONS, default_book_bindings
from .bindings import STICK_BUTTONS, TRIGGER_BUTTONS, Bindings
from .controller import BUTTONS
from .mapper import SPECIAL_ACTIONS, Timing, default_bindings
from .movement import MovementTuning
from .friends import FRIENDS_ACTIONS, default_friends_bindings
from .npc import NPC_ACTIONS, default_npc_bindings
from .shop import SHOP_ACTIONS, default_shop_bindings
from .speedchat import SPEEDCHAT_ACTIONS, default_speedchat_bindings

CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home())) / "ToontownControllerModule"
CONFIG_FILE = CONFIG_DIR / "config.json"
# A copy of config.json from before this session first rewrote it (the module or Settings).
BACKUP_NAME = "config.backup.json"

VALID_BUTTONS = (*BUTTONS, *STICK_BUTTONS, *TRIGGER_BUTTONS)
# Earlier names for the stick clicks, still accepted.
OLD_BUTTON_NAMES = {"l3": "ls", "r3": "rs"}

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
    "npc": "Bindings used while talking to an NPC (only the select button) and choosing a task. "
           "Actions: " + "; ".join(f"{name} = {desc}" for name, desc in NPC_ACTIONS.items()),
    "speedchat": "Bindings used while the speedchat menu is open. "
                 "Actions: " + "; ".join(f"{name} = {desc}" for name, desc in SPEEDCHAT_ACTIONS.items()),
    "friends": "Bindings used while the friends list or a toon's panel is open. "
               "Actions: " + "; ".join(f"{name} = {desc}" for name, desc in FRIENDS_ACTIONS.items()),
    "toggle_hud": "true: the map, tasks and gags buttons (showMap, showTasks, showGags) "
                             "show them on one press and hide them on the next. false: shown while held.",
    "hints": "true: show which controller button does what, as small button pictures on TTR's buttons "
             "(and covering popup buttons), while the controller is in use. false: no hints.",
    "hints_walking_bar": "true: while walking around, a small bar beside the laff meter lists the main buttons "
                         "(walk, jump, gags, tasks, map, unite). false: just the badges on TTR's buttons.",
    "fishing_cast": "How the left stick casts while fishing (A held): \"move\" moves the aim at a steady speed "
                    "(it stays put when the stick is let go), \"stick\" puts it where the stick points (at rest, the shortest cast). "
                    "LS switches between them on the dock and saves it here.",
    "two_toons": "true: two TTR windows, one played with keyboard and mouse and one with the controller "
                 "in the background. The module's window asks which TTR window is the controller's each time. "
                 "false: the controller plays the TTR window in front.",
    "close_to_tray": "true: closing the module's window keeps the controller running, with an icon in the "
                     "notification area (click it to open the window again, right-click for Settings and Quit). "
                     "false: closing it quits.",
    "rumble": "true: the controller rumbles when your toon takes damage (harder for bigger hits, long when "
              "it goes sad). Needs TTR's Companion App Support on (Options); TTR asks once to allow the module.",
    "hints_scale": "How big the hints are drawn: 1 is the normal size, 1.25 a quarter bigger.",
    "controller": "Which controller to use, by name (the settings window lists them). Empty: the first one "
                  "plugged in. If the named one isn't plugged in, the first one is used.",
    "button_pictures": "Which controller's buttons the hints show: \"auto\" (the one plugged in), \"xbox\", "
                       "\"playstation\", \"switch\" or \"steam\".",
    "book": "Bindings used while the shticker book is open. "
            "Actions: " + "; ".join(f"{name} = {desc}" for name, desc in BOOK_ACTIONS.items()),
}


# The button_pictures choices: "auto", then hint_draw.FAMILIES.
BUTTON_PICTURES = ("auto", "xbox", "playstation", "switch", "steam")

# The remappable tables besides walking around's (Config.bindings): each one's key (its
# Config field and its place under "bindings" in config.json), its actions, its defaults
# and what its problems call its actions. Everything that goes through every table
# (reading, writing, checking, the settings window, the hints) goes through this list.
SCREEN_TABLES = (
    ("battle", BATTLE_ACTIONS, default_battle_bindings, "battle"),
    ("shop", SHOP_ACTIONS, default_shop_bindings, "shop"),
    ("npc", NPC_ACTIONS, default_npc_bindings, "NPC"),
    ("speedchat", SPEEDCHAT_ACTIONS, default_speedchat_bindings, "speedchat"),
    ("friends", FRIENDS_ACTIONS, default_friends_bindings, "friends"),
    ("book", BOOK_ACTIONS, default_book_bindings, "book"),
)


@dataclass
class Config:
    bindings: Bindings = field(default_factory=default_bindings)
    battle: Bindings = field(default_factory=default_battle_bindings)
    shop: Bindings = field(default_factory=default_shop_bindings)
    npc: Bindings = field(default_factory=default_npc_bindings)
    speedchat: Bindings = field(default_factory=default_speedchat_bindings)
    friends: Bindings = field(default_factory=default_friends_bindings)
    book: Bindings = field(default_factory=default_book_bindings)
    movement: MovementTuning = field(default_factory=MovementTuning)
    # Every run starts with a sprint. The sprint button turns this on and off.
    auto_sprint: bool = False
    # Keep TTR's custom cursor turned off in its settings.json, so the cursor can be
    # fully hidden while the controller is in use.
    hide_cursor: bool = False
    # The map, tasks and gags buttons (showMap, showTasks, showGags) toggle: a press
    # shows them and the next press hides them, instead of showing them while held.
    toggle_hud: bool = False
    # The hints overlay (M11): controller buttons drawn on TTR's buttons.
    hints: bool = True
    hints_walking_bar: bool = True
    hints_scale: float = 1.0
    # The controller to use, by name ("": the first one plugged in).
    controller: str = ""
    # Which controller's button pictures the hints show: "auto" (the one in use) or a family.
    button_pictures: str = "auto"
    # Two toons (M13): the controller plays a chosen TTR window in the background. Only the
    # mode is kept; the window is picked in the module's window each session.
    two_toons: bool = False
    # Closing the module's window keeps it running in the notification area (the user: on by default).
    close_to_tray: bool = True
    # Rumble on damage, from laff read through TTR's Local API (companion app support).
    rumble: bool = True
    # Fishing (M14): "move" (the stick moves the aim) or "stick" (the stick is the aim).
    fishing_cast: str = "move"
    timing: Timing = field(default_factory=Timing)


def to_json(config: Config) -> dict:
    return {
        "_help": HELP,
        "bindings": {
            "press": config.bindings.press,
            "hold": config.bindings.hold,
            **{key: {"press": getattr(config, key).press, "hold": getattr(config, key).hold}
               for key, *_ in SCREEN_TABLES},
        },
        "auto_sprint": config.auto_sprint,
        "hide_cursor": config.hide_cursor,
        "toggle_hud": config.toggle_hud,
        "hints": config.hints,
        "hints_walking_bar": config.hints_walking_bar,
        "hints_scale": config.hints_scale,
        "controller": config.controller,
        "button_pictures": config.button_pictures,
        "two_toons": config.two_toons,
        "close_to_tray": config.close_to_tray,
        "rumble": config.rumble,
        "fishing_cast": config.fishing_cast,
        "movement": asdict(config.movement),
        "timing": asdict(config.timing),
    }


def _merge_bindings(defaults: dict[str, str], user: dict, warnings: list[str], table: str) -> dict[str, str]:
    merged = dict(defaults)
    for button, action in user.items():
        button = OLD_BUTTON_NAMES.get(button, button)
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
    tables = {}
    for key, *_ in SCREEN_TABLES:
        table, default = bindings.get(key, {}), getattr(defaults, key)
        tables[key] = Bindings(
            press=_merge_bindings(default.press, table.get("press", {}), warnings, f"{key}.press"),
            hold=_merge_bindings(default.hold, table.get("hold", {}), warnings, f"{key}.hold"))
    config = Config(
        bindings=Bindings(
            press=_merge_bindings(defaults.bindings.press, bindings.get("press", {}), warnings, "press"),
            hold=_merge_bindings(defaults.bindings.hold, bindings.get("hold", {}), warnings, "hold"),
        ),
        **tables,
        movement=_merge_numbers(defaults.movement, data.get("movement", {}), warnings, "movement"),
        timing=_merge_numbers(defaults.timing, data.get("timing", {}), warnings, "timing"),
    )
    scale = data.get("hints_scale", defaults.hints_scale)
    if isinstance(scale, (int, float)) and not isinstance(scale, bool) and 0.25 <= scale <= 4:
        config = replace(config, hints_scale=float(scale))
    else:
        warnings.append(f"hints_scale: must be a number from 0.25 to 4 (using {defaults.hints_scale})")
    controller = data.get("controller", defaults.controller)
    if isinstance(controller, str):
        config = replace(config, controller=controller)
    else:
        warnings.append('controller: must be a controller name, or "" for the first one')
    pictures = data.get("button_pictures", defaults.button_pictures)
    if pictures in BUTTON_PICTURES:
        config = replace(config, button_pictures=pictures)
    else:
        warnings.append(f'button_pictures: must be one of {", ".join(BUTTON_PICTURES)} '
                        f'(using "{defaults.button_pictures}")')
    cast = data.get("fishing_cast", defaults.fishing_cast)
    if cast in ("move", "stick"):
        config = replace(config, fishing_cast=cast)
    else:
        warnings.append(f'fishing_cast: must be "move" or "stick" (using "{defaults.fishing_cast}")')
    for name in ("auto_sprint", "hide_cursor", "toggle_hud", "hints", "hints_walking_bar", "two_toons",
                 "close_to_tray", "rumble"):
        value = data.get(name, getattr(defaults, name))
        if isinstance(value, bool):
            config = replace(config, **{name: value})
        else:
            warnings.append(f"{name}: must be true or false (using {str(getattr(defaults, name)).lower()})")
    return config, warnings


def binding_tables(config: Config) -> dict[str, Bindings]:
    """Every remappable table by its key: "overworld" (walking around), then SCREEN_TABLES'."""
    return {"overworld": config.bindings, **{key: getattr(config, key) for key, *_ in SCREEN_TABLES}}


REPLACE_TRIES = 10  # Windows refuses to swap a file in while another process is reading it


def write_json(path: Path, data) -> None:
    """Write JSON so nobody reading the file (the module, the settings window, the
    module's window: three processes) ever sees half of it: into a file beside it, then
    swapped in. Raises OSError if it can't."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    for attempt in range(REPLACE_TRIES):
        try:
            os.replace(temp, path)
            return
        except PermissionError:
            if attempt == REPLACE_TRIES - 1:
                raise
            time.sleep(0.02)


def back_up(path: Path) -> None:
    """Copy config.json to config.backup.json (before a session first rewrites it)."""
    if path.exists():
        shutil.copyfile(path, path.with_name(BACKUP_NAME))


def read(path: Path) -> tuple[dict | None, str | None]:
    """The file's JSON object, or None and what's wrong with it."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"couldn't read {path.name} ({e})"
    if not isinstance(data, dict):
        return None, f"{path.name} should contain a JSON object"
    return data, None


def load(path: Path = CONFIG_FILE) -> tuple[Config, list[str]]:
    """Load the config, creating it with defaults if it doesn't exist yet."""
    if not path.exists():
        write_json(path, to_json(Config()))
        return Config(), []
    data, problem = read(path)
    if problem is not None:
        # Don't overwrite a file the user is in the middle of editing.
        return Config(), [f"{problem}; using defaults"]
    return parse(data)


def unknown_actions(config: Config, ttr_controls) -> list[str]:
    """Bindings whose action is neither a special action nor a TTR control."""
    problems = []
    for table, bindings in (("press", config.bindings.press), ("hold", config.bindings.hold)):
        for button, action in bindings.items():
            if action not in SPECIAL_ACTIONS and action not in ttr_controls:
                problems.append(f"bindings.{table}.{button}: unknown action {action!r}")
    for section, actions, _, label in SCREEN_TABLES:
        bindings = getattr(config, section)
        for table, table_bindings in (("press", bindings.press), ("hold", bindings.hold)):
            for button, action in table_bindings.items():
                if action not in actions:
                    problems.append(f"bindings.{section}.{table}.{button}: unknown {label} action {action!r}")
    return problems


class ConfigWatcher:
    """Reloads config.json when it changes on disk."""

    def __init__(self, path: Path = CONFIG_FILE):
        self.path = path
        self.config, self.warnings = load(path)
        self._mtime = self._stat()
        self._backed_up = False  # config.backup.json taken before this run's first save

    def _stat(self) -> float | None:
        try:
            return self.path.stat().st_mtime
        except OSError:
            return None

    def save_auto_sprint(self, on: bool) -> None:
        """Remember auto-sprint in the file, keeping everything else as the user wrote it.
        Not reported as a change by check(), since the running module already has it."""
        self.save_value("auto_sprint", on)

    def save_value(self, key: str, value) -> None:
        """Remember one top-level setting the module changed itself (auto-sprint from LS,
        the fishing cast), the same way."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        data[key] = value
        try:
            if not self._backed_up:
                back_up(self.path)
                self._backed_up = True
            write_json(self.path, data)
        except OSError:
            return
        self.config = replace(self.config, **{key: value})
        self._mtime = self._stat()

    def check(self) -> Config | None:
        """Return the new config if the file changed since the last check, else None.
        A file that can't be read (a typo mid-edit) keeps the settings the module had,
        with a warning, instead of falling back to the defaults. A deleted file starts
        over from the defaults."""
        mtime = self._stat()
        if mtime == self._mtime:
            return None
        self._mtime = mtime
        if not self.path.exists():
            self.config, self.warnings = load(self.path)
        else:
            data, problem = read(self.path)
            if problem is None:
                self.config, self.warnings = parse(data)
            else:
                self.warnings = [f"{problem}; keeping the settings from before until it's fixed"]
        self._mtime = self._stat()
        return self.config
