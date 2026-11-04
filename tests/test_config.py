import json
import os

from ttcontroller import config
from ttcontroller.controller import ControllerState
from ttcontroller.mapper import Bindings, OverworldMapper


def test_defaults_round_trip():
    parsed, warnings = config.parse(json.loads(json.dumps(config.to_json(config.Config()))))
    assert warnings == []
    assert parsed == config.Config()


def test_user_bindings_merge_over_defaults():
    parsed, warnings = config.parse({"bindings": {"press": {"x": "performAction", "a": None}}})
    assert warnings == []
    assert parsed.bindings.press["x"] == "performAction"
    assert "a" not in parsed.bindings.press
    assert parsed.bindings.press["l3"] == "sprint"  # untouched default stays


def test_bad_values_warn_and_fall_back():
    parsed, warnings = config.parse({
        "bindings": {"press": {"zz": "jump", "a": 5}},
        "movement": {"deadzone": "big"},
        "timing": {"hold_seconds": 0.8},
    })
    assert len(warnings) == 3
    assert parsed.bindings.press["a"] == "jump"
    assert parsed.movement.deadzone == 0.25
    assert parsed.timing.hold_seconds == 0.8


def test_unknown_actions():
    cfg, _ = config.parse({"bindings": {"press": {"x": "flyAway"}}})
    ttr_controls = {"jump", "cameraNext", "showGags", "showTasks", "showMap",
                    "stickerBook", "lookUp", "lookDown", "options", "friendsList"}
    assert config.unknown_actions(cfg, ttr_controls) == ["bindings.press.x: unknown action 'flyAway'"]


def test_load_creates_file(tmp_path):
    path = tmp_path / "sub" / "config.json"
    cfg, warnings = config.load(path)
    assert path.exists() and warnings == [] and cfg == config.Config()


def test_broken_json_is_not_overwritten(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{ oops")
    cfg, warnings = config.load(path)
    assert cfg == config.Config() and warnings
    assert path.read_text() == "{ oops"


def test_watcher_reloads(tmp_path):
    path = tmp_path / "config.json"
    watcher = config.ConfigWatcher(path)
    assert watcher.check() is None
    path.write_text(json.dumps({"timing": {"hold_seconds": 1.5}}))
    os.utime(path, (1, 1))
    assert watcher.check().timing.hold_seconds == 1.5


def test_rebinding_changes_mapper():
    m = OverworldMapper(Bindings(press={"x": "jump"}, hold={}))
    assert m.update(ControllerState(buttons=frozenset({"x"})), 0.0) == {"jump"}
    assert m.update(ControllerState(buttons=frozenset({"a"})), 0.01) == set()


def test_hold_binding_on_any_button():
    m = OverworldMapper(Bindings(press={"y": "showGags"}, hold={"y": "showTasks"}))
    held = ControllerState(buttons=frozenset({"y"}))
    frames = [m.update(held, t / 100) for t in range(60)]
    assert any("showTasks" in f for f in frames)
    assert not any("showGags" in f for f in frames)
