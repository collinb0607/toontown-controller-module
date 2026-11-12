"""Measure where each button sits on a controller spritesheet (input_sprites/<family>-spritesheet.png).

All the sheets share one grid (four columns; D-pads, sticks and triggers, bumpers, face
buttons, stick clicks and the two small buttons). Some sprites' faint glow touches the next
row's, so each pair of columns is cut at its faintest row inside a window between two rows
(found per sheet: the PlayStation face buttons start higher than the others), and each
sprite's box is where its alpha is above GLOW inside its cell.

    .venv/Scripts/python.exe tools/measure_sprites.py playstation [--show out.png]

prints the RECTS and D-pad entries for hint_draw.py. --show saves the sheet with the boxes
drawn on it, to check by eye.
"""

import sys
from pathlib import Path

import pygame

SPRITES = Path(__file__).resolve().parents[1] / "input_sprites"
GLOW = 40  # alpha at or below this is glow, not the button
COLUMNS = ((100, 392), (392, 687), (687, 980), (980, 1275))
# Where the rows meet: windows to cut in, top to bottom (D-pad | stick/trigger | bumper/extra
# | face | stick click/small button).
CUT_WINDOWS = ((240, 275), (450, 505), (600, 645), (825, 895))

# Which sprite is in each cell: (column, band below the D-pads) -> name. The left columns'
# rows: stick, bumper, face, stick click; the right columns': trigger, extra, face, small button.
NAMES = {
    (0, 0): "L", (1, 0): "R", (2, 0): "LT", (3, 0): "RT",
    (0, 1): "LB", (1, 1): "RB", (2, 1): "EXTRA_L", (3, 1): "EXTRA_R",
    (0, 2): "A", (1, 2): "B", (2, 2): "X", (3, 2): "Y",
    (0, 3): "LS", (1, 3): "RS", (2, 3): "VIEW", (3, 3): "START",
}
DPAD_ORDER = ("up", "right", "down", "left")


def box(alpha, x0: int, y0: int, x1: int, y1: int):
    """The bounding box (x, y, w, h) of alpha > GLOW inside a cell, or None if it's empty."""
    cols = [x for x in range(x0, x1) if any(alpha[x][y] > GLOW for y in range(y0, y1, 2))]
    if not cols:
        return None
    rows = [y for y in range(y0, y1) if any(alpha[x][y] > GLOW for x in range(cols[0], cols[-1] + 1, 2))]
    # Exact edges (the scans above step by 2).
    left = min(x for x in range(max(x0, cols[0] - 2), cols[0] + 1) if any(alpha[x][y] > GLOW for y in range(rows[0], rows[-1] + 1)))
    right = max(x for x in range(cols[-1], min(x1, cols[-1] + 3)) if any(alpha[x][y] > GLOW for y in range(rows[0], rows[-1] + 1)))
    top = min(y for y in range(max(y0, rows[0] - 2), rows[0] + 1) if any(alpha[x][y] > GLOW for x in range(left, right + 1)))
    bottom = max(y for y in range(rows[-1], min(y1, rows[-1] + 3)) if any(alpha[x][y] > GLOW for x in range(left, right + 1)))
    return left, top, right - left + 1, bottom - top + 1


def cuts(alpha, x0: int, x1: int, height: int) -> list[tuple[int, int]]:
    """The rows (top, bottom) of the five bands in columns x0..x1: each cut is the faintest
    row in its window (the middle one of a run of equally faint rows)."""
    edges = [0]
    for lo, hi in CUT_WINDOWS:
        strength = [max(alpha[x][y] for x in range(x0, x1)) for y in range(lo, hi)]
        low = min(strength)
        faint = [lo + i for i, v in enumerate(strength) if v == low]
        edges.append(faint[len(faint) // 2])
    edges.append(height)
    return list(zip(edges, edges[1:]))


def measure(family: str):
    sheet = pygame.image.load(str(SPRITES / f"{family}-spritesheet.png"))
    alpha = pygame.surfarray.array_alpha(sheet)
    bands = {pair: cuts(alpha, COLUMNS[pair * 2][0], COLUMNS[pair * 2 + 1][1], sheet.get_height()) for pair in (0, 1)}
    rects = {}
    for (col, row), name in NAMES.items():
        x0, x1 = COLUMNS[col]
        y0, y1 = bands[col // 2][row + 1]
        found = box(alpha, x0, y0, x1, y1)
        if found:
            rects[name] = found
    dpads = {}
    for col, d in enumerate(DPAD_ORDER):
        x0, x1 = COLUMNS[col]
        y0, y1 = bands[col // 2][0]
        found = box(alpha, x0, y0, x1, y1)
        if found:
            dpads[d] = found
    return sheet, rects, dpads


def main() -> None:
    family = sys.argv[1] if len(sys.argv) > 1 else "xbox"
    sheet, rects, dpads = measure(family)
    alpha = pygame.surfarray.array_alpha(sheet)
    for pair in (0, 1):
        print(f"# cuts, columns {pair * 2}-{pair * 2 + 1}:",
              [b for b, _ in cuts(alpha, COLUMNS[pair * 2][0], COLUMNS[pair * 2 + 1][1], sheet.get_height())][1:])
    print(f"{family!r}: {{")
    for name, r in rects.items():
        print(f"    {name!r}: {r},")
    print("}")
    size = (max(r[2] for r in dpads.values()) + 6, max(r[3] for r in dpads.values()) + 6)
    centers = {d: (r[0] + r[2] // 2, r[1] + r[3] // 2) for d, r in dpads.items()}
    print(f"D-pad centers {centers}, crop {size}")
    if "--show" in sys.argv:
        out = sheet.copy()
        for r in list(rects.values()) + list(dpads.values()):
            pygame.draw.rect(out, (255, 0, 255), r, 2)
        pygame.image.save(out, sys.argv[sys.argv.index("--show") + 1])


if __name__ == "__main__":
    main()
