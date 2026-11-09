"""What the settings window (M12) shows and changes, without any Qt: the remappable
tables, friendly names for buttons and actions, moving a binding from one button to
another (swapping on a clash), and writing changes into config.json.

Writing keeps the user's file: only the keys a change touches are rewritten, a table is
written as its differences from the defaults (null unbinds a default button), and the
file is backed up to config.backup.json before the first write of a session.
"""

import json
import shutil
from dataclasses import dataclass, replace
from pathlib import Path

from .battle import BATTLE_ACTIONS
from .bindings import Bindings
from .book import BOOK_ACTIONS
from .config import CONFIG_FILE, Config, parse, to_json
from .friends import FRIENDS_ACTIONS
from .mapper import SPECIAL_ACTIONS
from .npc import NPC_ACTIONS
from .shop import SHOP_ACTIONS
from .speedchat import SPEEDCHAT_ACTIONS
from .ttr_settings import DEFAULT_CONTROLS


@dataclass(frozen=True)
class Table:
    key: str  # "overworld", "battle", ...: the Config field is `field`
    title: str  # the tab
    field: str  # the Config attribute
    note: str  # under the tabs
    actions: dict[str, str]  # action -> label, in menu order
    buttons: tuple[str, ...]  # the rows


_FACE = ("a", "b", "x", "y", "lb", "rb", "lt", "rt", "view", "start", "ls", "rs",
         "dpad_up", "dpad_down", "dpad_left", "dpad_right", "rs_up", "rs_down", "rs_left", "rs_right")
_LEFT_STICK = ("ls_up", "ls_down", "ls_left", "ls_right")

BUTTON_LABELS = {
    "a": "A", "b": "B", "x": "X", "y": "Y", "lb": "LB", "rb": "RB", "lt": "LT", "rt": "RT",
    "view": "View", "start": "Start", "ls": "Left stick click", "rs": "Right stick click",
    "dpad_up": "D-pad up", "dpad_down": "D-pad down", "dpad_left": "D-pad left", "dpad_right": "D-pad right",
    "ls_up": "Left stick up", "ls_down": "Left stick down", "ls_left": "Left stick left", "ls_right": "Left stick right",
    "rs_up": "Right stick up", "rs_down": "Right stick down", "rs_left": "Right stick left",
    "rs_right": "Right stick right", "guide": "Xbox button",
}

# The hint sprite (hint_draw) for each button.
BUTTON_SPRITES = {
    "a": "A", "b": "B", "x": "X", "y": "Y", "lb": "LB", "rb": "RB", "lt": "LT", "rt": "RT",
    "view": "VIEW", "start": "START", "ls": "LS", "rs": "RS",
    "dpad_up": "DU", "dpad_down": "DD", "dpad_left": "DL", "dpad_right": "DR",
    "ls_up": "L:u", "ls_down": "L:d", "ls_left": "L:l", "ls_right": "L:r",
    "rs_up": "R:u", "rs_down": "R:d", "rs_left": "R:l", "rs_right": "R:r",
}

_MOVE = {"up": "Move up", "down": "Move down", "left": "Move left", "right": "Move right"}

WALKING_ACTIONS = {
    "jump": "Jump", "back": "Back / close", "showGags": "Gags", "showTasks": "Tasks", "showMap": "Map",
    "friendsList": "Friends list", "unite": "Unite (Toon-Up)", "mail": "Clarabelle’s mail",
    "sillyMeter": "Silly Meter", "stickerBook": "Shticker book", "options": "TTR Options",
    "speedchat": "SpeedChat", "sprint": "Sprint", "cameraNext": "Next camera", "cameraPrev": "Previous camera",
    "lookUp": "Look up", "lookDown": "Look down", "walk": "Walk slowly", "chat": "Type a chat message",
    "performAction": "Action (throw a pie)", "exitActivity": "Exit an activity", "screenshot": "TTR screenshot",
    "forward": "Walk forward", "reverse": "Walk back", "left": "Turn left", "right": "Turn right",
}

TABLES = (
    Table("overworld", "Walking", "bindings", "While walking around, with nothing open.", WALKING_ACTIONS,
          _FACE),
    Table("battle", "Battle", "battle", "While a battle panel shows. Buttons not set here keep their walking action.",
          {**_MOVE, "select": "Select", "back": "Back", "run": "Run", "trunk": "Trunk (SOS cards)", "pass": "Pass",
           "teammates": "Teammates", "sos_filter": "SOS filter", "sos_scroll_up": "Scroll SOS cards up",
           "sos_scroll_down": "Scroll SOS cards down"}, _FACE + _LEFT_STICK),
    Table("shop", "Gag Shop", "shop", "In the gag shop and the trolley’s gag picker.",
          {**_MOVE, "select": "Buy one / select", "buy_max": "Buy max", "delete_mode": "Delete mode",
           "save_preset": "Save preset", "load_preset": "Load preset", "back": "Back / done",
           "play_again": "Play again (trolley)"}, _FACE + _LEFT_STICK),
    Table("npc", "NPC chat", "npc", "Talking to an NPC and choosing a task.",
          {"up": "Move up", "down": "Move down", "select": "Select / next", "back": "Back"}, _FACE + _LEFT_STICK),
    Table("speedchat", "SpeedChat", "speedchat", "While the SpeedChat menu is open. The left stick still walks.",
          {**_MOVE, "select": "Select", "back": "Back"}, _FACE),
    Table("friends", "Friends", "friends", "While the friends list or a toon’s panel is open. The left stick still walks.",
          {**_MOVE, "select": "Select", "back": "Back", "goTo": "Go To", "whisper": "Whisper",
           "invite": "Invite to a boarding group"}, _FACE),
    Table("book", "Book", "book", "While the shticker book is open.",
          {"prevPage": "Previous page", "nextPage": "Next page", "prevTab": "Previous tab", "nextTab": "Next tab",
           "close": "Close the book", "select": "Select", **_MOVE, "goHome": "Go home (Map page)",
           "pageAction": "Page action (trash, back to playground)", "filter": "Filter",
           "stickUp": "Stick up (scroll; Bossbot)", "stickDown": "Stick down (scroll; Sellbot)",
           "stickLeft": "Stick left (Lawbot; turn kart)", "stickRight": "Stick right (Cashbot; next month)"},
          _FACE + _LEFT_STICK),
)
TABLE_BY_KEY = {t.key: t for t in TABLES}

