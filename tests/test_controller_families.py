"""PlayStation, Switch and Steam controllers: which button pictures a pad gets, each
family's spritesheet boxes, switching art while running, and the button_pictures setting."""

import os

import pygame
import pytest

from ttcontroller import config as module_config
from ttcontroller import controller
from ttcontroller import hint_draw as hd
from ttcontroller import hints as H
from ttcontroller.controller import family_of
from ttcontroller.settings_model import BUTTON_LABELS, button_labels


# ---- which family a controller is ------------------------------------------------------

@pytest.mark.parametrize("sdl_type, vendor, product, name, family", [
    (1, 0x045E, 0x028E, "XInput Controller", "xbox"),  # Xbox 360
    (2, 0x045E, 0x02FF, "Xbox One Controller", "xbox"),  # what the user's pad reads as
    (3, 0x054C, 0x0268, "PS3 Controller", "playstation"),
    (4, 0x054C, 0x09CC, "PS4 Controller", "playstation"),
    (7, 0x054C, 0x0CE6, "DualSense Wireless Controller", "playstation"),
    (4, 0x0F0D, 0x00EE, "HORI Wireless Controller", "playstation"),  # third-party, SDL knows it's a PS4 pad
    (5, 0x057E, 0x2009, "Nintendo Switch Pro Controller", "switch"),
    (13, 0x057E, 0x2008, "Nintendo Switch Joy-Con (L/R)", "switch"),
    (0, 0x28DE, 0x1102, "Steam Controller", "steam"),  # wired; SDL 2 has no Steam type
    (0, 0x28DE, 0x1142, "Steam Controller", "steam"),  # its wireless dongle
    (1, 0x28DE, 0x11FF, "Steam Virtual Gamepad", "xbox"),  # Steam Input: drawn as what it says it is
    (4, 0x28DE, 0x11FF, "PS4 Controller", "playstation"),  # Steam Input with a PS4 pad behind it
    (0, 0x054C, 0x0000, "", "playstation"),  # SDL doesn't know the type: the vendor
    (0, 0x057E, 0x0000, "", "switch"),
    (0, 0, 0, "Wireless Steam Controller", "steam"),  # nothing but the name
    (0, 0, 0, "Generic USB Joystick", "xbox"),
])
def test_family_of(sdl_type, vendor, product, name, family):
    assert family_of(sdl_type, vendor, product, name) == family


def test_sdl_hints_are_set_before_sdl_starts():
    # Nintendo buttons by label (a Switch's A is "a"), and the Steam Controller read
    # directly instead of as a mouse.
    assert os.environ["SDL_GAMECONTROLLER_USE_BUTTON_LABELS"] == "1"
    assert os.environ["SDL_JOYSTICK_HIDAPI_STEAM"] == "1"


def test_device_family_of_a_missing_device_falls_back_to_the_name():
    pygame.init()
    controller.sdl_controller.init()
    assert controller.device_family(99, "DualSense Wireless Controller") == "playstation"


def test_pictures_for():
    assert hd.pictures_for("auto", "switch") == "switch"
    assert hd.pictures_for("auto", None) is None  # no controller: keep what's drawn
    assert hd.pictures_for("steam", "playstation") == "steam"  # the setting wins


# ---- the sheets --------------------------------------------------------------------------

def _sheet(family):
    path = hd.find_sheet(None, family)
    if path is None:
        pytest.skip(f"{family}-spritesheet.png is missing")
    return path


@pytest.mark.parametrize("family", hd.FAMILIES)
def test_every_family_has_every_sprite(family):
    assert set(hd.FAMILY_RECTS[family]) == set(hd.RECTS)
    assert set(hd.DPADS[family][0]) == {"up", "right", "down", "left"}


