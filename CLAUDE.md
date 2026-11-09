# Toontown Controller Module

Xbox controller support for Toontown Rewritten (TTR) on Windows, in Python. It reads the
controller with pygame-ce, reads the TTR window's pixels to tell which screen is showing,
and sends keyboard keys and real mouse clicks (SendInput) to drive the game.

- Repo: `collinb0607/toontown-controller-module` (public). Plan and progress: [plan.md](plan.md).
  Player-facing controls: [README.md](README.md).
- Milestones done: M0 to M8 (overworld, hotkeys, battles, menus, the whole shticker book,
  start-up, toon selection, TTR's Options window, auto-detection), M10 (Make-a-Toon and
  boarding groups) and M11 (hints overlay). Boss fights (M9) started early: CFO, CEO
  and the CJ's cannon round work; the VP's pie round and the CJ's evidence round (one
  reader) are built, waiting on testing in game. M12 settings window is built (Nov 8),
  waiting on testing. Then M13 two toons on one machine (moved into 1.0 Nov 8), then M14 release (1.0).
  Minigames are in Future, not 1.0. M13: a keyboard-and-mouse toon plus a controller toon driven by posted
  window messages: paced clicks, hover by a middle-button press since TTR ignores posted
  mouse moves; findings and experiments are in plan.md and tools/background_*. M3 no longer
  exists (the hints overlay was M3); done milestones keep their numbers because commit
  messages use them.

## Working with the user

- The user tests every change in game before it counts as done. Describe changes as built
  and tested in unit tests, not verified in game, until they say it works.
- **Commit and push only when the user says so.** Commit messages end with the
  Co-Authored-By line. One commit per milestone or page, named like "M6: Fishing page".
- Planning goes in plan.md, never the user's .docx. Each feature gets a Progress entry in
  plan.md ("built, not yet tested in game", then "done and tested in game") and a controls
  row in README.md.
- The user isn't worried about TTR's terms of service. Keep the user's config values. Back
  up config.json before rewriting it.
- New screens come from the user's screenshots, taken with
  `python tools/capture_ttr.py <screen>_<what>` into `captures/` (gitignored: screenshots
  are never published). The user says what each button should do; ask when it's unclear.

### Standing UI preferences

- **No gold highlight frame unless the user asks for it on that screen.** Many hovers
  show themselves (a lifted scroll, a tinted trophy).
- **A new page or screen starts with nothing hovered.** The first stick or D-pad press
  hovers the first item. Exceptions the user asked for: the Events calendar opens on
  today's first event, toon selection opens on the top middle toon, and each Make-a-Toon
  step opens on its first item (the left style, the top row, the First name list).
- **After any popup is cancelled or confirmed, the hover goes back to the item it was
  opened from.**
- **A screen's controls must not swallow the global ones.** In the book, route only the
  page's own actions so LT/RT (top tabs), LB/RB (pages), B and Start still work. This bit
  several times (Racing, Golf, Calendar).
- Clickable lists: up/down click each row as you go (Districts, Fishing Bucket); past the
  ends, click the scroll triangles. Holding a direction holds the triangle down so TTR
  scrolls fast (`held_scroll.py`).
- Confirms: A = OK, B = Cancel. Destructive second confirms can require Y instead of A
  (toon deletion types "delete" and presses OK on Y only).
- LB + RB together takes a TTR screenshot (combo window 0.08 s; the user found 0.12 laggy).
  LT is Unite and must never be delayed.

## Commands

- Python: `.venv/Scripts/python.exe`. Tests: `PYTHONPATH="src;tests" .venv/Scripts/python.exe -m pytest -q`
  (semicolons on Windows). All tests must pass before handing work back.
- Run the module: `ToontownControllerModule` (a gui-script: `launcher.py`'s small window runs
  `app.run` on a thread with a stop event, shows status and the log, opens Settings as its own
  process, one copy at a time) or `ttcontroller` (the same in a console); `--debug`
  logs screens and clicks, `--dry-run` moves nothing. The settings window:
  `ToontownControllerSettings` (or `ttcontroller --settings`). Check its pages offscreen with
  `QT_QPA_PLATFORM=offscreen QT_QPA_FONTDIR=C:/Windows/Fonts` and `widget.grab().save(...)`.
- Record a test fixture from a capture: `PYTHONPATH="src;tests" .venv/Scripts/python.exe tools/record_pixels.py captures/<name>.png`.
  It runs every screen reader and saves only the pixels they sampled to
  `tests/fixtures/battle/<name>.json` (no whole screenshots in the repo). Tests replay them
  with `replay(name)`. When a reader starts sampling new pixels, older fixtures that
  replay through it raise KeyError: re-record those from their captures.
- Bash heredocs with nested quotes break here. Write multi-line patch scripts to the
  scratchpad with the Write tool and run them; a `patch(path, [(old, new)])` helper that
  asserts each old string occurs exactly once has worked well.

## Architecture

`app.py` is the main loop. Each frame (screens every 0.1 s) it snapshots the TTR window
(BitBlt `Frame`) and runs readers, in order, each skipped when an earlier one matched:

0. `options.read_options`: TTR's own Options window (and its dropdowns and popups), over
   anything; nothing else is read while it's open.
1. `makeatoon.read_make_a_toon` (its five steps and the name dialogs), then `pregame.read_pregame`:
   start-up screen, toon selection, and the delete confirms.
