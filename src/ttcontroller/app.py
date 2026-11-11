"""Main loop: read the controller, map it, and send keys while TTR is focused."""

import sys
import threading
import time
from pathlib import Path
from typing import Callable

from . import config as module_config
from . import ttr_settings
from .battle import BattleMapper, BattleScreen, read_screen
from .combo import ButtonCombo
from .controller import NEUTRAL, ControllerReader
from .dialog import DialogMapper, find_cancel_alone, find_ok_cancel
from .cursor import MOVE_TOLERANCE, CursorHider
from .book import BookMapper, BookScreen, read_book
from .friends import FriendsMapper, FriendsScreen, read_friends
from .garden import GardenMapper, GardenScreen, read_garden
from .garden_intro import GardenIntro, GardenIntroMapper, read_garden_intro
from .golf_green import AIM_RADIUS, PIVOT, GolfGreenMapper, GolfGreenScreen, aim_image, read_golf_green
from .hud import HudMapper, HudScreen, read_hud
from .facility import FacilityMapper, FacilityScreen, read_facility
from .fishing import FishingMapper, FishingScreen, read_fishing
from .mailbox import MailboxMapper, MailboxScreen, read_mailbox
from .boarding import BoardingMapper, BoardingScreen, read_boarding
from .silly import SillyMapper, SillyScreen, read_silly
from .vp import read_pie_round
from . import hints as hint_layout
from .ceo import read_leave
from .elevator import read_hop_off
from .hint_draw import Drawer, find_sheet
from .mail import read_mail
from .mapper import OverworldMapper, controller_buttons
from .overlay import Highlighter, stack
from .output import KeyboardOutput, MouseClicker, cursor_pos, mouse_button_down, posted_output, send_key
from .npc import NpcMapper, NpcScreen, read_npc
from .options import OptionsMapper, OptionsScreen, read_options
from .pregame import PregameMapper, PregameScreen, read_pregame
from .makeatoon import MakeAToonMapper, MakeAToonScreen, read_make_a_toon
from .shop import ShopMapper, ShopScreen, read_shop
from .speedchat import SpeedchatMapper, SpeedchatScreen, read_speedchat
from .window import (BoundTarget, ForegroundTarget, ForegroundWatcher, TargetChoice, TTRView,  # noqa: F401
                     client_rect, make_dpi_aware)

FRAME_SECONDS = 1 / 120
SETTINGS_CHECK_SECONDS = 1.0
# How often to look at the screen for battle panels and the gag shop.
BATTLE_CHECK_SECONDS = 0.1
# A battle panel can vanish for a moment (a dialog fading in); stay in battle mode
# until none has shown for this long.
BATTLE_GRACE_SECONDS = 0.5
# Stick or trigger input past this counts as using the controller (to hide the cursor).
CONTROLLER_USE_THRESHOLD = 0.3


# Where log lines go besides the console: the module's window adds one (launcher.py).
log_sinks: list[Callable[[str], None]] = []


# What the status shows about the controller toon's window in two-toon mode.
TARGET_LOG = {
    "ok": "Controller toon's window ready: controller active.",
    "unpicked": "Two toons: no TTR window picked for the controller yet: controller paused.",
    "minimized": "Controller toon's window is minimized: controller paused.",
    "covered": "Controller toon's window is covered (the module reads it from the screen): controller paused. "
               "Move the windows apart.",
    "gone": "Controller toon's window closed: controller paused. Pick another in the module's window.",
}