# Descriptions for the action menus' tooltips.
ACTION_HELP = {
    "overworld": SPECIAL_ACTIONS, "battle": BATTLE_ACTIONS, "shop": SHOP_ACTIONS, "npc": NPC_ACTIONS,
    "speedchat": SPEEDCHAT_ACTIONS, "friends": FRIENDS_ACTIONS, "book": BOOK_ACTIONS,
}


def action_label(table: Table, action: str | None) -> str:
    if not action:
        return "Not set"
    return table.actions.get(action, action)


def action_choices(table: Table, current: str | None = None) -> list[tuple[str, str]]:
    """(action, label) for a menu: the table's actions, plus an unknown current one."""
    out = list(table.actions.items())
    if table.key == "overworld":
        out += [(c, c) for c in DEFAULT_CONTROLS if c not in table.actions]
    if current and current not in dict(out):
        out.append((current, current))
    return out


def bindings_of(config: Config, table: Table) -> Bindings:
    return getattr(config, table.field)


def move(b: Bindings, source: str, target: str) -> tuple[Bindings, bool]:
    """Move what `source` does (press and hold) to `target`. What `target` did goes to
    `source` (a swap); the bool says whether it did anything (a clash)."""
    press, hold = dict(b.press), dict(b.hold)
    clash = target in press or target in hold
    for table in (press, hold):
        s, t = table.pop(source, None), table.pop(target, None)
        if s is not None:
            table[target] = s
        if t is not None:
            table[source] = t
    return Bindings(press=press, hold=hold), clash


def clear(b: Bindings, button: str) -> Bindings:
    return Bindings(press={k: v for k, v in b.press.items() if k != button},
                    hold={k: v for k, v in b.hold.items() if k != button})


def with_action(b: Bindings, button: str, action: str | None, hold: bool) -> Bindings:
    table = dict(b.hold if hold else b.press)
    if action:
        table[button] = action
    else:
        table.pop(button, None)
    return Bindings(press=b.press, hold=table) if hold else Bindings(press=table, hold=b.hold)


def _diff(new: dict[str, str], default: dict[str, str]) -> dict[str, str | None]:
    out: dict[str, str | None] = {b: a for b, a in new.items() if default.get(b) != a}
    out.update({b: None for b in default if b not in new})
    return out


class SettingsStore:
    """config.json as the settings window sees it: the parsed Config, and the raw JSON it
    edits in place."""

    def __init__(self, path: Path = CONFIG_FILE):
        self.path = path
        self.backup = path.with_name("config.backup.json")
        self._backed_up = False
        self.error: str | None = None
        self.raw: dict = {}
        self.reload()

    def reload(self) -> None:
        self.error = None
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                data, self.error = {}, f"{self.path.name} couldn't be read ({e}). Fix or delete it to change settings here."
            if not isinstance(data, dict):
                data, self.error = {}, f"{self.path.name} should hold a JSON object."
        else:
            data = to_json(Config())
        self.raw = data
        self.config, self.warnings = parse(data)

    @property
    def writable(self) -> bool:
        return self.error is None

    def _write(self) -> None:
        if not self.writable:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self._backed_up and self.path.exists():
            shutil.copyfile(self.path, self.backup)
            self._backed_up = True
        self.raw.setdefault("_help", to_json(Config())["_help"])
        self.path.write_text(json.dumps(self.raw, indent=2) + "\n", encoding="utf-8")
        self.config, self.warnings = parse(self.raw)

    def set(self, key: str, value, section: str | None = None) -> None:
        """A top-level setting, or one inside "movement" / "timing"."""
        if section:
            self.raw.setdefault(section, {})[key] = value
            self.config = replace(self.config, **{section: replace(getattr(self.config, section), **{key: value})})
        else:
            self.raw[key] = value
            self.config = replace(self.config, **{key: value})
        self._write()

    def set_bindings(self, table: Table, b: Bindings) -> None:
        default = getattr(Config(), table.field)
        press, hold = _diff(b.press, default.press), _diff(b.hold, default.hold)
        section = self.raw.setdefault("bindings", {})
        if table.key == "overworld":
            section["press"], section["hold"] = press, hold
        else:
            section[table.key] = {"press": press, "hold": hold}
        self._write()

    def restore_table(self, table: Table) -> None:
        self.set_bindings(table, getattr(Config(), table.field))

    def restore_everything(self) -> None:
        self.raw = to_json(Config())
        self._write()
