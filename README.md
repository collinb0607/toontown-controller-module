# Toontown Controller Module

Play **Toontown Rewritten** with a controller.

Toontown Rewritten and Toontown Corporate Clash have no built-in controller support. This module runs alongside the game, reads your controller, and turns its input into the keyboard and mouse actions the game expects. Movement, battles, menus, the gag shop and boss fights all get controller support, with on-screen hints that show what each button does.

> **Status:** early development. Nothing is playable yet. See [plan.md](plan.md) for the full design.

## Planned features

- **Movement:** left stick to walk and turn, A to jump, L3 to sprint.
- **Battles:** move a highlight across your gags with the D-pad or stick, pick a target, hover teammates' gags with LB/RB, hold B to run.
- **Menus:** controller navigation for the shticker book, speedchat, friends list, settings, task choice and dialogue.
- **Gag shop:** buy one gag or buy max, and save/load presets.
- **Boss fights:** VP and CJ throwing, CFO crane, CEO charge attacks.
- **Trolley games:** support for each minigame.
- **Virtual cursor:** the right stick moves the mouse for any screen without dedicated support.
- **On-screen hints:** button prompts that change with what you're doing in game.
- **Remapping:** rebind any button for any game state.
- Works while the module window is unfocused, and never blocks your keyboard or mouse.

## Default controls

| State | Controls |
|---|---|
| Overworld | Left stick move · A jump · L3 sprint · LB select closest toon · RB friends list · D-pad left show gags · D-pad right show tasks · Start shticker book · View speedchat · hold Start game settings |
| Battle | Stick/D-pad move highlight · A select · B undo · hold B run · Y trunk · LB/RB hover teammates' gags |
| Gag shop | Stick/D-pad move highlight · A buy one · Y buy max · LB save preset · RB load preset · B done |
| Menus | Stick/D-pad move · A select · B back |
| Dialogue | A continue |
| Task choice | D-pad up/left/right/down pick option 1–4 · B cancel |
| VP / CJ | Hold RT to charge a throw, release to throw |
| CFO | Left stick move crane · hold X magnet · B leave |
| CEO | Left stick turn · hold X charge, release to fire · B leave |

## Requirements

- Windows 10 or 11
- An Xbox controller (more controllers planned)
- Toontown Rewritten running in **windowed** mode

## Roadmap

1. Project setup
2. Overworld movement (controller, window tracking, move/jump/sprint)
3. Overworld hotkeys
4. Overlay, hints and virtual cursor
5. Battle gag picker
6. Gag shop, dialogue, task choice and other menus
7. Settings window and remapping
8. Automatic game state detection
9. Boss fights
10. Trolley games and fishing
11. First release

**Later:** Toontown Corporate Clash, PlayStation/Switch controllers, Mac, borderless fullscreen, multi-toon.

## Development

Built with Python 3.12+, pygame-ce (controller input), pywin32 (keyboard/mouse output), PySide6 (settings window and overlay) and OpenCV (game state detection). Setup instructions will be added once there's code to run.

## Disclaimer

This is a fan project. It is not affiliated with or endorsed by Toontown Rewritten, Toontown Corporate Clash or Disney.