2. `book.read_book`: the shticker book. Read before the rest, because its pages fool them:
   a blank page looks like the battle waiting screen, the shop takes book dialogs, and the
   NPC search sees arrows in the SOS cards.
3. `battle.read_screen`, then `shop.read_shop`, then `npc.read_npc`.
4. `speedchat` and `friends`, which open over battles and the book and take buttons first.

Each screen has a **reader** (pixels to a frozen dataclass screen) and a **mapper**
(buttons + screen to `PointerCommand`s). `bindings.ButtonActions` turns buttons into
actions, with one-shots, repeats and hold actions. The overworld `mapper.OverworldMapper`
always runs; buttons a screen owns are passed as `blocked`, and `movement=False` stops
walking. Other modes send TTR keys through `mapper.tap(control)` (keys come from TTR's
settings.json via `ttr_settings`).

`PointerCommand(kind, point, name, notches, delay, size, frame_at)`:
- `kind` is "hover", "click", "scroll", "hold", "release" or "type" (types `name` letter by letter).
- `size` draws the gold highlight frame (`overlay.Highlighter`); `frame_at` puts the
  frame somewhere other than the hover point; `color` changes its color (Options' blue);
  `pointer` draws a pulsing gold pointer left of the item instead (Make-a-Toon).

Hints (M11): `hints.hints_for(Context)` says which button sprites go where for the screen
that owns the controller (badges on TTR's buttons, covers on popup buttons, small bars);
`hint_draw.Drawer.pieces` draws each as its own small overlay window (a press bounces its
badge). Style rules are in plan.md's M11 entry. Positions are mockup pixels at 1920x1009
kept relative to the button's own UIPoint (`_by(point, dx, dy)`). Hints on the seven
remappable screens carry `act=(table, actions, hold)` (`_walk`, `_bt`, `_sh`, `_fr`, `_np`,
`_bk`) and `hints_for` swaps in the config's button; give every new hint there an act.

Settings window (M12): `settings_window.py` (PySide6, Windows-style, follows the dark/light
theme) over `settings_model.py` (no Qt: tables, labels, move/swap, `SettingsStore` writing only
the touched keys of config.json, tables as differences from the defaults, backup first).
Run `ToontownControllerSettings` or `ttcontroller --settings`. A new action needs a label in
the table's `actions` in settings_model (a test checks every default action has one).

`output.MouseClicker` is a queue: click, hover, scroll, hold/release. `busy` includes holding.

### Coordinates

`ui.UIPoint(anchor, x, y, v_anchor)` stores offsets in units of the window's shorter side
from an anchor: horizontal left/center/right, vertical top/center/bottom. TTR's 2D UI
scales that way, so a point measured once works at any window size. Nearly everything was
measured at 1920x1009 (unit 1009, center 960,504.5). The book uses `_center(x, y)`; the
Quit/Options buttons are bottom-right anchored. Measure with a small pygame script over
the capture (`pygame.image.load(...).get_at`), then convert to units.

### Cursor and mouse

- The real cursor is the hover. While the controller is in use, Windows' cursors are swapped
  for blank ones (`cursor.CursorHider`), and the cursor parks on the title bar when nothing
  is hovered (the mapper's `hovering(screen)` decides).
- `hide_cursor` in the module config writes TTR's settings.json `video.enable-cursor`.
- Using the real mouse pauses the controller. Any controller input resumes it, and held
  buttons are ignored until released (`reset(ignore_held=True)`).
- Holds (kart turning, scroll triangles) are let go by their own mapper. The app forces a
  release only when neither the book nor the friends list is open, or when switching
  between them. Releasing every frame outside the book once broke friends-list holds.

## Hard-won lessons

- **Screens overlap and fool each other.** Order the readers, and require several
  independent probes per screen (a color at fixed spots plus a distinctive shape).
- **TTR redraws after a click.** Don't trust a read taken right after one. `_click` sets a
  settle time (0.25 s). The calendar is only kept once it reads the same for 0.15 s and
  differs from the month before (1.5 s fallback).
- **Popups cover things.** Event popups hide other days and even the book's page tabs. Read
  the layout once before hovering and cache it; keep the last known page when the current
  tab can't be told (`BookMapper._known`).
- Dimmed backdrops: a dialog over the book dims it (7,19,51); a dimmed screen still keeps
  hue, so test hue (yellowish, cyan) rather than brightness.
- Generic OK/Cancel dialogs: `dialog.find_ok_cancel` (red Cancel circle, OK level with it).
  Dialogs that aren't centered or don't dim (the Snapshots delete confirm, the "type delete"
  box) need their own detector.
- Page identity in the book: area-averaged 5x5 icon signatures, tried at -2..+2 px shifts,
  read for the current (pressed) tab only.
- Wrapped vs separate calendar lines: both lines stop short of the cell edge and the next
  line's first word wouldn't have fit (timed events run to the edge and get cut off).
  Colon detection for times was tried and misfired on letters like "e" and "o".
- Clicks must be real mouse input. Posting window messages was faster and invisible, but
  TTR missed some.
- TTR's custom cursor can't be turned off in its Options, only in settings.json.
- Expensive reads are fine at about 20 ms (calendar, SOS cards); keep pixel counts down
  by sampling every few pixels and stopping at the first empty row.
