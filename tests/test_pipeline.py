"""The screen reading pipeline: every reader in order on one frame, guarded, on a thread."""

import json
import threading
from pathlib import Path

import numpy as np
import pytest

from ttcontroller.pipeline import Gates, Guard, Reads, ReadWorker, changes, read_all
from ttcontroller.screen import Frame

FIXTURES = Path(__file__).parent / "fixtures" / "battle"
EVERYTHING = Gates(hud_gags=True, hud_tasks=True, look_for_unite=True, friends_dialogs=True, hints=True)


def fixture_frame(name: str) -> Frame:
    """A recorded capture as a frame: the pixels the readers sampled, black elsewhere."""
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    bgra = np.zeros((h, w, 4), np.uint8)
    for key, (r, g, b) in data["pixels"].items():
        x, y = map(int, key.split(","))
        if 0 <= x < w and 0 <= y < h:
            bgra[y, x] = (b, g, r, 255)
    return Frame(w, h, bgra.tobytes())


def quiet_guard():
    lines = []
    return Guard(lines.append), lines


@pytest.mark.parametrize("size", [(0, 0), (1, 1), (2, 2), (10, 10), (1, 600), (600, 1), (3, 900), (160, 90)])
@pytest.mark.parametrize("fill", [0, 255, "noise"])
def test_no_reader_fails_on_odd_windows(size, fill):
    # A minimized window reads as 0x0; tiny and thin windows had readers dividing by zero
    # or indexing empty samples (the facility reader did), which stopped the controller.
    w, h = size
    n = w * h * 4
    data = (np.random.default_rng(1).integers(0, 256, n, dtype=np.uint8).tobytes() if fill == "noise"
            else bytes([fill]) * n)
    guard, lines = quiet_guard()
    read_all(Frame(w, h, data), EVERYTHING, guard)
    assert lines == []


def test_a_failing_reader_reads_as_not_showing_and_is_logged_once():
    guard, lines = quiet_guard()

    def broken(*_):
        raise ZeroDivisionError("division by zero")

    assert guard("facility", "default", broken, 1, 2) == "default"
    assert guard("facility", "default", broken, 1, 2) == "default"
    assert len(lines) == 1 and "facility reader failed" in lines[0] and "ZeroDivisionError" in lines[0]
    assert guard("facility", None, lambda: "fine") == "fine"


def test_reads_a_battle_from_a_recorded_capture():
    guard, lines = quiet_guard()
    reads = read_all(fixture_frame("battle_gags_1920x1009"), EVERYTHING, guard)
    assert reads.battle.kind == "picker" and reads.in_game
    assert not reads.book.is_open and reads.shop.kind is None and reads.npc.kind is None  # ruled out by the battle
    assert lines == []


def test_the_book_rules_out_the_screens_under_it():
    guard, _ = quiet_guard()
    reads = read_all(fixture_frame("book_trunk_1920x1009"), EVERYTHING, guard)
    assert reads.book.is_open and reads.book.page == "gags"
    assert reads.battle.kind is None and reads.npc.kind is None and reads.stray_dialog is None


def test_gates_keep_readers_off_where_their_screen_cant_show():
    calls = []
    guard = Guard(lambda line: None)
    real_call = Guard.__call__

    def spy(self, name, default, reader, *args):
        calls.append(name)
        return real_call(self, name, default, reader, *args)

    Guard.__call__ = spy
    try:
        read_all(Frame(400, 300, bytes(400 * 300 * 4)),
                 Gates(estate=False, cog_hq=False, pies=False, leave=False, golf=False, fish=False), guard)
    finally:
        Guard.__call__ = real_call
    for name in ("gardening", "gardening intro", "mailbox", "facility", "pie round", "golf green", "fishing",
                 "HUD", "Clarabelle", "Hop off", "leave button"):
        assert name not in calls, name
    assert {"Options", "book", "battle", "NPC", "speedchat", "friends list"} <= set(calls)


def test_changes_describe_what_appeared():
    guard, _ = quiet_guard()
    battle = read_all(fixture_frame("battle_gags_1920x1009"), EVERYTHING, guard)
    assert "Battle screen: picker" in changes(Reads(), battle)
    assert "Battle screen: none" in changes(battle, Reads())
    assert changes(battle, battle) == []


def test_the_worker_reads_on_its_own_thread():
    frame = fixture_frame("battle_gags_1920x1009")
    threads = []

    def snapshot(hwnd, background):
        threads.append(threading.current_thread().name)
        assert (hwnd, background) == (42, True)
        return frame

    worker = ReadWorker(Guard(lambda line: None), snapshot)
    worker.start()
    try:
        worker.request(42, True, EVERYTHING, generation=7)
        for _ in range(500):
            taken = worker.take()
            if taken is not None:
                break
            threading.Event().wait(0.01)
        assert taken is not None
        generation, reads = taken
        assert generation == 7 and reads.battle.kind == "picker"
        assert threads == ["screen-reads"]
        assert worker.take() is None  # handed back once
        assert not worker.busy
    finally:
        worker.stop()


def test_a_failing_capture_reads_as_nothing():
    lines = []

    def snapshot(hwnd, background):
        raise OSError("the window is gone")

    worker = ReadWorker(Guard(lines.append), snapshot)
    assert worker.read_now(1, False, Gates()) == Reads()
    assert "window capture" in lines[0]
