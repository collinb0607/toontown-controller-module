"""Main loop: read the controller, map it, and send keys while TTR is focused."""

import time
from pathlib import Path

from . import config as module_config
from . import ttr_settings
from .battle import BattleMapper, BattleScreen, read_screen
from .controller import NEUTRAL, ControllerReader
from .cursor import MOVE_TOLERANCE, CursorHider
from .book import BookMapper, BookScreen, read_book
from .friends import FriendsMapper, FriendsScreen, read_friends
from .mapper import OverworldMapper, controller_buttons
from .output import KeyboardOutput, MouseClicker, cursor_pos, mouse_button_down, send_key
from .npc import NpcMapper, NpcScreen, read_npc
from .shop import ShopMapper, ShopScreen, read_shop
from .speedchat import SpeedchatMapper, SpeedchatScreen, read_speedchat
from .window import ForegroundWatcher, TTRView, make_dpi_aware

FRAME_SECONDS = 1 / 120
SETTINGS_CHECK_SECONDS = 1.0
# How often to look at the screen for battle panels and the gag shop.
BATTLE_CHECK_SECONDS = 0.1
# A battle panel can vanish for a moment (a dialog fading in); stay in battle mode
# until none has shown for this long.
BATTLE_GRACE_SECONDS = 0.5
# Stick or trigger input past this counts as using the controller (to hide the cursor).
CONTROLLER_USE_THRESHOLD = 0.3


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


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


def make_mapper(config: module_config.Config) -> OverworldMapper:
    return OverworldMapper(config.bindings, config.movement, config.timing, config.auto_sprint)


def controls_to_keys(controls: set[str], settings: ttr_settings.TTRSettings) -> set[str]:
    keys = set()
    for control in controls:
        if control in settings.controls:
            keys.update(settings.combo(control).names)
    return keys


