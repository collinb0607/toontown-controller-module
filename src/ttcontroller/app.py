"""Main loop: read the controller, map it, and send keys while TTR is focused.

Each frame: poll the controller, follow the target window, hand the screen reads to
pipeline.ReadWorker (its own thread) every BATTLE_CHECK_SECONDS and take its newest result,
decide which screen owns the controller (routing.route), run that screen's mapper and the
overworld's, and draw the overlay (the highlight frame, the hints, the name keyboard, the
golf aim)."""

import ctypes
import sys
import threading
import time
from pathlib import Path
from typing import Callable

from . import config as module_config
from . import hints as hint_layout
from . import keyboard_draw, name_keyboard, overlay, ttr_settings, ui, window_capture
from .battle import BattleMapper
from .boarding import BoardingMapper
from .book import CODE_PANEL_SIZE, CODE_PANEL_TOP, BookMapper
from .combo import ButtonCombo
from .controller import NEUTRAL, ControllerReader
from .cursor import MOVE_TOLERANCE, CursorHider
from .dialog import DialogMapper
from .facility import FacilityMapper
from .fishing import FishingMapper, FishingScreen
from .friends import FriendsMapper
from .garden import GardenMapper, GardenScreen
from .garden_intro import GardenIntro, GardenIntroMapper
from .golf_green import AIM_RADIUS, PIVOT, GolfGreenMapper, aim_image
from .hint_draw import FAMILY_NAMES, Drawer, find_sheet, pictures_for
from .hud import HudMapper, HudScreen
from .keyboard_watch import KeyboardWatcher
from .mailbox import MailboxMapper, MailboxScreen
from .makeatoon import MakeAToonMapper
from .mapper import OverworldMapper, controller_buttons
from .npc import NpcMapper
from .options import OptionsMapper, OptionsScreen
from .output import KeyboardOutput, MouseClicker, cursor_pos, mouse_button_down, posted_output, send_key, type_text
from .overlay import Highlighter, stack
from .pipeline import Gates, Guard, Reads, ReadWorker, changes
from .pregame import PregameMapper
from .routing import FREE_ORDER, route, share
from .boarding import BoardingScreen
from .facility import FacilityScreen
from .shop import ShopMapper
from .silly import SillyMapper, SillyScreen
from .speedchat import SpeedchatMapper
from .ttr_api import TOKEN_FILE, ToonWatcher, away_from_estate, may_be_in, may_fish, rumble_for
from .window import (BoundTarget, ForegroundTarget, ForegroundWatcher, TargetChoice, TTRView,  # noqa: F401
                     client_rect, focus_window, make_dpi_aware, ttr_windows, window_pid)
