"""The on-screen keyboards (M14): a toon's name in Make-a-Toon's Type-A-Name, and a code
on the shticker book's Options & Codes page.

Both are three rows of keys in QWERTY's shape (10, 9 and 7 keys, A under Q and Z under
S). The name keyboard is only the letters: the first letter of each word is a capital and
the rest are lowercase, and the keys show which comes next, so what's typed is always
what the keyboard showed. The code keyboard switches between lowercase, capitals and
symbols (numbers on the top row) with LS.

`NameKeyboard` and `CodeKeyboard` are the state (no drawing): the hovered key and what it
types. `KeyboardDrawer` draws one as a BGRA image for an overlay window. The key art comes
from input_sprites/all_input.png, like tools/osk_sample.py (the mock-up the user picked,
Nov 11).
"""

from dataclasses import dataclass, field
from pathlib import Path

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


# ---- Drawing ---------------------------------------------------------------------------

SHEET_NAME = "all_input.png"
_FONT_PATHS = ("C:/Windows/Fonts/ARLRDBD.TTF", "C:/Windows/Fonts/arialbd.ttf")
_KEY_W, _KEY_H, _PITCH = 74, 72, 78  # a key on the sheet, and the sheet's grid step
_FACE, _GLYPH = 89, 205  # the sheet's key face and label grays
_BLANK_KEY = (2 + _PITCH * 2, 582, _KEY_W, _KEY_H)  # "-": erased to make a blank key
_PANEL_FILL = (20, 24, 34, 255)
_PANEL_EDGE = (90, 98, 120, 255)
_HINT_TEXT = (225, 228, 235)


def find_sheet(extra: Path | None = None) -> Path | None:
    here = Path(__file__).resolve()
    for p in ([extra / SHEET_NAME] if extra else []) + [here.parents[2] / "input_sprites" / SHEET_NAME,
                                                        here.parent / SHEET_NAME]:
        if p.exists():
            return p
    return None


