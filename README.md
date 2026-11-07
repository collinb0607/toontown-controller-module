# Toontown Controller Module

Play **Toontown Rewritten** with a controller.

Toontown Rewritten's own controller support is experimental: it covers movement and a virtual mouse, but has no menu navigation and no remapping. This module runs alongside the game, reads your controller, and turns its input into the keyboard and mouse actions the game expects. Controller buttons press on-screen buttons for you directly, so you never have to steer a mouse cursor around. Every button can be remapped.

> **Status:** early development. Overworld controls, battles, the gag shop, NPCs, speedchat menus, the friends list, every page of the shticker book, the start-up screen, toon selection, TTR's own Options window, Make-a-Toon, boarding groups, gardening, the estate mailbox and the CFO and CEO fights work. Next: the hints overlay (M11). See [plan.md](plan.md) for the full design.

## Features

Working now:

- **Movement:** left stick to walk and turn (a small tilt walks, a full tilt runs), A to jump. Press LS (the left stick) to turn auto-sprint on or off: while it's on, every run (a full tilt, not a walk) starts with a sprint. The stick keeps walking while speedchat or the friends list is open.
- **Overworld hotkeys:** shticker book, options, gags, tasks, map, camera.
- **Friends list and speedchat:** open and close them with one button. The module checks the screen to see what's open, then clicks the right on-screen button and puts your mouse back.
- **Battles:** move a highlight across your gags with the D-pad or stick, pick a cog or toon, hover teammates' gags (LB, then left/right), pass, and hold B to run (A/B answer the "are you sure" prompt). Your last gag stays highlighted between rounds and battles.
- **Gag shop:** move across the gags, buy one or as many as fit, delete mode, and save/load your usual set. After a trolley game, exit to the playground or play again.
- **Talking to NPCs:** A clicks through speech bubbles; pick a ToonTask with the D-pad.
- **Speedchat menus:** move through the menus and submenus with the D-pad and say a phrase with A. Works with any speedchat color. LT jumps straight to UNITE! > Toon-Up, in battle too.
- **Friends list:** move down the list (it scrolls for you; hold the direction at the end to scroll fast), switch pages, open a toon, teleport to them (X) or whisper (Y). Nearby toons work too.
- **Shticker book:** LB/RB flip through the pages and LT/RT switch a page's tabs (like Gags and Trunk). Each page's own controls are next.
- **Trunk:** SOS cards (scrolling the list as you go, and filtering them from the dropdown or with LS), pink slips, remotes and doodle tricks, all with the D-pad or stick.
- **Remapping:** a config file lets you rebind any button.
- **Highlight frame:** where it's hard to tell what's hovered with the cursor hidden (battle gags, the trunk and the which cog/toon arrows, the gag shop, and the shticker book's Gags and Trunk tabs), a glowing frame is drawn around it, like a console game.
- **Hidden cursor:** the cursor disappears while you use the controller and comes back as soon as you move the mouse. When nothing needs hovering it waits on the window's title bar, out of the way. TTR's custom cursor can't be hidden and has no switch in TTR's Options, so set `"hide_cursor": true` in the config and the module turns it off in TTR's settings.json for you (it takes effect the next time TTR starts).
- **Mouse pauses the controller:** move or click the mouse in TTR and the controller pauses, like switching away from TTR. Press any controller button to resume (that press only resumes; it isn't sent).
- Uses your TTR keybinds automatically, works at any window size, and never blocks your keyboard or mouse.

Planned:

- **Make-a-Toon:** creating a toon with the controller, naming included.
- **Trolley games and fishing (after 1.0):** support for each minigame. Treasure Dive and Cannon already work with the existing controls.
- **On-screen hints:** button prompts that change with what you're doing in game.
- **Settings window:** remap buttons without editing a file.

## Default controls

Working now:

| Button | Overworld |
|---|---|
| Left stick | Move (small tilt walks) |
| A | Jump |
| B | Close speedchat or the friends list |
| LS (click the left stick) | Auto-sprint on/off |
| RS (click the right stick) | Switch camera |
| Right stick up/down | Look up/down |
| RB | Friends list (press again to close) |
| LB + RB | Take a screenshot (TTR's own Screenshot key), anywhere: walking, battles, the book |
| View | Speedchat (press again to close) |
| LT | Unite: opens speedchat at UNITE! with Toon-Up highlighted (in battle too) |
| RT | Clarabelle's mail: closes her popup if one is showing, otherwise clicks her icon (only while walking around with nothing else open; fires on letting go) |
| Hold RT | The Silly Meter (top right): opens it, or closes it if it's open · with it open: D-pad left the reward's details, B closes the top card |
| Y / X | Show gags / show tasks (while held, or press to show and again to hide with `toggle_hud`) |
| Gardening (its panel on the left) | Y clicks the top button (Pick, Plant Flower, Full) · X the bottom one (Water) · instead of showing gags and tasks · selling the basket: A Sell All, B Cancel |
| Cog HQ facility nametags (in the margins) | LB click the first facility's nametag (RB is still the friends list) · with its popup up: LB/RB the previous/next facility, A Teleport Here!, B close |
| Estate mailbox (open) | D-pad left/right go through the items · A take this item · X discard it · B close mailbox |
| Planting a gag tree (the gag panel) | Same as picking a gag in battle · B closes it (its red X) |
| Bean picker (Plant Flower) | D-pad left/right moves along the beans (wraps) · A adds the hovered bean (plants once no more beans fit) · Y plant · X reset · B cancel · D-pad up: the last flower you planted again (its beans put in and planted; remembered between runs) |
| "That didn't work" (a failed bean combination), and other OK-only popups like the new toon tutorial's | A or B clicks OK |
| Gags, trunk or tasks up (with `toggle_hud`) | D-pad hovers the gags, trunk items or tasks, as in the shticker book · right stick right/left switches from gags to the trunk and back · on the trunk: A clicks what's hovered (a tab, the SOS filter), right stick up/down scrolls the SOS cards, LS cycles the SOS filter (instead of auto-sprint, which LS still is on gags and tasks) · left stick still walks |
| D-pad up | Map (the same) |
| Start | Shticker book (tap) · Options (hold) |

| Battle screen | Controls |
|---|---|
| Gag picker | Stick/D-pad move highlight · A select · LB hover teammates' gags (left/right to choose, LB again to return) · X trunk · Y pass · hold B run |
| Which cog / toon? | Stick/D-pad left/right choose · A select · B back |
| Waiting for other toons | Hovers teammates' gags automatically · Stick/D-pad left/right choose · B back (change your gag) |
| Trunk | Stick/D-pad move between tabs and items · A use · LS next SOS filter · Right stick up/down scroll the SOS cards · LB hover teammates' gags · Y pass · B or X close |
| Run prompt | A OK · B cancel |

| Gag shop | Controls |
|---|---|
| Gags | Stick/D-pad move highlight · A buy one · Y buy max · X delete mode on/off · LB save preset · RB load preset · B done |
| After a trolley game | Same as Gags, but B exit to playground · RT play again |
| Delete mode | A delete one · Y delete all of that gag · X or B back to buying |
| Preset prompt | A OK · B cancel |

| Talking to NPCs | Controls |
|---|---|
| Speech bubble | A continue (or close the last one) |
| Choosing or handing in a ToonTask | Stick/D-pad up/down choose · A pick · B cancel |

| Menus | Controls |
|---|---|
| Speedchat | D-pad up/down move · right or A open a submenu · left or B go back · A say the phrase · B in the top menu closes speedchat |
| Friends list | D-pad up/down move (scrolls at the ends) · left/right change page · A open the toon · X Go To (teleport) · Y Whisper · RT Invite to your boarding group (near an elevator) · B close |
| Go To's "switch district?" popup | A Yes · B No |
| Friends on someone already a friend | A Stop being Toon friends · B Cancel · then "Are you sure?": A Yes · B No · "no longer your friend": A or B OK |
| Asking a toon to be friends | B Cancel (while waiting for their answer) |
| A toon asks to be your friend | A OK · B No |
| Other OK/Cancel popups while walking around (e.g. "teleport to your Estate?") | A OK · B Cancel |
| Ignore and Report (from a toon's panel) | A Ignore or Stop Ignoring · B Cancel · Report: D-pad up/down move through the reasons, A pick one, B Cancel |
| A toon's panel near an elevator | Its Invite (or Kick, for the leader) joins the up/down list last, after Toon Details: A clicks it, or RT straight away · inviting: B Cancel · invited: A OK, B No · declined: A or B OK |
| Whispering (the "Whisper To:" bar) | B ends the whisper (its X), after closing speedchat if it's open and before closing the toon's panel or the list |
| A toon's panel | D-pad up/down move between its buttons · A press · X Go To (teleport) · Y Whisper · B close Toon Details, then the panel |
| Shticker book | LB/RB previous/next page · LT/RT previous/next tab along the page's top · B close |
| Options & Codes page | Stick/D-pad up/down move · left/right change the SpeedChat color · A press · Exit Toontown's dialog: A OK · B cancel |
| Districts page | Stick/D-pad up/down choose the district above/below (wraps around) · A Teleport Here! · SpeedChat-only confirm: A OK · B cancel |
| Map page | Stick/D-pad move to the nearest place that way (clouded places are skipped) · A go there · Y Go Home · X Back to Playground |
| Gags page | Gags tab: Stick/D-pad hover gags for their info (starts on the cupcake) · Trunk tab: like the battle trunk (Stick/D-pad move, A pick a tab or filter, LS next SOS filter, right stick up/down scroll the SOS cards), for hovering info |
| ToonTasks page | Stick/D-pad hover tasks (blank scrolls are skipped) · X delete the hovered task, if it has a trash can · its confirm: A Delete · B cancel |
| Resistance Rank page | Stick/D-pad left/right turn its pages |
| Cog Gallery page | Right stick up/left/right/down: the tie/gavel/dollar sign/bar graph suits · Stick/D-pad move between summon buttons · A open Issue a Cog Summons · there: up/down move · A summon · B close |
| Fishing page | Bucket: Stick/D-pad up/down pick the fish above/below (scrolls at the ends) · X release it (A OK · B cancel) · Album: up/down flip through species · Trophies: just to look at |
| Racing page | Customize: right stick left/right turn the kart · Stick/D-pad left/right hover the accessory icons · A pick one · Records: just to look at · Trophy: Stick/D-pad hover the trophies |
| Cog Disguise page | Stick/D-pad up/down pick the suit tab (Bossbot, Lawbot, Cashbot, Sellbot) · Stick/D-pad left/right click the blue arrows, where a suit has them |
| Gardening page | Basket: Stick/D-pad up/down pick a flower (scrolling at the ends) · X release it · Album: Stick/D-pad up/down pick a collected flower · Right stick up/down the previous/next genus · Trophies, Specials: just to look at |
| Snapshots page | Stick/D-pad left/right flip through your snapshots · X delete the one shown · A Yep! / B Cancel |
| Events page | Calendar: opens on today's first event · Stick/D-pad move around the days, up/down going event by event (hovering one shows what it is) · Right stick left/right change month · L3 next filter (back to the first after the last) · Hosting, Invitations: nothing yet |
| Golf page | Records: Stick/D-pad or right stick up/down scroll the courses · Trophy: Stick/D-pad hover the trophies |
| Start-up screen | Start opens Options (Start or B closes it) · hold B to Quit · any other button enters |
| Toon selection | Start opens Options (Start or B closes it) · hold B to Quit · Stick/D-pad move between the toons (starting top middle) · A plays the toon, or makes one in an empty slot · X delete: A OK / B Cancel, then Y types "delete" and presses OK (A won't), B Cancel · Y Name Your Toon! (a toon whose name was skipped in Make-a-Toon) |
| TTR's Options | LT/RT previous/next tab · Stick/D-pad up/down move between settings (scrolling at the ends; a blue frame shows which) · A flip the toggle, open the dropdown or press the button · left/right turn a toggle off/on, or move a volume slider · Y show what the setting does (its ?), again to go back · right stick up/down scroll · B or Start close · in a dropdown: up/down (a long one scrolls at the ends), A pick, B close it · ToonSync code: A Copy, B Close · Pronoun Picker: left/right pick the list, up/down change it, X Reset, A or B Looks fine! |
| Make-a-Toon | LB/RB back/next step · B back a step (on the first step, or renaming a toon from Name Your Toon!: the X, cancel) · Start next (the check mark on the Name step) · right stick left/right turn the toon · Style: left/right pick (a pulsing gold pointer shows which), A choose · Type, Color, Clothes: up/down move between rows and Shuffle (the pointer), left/right click the row's arrows, A or X Shuffle · Name: left/right pick the list (Title, First, Last's two), up/down scroll it (hold to scroll fast), A tick its checkbox, X Shuffle, Y Type-A-Name (type with the keyboard; A Submit, Y or B back to Pick-A-Name), RT submit the toon without a name yet (the arrow above the check mark) · dialogs: A Yes / Continue Submission / Enter Toontorial, B No / Cancel Submission / Skip Toontorial |

| Boss fights | Controls |
|---|---|
| VP pie round, CJ evidence round | RT throws (TTR's throw key, Delete by default): press for one, hold to wind up, as with the key |
| CJ cannon round | Same as the trolley's Cannon game (already works) |
| CFO | Left stick move crane · hold X magnet · B leave the crane (clicks its red X) |
| CEO | Left stick turn · hold X charge, release to fire · B leaves the seltzer bottle or golf ball (clicks its red X) |
| Elevators and golf karts | B Hop off (with speedchat open, B closes it first, and B again hops off) |
| Boarding groups (by a Cog HQ elevator) | Right stick right opens the panel (the tab at the left edge), left closes it · while open: D-pad up/down hover a member (Start a Group is hovered as soon as it opens), A click it (a member opens their toon panel) · hold B leave the group (or disband it, as leader): A Yes / B No · "You cannot leave this area": A or B Cancel · walking still works |
| Cog Golf golf green (colored balls) | Left stick aims (an aim line and crosshair show where) · D-pad left/right fine-tune the aim · A shoot · Y How to Play · hold B Exit for Now |

## Requirements

- Windows 10 or 11
- An Xbox controller (more controllers planned)
- Toontown Rewritten running in **windowed** mode
- TTR's built-in controller support turned **off** (Options > Controls), or each button will act twice

## Changing controls

On first run the module creates `%APPDATA%\ToontownControllerModule\config.json`. Edit it while the module is running and changes apply right away. The `_help` section at the top lists every button name and action.

```json
"bindings": {
  "press": {
    "x": "performAction",
    "dpad_up": null
  },
  "hold": {
    "start": "options"
  }
}
```

- **`press`:** button → action. An action is any TTR control name from TTR's Options > Controls (e.g. `jump`, `showGags`), or one of `sprint`, `friendsList`, `speedchat`, `unite` or `back`. The triggers are `lt` and `rt`. Set a button to `null` to unbind it.
- **`hold`:** button → action after holding it for `timing.hold_seconds`. That button's `press` action then fires as a tap when it's released early.
- **`movement`** and **`timing`** hold the stick deadzone, walk threshold, hold time and sprint timing. **`auto_sprint`** (true or false) is the auto-sprint setting; LS flips it and saves it here. **`toggle_hud`** (true or false, default false): when true, the map, tasks and gags buttons show them on one press and hide them on the next, instead of only while held.

If something in the file is wrong, the console prints `Config problem: ...` and the module uses the default for that setting.

## Roadmap

1. ~~Project setup~~
2. ~~Overworld movement~~
3. ~~Overworld hotkeys, friends list, speedchat open/close, config file~~
4. ~~Battles~~ (including teammate hover, Toon-Up targets and the trunk)
5. ~~Gag shop, NPC dialogue and task choice, speedchat menus, friends list~~ (plus the Unite hotkey, hidden cursor and auto-sprint)
6. Shticker book
7. Settings window
8. Boss fights
9. Trolley games and fishing
10. On-screen hints overlay
11. First release

**After 1.0:** two toons on one machine (one on keyboard and mouse and one on a controller, or a controller each), minigames, Toontown Corporate Clash, PlayStation/Switch controllers, Mac, borderless fullscreen.

## Development

Built with Python 3.12+ and pygame-ce (controller input). Keyboard and mouse output, window tracking and screen reading use the Windows API directly. PySide6 (settings window and overlay) comes in a later milestone.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

# Run it (controls only work while the TTR window is focused)
.\.venv\Scripts\ToontownControllerModule.exe

# Print the keys it would send instead of sending them
.\.venv\Scripts\ToontownControllerModule.exe --dry-run

# Log every button press, key and click while playing
.\.venv\Scripts\ToontownControllerModule.exe --debug

# Run the tests
.\.venv\Scripts\python.exe -m pytest
```

The module reads your keybinds from TTR's `settings.json`, so rebinding keys in TTR's Options works automatically.

### Adding an on-screen button

TTR's 2D UI scales with the window's shorter side, and each element is pinned to an edge or the center. Positions in [src/ttcontroller/ui.py](src/ttcontroller/ui.py) are stored as an anchor plus offsets in units of the shorter side, so they work at any window size.

1. Capture the screen with the button showing: `.\.venv\Scripts\python.exe tools\capture_ttr.py NAME`, then click into TTR within 3 seconds.
2. Capture again at a different window size, including a tall one if you can.
3. Measure the button in both and check that the anchored offsets agree.
4. If the module needs to detect whether the button is showing, add probe points where a known color shows, then make test crops with `tools\make_fixture.py`.

## Disclaimer

This is a fan project. It is not affiliated with or endorsed by Toontown Rewritten, Toontown Corporate Clash or Disney.
