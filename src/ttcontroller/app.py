"""Main loop: read the controller, map it, and send keys while TTR is focused."""

import time
from pathlib import Path

from . import config as module_config
from . import ttr_settings
from .battle import BattleMapper, BattleScreen, read_screen
from .controller import NEUTRAL, ControllerReader
from .mapper import OverworldMapper, controller_buttons
from .output import KeyboardOutput, MouseClicker, send_key
from .window import ForegroundWatcher, TTRView, make_dpi_aware

FRAME_SECONDS = 1 / 120
SETTINGS_CHECK_SECONDS = 1.0
# How often to look at the screen for battle panels.
BATTLE_CHECK_SECONDS = 0.1


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
    if settings.display_mode != "window":
        log(f"Note: TTR display mode is '{settings.display_mode}'. Windowed mode is recommended.")


def describe_config(watcher: module_config.ConfigWatcher, settings: ttr_settings.TTRSettings) -> None:
    for problem in watcher.warnings + module_config.unknown_actions(watcher.config, settings.controls):
        log(f"Config problem: {problem}")


def make_mapper(config: module_config.Config) -> OverworldMapper:
    return OverworldMapper(config.bindings, config.movement, config.timing)


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

    def logged_send(name: str, down: bool) -> None:
        log(f"{'DOWN' if down else 'up  '} {name}" + ("" if dry_run else " (sent)"))
        if not dry_run:
            send_key(name, down)

    reader = ControllerReader()
    config = config_watcher.config
    mapper = make_mapper(config)
    battle_mapper = BattleMapper(config.battle)
    battle_screen = BattleScreen()
    output = KeyboardOutput(logged_send if dry_run or debug else send_key)
    clicker = MouseClicker()
    last_buttons = frozenset()
    foreground = ForegroundWatcher()

    def point(kind: str, target, name: str, view, restore: bool = True, notches: int = 0) -> None:
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
            clicker.click(x, y, restore=restore)

    controller_name = ""  # differs from None so the first poll logs either way
    ttr_focused = None
    next_settings_check = 0.0
    next_battle_check = 0.0
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
                if config_watcher.check() is not None:
                    log("Module config changed, reloaded.")
                    describe_config(config_watcher, watcher.settings)
                    output.release_all()
                    config = config_watcher.config
                    mapper = make_mapper(config)
                    battle_mapper.set_bindings(config.battle)

            if not focused:
                mapper.reset()
                battle_mapper.reset_buttons()
                battle_screen = BattleScreen()
                output.release_all()
            else:
                view = TTRView(foreground.ttr_hwnd) if foreground.ttr_hwnd else None
                if view is not None and now >= next_battle_check:
                    next_battle_check = now + BATTLE_CHECK_SECONDS
                    frame = view.snapshot()
                    screen = read_screen(frame.width, frame.height, frame.get_pixel)
                    if screen.kind != battle_screen.kind and (dry_run or debug):
                        log(f"Battle screen: {screen.kind or 'none'}")
                    battle_screen = screen

                state = state or NEUTRAL
                in_battle = battle_screen.kind is not None
                if in_battle:
                    buttons = controller_buttons(state, config.timing.stick_button_threshold)
                    for command in battle_mapper.update(buttons, now, battle_screen):
                        # Battle clicks leave the cursor on the button, where the highlight is.
                        point(command.kind, command.point, command.name, view, restore=False,
                              notches=command.notches)
                else:
                    battle_mapper.reset_buttons()
                # In battle, the battle bindings own their buttons and the left stick doesn't walk.
                blocked = frozenset(battle_mapper.buttons) if in_battle else frozenset()
                controls = mapper.update(state, now, view, blocked=blocked, movement=not in_battle)
                output.sync(controls_to_keys(controls, watcher.settings))
                for button in mapper.take_clicks():
                    point("click", button.center, button.name, view)
            # Runs even when unfocused, so a click in progress always puts the cursor back.
            clicker.update(now)

            time.sleep(max(0.0, FRAME_SECONDS - (time.monotonic() - now)))
    except KeyboardInterrupt:
        log("Quitting.")
    finally:
        output.release_all()
        reader.close()