class KeyboardDrawer:
    """Draws the keyboard panel at a window's size. pygame must be initialised (the
    hints overlay's Drawer does the same)."""

    def __init__(self, sheet_path: Path, buttons_path: Path | None = None):
        """sheet_path: the key art (all_input.png), used only for the keys themselves.
        buttons_path: the Xbox spritesheet (xbox-spritesheet.png), where every control
        hint's button comes from, as for the rest of the module's hints (the user, Nov 11);
        without it the hint bar writes the buttons' names. `use_buttons` switches to
        another controller's art (the hints overlay's)."""
        import pygame
        self._pg = pygame
        if not pygame.font.get_init():
            pygame.font.init()
        self._buttons = None
        if buttons_path is not None:
            from .hint_draw import Sprites
            self._buttons = Sprites(buttons_path)
        sheet = pygame.image.load(str(sheet_path))
        self._blank = _erase_label(pygame, sheet.subsurface(pygame.Rect(_BLANK_KEY)).copy())
        self._font_path = next((p for p in _FONT_PATHS if Path(p).exists()), None)
        self._fonts: dict[int, object] = {}
        self._keys: dict[tuple, object] = {}  # (letter, hovered, key px) -> scaled key

    def use_buttons(self, sprites) -> None:
        """Draw the hint bar's buttons from these sprites (hint_draw.Sprites) from now on."""
        self._buttons = sprites

    @property
    def buttons_family(self) -> str | None:
        """Whose button art the hint bar shows (part of what the panel looks like)."""
        return getattr(self._buttons, "family", None)

    def _font(self, px: int):
        font = self._fonts.get(px)
        if font is None:
            font = self._fonts[px] = self._pg.font.Font(self._font_path, px)
        return font

    def _key(self, letter: str, hovered: bool, key_px: int):
        cached = self._keys.get((letter, hovered, key_px))
        if cached is not None:
            return cached
        pg = self._pg
        key = self._blank.copy()
        label = self._font(40).render(letter, True, (_GLYPH, _GLYPH, _GLYPH))
        key.blit(label, label.get_rect(center=key.get_rect().move(0, -3).center))
        size = (key_px, round(_KEY_H * key_px / _KEY_W))
        key = pg.transform.smoothscale(key, size)
        if hovered:  # the hovered key lifts: brighter and a little larger
            key = pg.transform.smoothscale_by(key, 1.12)
            key.fill((55, 55, 55, 0), special_flags=pg.BLEND_RGBA_ADD)
        self._keys[(letter, hovered, key_px)] = key
        return key

    def surface(self, keyboard: _Keys, unit: int, size: tuple[float, float] = PANEL_SIZE):
        """The panel as a pygame Surface, `size` (in units) at this unit. The keys are as
        big as the name panel's, or smaller to fit a smaller panel (the book's)."""
        pg = self._pg
        width, height = round(size[0] * unit), round(size[1] * unit)
        rows = keyboard.keys
        pad = min(0.022 * unit, 0.06 * min(width, height))
        columns = len(ROWS[0])
        key_px = min(0.058 * unit, (width - 2 * pad) / (columns * 1.085))
        while True:
            gap = key_px * 0.085
            key_h = _KEY_H * key_px / _KEY_W
            row_h = key_h + gap
            hint_h = min(0.05 * unit, key_px * 0.86)
            lines, hint_gap = self._hint_lines(keyboard.hints, hint_h, width - 2 * pad)
            content_h = len(rows) * row_h + pad * 0.3 + len(lines) * hint_h
            if content_h <= height - 1.2 * pad or key_px < 10:
                break
            key_px *= 0.95
        key_px = max(8, round(key_px))
        keys_w = columns * key_px + (columns - 1) * gap

        panel = pg.Surface((width, height), pg.SRCALPHA)
        radius = max(2, round(pad))
        pg.draw.rect(panel, _PANEL_FILL, panel.get_rect(), border_radius=radius)
        pg.draw.rect(panel, _PANEL_EDGE, panel.get_rect(), max(1, round(unit / 500)), border_radius=radius)

        y = (height - content_h) / 2
        left = (width - keys_w) / 2
        lifted = None
        for r, row in enumerate(rows):
            x = left + _OFFSETS[r] * (key_px + gap)
            for c, shown in enumerate(row):
                hovered = (r, c) == (keyboard.row, keyboard.col)
                img = self._key(shown, hovered, key_px)
                rect = pg.Rect(round(x), round(y), key_px, round(key_h))
                if hovered:
                    lifted = (img, img.get_rect(center=rect.center).move(0, -round(gap / 2)))
                else:
                    panel.blit(img, rect)
                x += key_px + gap
            y += row_h
        if lifted is not None:
            panel.blit(*lifted)  # drawn last, over its neighbours
        y += pad * 0.3
        for line, line_w in lines:
            x = (width - line_w) / 2
            cy = y + hint_h / 2
            for icon, words in line:
                panel.blit(icon, icon.get_rect(midleft=(round(x), round(cy))))
                x += icon.get_width() + 4
                panel.blit(words, words.get_rect(midleft=(round(x), round(cy))))
                x += words.get_width() + hint_gap
            y += hint_h
        return panel

    def image(self, keyboard: _Keys, unit: int, size: tuple[float, float] = PANEL_SIZE):
        from .hint_draw import to_bgra
        return to_bgra(self.surface(keyboard, unit, size))

    def _button(self, button: str, h: int):
        """A controller button's picture, h pixels tall (None if there's none)."""
        if self._buttons is None:
            return None
        try:
            return self._buttons.get(button, h)
        except KeyError:
            return None

    def _hint_lines(self, hints, hint_h: float, max_w: float):
        """The hints, wrapped onto as many centered lines as they need."""
        pg = self._pg
        font = self._font(max(6, round(hint_h * 0.55)))
        icon_h = max(4, round(hint_h * 0.85))
        gap = round(hint_h * 0.6)
        lines: list[tuple[list, float]] = [([], 0.0)]
        for button, words in hints:
            icon = self._button(button, icon_h)
            if icon is None:  # a button without a picture (the D-pad): its name
                icon = self._font(max(6, round(hint_h * 0.5))).render(button, True, _HINT_TEXT)
            text = font.render(words, True, _HINT_TEXT)
            piece = icon.get_width() + 4 + text.get_width()
            line, line_w = lines[-1]
            if line and line_w + gap + piece > max_w:
                lines.append(([], 0.0))
                line, line_w = lines[-1]
            line.append((icon, text))
            lines[-1] = (line, line_w + (gap if line_w else 0) + piece)
        return lines, gap


def _erase_label(pg, key):
    """A key with its label painted over in the face color."""
    for y in range(key.get_height()):
        for x in range(key.get_width()):
            r, g, b, a = key.get_at((x, y))
            if a and r > 110:
                key.set_at((x, y), (_FACE, _FACE, _FACE, a))
    return key
