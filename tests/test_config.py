import json
import os

from ttcontroller import config
from ttcontroller.controller import ControllerState
from ttcontroller.bindings import Bindings
from ttcontroller.mapper import OverworldMapper


def test_defaults_round_trip():
    parsed, warnings = config.parse(json.loads(json.dumps(config.to_json(config.Config()))))
    assert warnings == []
    assert parsed == config.Config()


def test_user_bindings_merge_over_defaults():
    parsed, warnings = config.parse({"bindings": {"press": {"x": "performAction", "a": None}}})
    assert warnings == []
    assert parsed.bindings.press["x"] == "performAction"
    assert "a" not in parsed.bindings.press
    assert parsed.bindings.press["ls"] == "sprint"  # untouched default stays


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


def test_auto_sprint_is_saved_without_counting_as_a_change(tmp_path):
    path = tmp_path / "config.json"
    path.write_text('{"movement": {"deadzone": 0.2}}', encoding="utf-8")
    watcher = config.ConfigWatcher(path)
    assert not watcher.config.auto_sprint
    watcher.save_auto_sprint(True)
    assert watcher.config.auto_sprint
    assert watcher.check() is None
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == {"movement": {"deadzone": 0.2}, "auto_sprint": True}
    assert config.load(path)[0].auto_sprint


def test_auto_sprint_must_be_true_or_false():
    cfg, warnings = config.parse({"auto_sprint": "yes"})
    assert not cfg.auto_sprint and any("auto_sprint" in w for w in warnings)


def test_old_stick_click_names_still_work():
    cfg, warnings = config.parse({"bindings": {"press": {"l3": "jump", "r3": None}}})
    assert warnings == []
    assert cfg.bindings.press["ls"] == "jump" and "rs" not in cfg.bindings.press


def test_hide_cursor():
    from ttcontroller.config import parse
    assert not parse({})[0].hide_cursor
    assert parse({"hide_cursor": True})[0].hide_cursor
    config, warnings = parse({"hide_cursor": "yes"})
    assert not config.hide_cursor and warnings