@pytest.mark.parametrize("family", ["playstation", "switch", "steam"])
def test_boxes_hold_whole_buttons(family):
    """No box cuts a button off: just outside each box there's at most glow (the faint
    edge where neighbours touch), never solid art; and each box is mostly button. (The
    Xbox boxes, measured by hand and tested in game, are kept: they trim a pixel of rim.)"""
    sheet = pygame.image.load(str(_sheet(family)))
    alpha = pygame.surfarray.array_alpha(sheet)  # [x][y]
    width, height = sheet.get_size()
    for name, (x, y, w, h) in hd.FAMILY_RECTS[family].items():
        assert x > 0 and y > 0 and x + w < width and y + h < height, name
        inside = alpha[x:x + w, y:y + h]
        assert (inside > 128).mean() > 0.4, f"{family} {name}: box isn't on a button"
        ring = [alpha[x - 1, y:y + h], alpha[x + w, y:y + h], alpha[x:x + w, y - 1], alpha[x:x + w, y + h]]
        assert max(int(r.max()) for r in ring) <= 128, f"{family} {name}: box cuts the button off"
    centers, (cw, ch) = hd.DPADS[family]
    for d, (cx, cy) in centers.items():
        x, y = cx - cw // 2, cy - ch // 2
        assert x >= 0 and y >= 0 and x + cw <= width and y + ch <= height, d
        ring = [alpha[x, y:y + ch], alpha[x + cw - 1, y:y + ch], alpha[x:x + cw, y], alpha[x:x + cw, y + ch - 1]]
        assert max(int(r.max()) for r in ring) <= 40, f"{family} D-pad {d}: crop cuts it off"


ALL_SPRITES = ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "VIEW", "START", "LS", "RS", "L", "R",
               "L:u", "L:4", "R:ud", "R:lr", "DU", "DD", "DL", "DR", "DUD", "DLR", "D4"]


def test_switch_sprites_go_by_label():
    """The Switch sheet is laid out by position (B, A, Y, X where Xbox has A, B, X, Y), but
    its pads report by label, so sprite "A" is the sheet's A (the right one) and so on."""
    xbox, switch = hd.FAMILY_RECTS["xbox"], hd.FAMILY_RECTS["switch"]
    right, bottom = xbox["B"][0], xbox["A"][0]  # the columns the right and bottom buttons are in
    top, left = xbox["Y"][0], xbox["X"][0]
    assert abs(switch["A"][0] - right) < 15 and abs(switch["B"][0] - bottom) < 15
    assert abs(switch["X"][0] - top) < 15 and abs(switch["Y"][0] - left) < 15


@pytest.mark.parametrize("family", hd.FAMILIES)
def test_every_sprite_draws(family):
    pygame.init()
    sprites = hd.Sprites(_sheet(family), family)
    assert sprites.family == family
    for name in ALL_SPRITES:
        img = sprites.get(name, 40)
        # Wide ones (Steam's back and forward pills) are drawn shorter.
        assert img.get_height() >= 25 and img.get_width() >= 15, (family, name)
        assert img.get_width() * img.get_height() >= 900, (family, name)
        assert pygame.surfarray.array_alpha(img).max() > 200, (family, name)


def _bright(img) -> int:
    rgb, a = pygame.surfarray.array3d(img), pygame.surfarray.array_alpha(img)
    return int(((rgb.min(axis=2) > 210) & (a > 200)).sum())


