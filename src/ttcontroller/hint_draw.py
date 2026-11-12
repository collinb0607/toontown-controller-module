"""Draws the M11 hints (hints.py) as one premultiplied BGRA image for the overlay window.

The button art is cut from a controller spritesheet (input_sprites/<family>-spritesheet.png,
published with the code): Xbox, PlayStation, Switch or Steam, the user's art. The sheets
share one grid, and a sprite is named by the Xbox button SDL reports for it ("A" is the
bottom face button: Cross on a PlayStation pad; Nintendo pads go by label, so on a Switch
"A" is its A, on the right).
The D-pad sprites with a lit direction and the sticks with arrows are built from it, as
in the hints sample kit. tools/measure_sprites.py measures a sheet's boxes.

Pressing a button bounces its badges: they shrink, overshoot a little and settle.
"""

import math
from pathlib import Path

import numpy as np
import pygame

from .hints import Badge, Bar, sprite_buttons

# The controller families with their own button art (controller.family_of says which a
# controller is). Where a sheet is looked for: the module's config folder, beside the
# code (the repo's input_sprites folder), then the package (the packaged exe).
FAMILIES = ("xbox", "playstation", "switch", "steam")
FAMILY_NAMES = {"xbox": "Xbox", "playstation": "PlayStation", "switch": "Switch", "steam": "Steam"}
SHEET_NAMES = {f: f"{f}-spritesheet.png" for f in FAMILIES}
SHEET_NAME = SHEET_NAMES["xbox"]
FONT_PATHS = ("C:/Windows/Fonts/ARLRDBD.TTF", "C:/Windows/Fonts/arialbd.ttf")

RECTS = {
    "A": (138, 642, 204, 200), "B": (432, 642, 206, 200),
    "X": (730, 642, 202, 202), "Y": (1026, 642, 206, 202),
    "LT": (754, 266, 154, 200), "RT": (1048, 266, 156, 200),
    "LB": (132, 495, 224, 124), "RB": (430, 495, 228, 124),
    "L": (132, 264, 224, 230), "R": (430, 264, 228, 230),
    "LS": (140, 858, 198, 256), "RS": (438, 858, 196, 256),
    "VIEW": (728, 890, 200, 204), "START": (1022, 890, 202, 204),
}
_DPAD_CENTERS = {"up": (247, 136), "right": (543, 136), "down": (832, 136), "left": (1125, 136)}
# The other sheets, measured with tools/measure_sprites.py (each box is where the art's
# alpha is above 40; the glow past it is left out) and checked by eye.
FAMILY_RECTS = {
    "xbox": RECTS,
    "playstation": {
        "L": (138, 261, 213, 232), "R": (430, 261, 211, 232),
        "LT": (731, 268, 200, 201), "RT": (1026, 268, 200, 199),  # L2, R2
        "LB": (130, 493, 226, 117), "RB": (427, 493, 231, 117),  # L1, R1
        "A": (142, 625, 209, 213), "B": (436, 625, 206, 212),  # Cross, Circle
        "X": (726, 624, 210, 215), "Y": (1016, 624, 210, 215),  # Square, Triangle
        "LS": (141, 847, 200, 259), "RS": (439, 847, 200, 259),  # L3, R3
        "VIEW": (783, 893, 90, 202), "START": (1078, 886, 90, 209),  # Share/Create, Options
    },
    "switch": {
        "L": (138, 261, 213, 230), "R": (430, 261, 211, 230),
        "LT": (735, 286, 192, 160), "RT": (1030, 286, 192, 160),  # ZL, ZR
        "LB": (130, 491, 226, 134), "RB": (427, 491, 231, 134),  # L, R
        # By label (SDL reports Nintendo pads that way): the sheet is laid out by position
        # (B bottom, A right, Y left, X top), so A and B swap, and X and Y.
        "A": (432, 638, 205, 199), "B": (138, 638, 205, 199),
        "X": (1026, 639, 205, 199), "Y": (728, 639, 205, 199),
        "LS": (141, 847, 200, 259), "RS": (439, 847, 200, 259),
        "VIEW": (726, 888, 205, 199), "START": (1020, 888, 205, 199),  # minus, plus
    },
    "steam": {
        "L": (138, 261, 213, 230), "R": (438, 268, 214, 223),  # R: the right trackpad
        "LT": (755, 264, 152, 194), "RT": (1050, 264, 152, 194),
        "LB": (130, 491, 226, 134), "RB": (427, 491, 231, 134),
        "A": (138, 638, 205, 199), "B": (432, 638, 205, 199),
        "X": (728, 639, 205, 199), "Y": (1026, 639, 205, 199),
        "LS": (141, 847, 200, 259), "RS": (442, 847, 188, 245),
        "VIEW": (731, 937, 194, 110), "START": (1026, 937, 194, 110),  # the back and forward arrows
    },
}
# Each sheet's four D-pads (one lit direction each): their centers and the crop around them.
DPADS = {
    "xbox": (_DPAD_CENTERS, (232, 224)),
    "playstation": ({"up": (248, 137), "right": (544, 137), "down": (833, 137), "left": (1126, 137)}, (229, 229)),
    "switch": ({"up": (247, 134), "right": (543, 134), "down": (832, 134), "left": (1125, 134)}, (235, 232)),
    "steam": ({"up": (247, 131), "right": (543, 131), "down": (832, 131), "left": (1125, 131)}, (237, 230)),
}
# Sprite shapes differ (bumpers are wide, sticks have a base), so each is scaled to look
# the same size as the face buttons.
NORM = {"L": 1.4, "R": 1.4, "LS": 1.35, "RS": 1.35, "LB": 0.85, "RB": 0.85,
        "LT": 1.1, "RT": 1.1, "VIEW": 1.05, "START": 1.05}
