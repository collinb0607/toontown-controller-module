**This is a beta.** Most of Toontown Rewritten already plays well on a controller, but some screens
are new and haven't been play-tested much yet, so expect the odd button that does nothing or a
screen that isn't recognised. Feedback is very welcome.

### Install
1. Download **Toontown-Controller-0.9-beta-2-Windows.zip** below and unzip it (right-click > Extract All).
2. Open the **ToontownController** folder and run **ToontownController.exe**. Keep the whole folder
   together: the exe needs the `_internal` folder beside it.
3. Windows may say "Windows protected your PC" because the app isn't signed: click **More info**,
   then **Run anyway**.

No Python or anything else to install. Windows 11, or Windows 10 version 2004 or later.

### New in beta 2
- Windows 10: the hints, highlight frame and name keyboard could be turned off at start-up
  even on a new enough Windows. The module now tries again, and if it still can't, the log
  says why.

### In Toontown Rewritten
- Play in **windowed** mode.
- Turn **off** TTR's own controller support (Options > Controls), or each button acts twice.
- Optional: turn on **Companion App Support** in TTR's Options for damage rumble and your toon's
  name. The first time, TTR asks to allow the module: press **OK**.

Xbox, PlayStation (DualShock 4, DualSense), Switch Pro, Joy-Con and Steam controllers work. The
controls are listed in the [README](https://github.com/collinb0607/toontown-controller-module#default-controls),
and every button can be changed in **Settings**.

### Found a problem?
Say what you were doing and what happened, and include the log: in the module's window click
**Show log**, or find `ttcontroller.log` in `%APPDATA%\ToontownControllerModule` (paste that into
File Explorer's address bar). You can also [open an issue](https://github.com/collinb0607/toontown-controller-module/issues).
