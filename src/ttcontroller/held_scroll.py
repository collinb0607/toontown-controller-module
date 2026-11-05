"""Holding a direction on a list's scroll triangle.

TTR's scroll triangles (the friends list, the Fishing Bucket, Golf's Records) scroll
once per click, and faster while held down. So the first press clicks the triangle
like any other, and if that direction is still held when it would repeat, the mouse
button is held down on the triangle instead, until the direction is let go.
"""

from collections.abc import Iterable

from . import ui
from .battle import PointerCommand


class HeldScroll:
    def __init__(self) -> None:
        self._action: str | None = None  # the direction that just clicked a triangle
        self._arrow: ui.UIPoint | None = None
        self._after: list[PointerCommand] = []  # what to do once let go of
        self.holding = False

    def clicked(self, action: str, arrow: ui.UIPoint, after: Iterable[PointerCommand] = ()) -> None:
        """A triangle was just clicked for action; `after` runs when a hold on it ends."""
        self._action, self._arrow, self._after = action, arrow, list(after)
        self.holding = False

    def repeat(self, action: str) -> list[PointerCommand] | None:
        """For an action that fired: None if it isn't the held scroll's, else what to do
        (hold the button down the first time, then nothing while it's held)."""
        if action != self._action or self._arrow is None:
            return None
        if self.holding:
            return []
        self.holding = True
        return [PointerCommand("hold", self._arrow, "hold scroll")]

    def update(self, held_actions: set[str]) -> list[PointerCommand]:
        """Each frame, with the actions whose buttons are down: lets go once it's released."""
        if self._action is None or self._action in held_actions:
            return []
        return self.stop()

    def stop(self, finish: bool = True) -> list[PointerCommand]:
        """Let go (and, with finish, do what comes after) if it's held; forget it either way."""
        commands = [PointerCommand("release", self._arrow, "stop scrolling")] if self.holding else []
        if self.holding and finish:
            commands += self._after
        self._action, self._arrow, self._after, self.holding = None, None, [], False
        return commands
