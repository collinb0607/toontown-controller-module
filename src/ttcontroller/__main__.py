import argparse
from pathlib import Path

from .app import run


def main() -> None:
    parser = argparse.ArgumentParser(prog="ttcontroller", description="Controller support for Toontown Rewritten.")
    parser.add_argument("--ttr-dir", type=Path, help="TTR install folder (default: detected from the running game)")
    parser.add_argument("--dry-run", action="store_true", help="print keys instead of sending them, even when TTR isn't focused")
    parser.add_argument("--debug", action="store_true", help="log button presses and every key sent")
    args = parser.parse_args()
    run(ttr_dir=args.ttr_dir, dry_run=args.dry_run, debug=args.debug)


if __name__ == "__main__":
    main()
