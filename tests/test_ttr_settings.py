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
