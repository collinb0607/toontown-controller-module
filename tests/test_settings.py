import json
import os

import pytest

from ttcontroller.bindings import Bindings
from ttcontroller.config import Config, parse
from ttcontroller.settings_model import (BUTTON_LABELS, BUTTON_SPRITES, TABLE_BY_KEY, TABLES, SettingsStore,
                                         action_label, bindings_of, clear, move, with_action)


def test_every_default_action_has_a_label():
    for table in TABLES:
        b = bindings_of(Config(), table)
        for action in list(b.press.values()) + list(b.hold.values()):
            assert action in table.actions, (table.key, action)


def test_every_row_has_a_label_and_a_sprite():
    for table in TABLES:
        for button in table.buttons:
            assert button in BUTTON_LABELS and button in BUTTON_SPRITES
        b = bindings_of(Config(), table)
        assert set(b.press) | set(b.hold) <= set(table.buttons), table.key


def test_walking_has_no_left_stick_rows():
    assert not any(b.startswith("ls_") for b in TABLE_BY_KEY["overworld"].buttons)


def test_move_to_a_free_button():
    b = Bindings(press={"rt": "mail"}, hold={"rt": "sillyMeter"})
    moved, clash = move(b, "rt", "lb")
    assert not clash
    assert moved.press == {"lb": "mail"} and moved.hold == {"lb": "sillyMeter"}


def test_move_swaps_on_a_clash():
    b = Bindings(press={"a": "jump", "y": "showGags"}, hold={"y": "options"})
    moved, clash = move(b, "a", "y")
    assert clash
    assert moved.press == {"y": "jump", "a": "showGags"} and moved.hold == {"a": "options"}


def test_clear_and_with_action():
    b = Bindings(press={"a": "jump"}, hold={"a": "options"})
    assert clear(b, "a") == Bindings(press={}, hold={})
    assert with_action(b, "b", "back", False).press == {"a": "jump", "b": "back"}
    assert with_action(b, "a", None, True).hold == {}
    assert action_label(TABLE_BY_KEY["overworld"], None) == "Not set"


def _store(tmp_path, data):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return SettingsStore(path), path


def test_store_writes_only_the_differences_and_keeps_other_keys(tmp_path):
    store, path = _store(tmp_path, {"hints": False, "my_note": "keep me"})
    table = TABLE_BY_KEY["battle"]
    b, _ = move(bindings_of(store.config, table), "y", "rb")
    store.set_bindings(table, b)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["my_note"] == "keep me" and data["hints"] is False
    assert data["bindings"]["battle"]["press"] == {"rb": "pass", "y": None}
    reread, warnings = parse(data)
    assert reread.battle.press["rb"] == "pass" and "y" not in reread.battle.press
    assert warnings == []


def test_store_walking_table_and_numbers(tmp_path):
    store, path = _store(tmp_path, {})
    walking = TABLE_BY_KEY["overworld"]
    store.set_bindings(walking, with_action(bindings_of(store.config, walking), "lb", "cameraPrev", False))
    store.set("deadzone", 0.3, "movement")
    store.set("controller", "Xbox One Controller")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["bindings"]["press"] == {"lb": "cameraPrev"}
    assert data["movement"]["deadzone"] == 0.3 and data["controller"] == "Xbox One Controller"
    config, _ = parse(data)
    assert config.bindings.press["lb"] == "cameraPrev" and config.movement.deadzone == 0.3


def test_store_backs_up_once(tmp_path):
    store, path = _store(tmp_path, {"hints": True})
    store.set("hints", False)
    backup = tmp_path / "config.backup.json"
    assert json.loads(backup.read_text(encoding="utf-8")) == {"hints": True}
    store.set("hints", True)
    assert json.loads(backup.read_text(encoding="utf-8")) == {"hints": True}  # still the first


def test_store_restore(tmp_path):
    store, path = _store(tmp_path, {"bindings": {"battle": {"press": {"y": None}}}, "hints": False})
    store.restore_table(TABLE_BY_KEY["battle"])
    assert store.config.battle == Config().battle
    store.restore_everything()
    assert json.loads(path.read_text(encoding="utf-8"))["hints"] is True


def test_store_leaves_a_broken_file_alone(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ not json", encoding="utf-8")
    store = SettingsStore(path)
    assert not store.writable and store.error
    store.set("hints", False)
    assert path.read_text(encoding="utf-8") == "{ not json"


def test_controller_setting_parses():
    config, warnings = parse({"controller": "Xbox One Controller"})
    assert config.controller == "Xbox One Controller" and warnings == []
    config, warnings = parse({"controller": 3})
    assert config.controller == "" and warnings


# ---- the window itself, offscreen ------------------------------------------------------
def _qt():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return pytest.importorskip("PySide6.QtWidgets")


def test_window_builds_and_saves(tmp_path):
    widgets = _qt()
    from PySide6.QtCore import QObject, Signal

    from ttcontroller import settings_window as sw

    class FakeReader:
        family = None

        def set_preferred(self, name):
            self.preferred = name

    class FakePad(QObject):
        buttons_changed = Signal(frozenset)
        name_changed = Signal(str)

        def __init__(self):
            super().__init__()
            self.buttons, self.name, self.threshold, self.reader = frozenset(), "", 0.5, FakeReader()

        def close(self):
            pass

    app = widgets.QApplication.instance() or widgets.QApplication([])
    store, path = _store(tmp_path, {})
    window = sw.SettingsWindow(store=store, pad=FakePad())
    for i in range(5):
        window.nav.setCurrentRow(i)
        app.processEvents()
    for i in range(len(TABLES)):
        window.tabs.setCurrentIndex(i)
        app.processEvents()
    window.tabs.setCurrentIndex(0)
    window._set_action("lb", "cameraPrev", False)
    window.save("hints_scale", 1.5)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["bindings"]["press"] == {"lb": "cameraPrev"} and data["hints_scale"] == 1.5
    window.pad.buttons_changed.emit(frozenset({"a"}))  # lights the Test row
    if window.art.drawer is not None:
        # A PlayStation pad plugged in: its pictures and names (Auto), then Switch chosen.
        window.pad.reader.family = "playstation"
        window.pad.name = "DualSense Wireless Controller"
        window.pad.name_changed.emit(window.pad.name)
        assert window.art.family == "playstation" and window.labels["a"] == "Cross"
        assert "PlayStation buttons" in window.pad_card.desc.text()
        window.save("button_pictures", "switch")
        assert window.art.family == "switch" and window.labels["a"] == "A" and window.labels["lt"] == "ZL"
        assert json.loads(path.read_text(encoding="utf-8"))["button_pictures"] == "switch"
        window.save("button_pictures", "auto")
        assert window.art.family == "playstation"
    window.close()
