import json
import os
from pathlib import Path

import numpy as np
import pytest

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

from ttcontroller.npc import TASK_CANCEL, NpcMapper, NpcScreen, find_bubble_button, read_npc  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"
CROPS = json.loads((FIXTURES / "npc" / "crops.json").read_text())


def bubble_frame(name):
    """The window with only its speech bubble (cropped from a capture) on a plain background."""
    meta = CROPS[name]
    w, h = meta["size"]
    x0, y0 = meta["at"]
    crop = np.ascontiguousarray(pygame.surfarray.array3d(pygame.image.load(str(FIXTURES / "npc" / f"{name}.png")))
                                .transpose(1, 0, 2))
    rgb = np.full((h, w, 3), (120, 90, 60), dtype=np.uint8)  # brownish, like the HQ floor
    rgb[y0:y0 + crop.shape[0], x0:x0 + crop.shape[1]] = crop
    return w, h, rgb


def replay(name):
    data = json.loads((FIXTURES / "battle" / f"{name}.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    return read_npc(w, h, lambda x, y: tuple(pixels[f"{x},{y}"]))


@pytest.mark.parametrize("name,last,at", [
    ("dialogue_1920x1009", False, (1346, 254)),
    ("dialogue_hover_1920x1009", False, (1345, 254)),
    ("dialogue_461x907", False, (408, 339)),
    ("dialogue_958x300", False, (594, 76)),
    ("dialogue_last_1920x1009", True, (1148, 252)),
    ("dialogue_last_hover_1920x1009", True, (1150, 257)),
])
def test_speech_bubble_button(name, last, at):
    w, h, rgb = bubble_frame(name)
    found = find_bubble_button(rgb)
    assert found is not None
    is_close, x, y = found
    assert is_close == last
    assert abs(x - at[0]) <= 3 and abs(y - at[1]) <= 3


def test_close_circle_under_the_last_line_of_text():
    # "Come back later if you need a ToonTask! Bye!": the "!" ends right over the circle.
    w, h, rgb = bubble_frame("dialogue_last_1920x1009")
    rgb[218:240, 1144:1158] = 20
    found = find_bubble_button(rgb)
    assert found is not None and found[0]
    assert abs(found[1] - 1148) <= 3 and abs(found[2] - 252) <= 3


def test_no_bubble():
    assert find_bubble_button(np.full((400, 600, 3), 255, dtype=np.uint8)) is None  # all white
    assert find_bubble_button(np.full((400, 600, 3), (120, 90, 60), dtype=np.uint8)) is None


@pytest.mark.parametrize("name", ["task_choice_1920x1009", "task_choice_659x890", "task_choice_958x300",
                                  "task_choice_hover_1920x1009"])
def test_task_choice(name):
    screen = replay(name)
    assert screen.kind == "tasks"
    assert [c.y for c in screen.choices] == pytest.approx([-0.444, -0.181, 0.081], abs=0.005)


@pytest.mark.parametrize("name", ["test_1920x1009", "speedchat_1920x1009", "options_1920x1009"])
def test_not_an_npc_screen(name):
    assert replay(name).kind is None


# --- Mapper ---

def press(m, screen, t, *buttons):
    out = m.update(frozenset(buttons), t, screen)
    return out + m.update(frozenset(), t + 0.01, screen)


def test_a_continues_the_conversation_and_only_a_is_taken():
    w, h, rgb = bubble_frame("dialogue_1920x1009")
    screen = read_npc(w, h, lambda x, y: tuple(int(v) for v in rgb[y, x]), rgb)
    assert screen.kind == "dialogue"
    m = NpcMapper()
    assert m.buttons(screen) == {"a"}  # B, the stick and speedchat still work
    assert m.update(frozenset(), 0.0, screen) == []  # no hover: nothing to pick
    assert [(c.kind, c.point) for c in press(m, screen, 1.0, "a")] == [("click", screen.button)]


def test_task_choice_up_down_choose_and_cancel():
    screen = replay("task_choice_1920x1009")
    m = NpcMapper()
    assert [c.point for c in m.update(frozenset(), 0.0, screen)] == [screen.choices[0]]
    assert press(m, screen, 1.0, "dpad_down")[-1].point == screen.choices[1]
    assert press(m, screen, 2.0, "ls_down")[-1].point == screen.choices[2]
    assert press(m, screen, 3.0, "dpad_down")[-1].point == screen.choices[2]  # stays at the bottom
    assert [(c.kind, c.point) for c in press(m, screen, 4.0, "a")] == [("click", screen.choices[2])]
    m.update(frozenset(), 5.0, screen)
    assert [c.point for c in press(m, screen, 6.0, "b")] == [TASK_CANCEL]


def test_one_task():
    screen = NpcScreen("tasks", choices=(TASK_CANCEL,), cancel=TASK_CANCEL)
    m = NpcMapper()
    m.update(frozenset(), 0.0, screen)
    assert press(m, screen, 1.0, "dpad_down")[-1].name == "task 1"