FAMILY_NORM = {
    "xbox": NORM,
    "playstation": {**NORM, "LT": 1.05, "RT": 1.05, "VIEW": 1.3, "START": 1.3},
    "switch": {**NORM, "LT": 0.95, "RT": 0.95, "VIEW": 1.0, "START": 1.0},
    "steam": {**NORM, "R": 1.15, "RS": 1.3, "VIEW": 0.7, "START": 0.7},
}
# How far down a stick sprite its cap's middle is (the arrows go round it): a stick has a
# base under its cap; Steam's right trackpad is just the round pad.
STICK_CAP = {"steam": {"R": 0.5}}
_LIT = {"DU": "u", "DD": "d", "DL": "l", "DR": "r", "DUD": "ud", "DLR": "lr", "D4": "udlr"}

BOUNCE_SECONDS = 0.28
_SHRINK_SECONDS = 0.10
BOUNCE_STEPS = 14  # sizes drawn per bounce (each frame of it is redrawn)
RING_STEPS = 24  # how finely a hold ring fills while its button is held
GOLD = (255, 215, 60)
BAR_FILL = (15, 25, 60, 185)


def bounce(t: float) -> float:
    """A badge's size, as a multiple of its own, t seconds after its button was pressed:
    down to 0.8, up past 1 to 1.1, then back to 1."""
    if t < 0 or t >= BOUNCE_SECONDS:
        return 1.0
    if t < _SHRINK_SECONDS:
        return 1 - 0.2 * math.sin(math.pi / 2 * t / _SHRINK_SECONDS)
    u = (t - _SHRINK_SECONDS) / (BOUNCE_SECONDS - _SHRINK_SECONDS)
    return 0.8 + 0.2 * u + 0.3 * math.sin(math.pi * u) * (1 - u) ** 0.5


def pictures_for(choice: str, detected: str | None) -> str | None:
    """The family to draw: the config's button_pictures, or with "auto" the controller's
    (None with no controller: keep what's drawn)."""
    return choice if choice in FAMILIES else detected