@pytest.mark.parametrize("family", hd.FAMILIES)
def test_the_dpad_is_blank_but_for_gold_arrows(family):
    """The D-pad is built from the four lit crops' unlit arms, so none of the sheet's own
    lit (whitish) arrows is left on it: each lit crop is clearly brighter than the blank.
    (The Xbox pad's rim is bright too, so it's compared, not counted.)"""
    pygame.init()
    centers, (cw, ch) = hd.DPADS[family]
    sheet = pygame.image.load(str(_sheet(family)))
    crops = {d: sheet.subsurface(pygame.Rect(x - cw // 2, y - ch // 2, cw, ch)).copy() for d, (x, y) in centers.items()}
    blank = _bright(hd._wedges(crops))
    for d, crop in crops.items():
        lit = _bright(crop)
        assert lit - blank > 0.003 * cw * ch and blank < 0.6 * lit, f"{family}: {d}'s lit arrow is left on the D-pad"


def test_unknown_family_is_drawn_as_xbox():
    pygame.init()
    assert hd.Sprites(_sheet("xbox"), "gamecube").family == "xbox"


# ---- switching while running ---------------------------------------------------------------

def test_drawer_switches_family_and_redraws():
    pygame.init()
    for family in hd.FAMILIES:
        _sheet(family)
    drawer = hd.Drawer(_sheet("xbox"))
    hints = H.hints_for(H.Context())
    before = drawer.pieces(hints, 1920, 1009, 0.0)
    assert drawer.use("xbox") is False  # already
    assert drawer.use("playstation") is True and drawer.family == "playstation"
    after = drawer.pieces(hints, 1920, 1009, 0.0)
    assert len(after) == len(before)
    # Every piece's key changes, so each overlay window redraws with the new art.
    assert not {p[0] for p in before} & {p[0] for p in after}
    start = [p for p in before if getattr(p[0][0], "sprite", "") == "START"]
    options = [p for p in after if getattr(p[0][0], "sprite", "") == "START"]
    assert start and options and start[0][1].shape != options[0][1].shape  # Options is a thin pill


def test_drawer_keeps_its_art_when_a_sheet_is_missing(tmp_path, monkeypatch):
    pygame.init()
    drawer = hd.Drawer(_sheet("xbox"))
    monkeypatch.setattr(hd, "find_sheet", lambda extra=None, family="xbox": None)
    assert drawer.use("switch") is False and drawer.family == "xbox"


def test_name_keyboard_hint_bar_follows_the_family():
    from ttcontroller import name_keyboard as nk
    from ttcontroller.name_keyboard import NameKeyboard
    keys = nk.find_sheet()
    if keys is None:
        pytest.skip("no input_sprites/all_input.png")
    pygame.init()
    drawer = nk.KeyboardDrawer(keys, _sheet("xbox"))
    assert drawer.buttons_family == "xbox"
    k = NameKeyboard(text="Ga")
    xbox = drawer.image(k, 1009)
    drawer.use_buttons(hd.Sprites(_sheet("switch"), "switch"))
    assert drawer.buttons_family == "switch"
    switch = drawer.image(k, 1009)
    assert xbox.shape == switch.shape and (xbox != switch).any()


# ---- the setting and the names ----------------------------------------------------------------

def test_button_pictures_setting():
    assert module_config.Config().button_pictures == "auto"
    config, warnings = module_config.parse({"button_pictures": "playstation"})
    assert config.button_pictures == "playstation" and not warnings
    config, warnings = module_config.parse({"button_pictures": "gamecube"})
    assert config.button_pictures == "auto" and any("button_pictures" in w for w in warnings)
    assert module_config.to_json(config)["button_pictures"] == "auto"
    assert "button_pictures" in module_config.HELP


def test_button_names_per_family():
    assert button_labels(None) is BUTTON_LABELS and button_labels("xbox") is BUTTON_LABELS
    ps = button_labels("playstation")
    assert (ps["a"], ps["b"], ps["x"], ps["y"], ps["lb"], ps["rt"]) == ("Cross", "Circle", "Square", "Triangle", "L1", "R2")
    sw = button_labels("switch")
    # By label: a Switch's A is "a", like Xbox's A.
    assert (sw["a"], sw["b"], sw["x"], sw["y"], sw["lt"], sw["view"]) == ("A", "B", "X", "Y", "ZL", "Minus")
    assert button_labels("steam")["rs_up"] == "Right trackpad up"
    for family in hd.FAMILIES:
        assert set(button_labels(family)) == set(BUTTON_LABELS)
