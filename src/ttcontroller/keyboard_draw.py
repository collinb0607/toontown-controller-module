"""Draws the on-screen keyboards (name_keyboard.NameKeyboard and CodeKeyboard) as a BGRA
image for an overlay window. The key art comes from input_sprites/all_input.png, like
tools/osk_sample.py (the mock-up the user picked, Nov 11)."""

from pathlib import Path

import pygame

from .hint_draw import Sprites, to_bgra
from .name_keyboard import _OFFSETS, PANEL_SIZE, ROWS, _Keys

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
        self._pg = pygame
        if not pygame.font.get_init():
            pygame.font.init()
        self._buttons = None
        if buttons_path is not None:
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
