"""Translate TTR key names (Panda3D button names) into Windows virtual-key codes.

TTR stores keybinds in settings.json using Panda3D names such as "w", "space",
"page_down" or "shift-escape" (a modifier combo).
"""

from dataclasses import dataclass

MODIFIERS = ("shift", "control", "alt")

_VK = {
    "space": 0x20, "enter": 0x0D, "escape": 0x1B, "tab": 0x09, "backspace": 0x08,
    "shift": 0x10, "lshift": 0xA0, "rshift": 0xA1,
    "control": 0x11, "lcontrol": 0xA2, "rcontrol": 0xA3,
    "alt": 0x12, "lalt": 0xA4, "ralt": 0xA5,
    "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "page_up": 0x21, "page_down": 0x22,
    "arrow_left": 0x25, "arrow_up": 0x26, "arrow_right": 0x27, "arrow_down": 0x28,
    "caps_lock": 0x14, "num_lock": 0x90, "scroll_lock": 0x91,
    "print_screen": 0x2C, "pause": 0x13,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, "\\": 0xDC,
    ";": 0xBA, "'": 0xDE, ",": 0xBC, ".": 0xBE, "/": 0xBF,
}
_VK.update({f"f{i}": 0x6F + i for i in range(1, 25)})
_VK.update({chr(c): ord(chr(c).upper()) for c in range(ord("a"), ord("z") + 1)})
_VK.update({str(d): ord(str(d)) for d in range(10)})

# Keys that need KEYEVENTF_EXTENDEDKEY when sent by scan code.
_EXTENDED = {
    "insert", "delete", "home", "end", "page_up", "page_down",
    "arrow_left", "arrow_up", "arrow_right", "arrow_down",
    "rcontrol", "ralt", "num_lock", "print_screen",
}


@dataclass(frozen=True)
class KeyCombo:
    modifiers: tuple[str, ...]
    key: str

    @property
    def names(self) -> tuple[str, ...]:
        return (*self.modifiers, self.key)


def parse_combo(text: str) -> KeyCombo:
    """Parse a TTR keybind like "shift-escape" or "-" into a KeyCombo."""
    parts = text.strip().lower().split("-")
    modifiers = []
    while len(parts) > 1 and parts[0] in MODIFIERS:
        modifiers.append(parts.pop(0))
    # Rejoining handles the "-" key itself: "-" and "shift--" both leave ["", ""].
    key = "-".join(parts)
    if key not in _VK:
        raise ValueError(f"Unknown key name: {text!r}")
    return KeyCombo(tuple(modifiers), key)


def vk_code(name: str) -> int:
    return _VK[name]


def is_extended(name: str) -> bool:
    return name in _EXTENDED


def is_modifier(name: str) -> bool:
    return name.lstrip("lr") in MODIFIERS
