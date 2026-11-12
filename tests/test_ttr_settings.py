import json

from ttcontroller import ttr_settings
from ttcontroller.keys import KeyCombo


def test_parse_user_keybinds():
    s = ttr_settings.parse({
        "controls": {"forward": "w", "jump": "space", "options": "shift-escape", "bogus": "mouse1",
                     "auto-jump": False},
        "controller": {"controller-enabled": True},
        "video": {"display-mode": "fullscreen"},
    })
    assert s.combo("forward") == KeyCombo((), "w")
    assert s.combo("options") == KeyCombo(("shift",), "escape")
    assert "bogus" not in s.controls
    assert "auto-jump" not in s.controls
    assert s.native_controller_enabled
    assert s.display_mode == "fullscreen"


def test_missing_controls_fall_back_to_defaults():
    s = ttr_settings.parse({})
    assert s.combo("forward") == KeyCombo((), "arrow_up")
    assert not s.native_controller_enabled


def test_watcher_reloads_on_change(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"controls": {"jump": "space"}}))
    watcher = ttr_settings.SettingsWatcher(tmp_path)
    assert watcher.settings.combo("jump").key == "space"
    assert watcher.check() is None

    path.write_text(json.dumps({"controls": {"jump": "j"}}))
    import os
    os.utime(path, (1, 1))
    assert watcher.check().combo("jump").key == "j"


def test_set_custom_cursor_keeps_the_rest(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"controls": {"jump": "space"}, "video": {"enable-cursor": True, "fps": 60}}))
    assert ttr_settings.set_custom_cursor(path, False)
    assert json.loads(path.read_text()) == {"controls": {"jump": "space"},
                                            "video": {"enable-cursor": False, "fps": 60}}
    assert not ttr_settings.load(path).custom_cursor


def test_set_custom_cursor_backs_up_first_and_leaves_no_temporary_file(tmp_path):
    path = tmp_path / "settings.json"
    before = json.dumps({"controls": {"jump": "space"}, "video": {"enable-cursor": True}})
    path.write_text(before)
    assert ttr_settings.set_custom_cursor(path, False)
    assert (tmp_path / "settings.backup.json").read_text() == before
    assert sorted(p.name for p in tmp_path.iterdir()) == ["settings.backup.json", "settings.json"]


def test_set_custom_cursor_failing_keeps_the_old_file(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    before = json.dumps({"video": {"enable-cursor": True}})
    path.write_text(before)

    def locked(*args):
        raise PermissionError("in use")

    monkeypatch.setattr(ttr_settings.os, "replace", locked)
    assert not ttr_settings.set_custom_cursor(path, False)
    assert path.read_text() == before
    assert not (tmp_path / "settings.json.tmp").exists()


def test_set_custom_cursor_leaves_a_broken_file_alone(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json")
    assert not ttr_settings.set_custom_cursor(path, False)
    assert path.read_text() == "{not json"
