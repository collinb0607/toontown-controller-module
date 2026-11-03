"""Main loop: read the controller, map it, and send keys while TTR is focused."""

import time
from pathlib import Path

from . import ttr_settings
from .controller import NEUTRAL, ControllerReader
from .mapper import OverworldMapper
from .output import KeyboardOutput, send_key
from .window import ForegroundWatcher

FRAME_SECONDS = 1 / 120
SETTINGS_CHECK_SECONDS = 1.0


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


def controls_to_keys(controls: set[str], settings: ttr_settings.TTRSettings) -> set[str]:
    keys = set()
    for control in controls:
        if control in settings.controls:
            keys.update(settings.combo(control).names)
    return keys


def run(ttr_dir: Path | None = None, dry_run: bool = False, debug: bool = False) -> None:
    watcher = ttr_settings.SettingsWatcher(ttr_dir or ttr_settings.DEFAULT_TTR_DIR)
    log(f"Reading TTR settings from {watcher.path}")
    describe_settings(watcher.settings)

    def logged_send(name: str, down: bool) -> None:
        log(f"{'DOWN' if down else 'up  '} {name}" + ("" if dry_run else " (sent)"))
        if not dry_run:
            send_key(name, down)

    reader = ControllerReader()
    mapper = OverworldMapper()
    output = KeyboardOutput(logged_send if dry_run or debug else send_key)
    last_buttons = frozenset()
    foreground = ForegroundWatcher()

    controller_name = ""  # differs from None so the first poll logs either way
    ttr_focused = None
    next_settings_check = 0.0
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

            if not focused:
                mapper.reset()
                output.release_all()
            else:
                controls = mapper.update(state or NEUTRAL, now)
                output.sync(controls_to_keys(controls, watcher.settings))

            time.sleep(max(0.0, FRAME_SECONDS - (time.monotonic() - now)))
    except KeyboardInterrupt:
        log("Quitting.")
    finally:
        output.release_all()
        reader.close()
