"""Hide the mouse cursor while the controller is in use, like a console game.

The module still moves the real cursor to hover and click on-screen buttons; it's
just not drawn. Another program's cursor can't be hidden directly, so while TTR
is focused and the controller is in use, Windows' own cursors are swapped for a
blank one. Moving the real mouse, or TTR losing focus, puts them back right away,
as does quitting (even by closing the console window).

TTR's own custom cursor (Options) isn't one of Windows' cursors, so it can't be
hidden this way.
"""

import atexit
import ctypes
from ctypes import wintypes

from .output import MOUSEEVENTF_MOVE, _send_mouse as send_mouse

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.CreateCursor.restype = wintypes.HANDLE
_user32.CreateCursor.argtypes = (wintypes.HINSTANCE, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_void_p, ctypes.c_void_p)
_user32.SetSystemCursor.argtypes = (wintypes.HANDLE, wintypes.DWORD)
_user32.SystemParametersInfoW.argtypes = (wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT)

SPI_SETCURSORS = 0x0057
# Arrow, I-beam, wait, crosshair, the resize arrows, move, no, hand, app starting, help.
_CURSOR_IDS = (32512, 32513, 32514, 32515, 32516, 32642, 32643, 32644, 32645, 32646, 32648, 32649, 32650, 32651)
_SIZE = 32
_AND = (ctypes.c_ubyte * (_SIZE * _SIZE // 8))(*([0xFF] * (_SIZE * _SIZE // 8)))  # keep the screen as is
_XOR = (ctypes.c_ubyte * (_SIZE * _SIZE // 8))()  # draw nothing

# A real mouse move is one the module didn't just make (its own moves can land a
# pixel off, from SendInput's 0..65535 coordinates).
MOVE_TOLERANCE = 3


def _redraw() -> None:
    """Windows only redraws the cursor when it moves, so nudge it a pixel and back. The
    nudge goes through the input queue, so it lands after any move the module just sent
    instead of putting the cursor back where that move started."""
    send_mouse(MOUSEEVENTF_MOVE, 1, 0)
    send_mouse(MOUSEEVENTF_MOVE, -1, 0)


def hide_system_cursors() -> None:
    for cursor_id in _CURSOR_IDS:
        # SetSystemCursor takes ownership of (and destroys) the cursor, so each needs its own.
        blank = _user32.CreateCursor(None, 0, 0, _SIZE, _SIZE, _AND, _XOR)
        if blank:
            _user32.SetSystemCursor(blank, cursor_id)
    _redraw()


def restore_system_cursors() -> None:
    """Reload the user's cursor scheme."""
    _user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, 0)
    _redraw()


_HANDLER = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)


@_HANDLER
def _on_console_event(_event: int) -> bool:
    # Ctrl+C, closing the console window, logging off: put the cursors back first.
    restore_system_cursors()
    return False


class CursorHider:
    def __init__(self, hide=hide_system_cursors, show=restore_system_cursors):
        self._hide, self._show = hide, show
        self.hidden = False
        self._last_pos: tuple[int, int] | None = None
        # In case a previous run was killed while the cursor was hidden.
        self._show()
        atexit.register(self.show)
        if hide is hide_system_cursors:
            ctypes.WinDLL("kernel32").SetConsoleCtrlHandler(_on_console_event, True)

    def show(self) -> None:
        if self.hidden:
            self.hidden = False
            self._show()

    def update(self, focused: bool, controller_used: bool, pos: tuple[int, int],
               module_moving: bool, module_pos: tuple[int, int] | None) -> bool:
        """controller_used: any button or stick input this frame. module_moving: the
        module is moving the cursor right now; module_pos: where it last put it.
        Returns whether the real mouse moved."""
        last, self._last_pos = self._last_pos, pos
        moved = last is not None and max(abs(pos[0] - last[0]), abs(pos[1] - last[1])) > MOVE_TOLERANCE
        by_module = module_moving or (module_pos is not None and max(abs(pos[0] - module_pos[0]),
                                                                       abs(pos[1] - module_pos[1])) <= MOVE_TOLERANCE)
        mouse_moved = moved and not by_module
        if not focused or mouse_moved:
            self.show()
        elif controller_used and not self.hidden:
            self.hidden = True
            self._hide()
        return mouse_moved