from .window_switch import next_window

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
        on_status: Callable[[str | None, bool, bool, str | None, str | None], None] | None = None,
        choice: TargetChoice | None = None) -> None:
    """The module's loop, until Ctrl+C or `stop` is set. on_status(controller name, TTR in
    front, paused for the mouse, the controller toon's window's state in two-toon mode or
    None, the toon's name from TTR's Local API or None) is called whenever one of those changes. choice: which window to drive (two
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
    shop_mapper = ShopMapper(config.shop)
    npc_mapper = NpcMapper(config.npc)
    speedchat_mapper = SpeedchatMapper(config.speedchat)
    friends_mapper = FriendsMapper(config.friends)
    book_mapper = BookMapper(config.book)
    # The remappable screens' mappers, by their table's key (config.SCREEN_TABLES).
    table_mappers = {"battle": battle_mapper, "shop": shop_mapper, "npc": npc_mapper,
                     "speedchat": speedchat_mapper, "friends": friends_mapper, "book": book_mapper}
    hud_mapper = HudMapper()
    garden_mapper = GardenMapper(cache_path=module_config.CONFIG_DIR / "garden.json")  # the last flower's beans kept there
    garden_intro_mapper = GardenIntroMapper()  # the first-time gardening introduction's pages
    golf_mapper = GolfGreenMapper()  # the Cog Golf golf green puzzle
    golf_aim = None  # its aim angle, while aiming (for the aim line and crosshair)
    fishing_mapper = FishingMapper()  # a pond's dock: hold A to cast (M14)
    fishing_mapper.method = config.fishing_cast
    mailbox_mapper = MailboxMapper()  # the estate mailbox, open
    facility_mapper = FacilityMapper()  # Cog HQ facility nametags and their teleport popup
    boarding_mapper = BoardingMapper()  # the boarding group panel by a Cog HQ elevator
    silly_mapper = SillyMapper()  # the Silly Meter's card, open
    dialog_mapper = DialogMapper()  # an OK/Cancel dialog nothing else owns
    pregame_mapper = PregameMapper()  # the start-up screen and toon selection
    options_mapper = OptionsMapper()  # TTR's own Options window, over anything
    mat_mapper = MakeAToonMapper()  # Make-a-Toon, from an empty slot on toon selection
    # Every screen's mapper: all start over when the controller pauses.
    screen_mappers = (*table_mappers.values(), hud_mapper, garden_mapper, garden_intro_mapper, golf_mapper,
                      fishing_mapper, mailbox_mapper, facility_mapper, boarding_mapper, silly_mapper,
                      dialog_mapper, pregame_mapper, options_mapper, mat_mapper)
    # Walking around, the small screens that can show together (routing.FREE_ORDER).
    free_mappers = {"dialog": dialog_mapper, "garden": garden_mapper, "facility": facility_mapper,
                    "mailbox": mailbox_mapper, "hud": hud_mapper, "garden_intro": garden_intro_mapper,
                    "silly": silly_mapper, "boarding": boarding_mapper}
    assert tuple(free_mappers) == FREE_ORDER
    reads = Reads()  # what the screen readers last saw
    send = logged(send_key) if dry_run or debug else send_key
    output = KeyboardOutput(send)
    clicker = MouseClicker()
    hider = CursorHider()
    # TTR is read from its own window picture where Windows allows it, so the overlay
    # doesn't need to hide from capture and shows in recordings and streams; if that stops
    # working, the module reads the screen again and the overlay hides.
    if window_capture.supported():
        overlay.set_capture_exclusion(False)

        def capture_failed(reason: str) -> None:
            if overlay.set_capture_exclusion(True):
                log(f"Note: TTR's window can't be captured ({reason}), so the screen is read instead "
                    "and the hints won't show in recordings or streams.")
            else:
                log(f"Note: TTR's window can't be captured ({reason}), so the screen is read instead. "
                    "This Windows can't hide the hints, highlight frame and name keyboard from that "
                    "screen reading, so they're turned off.")
        window_capture.on_failure(capture_failed)
        if window_capture.borderless():
            log("Reading TTR's own window picture: the hints show in recordings and streams.")
        else:
            log("Reading TTR's own window picture, so the hints can show. Windows 10 draws a yellow "
                "border around TTR while it's read (only Windows 11 can leave it out).")
    # The screens are read on a thread of their own (pipeline.py).
    read_worker = ReadWorker(Guard(log, debug), lambda hwnd, background: TTRView(hwnd, background).snapshot())
    generation = 0  # goes up whenever the screens start over: a read asked for before is dropped
    highlighter = None if dry_run else Highlighter()
    if highlighter is not None and not highlighter.excluded and not window_capture.enabled():
        # A frame the module's own screen reading could see would throw it off.
        build = sys.getwindowsversion().build
        why = ("the overlay window couldn't be made" if not highlighter.hwnd
               else "Windows refused to hide the overlay from screen captures")
        code = f", error {highlighter.error}: {ctypes.FormatError(highlighter.error).strip()}" \
            if highlighter.error else ""
        log(f"Note: no hints, highlight frame or name keyboard: {why} (Windows build {build}{code}). "
            "The module reads the screen here, so anything it can't hide would throw it off. "
            "It needs Windows 10 version 2004 (build 19041) or later.")
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
    # Make-a-Toon's name keyboard (M14), in a window of its own. The art is
    # input_sprites/all_input.png; without it, Type-A-Name takes the real keyboard only.
    osk_drawer = osk_window = osk_key = osk_image = None
    if highlighter is not None:
        osk_sheet = keyboard_draw.find_sheet(module_config.CONFIG_DIR)
        if osk_sheet is None:
            log("Note: no on-screen keyboard for names (input_sprites/all_input.png wasn't found).")
        else:
            try:
                osk_drawer = keyboard_draw.KeyboardDrawer(osk_sheet, find_sheet(module_config.CONFIG_DIR))
                osk_window = Highlighter()
            except Exception as e:  # broken art shouldn't stop the controller
                log(f"Note: no on-screen keyboard for names ({e}).")
    # Whose button pictures the hints and the name keyboard show (the config's button_pictures,
    # or the controller in use); the last one tried, so a missing sheet is looked for once.
    pictures_tried: str | None = None
    hints = ()  # what the hints overlay shows now
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
            type_text(send, name)
        else:
            clicker.click(x, y, restore=restore, delay=delay)

    def do(commands, view, restore: bool = True) -> None:
        """Carry out a mapper's PointerCommands."""
        for c in commands:
            point(c.kind, c.point, c.name, view, restore=restore, notches=c.notches, delay=c.delay, size=c.size,
                  frame_at=c.frame_at, color=c.color, to=c.to, pointer=c.pointer)

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
    # LB + RB: a screenshot when let go; with D-pad left/right while held, the TTR window
    # to that side comes to the front (one toon).
    bumper_combo = ButtonCombo()
    switch_until = 0.0  # just switched windows: paused until then, so the screens start over
    last_holder: str | None = None  # the menu that may hold the mouse button down ("book"/"friends")
    log(("Running." if stop is not None else "Running. Press Ctrl+C to quit.")
        + (" (dry run: keys are printed, not sent)" if dry_run else ""))
    status = None
    # TTR's Local API, for the game the controller plays: laff (damage rumble), the toon's
    # name and ID, where it is and its Unites.
    toon_api = ToonWatcher(module_config.CONFIG_DIR / TOKEN_FILE, log=log,
                           places=module_config.CONFIG_DIR / "places.log")  # M14: what the location reads where
    toon_api.start()
    read_worker.start()
    # The real keyboard pauses the controller like the mouse (one toon only).
    keyboard_watch = KeyboardWatcher()
    if not dry_run:
        keyboard_watch.start()
        if not keyboard_watch.working:
            log("Note: the keyboard can't be watched, so typing won't pause the controller.")
    toon = toon_api.info

    try:
        while stop is None or not stop.is_set():
            now = time.monotonic()

            state = reader.poll()
            if reader.name != controller_name:
                controller_name = reader.name
                log(f"Controller connected: {controller_name} ({FAMILY_NAMES.get(reader.family, 'Xbox')} buttons)"
                    if controller_name else
                    "No controller connected. Waiting for one (press its Xbox, PS or Home button to wake it).")
            pictures = pictures_for(config.button_pictures, reader.family)
            if hint_drawer is not None and pictures is not None and pictures != pictures_tried:
                pictures_tried = pictures
                if hint_drawer.use(pictures, module_config.CONFIG_DIR):
                    log(f"Button pictures: {FAMILY_NAMES[pictures]}.")
                elif hint_drawer.family != pictures:
                    log(f"Note: no {FAMILY_NAMES.get(pictures, pictures)} button pictures "
                        f"({pictures}-spritesheet.png wasn't found); showing {FAMILY_NAMES[hint_drawer.family]}.")
                if osk_drawer is not None:
                    osk_drawer.use_buttons(hint_drawer.sprites)

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
                for window in (highlighter, aimer, osk_window, *hint_windows):
                    if window is not None:
                        window.attach(hwnd)
                ttr_focused = None
            target.update()
            ttr_path = target.path
            focused = dry_run or target.active
            if (focused, target.state) != ttr_focused:
                was_focused = ttr_focused is not None and ttr_focused[0]
                ttr_focused = (focused, target.state)
                if not dry_run:
                    if target.background:
                        log(TARGET_LOG[target.state])
                    elif focused and not was_focused and now >= switch_until:
                        # Brought to the front by the mouse or keyboard (a click, Alt+Tab, the
                        # taskbar): it waits for the controller, so nothing moves the cursor
                        # under the click that brought it up. (The LB + RB window switch is
                        # the controller's own, so that one stays active.)
                        mouse_paused = True
                        clicker.cancel()
                        log("TTR focused: press any controller button to take over.")
                    else:
                        log("TTR focused: controller active." if focused else "TTR not focused: controller paused.")
            toon_api.follow(window_pid(target.hwnd) if focused and target.hwnd else None)
            toon = toon_api.info
            garden_mapper.set_toon(toon.id)  # each toon keeps its own last flower
            mapper.unites_available = toon.unites != 0  # not known: as before
            leave_maybe = may_be_in(toon, "Cashbot HQ", "Bossbot HQ")  # CFO cranes, CEO seltzer and golf balls
            mapper.leave_possible = leave_maybe
            for change in toon_api.changes():
                rumble = rumble_for(change)
                if rumble is not None and config.rumble:
                    reader.rumble(*rumble)
                    if debug:
                        log(f"Laff {change.old} -> {change.new}/{change.max}: rumble {rumble}")
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
                    for key, table_mapper in table_mappers.items():
                        table_mapper.set_bindings(getattr(config, key))
                    fishing_mapper.method = config.fishing_cast

            # The real mouse and keyboard are checked before any screen runs, so the module
            # never moves the cursor (a hover, parking it) under the user's own click.
            # Taken every frame, so a key pressed while paused or in two-toon mode doesn't
            # pause the controller later.
            key_pressed = keyboard_watch.take()
            if not dry_run and not target.background:
                # The real cursor and mouse are the other toon's in two-toon mode.
                would_be_active = focused and not mouse_paused and not swapped and now >= switch_until
                was_hidden = hider.hidden
                pos = cursor_pos()
                mouse_moved = hider.update(would_be_active, controller_used(state), pos, clicker.busy,
                                           clicker.moved_to)
                if debug and hider.hidden != was_hidden:
                    reason = "mouse moved" if mouse_moved else "controller used" if hider.hidden else "paused"
                    log(f"Cursor {'hidden' if hider.hidden else 'shown'} ({reason}) at {pos[0]},{pos[1]}, "
                        f"module last moved it to {clicker.moved_to}")
                if would_be_active and (mouse_moved or (not clicker.busy and mouse_button_down())):
                    mouse_paused = True
                    clicker.cancel()
                    hider.show()
                    log("Mouse in use: controller paused. Press any controller button to resume."
                        + (f" ({'moved' if mouse_moved else 'button'})" if debug else ""))
                elif would_be_active and key_pressed:
                    mouse_paused = True
                    clicker.cancel()
                    hider.show()
                    log("Keyboard in use: controller paused. Press any controller button to resume.")
            if mouse_paused and (not focused or controller_used(state)):
                mouse_paused = False
                if focused:
                    log("Controller resumed.")
                    # Whatever the mouse opened is read right away.
                    next_battle_check = now
            # A swap starts like TTR losing focus: every screen and mapper starts over.
            active = focused and not mouse_paused and not swapped and now >= switch_until
            # The hints and frame show while the controller is in use; in two-toon mode the
            # controller toon's window is the controller's alone, so always.
            presenting = hider.hidden or target.background
            if on_status is not None and (controller_name, focused, mouse_paused, target_state(target),
                                          toon.name) != status:
                status = (controller_name, focused, mouse_paused, target_state(target), toon.name)
                on_status(*status)
            taken = read_worker.take()
            if not active:
                clicker.release()
                # The button that resumes the controller only resumes it: anything held
                # when it comes back does nothing until it's let go.
                mapper.reset(ignore_held=True)
                for screen_mapper in screen_mappers:
                    screen_mapper.reset_buttons()
                reads = Reads()
                generation += 1  # a read still running is from before: dropped
                output.release_all()
            else:
                view = TTRView(target.hwnd, target.background) if target.hwnd else None
                if taken is not None and taken[0] == generation:
                    if dry_run or debug:
                        for line in changes(reads, taken[1]):
                            log(line)
                    reads = taken[1]
                if view is not None and now >= next_battle_check and not read_worker.busy:
                    next_battle_check = now + BATTLE_CHECK_SECONDS
                    shown = mapper.shown
                    read_worker.request(target.hwnd, target.background, Gates(
                        estate=not away_from_estate(toon),  # gardening and the mailbox are only there
                        # Boss and Cog HQ screens only where they can show (the user, Nov 11); not known: everywhere.
                        cog_hq=may_be_in(toon, "Sellbot HQ", "Cashbot HQ", "Lawbot HQ", "Bossbot HQ"),
                        pies=may_be_in(toon, "Sellbot HQ", "Lawbot HQ"),  # the VP's pie round, the CJ's evidence
                        leave=leave_maybe, golf=may_be_in(toon, "Bossbot HQ"), fish=may_fish(toon),
                        hud_gags="showGags" in shown, hud_tasks="showTasks" in shown,
                        look_for_unite=speedchat_mapper.wants_unite,
                        friends_dialogs=friends_mapper.expects_dialog(now),
                        hints=hint_drawer is not None and config.hints), generation)

                state = state or NEUTRAL
                state, screenshot, step = bumper_combo.update(state, now)
                if step and not target.background and not dry_run:
                    windows = [hwnd for hwnd, _ in ttr_windows()]
                    after = next_window(windows, target.hwnd, step)
                    if after is not None and after != target.hwnd:
                        output.release_all()
                        clicker.release()
                        moved = focus_window(after)
                        switch_until = now + 0.2
                        log(f"Switched to the TTR window {'on the left' if step < 0 else 'on the right'} "
                            f"({windows.index(after) + 1} of {len(windows)})." if moved
                            else "Couldn't bring the next TTR window to the front.")
                if screenshot:
                    log("Screenshot (LB + RB).")
                    mapper.tap("screenshot", now)
                # The run prompt only follows a battle screen: one out of nowhere is another
                # dialog laid out the same (Ignore A Player's), not a battle.
                if reads.battle.kind is not None and (reads.battle.kind != "confirm_run"
                                                      or now - last_battle_seen < BATTLE_GRACE_SECONDS):
                    last_battle_seen = now
                if reads.shop.kind is not None:
                    last_shop_seen = now
                r = route(reads, battle_recent=now - last_battle_seen < BATTLE_GRACE_SECONDS,
                          shop_recent=now - last_shop_seen < BATTLE_GRACE_SECONDS)
                buttons = controller_buttons(state, config.timing.stick_button_threshold)
                if r.options:
                    do(options_mapper.update(buttons, now, reads.options), view, restore=False)
                else:
                    options_mapper.reset_buttons()
                    options_mapper.update(frozenset(), now, OptionsScreen())
                if r.mat:
                    do(mat_mapper.update(buttons, now, reads.mat), view, restore=False)
                else:
                    mat_mapper.reset_buttons()
                if r.pregame:
                    do(pregame_mapper.update(buttons, now, reads.pregame), view, restore=False)
                elif r.options:
                    pregame_mapper.pause()  # back to the same toon when Options closes over toon selection
                else:
                    pregame_mapper.reset_buttons()
                if r.shop:
                    do(shop_mapper.update(buttons, now, reads.shop), view, restore=False)
                else:
                    shop_mapper.reset_buttons()
                if r.shop and reads.shop.kind != "shop":
                    highlight = None
                if (r.speedchat or r.friends) and npc_mapper.choosing:
                    # The task panel is under it (speedchat can cover the panel, so it may
                    # not be read until speedchat closes).
                    npc_was_paused = True
                if r.npc:
                    if npc_was_paused:
                        npc_mapper.rehover()  # back on the task it was on
                        npc_was_paused = False
                    do(npc_mapper.update(buttons, now, reads.npc), view, restore=False)
                else:
                    npc_mapper.reset_buttons()
                    if not (r.npc_open or r.speedchat or r.friends):
                        # Gone (the panel's timer can close it): nothing to come back to.
                        npc_mapper.forget()
                        npc_was_paused = False
                for menu_open, menu_mapper, menu_screen in ((r.speedchat, speedchat_mapper, reads.speedchat),
                                                            (r.friends, friends_mapper, reads.friends),
                                                            (r.book, book_mapper, reads.book)):
                    if menu_open:
                        do(menu_mapper.update(buttons, now, menu_screen), view, restore=False)
                    else:
                        menu_mapper.reset_buttons()
                if r.battle and was_in_menu and not r.menu:
                    battle_mapper.rehover()
                was_in_menu = r.menu
                if r.battle and not r.menu:
                    # Battle clicks leave the cursor on the button, where the highlight is.
                    do(battle_mapper.update(buttons, now, reads.battle), view, restore=False)
                else:
                    battle_mapper.reset_buttons()
                if r.battle and not r.menu and reads.battle.kind not in ("picker", "trunk", "target"):
                    # The frame goes around gags, trunk items and target arrows; once those
                    # are gone (a gag clicked, the round over) it goes too.
                    highlight = None
                # In battle or the shop, their bindings own their buttons and the left stick doesn't walk.
                if r.options or r.mat:
                    blocked = buttons
                elif r.pregame:
                    blocked = pregame_mapper.buttons(reads.pregame)
                elif r.battle:
                    blocked = frozenset(battle_mapper.buttons(reads.battle))
                    if r.speedchat:
                        blocked |= speedchat_mapper.buttons(reads.speedchat)
                    elif r.friends:
                        blocked |= friends_mapper.buttons(reads.friends)
                elif r.shop:
                    blocked = frozenset(shop_mapper.buttons(reads.shop))
                elif r.npc:
                    blocked = frozenset(npc_mapper.buttons(reads.npc))
                elif r.speedchat:
                    blocked = frozenset(speedchat_mapper.buttons(reads.speedchat))
                elif r.friends:
                    blocked = frozenset(friends_mapper.buttons(reads.friends))
                elif r.book:
                    blocked = frozenset(book_mapper.buttons(reads.book))
                else:
                    blocked = frozenset()
                for control in book_mapper.take_taps():
                    mapper.tap(control, now)
                if book_mapper.take_left_page():
                    highlight = None
                # The book and friends list let go of their own holds while open (the kart, a
                # scroll triangle); one held when it closes, or the other opens, is let go here.
                if r.holder is None or r.holder != last_holder:
                    clicker.release()
                last_holder = r.holder
                if r.golf:
                    blocked = blocked | golf_mapper.buttons(reads.golf)
                    do(golf_mapper.update(buttons, state.left_stick, now, reads.golf), view, restore=False)
                    golf_aim = golf_mapper.angle
                else:
                    if golf_aim is not None or golf_mapper.angle is not None:
                        golf_mapper.reset()
                    golf_aim = None
                if r.fishing:
                    blocked = blocked | fishing_mapper.buttons(reads.fishing)
                    fishing_commands = fishing_mapper.update(buttons, state.left_stick, now, reads.fishing)
                else:
                    # Let go of a cast in progress when the dock goes (a popup, the book).
                    fishing_commands = fishing_mapper.update(frozenset(), (0.0, 0.0), now, FishingScreen())
                do(fishing_commands, view, restore=False)
                if fishing_mapper.take_switch():
                    log("Fishing: the stick " + ("moves the aim." if fishing_mapper.method == "move"
                                                 else "is the aim (where it points)."))
                    config_watcher.save_value("fishing_cast", fishing_mapper.method)
                    config = config_watcher.config
                # Walking around, the small screens showing, each with the buttons no screen
                # before it took (routing.share): a dialog first, as TTR's dialogs are modal.
                stray = reads.stray_dialog
                showing = {
                    # Not over gardening: its own popups are dialogs it reads itself.
                    "dialog": r.free and stray is not None and not reads.garden.is_open,
                    # The gardening HUD's buttons on Y and X, instead of showing gags and tasks.
                    "garden": r.free and reads.garden.is_open,
                    "facility": r.free and bool(facility_mapper.buttons(reads.facility)),
                    "mailbox": r.free and reads.mailbox.is_open,
                    "hud": r.free and reads.hud.kind is not None,
                    # The gardening introduction: A next (Done on the last page), B / D-pad left back.
                    "garden_intro": r.free and reads.garden_intro.is_open and stray is None,
                    # The Silly Meter's card: D-pad left its details, B closes the top card.
                    "silly": r.free and reads.silly.card and stray is None,
                    # The boarding group panel: the right stick opens and closes it; while open the
                    # D-pad and A work its list, and holding B leaves the group. Not over the HUD
                    # (it has the right stick) or a dialog (A and B are its).
                    "boarding": (r.free and reads.boarding.kind is not None and reads.hud.kind is None
                                 and stray is None),
                }
                free_screens = {"dialog": stray, "garden": reads.garden, "facility": reads.facility,
                                "mailbox": reads.mailbox, "hud": reads.hud, "garden_intro": reads.garden_intro,
                                "silly": reads.silly, "boarding": reads.boarding}
                shares = share((name, free_mappers[name].buttons(free_screens[name]))
                               for name in FREE_ORDER if showing[name])
                earlier: frozenset[str] = frozenset()
                for name in FREE_ORDER:
                    free_mapper, screen = free_mappers[name], free_screens[name]
                    if not showing[name]:
                        if name == "garden":
                            garden_mapper.reset_buttons()
                            garden_mapper.update(frozenset(), now, GardenScreen())
                        elif name == "hud":
                            hud_mapper.update(frozenset(), now, HudScreen())
                        elif name != "boarding":
                            free_mapper.reset_buttons()
                        continue
                    mine = shares[name]
                    blocked = blocked | mine
                    usable = buttons - earlier
                    if name == "facility":
                        usable = usable & mine
                    elif name == "boarding":
                        usable = usable & (mine | {"b"})  # holding B leaves (B isn't taken: it still closes menus)
                    restore = name not in ("hud", "boarding")
                    do(free_mapper.update(usable, now, screen), view, restore=restore)
                    earlier = earlier | mine
                controls = mapper.update(state, now, view, blocked=blocked, movement=r.walk, free=r.free,
                                         pies=reads.pies and r.free)
                output.sync(controls_to_keys(controls, watcher.settings))
                for button in mapper.take_clicks():
                    point("click", button.center, button.name, view)
                # Nothing to hover: while the cursor is hidden, leave it off the game area.
                # Book pages without controls of their own don't hover anything.
                idle = not (r.battle or r.shop or r.speedchat or r.friends or reads.npc.kind == "tasks" or r.golf
                            or (r.fishing and fishing_mapper.holding)
                            or (showing["hud"] and hud_mapper.hovering(reads.hud))
                            or (r.free and reads.garden.planting and garden_mapper.hovering(reads.garden))
                            or (r.book and book_mapper.hovering(reads.book))
                            or (r.pregame and pregame_mapper.hovering(reads.pregame))
                            or (showing["boarding"] and boarding_mapper.hovering(reads.boarding))
                            or (r.options and options_mapper.hovering(reads.options))
                            or (r.mat and mat_mapper.hovering(reads.mat)))
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
                    free = r.free
                    hints = hint_layout.hints_for(hint_layout.Context(
                        mode=r.mode, options=reads.options, options_row_y=options_mapper.row_y, mat=reads.mat,
                        mat_keyboard=mat_mapper.showing_keyboard(reads.mat),
                        book_keyboard=book_mapper.showing_keyboard(reads.book),
                        pregame=reads.pregame, toon_slot=pregame_mapper.slot, battle=reads.battle,
                        shop=reads.shop, friends=reads.friends, npc=reads.npc, book=reads.book,
                        book_task=book_mapper.hovered_task, fishing=reads.fishing,
                        fishing_cast=fishing_mapper.method, garden=reads.garden if free else GardenScreen(),
                        garden_intro=reads.garden_intro if free and stray is None else GardenIntro(),
                        mailbox=reads.mailbox if free else MailboxScreen(),
                        facility=reads.facility if free else FacilityScreen(),
                        silly=reads.silly if free else SillyScreen(),
                        boarding=reads.boarding if showing["boarding"] else BoardingScreen(),
                        dialog=stray if showing["dialog"] else None,
                        mail_close=reads.hint_mail_close, mail_icon=reads.hint_mail_icon, hop_off=reads.hint_hop,
                        leave=reads.hint_leave, hud=showing["hud"],
                        friends_button=reads.hint_friends, book_button=reads.hint_book,
                        walking_bar=config.hints_walking_bar, unites=toon.unites != 0,
                        tables=module_config.binding_tables(config)))
                    hint_drawer.hold_seconds = config.timing.hold_seconds
                    hint_drawer.press(buttons, now)
            # Runs even when unfocused, so a click in progress always puts the cursor back.
            clicker.update(now)
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
            if osk_window is not None:
                view = overlay_view
                keyboard_shown = None  # (keyboard, its top middle, its size)
                if mat_mapper.showing_keyboard(reads.mat):
                    submit = reads.mat.buttons[0]
                    keyboard_shown = (mat_mapper.keyboard,
                                      ui.UIPoint(submit.anchor, submit.x + name_keyboard.PANEL_DX,
                                                 submit.y + name_keyboard.PANEL_TOP_DY, submit.v_anchor),
                                      name_keyboard.PANEL_SIZE)
                elif book_mapper.showing_keyboard(reads.book):
                    keyboard_shown = (book_mapper.code_keyboard, CODE_PANEL_TOP, CODE_PANEL_SIZE)
                if view is not None and presenting and keyboard_shown is not None:
                    keyboard, top, size = keyboard_shown
                    unit = min(client_rect(view.hwnd)[2:])
                    x, y = view.to_screen(top)
                    key = (keyboard.keys, keyboard.row, keyboard.col, keyboard.hints, size, unit, x, y,
                           osk_drawer.buttons_family)
                    if key != osk_key:
                        osk_key = key
                        osk_image = osk_drawer.image(keyboard, unit, size)
                    osk_window.show_image(x - osk_image.shape[1] // 2, y, osk_image, key)
                else:
                    osk_window.hide()
                osk_window.pump()
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
        read_worker.stop()
        window_capture.stop_all()
        toon_api.stop()
        keyboard_watch.stop()
        clicker.release()
        hider.show()
        if highlighter is not None:
            highlighter.close()
        if aimer is not None:
            aimer.close()
        if osk_window is not None:
            osk_window.close()
        for window in hint_windows:
            window.close()
        output.release_all()
        reader.close()
