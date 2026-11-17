"""The on-screen keyboards (M14): a toon's name in Make-a-Toon's Type-A-Name, and a code
on the shticker book's Options & Codes page.

Both are three rows of keys in QWERTY's shape (10, 9 and 7 keys, A under Q and Z under
S). The name keyboard is only the letters: the first letter of each word is a capital and
the rest are lowercase, and the keys show which comes next, so what's typed is always
what the keyboard showed. The code keyboard switches between lowercase, capitals and
symbols (numbers on the top row) with LS.

`NameKeyboard` and `CodeKeyboard` are the state (no drawing): the hovered key and what it
types. keyboard_draw.py draws one.
"""

from dataclasses import dataclass, field

ROWS = ("QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM")
# The code keyboard's symbols, in the same shape.
SYMBOL_ROWS = ("1234567890", "-_.,!?@#&", "'+=*/:;")
# Each row's left edge, in key widths from the top row's: A under Q, Z under S, so up
# and down go straight between the rows (the user, Nov 11).
_OFFSETS = (0, 0, 1)

# Where the name panel goes, in units of the window's shorter side from TTR's Submit
# button (measured at 1920x1009: under the name box, over the text and buttons below it).
PANEL_DX = 3 / 1009  # its middle, right of Submit's
PANEL_TOP_DY = -253 / 1009  # its top, above Submit's middle
PANEL_SIZE = (675 / 1009, 370 / 1009)

HINTS = (("A", "Select"), ("X", "Delete"), ("Y", "Space"), ("START", "Submit"), ("B", "Clear"))
# Backspaces sent to clear TTR's box: more than a name or a code can hold.
CLEAR_PRESSES = 40

# The code keyboard's modes, in the order LS steps through them, and how the LS hint
# names the next one.
CODE_MODES = ("lower", "upper", "symbols")
_MODE_LABELS = {"lower": "abc", "upper": "ABC", "symbols": "#+="}


@dataclass
class _Keys:
    """Three rows of keys and the one hovered."""
    row: int = 0
    col: int = 0

    @property
    def keys(self) -> tuple[str, str, str]:
        """Each row's keys, as they show and type now."""
        raise NotImplementedError

    @property
    def letter(self) -> str:
        """The hovered key, as it would be typed now."""
        return self.keys[self.row][self.col]

    def move(self, direction: str) -> bool:
        """Moves the hover; False at an edge. Up and down go to the key straight above or
        below (the last one of a shorter row)."""
        keys = self.keys
        if direction in ("left", "right"):
            col = self.col + (1 if direction == "right" else -1)
            if not 0 <= col < len(keys[self.row]):
                return False
            self.col = col
            return True
        row = self.row + (1 if direction == "down" else -1)
        if not 0 <= row < len(keys):
            return False
        x = _OFFSETS[self.row] + self.col
        self.col = min(max(int(x - _OFFSETS[row] + 0.5), 0), len(keys[row]) - 1)
        self.row = row
        return True


@dataclass
class NameKeyboard(_Keys):
    text: str = ""  # typed with this keyboard
    # TTR's box already had text before `text` (typed some other way, or before a
    # pause): taken as the middle of a word, so the next letter is lowercase.
    prefix: bool = False
    hints: tuple = HINTS

    @property
    def capital(self) -> bool:
        """The next letter starts a word: the name's first, or the first after a space."""
        return self.text.endswith(" ") if self.text else not self.prefix

    @property
    def empty(self) -> bool:
        return not self.text and not self.prefix

    @property
    def keys(self) -> tuple[str, str, str]:
        return ROWS if self.capital else tuple(r.lower() for r in ROWS)

    def type_letter(self) -> str:
        letter = self.letter
        self.text += letter
        return letter

    def space(self) -> bool:
        """A space between words: not at the start or after another space."""
        if self.capital:
            return False
        self.text += " "
        return True

    def delete(self) -> bool:
        """Into the earlier text, each delete still sends a backspace (the keyboard can't
        see where it ends; the box reading empty starts it over)."""
        if self.text:
            self.text = self.text[:-1]
            return True
        return self.prefix

    def clear(self) -> None:
        self.text, self.prefix = "", False


@dataclass
class CodeKeyboard(_Keys):
    mode: str = "lower"
    # (button sprite, words) for its hint bar: from the book's buttons (remappable).
    hint_buttons: tuple = field(default_factory=lambda: (
        ("A", "Select"), ("X", "Delete"), ("Y", "Space"), ("LS", None), ("START", "Submit"), ("B", "Clear")))

    @property
    def keys(self) -> tuple[str, str, str]:
        if self.mode == "symbols":
            return SYMBOL_ROWS
        return ROWS if self.mode == "upper" else tuple(r.lower() for r in ROWS)

    @property
    def next_mode(self) -> str:
        return CODE_MODES[(CODE_MODES.index(self.mode) + 1) % len(CODE_MODES)]

    def switch(self) -> None:
        """LS: lowercase, then capitals, then symbols, then lowercase again."""
        self.mode = self.next_mode

    @property
    def hints(self) -> tuple:
        # The mode switch's hint names the mode it switches to.
        return tuple((b, _MODE_LABELS[self.next_mode] if words is None else words) for b, words in self.hint_buttons)

