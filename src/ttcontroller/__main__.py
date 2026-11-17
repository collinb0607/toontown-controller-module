import argparse
import ctypes
import sys
from pathlib import Path



def main() -> None:
    parser = argparse.ArgumentParser(prog="ttcontroller", description="Controller support for Toontown Rewritten.")
    parser.add_argument("--ttr-dir", type=Path, help="TTR install folder (default: detected from the running game)")
    parser.add_argument("--dry-run", action="store_true", help="print keys instead of sending them, even when TTR isn't focused")
    parser.add_argument("--debug", action="store_true", help="log button presses and every key sent")
    parser.add_argument("--settings", action="store_true", help="open the settings window instead")
    args = parser.parse_args()
    if args.settings:
        from .settings_window import main as settings
        settings()
        return
    from . import instance
    from .app import run
    # One copy at a time, as with the module's window: a second would fight the first
    # over the keys and the cursor.
    mutex = instance.claim()
    if mutex is None:
        print("Toontown Controller is already running (in its window or another console). "
              "Close that one first.")
        sys.exit(1)
    # So it's easy to find in Task Manager (the console window's title names it there).
    ctypes.WinDLL("kernel32").SetConsoleTitleW("Toontown Controller Module")
    try:
        run(ttr_dir=args.ttr_dir, dry_run=args.dry_run, debug=args.debug)
    finally:
        instance.release(mutex)


if __name__ == "__main__":
    main()