def find_sheet(extra: Path | None = None, family: str = "xbox") -> Path | None:
    """The family's sheet, or None when it isn't found."""
    name = SHEET_NAMES.get(family, SHEET_NAME)
    here = Path(__file__).resolve()
    for p in ([extra / name] if extra else []) + [here.parents[2] / "input_sprites" / name, here.parent / name]:
        if p.exists():
            return p
    return None


class Sprites:
    def __init__(self, sheet_path: Path, family: str = "xbox"):
        self.family = family if family in FAMILY_RECTS else "xbox"
        sheet = pygame.image.load(str(sheet_path))
        self._base = {k: sheet.subsurface(pygame.Rect(r)).copy() for k, r in FAMILY_RECTS[self.family].items()}
        centers, (cw, ch) = DPADS[self.family]
        dpad = {d: sheet.subsurface(pygame.Rect(x - cw // 2, y - ch // 2, cw, ch)).copy()
                for d, (x, y) in centers.items()}
        blank = _wedges(dpad)
        for name, arms in _LIT.items():
            self._base[name] = _lit(blank, arms)
        self._norm = FAMILY_NORM[self.family]
        self._cap = STICK_CAP.get(self.family, {})
        self._scaled: dict = {}
        self._shadows: dict = {}

    def get(self, name: str, h: float) -> pygame.Surface:
        key = (name, round(h))
        img = self._scaled.get(key)
        if img is None:
            base, _, arrows = name.partition(":")
            src = self._base[base]
            hh = max(4.0, h * self._norm.get(base, 1.0))
            w = max(1, round(src.get_width() * hh / src.get_height()))
            img = pygame.transform.smoothscale(src, (w, max(1, round(hh))))
            if arrows:
                img = _stick_arrows(img, arrows, self._cap.get(base, 0.36))
            if len(self._scaled) > 600:
                self._scaled.clear()
            self._scaled[key] = img
        return img

    def shadow(self, name: str, h: float) -> tuple[pygame.Surface, int]:
        key = (name, round(h))
        found = self._shadows.get(key)
        if found is None:
            found = _shadow(self.get(name, h))
            if len(self._shadows) > 600:
                self._shadows.clear()
            self._shadows[key] = found
        return found


def _wedges(dpad: dict) -> pygame.Surface:
    """A D-pad with no direction lit: each arm taken from the crop where it isn't lit."""
    src = {"t": dpad["down"], "b": dpad["up"], "l": dpad["right"], "r": dpad["left"]}
    w, h = src["t"].get_size()
    ys, xs = np.mgrid[0:h, 0:w]
    dx, dy = xs - w / 2, ys - h / 2
    vertical = np.abs(dy) > np.abs(dx)
    masks = {"t": vertical & (dy < 0), "b": vertical & (dy >= 0), "l": ~vertical & (dx < 0), "r": ~vertical & (dx >= 0)}
    rgb = np.zeros((w, h, 3), np.uint8)
    alpha = np.zeros((w, h), np.uint8)
    for k, m in masks.items():
        mt = m.T
        rgb[mt] = pygame.surfarray.array3d(src[k])[mt]
        alpha[mt] = pygame.surfarray.array_alpha(src[k])[mt]
    out = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.surfarray.blit_array(out, rgb)
    pygame.surfarray.pixels_alpha(out)[:] = alpha
    return out


def _lit(blank: pygame.Surface, arms: str) -> pygame.Surface:
    """The D-pad with gold arrows on the arms that do something."""
    s = blank.copy()
    w, h = s.get_size()
    cx, cy = w / 2, h / 2
    length, half = w * 0.40, w * 0.15
    dirs = {"u": (0, -1), "d": (0, 1), "l": (-1, 0), "r": (1, 0)}
    for a in arms:
        dx, dy = dirs[a]
        px, py = -dy, dx
        tip = (cx + dx * length, cy + dy * length)
        base = (cx + dx * length * 0.35, cy + dy * length * 0.35)
        pts = [tip, (base[0] + px * half, base[1] + py * half), (base[0] - px * half, base[1] - py * half)]
        pygame.draw.polygon(s, (40, 30, 0), [(x + dx * 3, y + dy * 3) for x, y in pts])
        pygame.draw.polygon(s, (255, 205, 40), pts)
    return s


def _tri(surf, cx, cy, size, ang):
    pts = [(cx + size * math.cos(ang + a), cy + size * math.sin(ang + a)) for a in (0, 2.4, -2.4)]
    pygame.draw.polygon(surf, (30, 30, 30), pts)
    pygame.draw.polygon(surf, (255, 255, 255), [(cx + (x - cx) * 0.62, cy + (y - cy) * 0.62) for x, y in pts])


def _stick_arrows(img: pygame.Surface, arrows: str, cap: float = 0.36) -> pygame.Surface:
    w, h = img.get_size()
    pad = round(h * 0.28)
    out = pygame.Surface((w + 2 * pad, h + 2 * pad), pygame.SRCALPHA)
    out.blit(img, (pad, pad))
    cx, cy = out.get_width() / 2, pad + h * cap  # round the stick's cap, not its base
    r, size = h * 0.5 + pad * 0.35, pad * 0.75
    angles = {"u": -math.pi / 2, "d": math.pi / 2, "l": math.pi, "r": 0.0}
    for c in {"ud": "ud", "lr": "lr", "4": "udlr"}.get(arrows, arrows):
        _tri(out, cx + r * math.cos(angles[c]), cy + r * math.sin(angles[c]), size, angles[c])
    return out


def _shadow(img: pygame.Surface, amount: int = 150) -> tuple[pygame.Surface, int]:
    """A soft dark halo from the sprite's shape, so it reads on busy backgrounds."""
    w, h = img.get_size()
    pad = max(4, h // 6)
    m = pygame.Surface((w + 2 * pad, h + 2 * pad), pygame.SRCALPHA)
    mask = pygame.mask.from_surface(img, 40).to_surface(setcolor=(0, 0, 0, amount), unsetcolor=(0, 0, 0, 0))
    m.blit(mask, (pad, pad))
    small = pygame.transform.smoothscale(m, (max(1, m.get_width() // 6), max(1, m.get_height() // 6)))
    return pygame.transform.smoothscale(small, m.get_size()), pad


class Drawer:
    """Lays out and draws hints for a window, and remembers button presses for bounces."""

    def __init__(self, sheet_path: Path, family: str = "xbox"):
        if not pygame.font.get_init():
            pygame.font.init()
        self.sprites = Sprites(sheet_path, family)
        self._fonts: dict[int, pygame.font.Font] = {}
        self._labels: dict = {}
        self._pressed_at: dict[str, float] = {}
        self._held: frozenset[str] = frozenset()
        self._pieces: dict = {}
        # How long a hold takes (the config's timing.hold_seconds): a hold ring fills in this.
        self.hold_seconds = 0.5

    @property
    def family(self) -> str:
        return self.sprites.family

    def use(self, family: str, extra: Path | None = None) -> bool:
        """Draw `family`'s buttons from now on. If its sheet is missing or broken, the art
        stays as it is. True if the art changed."""
        if family == self.family:
            return False
        sheet = find_sheet(extra, family)
        if sheet is None:
            return False
        try:
            self.sprites = Sprites(sheet, family)
        except (pygame.error, ValueError, OSError):
            return False
        self._pieces.clear()
        return True

    # ---- presses --------------------------------------------------------------------
    def press(self, buttons: frozenset[str], now: float) -> None:
        """Call each frame with the buttons held; new presses start bounces."""
        for b in buttons - self._held:
            self._pressed_at[b] = now
        self._held = buttons

    def _bounce_step(self, sprite: str, now: float) -> int:
        """Which step of a bounce the sprite is on (0 = resting)."""
        latest = max((self._pressed_at.get(b, -1e9) for b in sprite_buttons(sprite)), default=-1e9)
        t = now - latest
        if t >= BOUNCE_SECONDS or t < 0:
            return 0
        return 1 + int(t / BOUNCE_SECONDS * BOUNCE_STEPS)

    def _ring_step(self, sprite: str, now: float) -> int:
        """How full a hold ring is (0 = not held, RING_STEPS = the hold has fired): it fills
        from when its button went down, while it stays down."""
        held = [self._pressed_at.get(b, now) for b in sprite_buttons(sprite) if b in self._held]
        if not held:
            return 0
        t = now - max(held)
        return min(RING_STEPS, 1 + int(max(0.0, t) / max(self.hold_seconds, 1e-3) * RING_STEPS))

    # ---- drawing --------------------------------------------------------------------
    def _font(self, px: int) -> pygame.font.Font:
        f = self._fonts.get(px)
        if f is None:
            path = next((p for p in FONT_PATHS if Path(p).exists()), None)
            f = self._fonts[px] = pygame.font.Font(path, px)
        return f

    def _label(self, text: str, px: int) -> pygame.Surface:
        key = (text, px)
        out = self._labels.get(key)
        if out is None:
            f = self._font(px)
            fg = f.render(text, True, (255, 255, 255))
            outline = f.render(text, True, (20, 20, 20))
            out = pygame.Surface((fg.get_width() + 4, fg.get_height() + 4), pygame.SRCALPHA)
            for dx in (-2, -1, 0, 1, 2):
                for dy in (-2, -1, 0, 1, 2):
                    if dx or dy:
                        out.blit(outline, (2 + dx, 2 + dy))
            out.blit(fg, (2, 2))
            self._labels[key] = out
        return out

    def _bar_parts(self, bar: Bar, unit: int, scale: float):
        h = bar.size * unit * scale
        gap, inner = round(h * 0.15), round(h * 0.7)
        parts = []
        for name, text in bar.items:
            icon = self.sprites.get(name, h)
            label = self._label(text, max(8, round(h * 0.5)))
            parts.append((name, icon, label))
        total = sum(i.get_width() + gap + l.get_width() for _, i, l in parts) + inner * (len(parts) - 1)
        return h, gap, inner, parts, total

    def pieces(self, hints, width: int, height: int, now: float, scale: float = 1.0) -> list:
        """Each hint drawn on its own, for a width x height window: (key, premultiplied BGRA
        image, left, top) in window coordinates. Each is a small window on screen, so a
        bounce redraws just its badge. key changes whenever the image would."""
        out = []
        for hint in hints:
            step = self._bounce_step(hint.sprite, now) if isinstance(hint, Badge) else 0
            ring = self._ring_step(hint.sprite, now) if isinstance(hint, Badge) and hint.hold else 0
            key = (hint, width, height, scale, self.family, step, ring)
            found = self._pieces.get(key)
            if found is None:
                found = self._draw_one(hint, width, height, scale, step, ring)
                if len(self._pieces) > 400:
                    self._pieces.clear()
                self._pieces[key] = found
            if found is not None:
                out.append((key, *found))
        return out

    def _draw_one(self, hint, width: int, height: int, scale: float, step: int, ring: int = 0):
        unit = min(width, height)
        if isinstance(hint, Badge):
            x, y = hint.at.to_client(width, height)
            h = hint.size * unit * scale * bounce_scale(step)
            img = self.sprites.get(hint.sprite, h)
            margin = round(h * 0.5) + 2  # its shadow and hold ring
            surf = pygame.Surface((img.get_width() + 2 * margin, img.get_height() + 2 * margin), pygame.SRCALPHA)
            r = img.get_rect(center=(surf.get_width() // 2, surf.get_height() // 2))
            if not hint.cover:
                sh, pad = self.sprites.shadow(hint.sprite, h)
                surf.blit(sh, (r.x - pad, r.y - pad + 2))
            surf.blit(img, r)
            if hint.hold:
                _hold_ring(surf, r.center, h, ring / RING_STEPS)
            return to_bgra(surf), x - surf.get_width() // 2, y - surf.get_height() // 2
        if isinstance(hint, Bar):
            h, gap, inner, parts, total = self._bar_parts(hint, unit, scale)
            rect = pygame.Rect(0, 0, round(total + h * 1.2), round(h * 1.35))
            rect.center = hint.at.to_client(width, height)
            rect.clamp_ip(pygame.Rect(4, 4, width - 8, height - 8))
            margin = round(h * 0.3)
            surf = pygame.Surface((rect.w + 2 * margin, rect.h + 2 * margin), pygame.SRCALPHA)
            self._draw_bar(surf, (h, gap, inner, parts), pygame.Rect(margin, margin, rect.w, rect.h))
            return to_bgra(surf), rect.x - margin, rect.y - margin
        return None

    def _draw_bar(self, surf, data, rect: pygame.Rect) -> None:
        h, gap, inner, parts = data
        back = pygame.Surface(rect.size, pygame.SRCALPHA)
        radius = max(2, round(h * 0.4))
        pygame.draw.rect(back, BAR_FILL, back.get_rect(), border_radius=radius)
        pygame.draw.rect(back, (*GOLD, 220), back.get_rect(), width=2, border_radius=radius)
        surf.blit(back, rect)
        x = rect.x + h * 0.6
        for name, icon, label in parts:
            r = icon.get_rect(center=(round(x + icon.get_width() / 2), rect.centery))
            sh, pad = self.sprites.shadow(name, h)
            surf.blit(sh, (r.x - pad, r.y - pad + 2))
            surf.blit(icon, r)
            x += icon.get_width() + gap
            surf.blit(label, (round(x), round(rect.centery - label.get_height() / 2)))
            x += label.get_width() + inner


def bounce_scale(step: int) -> float:
    return 1.0 if step == 0 else bounce((step - 0.5) / BOUNCE_STEPS * BOUNCE_SECONDS)


def _hold_ring(surf, center, h, frac=0.0):
    """A hold marker round the badge: a dark track with a thin gold line at rest, and a
    gold arc filling clockwise from the top while the button is held (frac 0..1)."""
    x, y = center
    rad = h * 0.62
    width = max(3, round(h * 0.11))
    pygame.draw.circle(surf, (0, 0, 0), (x, y), rad + 1, width)
    pygame.draw.circle(surf, GOLD, (x, y), rad - width / 2 + 1, max(1, width // 3))
    if frac <= 0:
        return
    if frac >= 1:
        pygame.draw.circle(surf, GOLD, (x, y), rad + 1, width)
        return
    # Short overlapping chords, so the arc has no gaps (pygame's arc leaves pinholes).
    mid = rad + 1 - width / 2
    n = max(2, round(64 * frac))
    pts = [(x + mid * math.sin(2 * math.pi * frac * i / n), y - mid * math.cos(2 * math.pi * frac * i / n))
           for i in range(n + 1)]
    pygame.draw.lines(surf, GOLD, False, pts, width)
    for px, py in (pts[0], pts[-1]):  # round ends
        pygame.draw.circle(surf, GOLD, (px, py), width / 2)


def to_bgra(surf: pygame.Surface) -> np.ndarray:
    """A surface as premultiplied BGRA rows (what layered windows take)."""
    rgb = pygame.surfarray.array3d(surf).transpose(1, 0, 2).astype(np.uint16)
    alpha = pygame.surfarray.array_alpha(surf).T.astype(np.uint16)
    out = np.empty((*alpha.shape, 4), np.uint8)
    for i, c in enumerate((2, 1, 0)):
        out[..., i] = (rgb[..., c] * alpha + 127) // 255
    out[..., 3] = alpha
    return out