def run(ttr_dir: Path | None = None, dry_run: bool = False, debug: bool = False) -> None:
    make_dpi_aware()
    watcher = ttr_settings.SettingsWatcher(ttr_dir or ttr_settings.DEFAULT_TTR_DIR)
    log(f"Reading TTR settings from {watcher.path}")
    describe_settings(watcher.settings)
    config_watcher = module_config.ConfigWatcher()
    log(f"Module config: {config_watcher.path}")
    describe_config(config_watcher, watcher.settings)
    apply_hide_cursor(watcher, config_watcher.config.hide_cursor, False)

    def logged_send(name: str, down: bool) -> None:
        log(f"{'DOWN' if down else 'up  '} {name}" + ("" if dry_run else " (sent)"))
        if not dry_run:
            send_key(name, down)

    reader = ControllerReader()
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
    book_mapper = BookMapper(config.book)
    book_screen = BookScreen()
    output = KeyboardOutput(logged_send if dry_run or debug else send_key)
    clicker = MouseClicker()
    hider = CursorHider()
    last_buttons = frozenset()
    foreground = ForegroundWatcher()

    def point(kind: str, target, name: str, view, restore: bool = True, notches: int = 0,
              delay: float = 0.0) -> None:
        """Hover or click an on-screen point (a ui.UIPoint) in the TTR window."""
        if view is None:
            return
        x, y = view.to_screen(target)
        if dry_run or debug:
            log(f"{kind.capitalize()} {name} at screen {x},{y}" + (" (dry run, not moved)" if dry_run else ""))
        if dry_run:
            return
        if kind == "hover":
            clicker.hover(x, y)
        elif kind == "scroll":
            clicker.scroll(x, y, notches)
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
    log("Running. Press Ctrl+C to quit." + (" (dry run: keys are printed, not sent)" if dry_run else ""))

    try:
        while True:
            now = time.monotonic()

            state = reader.poll()
            if reader.name != controller_name:
                controller_name = reader.name
                log(f"Controller connected: {controller_name}" if controller_name else
                    "No controller connected. Waiting for one (press the Xbox button to wake it).")

            if debug and state is not None and state.buttons != last_buttons:
                last_buttons = state.buttons
                log(f"Buttons held: {', '.join(sorted(state.buttons)) or 'none'}")

            ttr_path = foreground.ttr_foreground()
            focused = dry_run or ttr_path is not None
            if focused != ttr_focused:
                ttr_focused = focused
                if not dry_run:
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
                    mapper = make_mapper(config)
                    battle_mapper.set_bindings(config.battle)
                    shop_mapper.set_bindings(config.shop)
                    npc_mapper.set_bindings(config.npc)
                    speedchat_mapper.set_bindings(config.speedchat)
                    friends_mapper.set_bindings(config.friends)
                    book_mapper.set_bindings(config.book)

            if mouse_paused and (not focused or controller_used(state)):
                mouse_paused = False
                if focused:
                    log("Controller resumed.")
                    # Whatever the mouse opened is read right away.
                    next_battle_check = now
            active = focused and not mouse_paused
            if not active:
                # The button that resumes the controller only resumes it: anything held
                # when it comes back does nothing until it's let go.
                mapper.reset(ignore_held=True)
                battle_mapper.reset_buttons()
                shop_mapper.reset_buttons()
                npc_mapper.reset_buttons()
                speedchat_mapper.reset_buttons()
                friends_mapper.reset_buttons()
                book_mapper.reset_buttons()
                battle_screen = BattleScreen()
                shop_screen = ShopScreen()
                npc_screen = NpcScreen()
                speedchat_screen = SpeedchatScreen()
                friends_screen = FriendsScreen()
                book_screen = BookScreen()
                output.release_all()
            else:
                view = TTRView(foreground.ttr_hwnd) if foreground.ttr_hwnd else None
                if view is not None and now >= next_battle_check:
                    next_battle_check = now + BATTLE_CHECK_SECONDS
                    frame = view.snapshot()
                    # The book can't open in battle or the shop, so it's read first and the
                    # rest are skipped while it's open: a blank white page looks like the
                    # battle's waiting screen, the shop takes a dialog over the book for its
                    # own, and the NPC bubble search finds false arrows in its pages.
                    book = read_book(frame.width, frame.height, frame.get_pixel)
                    screen = read_screen(frame.width, frame.height, frame.get_pixel) if not book.is_open else BattleScreen()
                    if screen.kind != battle_screen.kind and (dry_run or debug):
                        log(f"Battle screen: {screen.kind or 'none'}")
                    battle_screen = screen
                    if ((book.is_open, book.page, book.dialog is not None)
                            != (book_screen.is_open, book_screen.page, book_screen.dialog is not None)
                            and (dry_run or debug)):
                        log(f"Book: {'closed' if not book.is_open else 'dialog' if book.dialog else book.page or 'unknown page'}")
                    book_screen = book
                    shop = (read_shop(frame.width, frame.height, frame.get_pixel)
                            if screen.kind is None and not book.is_open else ShopScreen())
                    if shop.kind != shop_screen.kind and (dry_run or debug):
                        log(f"Gag shop screen: {shop.kind or 'none'}")
                    shop_screen = shop
                    npc = (read_npc(frame.width, frame.height, frame.get_pixel, frame.rgb())
                           if screen.kind is None and shop.kind is None and not book.is_open else NpcScreen())
                    if npc.kind != npc_screen.kind and (dry_run or debug):
                        log(f"NPC screen: {npc.kind or 'none'}")
                    npc_screen = npc
                    # Speedchat and the friends list work in battle too.
                    menus = shop.kind is None and npc.kind != "tasks"
                    speedchat = (read_speedchat(frame.width, frame.height, frame.get_pixel,
                                                look_for_unite=speedchat_mapper.wants_unite)
                                 if menus else SpeedchatScreen())
                    if speedchat.is_open != speedchat_screen.is_open and (dry_run or debug):
                        log(f"Speedchat menu: {'open' if speedchat.is_open else 'closed'}")
                    speedchat_screen = speedchat
                    friends = read_friends(frame.width, frame.height, frame.get_pixel) if menus else FriendsScreen()
                    if friends.kind != friends_screen.kind and (dry_run or debug):
                        log(f"Friends screen: {friends.kind or 'none'}")
                    friends_screen = friends

                state = state or NEUTRAL
                if battle_screen.kind is not None:
                    last_battle_seen = now
                if shop_screen.kind is not None:
                    last_shop_seen = now
                in_battle = now - last_battle_seen < BATTLE_GRACE_SECONDS
                in_shop = not in_battle and now - last_shop_seen < BATTLE_GRACE_SECONDS
                if in_shop:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    for command in shop_mapper.update(buttons, now, shop_screen):
                        point(command.kind, command.point, command.name, view, restore=False)
                else:
                    shop_mapper.reset_buttons()
                # NPC screens come and go with the conversation, so no grace period.
                in_npc = not (in_battle or in_shop) and npc_screen.kind is not None
                if in_npc:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    for command in npc_mapper.update(buttons, now, npc_screen):
                        point(command.kind, command.point, command.name, view, restore=False)
                else:
                    npc_mapper.reset_buttons()
                # Speedchat first when both are open: it closes as soon as a phrase is said.
                # Both are above battles too, which pause while one is open.
                in_speedchat = not (in_shop or in_npc) and speedchat_screen.is_open
                in_friends = not (in_shop or in_npc or in_speedchat) and friends_screen.kind is not None
                # The book is under both (speedchat and the friends list open over it).
                in_book = not (in_battle or in_shop or in_npc or in_speedchat or in_friends) and book_screen.is_open
                in_menu = in_speedchat or in_friends or in_book
                for menu_open, menu_mapper, menu_screen in ((in_speedchat, speedchat_mapper, speedchat_screen),
                                                            (in_friends, friends_mapper, friends_screen),
                                                            (in_book, book_mapper, book_screen)):
                    if menu_open:
                        buttons = controller_buttons(state, config.timing.stick_button_threshold)
                        for command in menu_mapper.update(buttons, now, menu_screen):
                            point(command.kind, command.point, command.name, view, restore=False,
                                  delay=command.delay)
                    else:
                        menu_mapper.reset_buttons()
                if in_battle and was_in_menu and not in_menu:
                    battle_mapper.rehover()
                was_in_menu = in_menu
                if in_battle and not in_menu:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    for command in battle_mapper.update(buttons, now, battle_screen):
                        # Battle clicks leave the cursor on the button, where the highlight is.
                        point(command.kind, command.point, command.name, view, restore=False,
                              notches=command.notches, delay=command.delay)
                else:
                    battle_mapper.reset_buttons()
                # In battle or the shop, their bindings own their buttons and the left stick doesn't walk.
                if in_battle:
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
                # Walking still works mid-conversation (it walks away); not while choosing a task.
                walk = not (in_battle or in_shop or in_book or npc_screen.kind == "tasks")
                for control in book_mapper.take_taps():
                    mapper.tap(control, now)
                controls = mapper.update(state, now, view, blocked=blocked, movement=walk)
                output.sync(controls_to_keys(controls, watcher.settings))
                for button in mapper.take_clicks():
                    point("click", button.center, button.name, view)
                # Nothing to hover: while the cursor is hidden, leave it off the game area.
                # Book pages without controls of their own don't hover anything.
                idle = not (in_battle or in_shop or in_speedchat or in_friends or npc_screen.kind == "tasks"
                            or (in_book and book_screen.hovers))
                if idle and hider.hidden and view is not None and not clicker.busy and not dry_run:
                    spot = view.park_spot()
                    # Checked against where the cursor really is: the mouse may have moved it.
                    pos = cursor_pos()
                    if spot is not None and max(abs(pos[0] - spot[0]), abs(pos[1] - spot[1])) > MOVE_TOLERANCE:
                        clicker.hover(*spot)
                if mapper.take_sprint_toggle():
                    log(f"Auto-sprint {'on' if mapper.auto_sprint else 'off'}.")
                    config_watcher.save_auto_sprint(mapper.auto_sprint)
                    config = config_watcher.config
                if mapper.take_unite():
                    speedchat_mapper.go_to_unite(now)
            # Runs even when unfocused, so a click in progress always puts the cursor back.
            clicker.update(now)
            if not dry_run:
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

            time.sleep(max(0.0, FRAME_SECONDS - (time.monotonic() - now)))
    except KeyboardInterrupt:
        log("Quitting.")
    finally:
        hider.show()
        output.release_all()
        reader.close()
