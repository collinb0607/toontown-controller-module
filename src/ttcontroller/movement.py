"""Turn the analog left stick into TTR's digital movement controls."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MovementTuning:
    deadzone: float = 0.25
    # Tilting less than this (but past the deadzone) holds the walk key.
    walk_threshold: float = 0.7
    # sin(22.5 deg): splits the stick into 8 directions of 45 degrees each.
    direction_threshold: float = 0.38


def stick_to_movement(x: float, y: float, tuning: MovementTuning = MovementTuning()) -> set[str]:
    """Return the TTR controls to hold for a stick position.

    Uses SDL's convention where y is negative when the stick is pushed up.
    """
    magnitude = math.hypot(x, y)
    if magnitude < tuning.deadzone:
        return set()

    nx, ny = x / magnitude, y / magnitude
    t = tuning.direction_threshold
    controls = set()
    if ny < -t:
        controls.add("forward")
    elif ny > t:
        controls.add("reverse")
    if nx < -t:
        controls.add("left")
    elif nx > t:
        controls.add("right")
    if magnitude < tuning.walk_threshold:
        controls.add("walk")
    return controls