def log(message: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {message}"
    if sys.stdout is not None:  # None without a console (the windowed exe)
        print(line, flush=True)
    for sink in log_sinks:
        sink(line)


def describe_settings(settings: ttr_settings.TTRSettings) -> None:
    shown = ("forward", "reverse", "left", "right", "jump", "walk",
             "showGags", "showTasks", "stickerBook", "friendsList", "options")
    binds = ", ".join(f"{c}={'-'.join(settings.combo(c).names)}" for c in shown)
    log(f"TTR keybinds: {binds}")
    if settings.native_controller_enabled:
        log("WARNING: TTR's built-in controller support is on. Turn it off in TTR Options > Controls, "
            "or every button will act twice.")
    if settings.custom_cursor:
        log("Note: TTR's custom cursor is on, so the cursor can blink while the module clicks. "
            'Set "hide_cursor": true in the module config to turn it off.')
    if settings.display_mode != "window":
        log(f"Note: TTR display mode is '{settings.display_mode}'. Windowed mode is recommended.")


def apply_hide_cursor(watcher: ttr_settings.SettingsWatcher, hide: bool, was_hidden: bool) -> None:
    """Keep TTR's custom cursor off while hide_cursor is on (TTR may write it back), and
    turn it back on when hide_cursor is turned off."""
    if hide and watcher.settings.custom_cursor:
        if ttr_settings.set_custom_cursor(watcher.path, False):
            log("Turned off TTR's custom cursor (hide_cursor). It takes effect the next time TTR starts.")
        else:
            log(f"Couldn't turn off TTR's custom cursor: {watcher.path} couldn't be written.")
    elif was_hidden and not hide and not watcher.settings.custom_cursor:
        if ttr_settings.set_custom_cursor(watcher.path, True):
            log("Turned TTR's custom cursor back on. It takes effect the next time TTR starts.")


def describe_config(watcher: module_config.ConfigWatcher, settings: ttr_settings.TTRSettings) -> None:
    for problem in watcher.warnings + module_config.unknown_actions(watcher.config, settings.controls):
        log(f"Config problem: {problem}")


def controller_used(state) -> bool:
    if state is None:
        return False
    axes = (*state.left_stick, *state.right_stick, state.left_trigger, state.right_trigger)
    return bool(state.buttons) or any(abs(a) > CONTROLLER_USE_THRESHOLD for a in axes)


def target_state(target) -> str | None:
    """The controller toon's window's state for the status (two toons), else None."""
    return target.state if target.background else None


def make_mapper(config: module_config.Config) -> OverworldMapper:
    return OverworldMapper(config.bindings, config.movement, config.timing, config.auto_sprint,
                           config.toggle_hud)


def controls_to_keys(controls: set[str], settings: ttr_settings.TTRSettings) -> set[str]:
    keys = set()
    for control in controls:
        if control in settings.controls:
            keys.update(settings.combo(control).names)
    return keys


def run(ttr_dir: Path | None = None, dry_run: bool = False, debug: bool = False,
        stop: threading.Event | None = None,
        on_status: Callable[[str | None, bool, bool, str | None], None] | None = None,
        choice: TargetChoice | None = None) -> None:
    """The module's loop, until Ctrl+C or `stop` is set. on_status(controller name, TTR in
    front, paused for the mouse, the controller toon's window's state in two-toon mode or
    None) is called whenever one of those changes. choice: which window to drive (two
    toons); None or choice.hwnd None drives the TTR window in front."""
    make_dpi_aware()
    watcher = ttr_settings.SettingsWatcher(ttr_dir or ttr_settings.DEFAULT_TTR_DIR)
    log(f"Reading TTR settings from {watcher.path}")
    describe_settings(watcher.settings)
    config_watcher = module_config.ConfigWatcher()
    log(f"Module config: {config_watcher.path}")
    describe_config(config_watcher, watcher.settings)
    apply_hide_cursor(watcher, config_watcher.config.hide_cursor, False)

    def logged(send):
        def logged_send(name: str, down: bool) -> None:
            log(f"{'DOWN' if down else 'up  '} {name}" + ("" if dry_run else " (sent)"))
            if not dry_run:
                send(name, down)
        return logged_send

    reader = ControllerReader(config_watcher.config.controller)
    config = config_watcher.config
    mapper = make_mapper(config)
    battle_mapper = BattleMapper(config.battle)
    battle_screen = BattleScreen()
    shop_mapper = ShopMapper(config.shop)
    shop_screen = ShopScreen()
    npc_mapper = NpcMapper(config.npc)
    npc_screen = NpcScreen()
    speedchat_mapper = SpeedchatMapper(config.speedchat)
    speedchat_screen = SpeedchatScreen()
    friends_mapper = FriendsMapper(config.friends)
    friends_screen = FriendsScreen()
    hud_mapper = HudMapper()
    hud_screen = HudScreen()
    garden_mapper = GardenMapper(cache_path=module_config.CONFIG_DIR / "garden.json")  # the last flower's beans kept there
    garden_screen = GardenScreen()
    garden_intro_mapper = GardenIntroMapper()  # the first-time gardening introduction's pages
    garden_intro = GardenIntro()
    pie_round = False
    golf_mapper = GolfGreenMapper()  # the Cog Golf golf green puzzle
    golf_screen = GolfGreenScreen()
    golf_aim = None  # its aim angle, while aiming (for the aim line and crosshair)
    fishing_mapper = FishingMapper()  # a pond's dock: hold A to cast (M14)
    fishing_mapper.method = config.fishing_cast
    fishing_screen = FishingScreen()
    mailbox_mapper = MailboxMapper()  # the estate mailbox, open
    facility_mapper = FacilityMapper()  # Cog HQ facility nametags and their teleport popup
    facility_screen = FacilityScreen()
    mailbox_screen = MailboxScreen()
    boarding_mapper = BoardingMapper()  # the boarding group panel by a Cog HQ elevator
    boarding_screen = BoardingScreen()
    silly_mapper = SillyMapper()  # the Silly Meter's card, open
    silly_screen = SillyScreen()
    dialog_mapper = DialogMapper()  # an OK/Cancel dialog nothing else owns
    stray_dialog = None  # its OK and Cancel, when one is showing
    pregame_mapper = PregameMapper()  # the start-up screen and toon selection
    pregame_screen = PregameScreen()
    book_mapper = BookMapper(config.book)
    book_screen = BookScreen()
    options_mapper = OptionsMapper()  # TTR's own Options window, over anything
    options_screen = OptionsScreen()
    mat_mapper = MakeAToonMapper()  # Make-a-Toon, from an empty slot on toon selection
    mat_screen = MakeAToonScreen()
    send = logged(send_key) if dry_run or debug else send_key
    output = KeyboardOutput(send)
    clicker = MouseClicker()
    hider = CursorHider()
    highlighter = None if dry_run else Highlighter()
    if highlighter is not None and not highlighter.excluded:
        # A frame the module's own screen reading could see would throw it off.
        log("Note: this version of Windows can't keep the highlight frame out of screen captures, "
            "so it's turned off (it needs Windows 10 version 2004 or later).")
        highlighter.close()
        highlighter = None
    # The golf green's aim line and crosshair, in a window of their own.
    aimer = Highlighter() if highlighter is not None else None
    # What the frame goes around: the hovered point and the item's size, if it has one.
    highlight = None
    # The hints overlay (M11): controller buttons drawn on TTR's buttons, in a window of
    # their own like the frame. If the button art (input_sprites) is missing, there are no
    # hints.
    hint_drawer = None
    hint_windows: list[Highlighter] = []  # one small window per hint, made as needed
    if highlighter is not None:
        sheet = find_sheet(module_config.CONFIG_DIR)
        if sheet is None:
            log(f"Note: no hints (the controller button pictures, {module_config.CONFIG_DIR / 'xbox-spritesheet.png'}, "
                "weren't found).")
        else:
            try:
                hint_drawer = Drawer(sheet)
            except Exception as e:  # a broken sheet shouldn't stop the controller
                log(f"Note: no hints ({e}).")
    hints = ()  # what the hints overlay shows now
    hint_mail = hint_hop = hint_leave = None  # read for the hints only: Clarabelle's X, Hop off, a CEO leave button
    last_buttons = frozenset()
    foreground = ForegroundWatcher()
    # The window the controller drives (two toons, M13): the TTR window in front, or the
    # one chosen in the module's window. Two-toon mode swaps the output for posted input,
    # leaves the real cursor and the mouse pause to the other toon, and keeps the overlay
    # windows with that TTR window. Everything else doesn't know which mode it's in.
    target = ForegroundTarget(foreground)
    bound_to = (False, None)
    if config.two_toons and choice is None:
        log("Note: two toons is picked in the module's window (ToontownControllerModule). Here the controller "
            "drives the TTR window in front.")

    def point(kind: str, target, name: str, view, restore: bool = True, notches: int = 0,
              delay: float = 0.0, size=None, frame_at=None, color=None, to=None, pointer=False) -> None:
        """Hover or click an on-screen point (a ui.UIPoint) in the TTR window."""
        nonlocal highlight
        if view is None:
            return
        if kind == "hover":
            highlight = (frame_at or target, size, color, pointer) if size is not None else None
        elif kind == "scroll":
            # What was highlighted is moving; the next hover puts the frame back.
            highlight = None
        x, y = view.to_screen(target)
        if dry_run or debug:
            log(f"{kind.capitalize()} {name} at screen {x},{y}" + (" (dry run, not moved)" if dry_run else ""))
        if dry_run:
            return
        if kind == "hover":
            clicker.hover(x, y)
        elif kind == "hold":
            clicker.hold(x, y)
        elif kind == "release":
            clicker.release()
        elif kind == "drag":
            clicker.drag(x, y, *view.to_screen(to))
        elif kind == "scroll":
            clicker.scroll(x, y, notches)
        elif kind == "type":
            # Typed straight away, letter by letter (a click after it waits its delay).
            for letter in name:
                send(letter, True)
                send(letter, False)
        else:
            clicker.click(x, y, restore=restore, delay=delay)

    controller_name = ""  # differs from None so the first poll logs either way
    ttr_focused = None
    # Using the real mouse in TTR pauses the controller, like TTR losing focus, until
    # the controller is used again.
    mouse_paused = False
    next_settings_check = 0.0
    next_battle_check = 0.0
    last_battle_seen = -BATTLE_GRACE_SECONDS
    last_shop_seen = -BATTLE_GRACE_SECONDS
    was_in_menu = False
    npc_was_paused = False  # the task panel was showing when speedchat or the friends list opened
    bumper_combo = ButtonCombo()  # LB + RB: a screenshot
    last_holder: str | None = None  # the menu that may hold the mouse button down ("book"/"friends")
    log(("Running." if stop is not None else "Running. Press Ctrl+C to quit.")
        + (" (dry run: keys are printed, not sent)" if dry_run else ""))
    status = None

    try:
        while stop is None or not stop.is_set():
            now = time.monotonic()

            state = reader.poll()
            if reader.name != controller_name:
                controller_name = reader.name
                log(f"Controller connected: {controller_name}" if controller_name else
                    "No controller connected. Waiting for one (press the Xbox button to wake it).")

            if debug and state is not None and state.buttons != last_buttons:
                last_buttons = state.buttons
                log(f"Buttons held: {', '.join(sorted(state.buttons)) or 'none'}")

            wanted = choice.wanted if choice is not None else (False, None)
            swapped = wanted != bound_to
            if swapped:
                # Let go of everything on the old window before driving the new one.
                output.release_all()
                clicker.release()
                hider.show()
                mouse_paused = False
                bound_to = wanted
                two_toons, hwnd = wanted
                if not two_toons:
                    target = ForegroundTarget(foreground)
                    send = logged(send_key) if dry_run or debug else send_key
                    output, clicker = KeyboardOutput(send), MouseClicker()
                    log("One toon: the controller drives the TTR window in front.")
                else:
                    target = BoundTarget(hwnd)
                    if hwnd is None:  # nothing picked: nothing to send to
                        send = lambda name, down: None  # noqa: E731
                        output = KeyboardOutput(send)
                        clicker = MouseClicker(lambda x, y: None, lambda down: None, lambda: (0, 0), lambda n: None)
                    else:
                        output, clicker, send = posted_output(hwnd, logged if dry_run or debug else None)
                    log("Two toons: the controller drives the chosen TTR window, in front or not.")
                for window in (highlighter, aimer, *hint_windows):
                    if window is not None:
                        window.attach(hwnd)
                ttr_focused = None
            target.update()
            ttr_path = target.path
            focused = dry_run or target.active
            if (focused, target.state) != ttr_focused:
                ttr_focused = (focused, target.state)
                if not dry_run:
                    if target.background:
                        log(TARGET_LOG[target.state])
                    else:
                        log("TTR focused: controller active." if focused else "TTR not focused: controller paused.")
            if ttr_path is not None and ttr_dir is None:
                # Follow the running game's install folder in case it isn't the default.
                watcher.set_dir(ttr_path.parent)

            if now >= next_settings_check:
                next_settings_check = now + SETTINGS_CHECK_SECONDS
                if watcher.check() is not None:
                    log("TTR settings changed, reloaded.")
                    describe_settings(watcher.settings)
                    describe_config(config_watcher, watcher.settings)
                    apply_hide_cursor(watcher, config.hide_cursor, config.hide_cursor)
                if config_watcher.check() is not None:
                    log("Module config changed, reloaded.")
                    describe_config(config_watcher, watcher.settings)
                    output.release_all()
                    apply_hide_cursor(watcher, config_watcher.config.hide_cursor, config.hide_cursor)
                    config = config_watcher.config
                    reader.set_preferred(config.controller)
                    mapper = make_mapper(config)
                    battle_mapper.set_bindings(config.battle)
                    shop_mapper.set_bindings(config.shop)
                    npc_mapper.set_bindings(config.npc)
                    speedchat_mapper.set_bindings(config.speedchat)
                    friends_mapper.set_bindings(config.friends)
                    book_mapper.set_bindings(config.book)
                    fishing_mapper.method = config.fishing_cast

            if mouse_paused and (not focused or controller_used(state)):
                mouse_paused = False
                if focused:
                    log("Controller resumed.")
                    # Whatever the mouse opened is read right away.
                    next_battle_check = now
            # A swap starts like TTR losing focus: every screen and mapper starts over.
            active = focused and not mouse_paused and not swapped
            # The hints and frame show while the controller is in use; in two-toon mode the
            # controller toon's window is the controller's alone, so always.
            presenting = hider.hidden or target.background
            if on_status is not None and (controller_name, focused, mouse_paused, target_state(target)) != status:
                status = (controller_name, focused, mouse_paused, target_state(target))
                on_status(*status)
            if not active:
                clicker.release()
                # The button that resumes the controller only resumes it: anything held
                # when it comes back does nothing until it's let go.
                mapper.reset(ignore_held=True)
                battle_mapper.reset_buttons()
                shop_mapper.reset_buttons()
                npc_mapper.reset_buttons()
                speedchat_mapper.reset_buttons()
                friends_mapper.reset_buttons()
                book_mapper.reset_buttons()
                pregame_mapper.reset_buttons()
                pregame_screen = PregameScreen()
                options_mapper.reset_buttons()
                options_screen = OptionsScreen()
                mat_mapper.reset_buttons()
                mat_screen = MakeAToonScreen()
                battle_screen = BattleScreen()
                shop_screen = ShopScreen()
                npc_screen = NpcScreen()
                speedchat_screen = SpeedchatScreen()
                friends_screen = FriendsScreen()
                hud_screen = HudScreen()
                garden_screen = GardenScreen()
                garden_intro_mapper.reset_buttons()
                garden_intro = GardenIntro()
                pie_round = False
                stray_dialog = None
                mailbox_screen = MailboxScreen()
                boarding_mapper.reset()
                boarding_screen = BoardingScreen()
                silly_mapper.reset_buttons()
                silly_screen = SillyScreen()
                golf_screen = GolfGreenScreen()
                fishing_mapper.reset()
                fishing_screen = FishingScreen()
                facility_screen = FacilityScreen()
                book_screen = BookScreen()
                output.release_all()
            else:
                view = TTRView(target.hwnd, target.background) if target.hwnd else None
                if view is not None and now >= next_battle_check:
                    next_battle_check = now + BATTLE_CHECK_SECONDS
                    frame = view.snapshot()
                    # The book can't open in battle or the shop, so it's read first and the
                    # rest are skipped while it's open: a blank white page looks like the
                    # battle's waiting screen, the shop takes a dialog over the book for its
                    # own, and the NPC bubble search finds false arrows in its pages.
                    # TTR's Options window is over everything, so it comes first, and the
                    # rest aren't read while it's open (their screens are under it).
                    opts = read_options(frame.width, frame.height, frame.get_pixel)
                    if (opts.kind, opts.tab) != (options_screen.kind, options_screen.tab) and (dry_run or debug):
                        log(f"Options: {opts.kind or 'closed'}" + (f" ({opts.tab + 1})" if opts.tab is not None else ""))
                    options_screen = opts
                    # Make-a-Toon, the start-up screen and toon selection come before all the rest.
                    mat = (read_make_a_toon(frame.width, frame.height, frame.get_pixel) if opts.kind is None
                           else MakeAToonScreen())
                    if mat.kind != mat_screen.kind and (dry_run or debug):
                        log(f"Make-a-Toon: {mat.kind or 'closed'}")
                    mat_screen = mat
                    pregame = (read_pregame(frame.width, frame.height, frame.get_pixel)
                               if opts.kind is None and mat.kind is None else PregameScreen())
                    if pregame.kind != pregame_screen.kind and (dry_run or debug):
                        log(f"Pre-game screen: {pregame.kind or 'none'}")
                    pregame_screen = pregame
                    in_game = pregame.kind is None and opts.kind is None and mat.kind is None
                    book = read_book(frame.width, frame.height, frame.get_pixel) if in_game else BookScreen()
                    screen = (read_screen(frame.width, frame.height, frame.get_pixel) if in_game and not book.is_open
                              else BattleScreen())
                    if screen.kind != battle_screen.kind and (dry_run or debug):
                        log(f"Battle screen: {screen.kind or 'none'}")
                    battle_screen = screen
                    # The Run? prompt's layout is any OK/Cancel dialog's: outside a battle it's
                    # another one (the estate's "Do you want to teleport?"), handled below.
                    stray_dialog = (find_ok_cancel(frame.width, frame.height, frame.get_pixel)
                                    if screen.kind == "confirm_run" else None)
                    if stray_dialog is None and in_game and screen.kind is None and not book.is_open:
                        # A dialog with Cancel alone (a boarding group keeping you in the area):
                        # A and B both click it.
                        alone = find_cancel_alone(frame.width, frame.height, frame.get_pixel)
                        stray_dialog = (alone, alone) if alone is not None else None
                    if ((book.is_open, book.page, book.dialog is not None)
                            != (book_screen.is_open, book_screen.page, book_screen.dialog is not None)
                            and (dry_run or debug)):
                        log(f"Book: {'closed' if not book.is_open else 'dialog' if book.dialog else book.page or 'unknown page'}")
                    book_screen = book
                    shop = (read_shop(frame.width, frame.height, frame.get_pixel)
                            if in_game and screen.kind is None and not book.is_open else ShopScreen())
                    if shop.kind != shop_screen.kind and (dry_run or debug):
                        log(f"Gag shop screen: {shop.kind or 'none'}")
                    shop_screen = shop
                    # The gags/trunk and tasks HUDs, kept up by toggle_hud. Read before NPCs:
                    # the bubble search finds arrows in the trunk's SOS cards, as in the book.
                    # (They only take buttons with nothing else open; see free below.)
                    shown = mapper.shown
                    hud = (read_hud(frame.width, frame.height, frame.get_pixel,
                                    gags="showGags" in shown, tasks="showTasks" in shown)
                           if (in_game and {"showGags", "showTasks"} & shown and not book.is_open
                               and screen.kind is None and shop.kind is None)
                           else HudScreen())
                    if hud.kind != hud_screen.kind and (dry_run or debug):
                        log(f"HUD: {hud.kind or 'none'}")
                    hud_screen = hud
                    # Gardening, before NPCs too: the bubble search finds one in the bean picker.
                    garden = (read_garden(frame.width, frame.height, frame.get_pixel)
                              if in_game and screen.kind is None and shop.kind is None and not book.is_open
                              else GardenScreen())
                    if garden != garden_screen and (dry_run or debug):
                        log(f"Gardening: {'bean picker' if garden.planting else 'sell popup' if garden.selling else 'OK popup' if garden.ok else 'panel' if garden.is_open else 'none'}"
                            + (" (no beans)" if garden.planting and not garden.beans else ""))
                    garden_screen = garden
                    intro = (read_garden_intro(frame.width, frame.height, frame.get_pixel)
                             if in_game and screen.kind is None and shop.kind is None and not book.is_open
                             else GardenIntro())
                    if intro.is_open != garden_intro.is_open and (dry_run or debug):
                        log(f"Gardening intro: {'open' if intro.is_open else 'closed'}")
                    garden_intro = intro
                    mailbox = (read_mailbox(frame.width, frame.height, frame.get_pixel)
                               if in_game and screen.kind is None and shop.kind is None and not book.is_open
                               else MailboxScreen())
                    if mailbox != mailbox_screen and (dry_run or debug):
                        log(f"Mailbox: {'open' if mailbox.is_open else 'closed'}")
                    mailbox_screen = mailbox
                    boarding = (read_boarding(frame.width, frame.height, frame.get_pixel)
                                if in_game and screen.kind is None and shop.kind is None and not book.is_open
                                else BoardingScreen())
                    if boarding.kind != boarding_screen.kind and (dry_run or debug):
                        log(f"Boarding group: {boarding.kind or 'none'}")
                    boarding_screen = boarding
                    silly = (read_silly(frame.width, frame.height, frame.get_pixel)
                             if in_game and screen.kind is None and shop.kind is None and not book.is_open
                             else SillyScreen())
                    if silly.card != silly_screen.card and (dry_run or debug):
                        log(f"Silly Meter: {'open' if silly.card else 'closed'}")
                    silly_screen = silly
                    golf = (read_golf_green(frame.width, frame.height, frame.get_pixel)
                            if in_game and screen.kind is None and shop.kind is None and not book.is_open
                            else GolfGreenScreen())
                    if golf.is_open != golf_screen.is_open and (dry_run or debug):
                        log(f"Golf green: {'up' if golf.is_open else 'gone'}")
                    golf_screen = golf
                    fishing = (read_fishing(frame.width, frame.height, frame.get_pixel)
                               if in_game and screen.kind is None and shop.kind is None and not book.is_open
                               else FishingScreen())
                    if fishing.kind != fishing_screen.kind and (dry_run or debug):
                        log(f"Fishing: {fishing.kind or 'none'}")
                    fishing_screen = fishing
                    facility = (read_facility(frame.width, frame.height, frame.get_pixel)
                                if in_game and screen.kind is None and shop.kind is None and not book.is_open
                                and not golf.is_open else FacilityScreen())
                    if ((facility.popup, len(facility.tags)) != (facility_screen.popup, len(facility_screen.tags))
                            and (dry_run or debug)):
                        log(f"Facility: {len(facility.tags)} nametags" + (", popup up" if facility.popup else ""))
                    facility_screen = facility
                    npc = (read_npc(frame.width, frame.height, frame.get_pixel, frame.rgb())
                           if (in_game and screen.kind is None and shop.kind is None and not book.is_open
                               and hud.kind != "trunk" and not garden.popup and not mailbox.is_open
                               and not golf.is_open and not facility.popup
                               # The bubble search took the fishing bucket's "4/20" for a
                               # bubble's arrow; nobody talks to NPCs from a dock.
                               and fishing.kind is None and not intro.is_open)
                           else NpcScreen())
                    if npc.kind != npc_screen.kind and (dry_run or debug):
                        log(f"NPC screen: {npc.kind or 'none'}")
                    npc_screen = npc
                    # Speedchat and the friends list work in battle too.
                    menus = in_game and shop.kind is None and npc.kind != "tasks"
                    speedchat = (read_speedchat(frame.width, frame.height, frame.get_pixel,
                                                look_for_unite=speedchat_mapper.wants_unite)
                                 if menus else SpeedchatScreen())
                    if speedchat.is_open != speedchat_screen.is_open and (dry_run or debug):
                        log(f"Speedchat menu: {'open' if speedchat.is_open else 'closed'}")
                    speedchat_screen = speedchat
                    friends = (read_friends(frame.width, frame.height, frame.get_pixel,
                                            dialogs=friends_mapper.expects_dialog(now)) if menus else FriendsScreen())
                    if friends.kind != friends_screen.kind and (dry_run or debug):
                        log(f"Friends screen: {friends.kind or 'none'}")
                    friends_screen = friends
                    pies = in_game and screen.kind is None and not book.is_open and read_pie_round(
                        frame.width, frame.height, frame.get_pixel)
                    if pies != pie_round and (dry_run or debug):
                        log(f"VP pie round: {'on' if pies else 'off'}")
                    pie_round = pies
                    # Buttons the overworld reads only when pressed, read here for their hints.
                    calm = (hint_drawer is not None and config.hints and in_game and screen.kind is None
                            and shop.kind is None and not book.is_open and npc.kind is None and not speedchat.is_open
                            and friends.kind is None)
                    hint_mail = read_mail(frame.width, frame.height, frame.get_pixel) if calm else None
                    hint_hop = read_hop_off(frame.width, frame.height, frame.get_pixel) if calm else None
                    hint_leave = read_leave(frame.width, frame.height, frame.get_pixel) if calm else None

                state = state or NEUTRAL
                state, screenshot = bumper_combo.update(state, now)
                if screenshot:
                    log("Screenshot (LB + RB).")
                    mapper.tap("screenshot", now)
                # The run prompt only follows a battle screen: one out of nowhere is another
                # dialog laid out the same (Ignore A Player's), not a battle.
                if battle_screen.kind is not None and (battle_screen.kind != "confirm_run"
                                                       or now - last_battle_seen < BATTLE_GRACE_SECONDS):
                    last_battle_seen = now
                if shop_screen.kind is not None:
                    last_shop_seen = now
                in_options = options_screen.kind is not None
                if in_options:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    for command in options_mapper.update(buttons, now, options_screen):
                        point(command.kind, command.point, command.name, view, size=command.size, restore=False,
                              notches=command.notches, delay=command.delay, frame_at=command.frame_at,
                              color=command.color, to=command.to)
                else:
                    options_mapper.reset_buttons()
                    options_mapper.update(frozenset(), now, OptionsScreen())
                in_mat = mat_screen.kind is not None and not in_options
                if in_mat:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    for command in mat_mapper.update(buttons, now, mat_screen):
                        point(command.kind, command.point, command.name, view, size=command.size, restore=False,
                              pointer=command.pointer)
                else:
                    mat_mapper.reset_buttons()
                in_pregame = pregame_screen.kind is not None
                if in_pregame:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    for command in pregame_mapper.update(buttons, now, pregame_screen):
                        point(command.kind, command.point, command.name, view, restore=False, delay=command.delay)
                elif in_options:
                    pregame_mapper.pause()  # back to the same toon when Options closes over toon selection
                else:
                    pregame_mapper.reset_buttons()
                in_battle = not in_options and now - last_battle_seen < BATTLE_GRACE_SECONDS
                in_shop = not (in_options or in_battle) and now - last_shop_seen < BATTLE_GRACE_SECONDS
                if in_shop:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    for command in shop_mapper.update(buttons, now, shop_screen):
                        point(command.kind, command.point, command.name, view, size=command.size, restore=False)
                else:
                    shop_mapper.reset_buttons()
                if in_shop and shop_screen.kind != "shop":
                    highlight = None
                # NPC screens come and go with the conversation, so no grace period.
                npc_open = not (in_battle or in_shop) and npc_screen.kind is not None
                # Speedchat first when both are open: it closes as soon as a phrase is said.
                # Both are above battles and NPC screens too (a conversation, the task panel),
                # which pause while one is open.
                in_speedchat = not in_shop and speedchat_screen.is_open
                in_friends = not (in_shop or in_speedchat) and friends_screen.kind is not None
                in_npc = npc_open and not (in_speedchat or in_friends)
                if (in_speedchat or in_friends) and npc_mapper.choosing:
                    # The task panel is under it (speedchat can cover the panel, so it may
                    # not be read until speedchat closes).
                    npc_was_paused = True
                if in_npc:
                    if npc_was_paused:
                        npc_mapper.rehover()  # back on the task it was on
                        npc_was_paused = False
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    for command in npc_mapper.update(buttons, now, npc_screen):
                        point(command.kind, command.point, command.name, view, size=command.size, restore=False)
                else:
                    npc_mapper.reset_buttons()
                    if not (npc_open or in_speedchat or in_friends):
                        # Gone (the panel's timer can close it): nothing to come back to.
                        npc_mapper.forget()
                        npc_was_paused = False
                # The book is under both (speedchat and the friends list open over it).
                in_book = not (in_battle or in_shop or npc_open or in_speedchat or in_friends) and book_screen.is_open
                in_menu = in_speedchat or in_friends or in_book
                for menu_open, menu_mapper, menu_screen in ((in_speedchat, speedchat_mapper, speedchat_screen),
                                                            (in_friends, friends_mapper, friends_screen),
                                                            (in_book, book_mapper, book_screen)):
                    if menu_open:
                        buttons = controller_buttons(state, config.timing.stick_button_threshold)
                        for command in menu_mapper.update(buttons, now, menu_screen):
                            point(command.kind, command.point, command.name, view, size=command.size, restore=False,
                                  notches=command.notches, delay=command.delay, frame_at=command.frame_at)
                    else:
                        menu_mapper.reset_buttons()
                if in_battle and was_in_menu and not in_menu:
                    battle_mapper.rehover()
                was_in_menu = in_menu
                if in_battle and not in_menu:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    for command in battle_mapper.update(buttons, now, battle_screen):
                        # Battle clicks leave the cursor on the button, where the highlight is.
                        point(command.kind, command.point, command.name, view, size=command.size, restore=False,
                              notches=command.notches, delay=command.delay, frame_at=command.frame_at)
                else:
                    battle_mapper.reset_buttons()
                if in_battle and not in_menu and battle_screen.kind not in ("picker", "trunk", "target"):
                    # The frame goes around gags, trunk items and target arrows; once those
                    # are gone (a gag clicked, the round over) it goes too.
                    highlight = None
                # In battle or the shop, their bindings own their buttons and the left stick doesn't walk.
                if in_options or in_mat:
                    blocked = controller_buttons(state, config.timing.stick_button_threshold)
                elif in_pregame:
                    # Toon selection takes every button. The start-up screen only Start and B:
                    # any other key enters, as TTR says.
                    blocked = (frozenset({"start", "b"}) if pregame_screen.kind == "startup"
                               else controller_buttons(state, config.timing.stick_button_threshold))
                elif in_battle:
                    blocked = frozenset(battle_mapper.buttons)
                    if in_speedchat:
                        blocked |= speedchat_mapper.buttons
                    elif in_friends:
                        blocked |= friends_mapper.buttons
                elif in_shop:
                    blocked = frozenset(shop_mapper.buttons)
                elif in_npc:
                    blocked = frozenset(npc_mapper.buttons(npc_screen))
                elif in_speedchat:
                    blocked = frozenset(speedchat_mapper.buttons)
                elif in_friends:
                    blocked = frozenset(friends_mapper.buttons)
                elif in_book:
                    blocked = frozenset(book_mapper.buttons)
                else:
                    blocked = frozenset()
                # The golf green: the left stick aims instead of walking.
                in_golf = golf_screen.is_open and not (in_options or in_mat or in_pregame or in_battle or in_shop
                                                       or in_speedchat or in_friends or book_screen.is_open)
                # Fishing on a dock: A casts (held, the stick pulls), B leaves. Its popups
                # (bucket full, out of jellybeans) are dialogs with one button (stray_dialog).
                in_fishing = (fishing_screen.kind is not None and stray_dialog is None
                              and not (in_options or in_mat or in_pregame or in_battle or in_shop
                                       or in_speedchat or in_friends or book_screen.is_open))
                # Walking still works mid-conversation (it walks away); not while choosing a task.
                walk = not (in_options or in_mat or in_battle or in_shop or in_book or npc_screen.kind == "tasks"
                            or (in_pregame and pregame_screen.kind != "startup") or in_golf or in_fishing)
                for control in book_mapper.take_taps():
                    mapper.tap(control, now)
                if book_mapper.take_left_page():
                    highlight = None
                # The book and friends list let go of their own holds while open (the kart, a
                # scroll triangle); one held when it closes, or the other opens, is let go here.
                holder = ("options" if in_options else "makeatoon" if in_mat else "book" if in_book
                          else "friends" if in_friends else "fishing" if in_fishing else None)
                if holder is None or holder != last_holder:
                    clicker.release()
                last_holder = holder
                free = not (in_options or in_mat or in_pregame or in_battle or in_shop or npc_screen.kind is not None or in_speedchat
                            or in_friends or book_screen.is_open)
                if in_golf:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    blocked = blocked | golf_mapper.buttons
                    for command in golf_mapper.update(buttons, state.left_stick, now, golf_screen):
                        point(command.kind, command.point, command.name, view, restore=False)
                    golf_aim = golf_mapper.angle
                else:
                    if golf_aim is not None or golf_mapper.angle is not None:
                        golf_mapper.reset()
                    golf_aim = None
                if in_fishing:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    blocked = blocked | fishing_mapper.buttons(fishing_screen)
                    fishing_commands = fishing_mapper.update(buttons, state.left_stick, now, fishing_screen)
                else:
                    # Let go of a cast in progress when the dock goes (a popup, the book).
                    fishing_commands = fishing_mapper.update(frozenset(), (0.0, 0.0), now, FishingScreen())
                for command in fishing_commands:
                    point(command.kind, command.point, command.name, view, restore=False)
                if fishing_mapper.take_switch():
                    log("Fishing: the stick " + ("moves the aim." if fishing_mapper.method == "move"
                                                 else "is the aim (where it points)."))
                    config_watcher.save_value("fishing_cast", fishing_mapper.method)
                    config = config_watcher.config
                # The gardening HUD's buttons on Y and X, instead of showing gags and tasks.
                if free and garden_screen.is_open:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    blocked = blocked | garden_mapper.buttons(garden_screen)
                    for command in garden_mapper.update(buttons, now, garden_screen):
                        point(command.kind, command.point, command.name, view, size=command.size,
                              delay=command.delay)
                else:
                    garden_mapper.reset_buttons()
                    garden_mapper.update(frozenset(), now, GardenScreen())
                facility_buttons = facility_mapper.buttons(facility_screen) if free else frozenset()
                if facility_buttons:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    blocked = blocked | facility_buttons
                    for command in facility_mapper.update(buttons & facility_buttons, now, facility_screen):
                        point(command.kind, command.point, command.name, view)
                else:
                    facility_mapper.reset_buttons()
                if free and mailbox_screen.is_open:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    blocked = blocked | mailbox_mapper.buttons
                    for command in mailbox_mapper.update(buttons, now, mailbox_screen):
                        point(command.kind, command.point, command.name, view)
                else:
                    mailbox_mapper.reset_buttons()
                if free and stray_dialog is not None and not garden_screen.is_open:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    blocked = blocked | DialogMapper.BUTTONS
                    for command in dialog_mapper.update(buttons, now, stray_dialog):
                        point(command.kind, command.point, command.name, view)
                else:
                    dialog_mapper.reset_buttons()
                in_hud = free and hud_screen.kind is not None
                if in_hud:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    blocked = blocked | hud_mapper.buttons(hud_screen)
                    for command in hud_mapper.update(buttons, now, hud_screen):
                        point(command.kind, command.point, command.name, view, restore=False,
                              notches=command.notches, size=command.size, frame_at=command.frame_at)
                else:
                    hud_mapper.update(frozenset(), now, HudScreen())
                # The boarding group panel: the right stick opens and closes it; while open the
                # D-pad and A work its list, and holding B leaves the group. Not over the HUD
                # (it has the right stick) or a dialog (A and B are its).
                # The gardening introduction: A next (Done on the last page), B / D-pad left back.
                if free and garden_intro.is_open and stray_dialog is None:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    blocked = blocked | GardenIntroMapper.BUTTONS
                    for command in garden_intro_mapper.update(buttons, now, garden_intro):
                        point(command.kind, command.point, command.name, view)
                else:
                    garden_intro_mapper.reset_buttons()
                # The Silly Meter's card: D-pad left its details, B closes the top card.
                if free and silly_screen.card and stray_dialog is None:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    blocked = blocked | SillyMapper.BUTTONS
                    for command in silly_mapper.update(buttons, now, silly_screen):
                        point(command.kind, command.point, command.name, view)
                else:
                    silly_mapper.reset_buttons()
                in_boarding = (free and boarding_screen.kind is not None and not in_hud and stray_dialog is None)
                if in_boarding:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    taken = boarding_mapper.buttons(boarding_screen)
                    blocked = blocked | taken
                    for command in boarding_mapper.update(buttons & (taken | {"b"}), now, boarding_screen):
                        point(command.kind, command.point, command.name, view, restore=False)
                controls = mapper.update(state, now, view, blocked=blocked, movement=walk, free=free,
                                         pies=pie_round and free)
                output.sync(controls_to_keys(controls, watcher.settings))
                for button in mapper.take_clicks():
                    point("click", button.center, button.name, view)
                # Nothing to hover: while the cursor is hidden, leave it off the game area.
                # Book pages without controls of their own don't hover anything.
                idle = not (in_battle or in_shop or in_speedchat or in_friends or npc_screen.kind == "tasks" or in_golf
                            or (in_fishing and fishing_mapper.holding)
                            or (in_hud and hud_mapper.hovering())
                            or (free and garden_screen.planting and garden_mapper.hovering)
                            or (in_book and book_mapper.hovering(book_screen))
                            or (in_pregame and pregame_mapper.hovering(pregame_screen))
                            or (in_boarding and boarding_mapper.hovering(boarding_screen))
                            or (in_options and options_mapper.hovering(options_screen))
                            or (in_mat and mat_mapper.hovering(mat_screen)))
                if idle and hider.hidden and view is not None and not clicker.busy and not dry_run:
                    spot = view.park_spot()
                    # Checked against where the cursor really is: the mouse may have moved it.
                    pos = cursor_pos()
                    if spot is not None and max(abs(pos[0] - spot[0]), abs(pos[1] - spot[1])) > MOVE_TOLERANCE:
                        clicker.hover(*spot)
                if idle:
                    highlight = None
                if mapper.take_sprint_toggle():
                    log(f"Auto-sprint {'on' if mapper.auto_sprint else 'off'}.")
                    config_watcher.save_auto_sprint(mapper.auto_sprint)
                    config = config_watcher.config
                if mapper.take_unite():
                    speedchat_mapper.go_to_unite(now)
                if hint_drawer is not None:
                    mode = ("options" if in_options else "mat" if in_mat else "pregame" if in_pregame
                            else "speedchat" if in_speedchat else "friends" if in_friends else "battle" if in_battle
                            else "shop" if in_shop else "npc" if in_npc else "book" if in_book
                            else "golf" if in_golf else "fishing" if in_fishing else "free")
                    hints = hint_layout.hints_for(hint_layout.Context(
                        mode=mode, options=options_screen, options_row_y=options_mapper.row_y, mat=mat_screen,
                        pregame=pregame_screen, toon_slot=pregame_mapper.slot, battle=battle_screen,
                        shop=shop_screen, friends=friends_screen, npc=npc_screen, book=book_screen,
                        book_task=book_mapper.hovered_task, fishing=fishing_screen,
                        fishing_cast=fishing_mapper.method, garden=garden_screen if free else GardenScreen(),
                        garden_intro=garden_intro if free and stray_dialog is None else GardenIntro(),
                        mailbox=mailbox_screen if free else MailboxScreen(),
                        facility=facility_screen if free else FacilityScreen(),
                        silly=silly_screen if free else SillyScreen(),
                        boarding=boarding_screen if in_boarding else BoardingScreen(),
                        dialog=stray_dialog if free and not garden_screen.is_open else None,
                        mail_close=hint_mail.close if hint_mail else None,
                        mail_icon=hint_mail.icon if hint_mail else None, hop_off=hint_hop, leave=hint_leave, hud=in_hud,
                        walking_bar=config.hints_walking_bar,
                        tables={"overworld": config.bindings, "battle": config.battle, "shop": config.shop,
                                "npc": config.npc, "speedchat": config.speedchat, "friends": config.friends,
                                "book": config.book}))
                    hint_drawer.hold_seconds = config.timing.hold_seconds
                    hint_drawer.press(controller_buttons(state, config.timing.stick_button_threshold), now)
            # Runs even when unfocused, so a click in progress always puts the cursor back.
            clicker.update(now)
            if not dry_run and not target.background:
                # The real cursor and mouse are the other toon's in two-toon mode.
                was_hidden = hider.hidden
                pos = cursor_pos()
                mouse_moved = hider.update(active, controller_used(state), pos, clicker.busy, clicker.moved_to)
                if debug and hider.hidden != was_hidden:
                    reason = "mouse moved" if mouse_moved else "controller used" if hider.hidden else "paused"
                    log(f"Cursor {'hidden' if hider.hidden else 'shown'} ({reason}) at {pos[0]},{pos[1]}, "
                        f"module last moved it to {clicker.moved_to}")
                if active and (mouse_moved or (not clicker.busy and mouse_button_down())):
                    mouse_paused = True
                    log("Mouse in use: controller paused. Press any controller button to resume."
                        + (f" ({'moved' if mouse_moved else 'button'})" if debug else ""))
            overlay_view = TTRView(target.hwnd, target.background) if active and target.hwnd else None
            above = target.hwnd if target.background else None
            if highlighter is not None:
                view = overlay_view
                if highlight is not None and view is not None and presenting:
                    # (Not `target`: that's the window the controller drives.)
                    framed, (w, h), color, pointer = highlight
                    left, top, width, height = client_rect(view.hwnd)
                    unit = min(width, height)
                    x, y = view.to_screen(framed)
                    w, h = round(w * unit), round(h * unit)
                    if pointer:
                        highlighter.show_pointer(x - w // 2, y, unit)
                    else:
                        highlighter.show((x - w // 2, y - h // 2, w, h), unit, *([color] if color else []))
                else:
                    highlighter.hide()
                highlighter.pump()
            if hint_drawer is not None:
                view = overlay_view
                pieces = []
                if config.hints and hints and view is not None and presenting:
                    left, top, width, height = client_rect(view.hwnd)
                    pieces = hint_drawer.pieces(hints, width, height, now, config.hints_scale)
                while len(hint_windows) < len(pieces):
                    hint_windows.append(Highlighter())
                    hint_windows[-1].attach(bound_to[1])
                for i, window in enumerate(hint_windows):
                    if i < len(pieces):
                        # Redrawn only when its key changes.
                        key, image, x, y = pieces[i]
                        window.show_image(left + x, top + y, image, (key, left, top), raise_it=False)
                    else:
                        window.hide()
                    window.pump()
                # Every frame, so they stay above TTR: all at once in a fixed order (later
                # hints on top), so overlapping ones don't flicker.
                stack(hint_windows[:len(pieces)][::-1], above=above)
            if aimer is not None:
                view = overlay_view
                if golf_aim is not None and view is not None and presenting:
                    unit = min(client_rect(view.hwnd)[2:])
                    px, py = view.to_screen(PIVOT)
                    key = (px, py, round(golf_aim, 2), unit)
                    image, (ox, oy) = aim_image(round(AIM_RADIUS * unit), golf_aim, unit)
                    aimer.show_image(px - ox, py - oy, image, key)
                else:
                    aimer.hide()
                aimer.pump()

            time.sleep(max(0.0, FRAME_SECONDS - (time.monotonic() - now)))
    except KeyboardInterrupt:
        log("Quitting.")
    finally:
        clicker.release()
        hider.show()
        if highlighter is not None:
            highlighter.close()
        if aimer is not None:
            aimer.close()
        for window in hint_windows:
            window.close()
        output.release_all()
        reader.close()
