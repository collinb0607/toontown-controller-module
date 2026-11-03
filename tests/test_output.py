from ttcontroller.output import KeyboardOutput


def make():
    sent = []
    return KeyboardOutput(lambda name, down: sent.append((name, down))), sent


def test_sync_presses_and_releases_diff_only():
    out, sent = make()
    out.sync({"w"})
    out.sync({"w", "a"})
    out.sync({"a"})
    assert sent == [("w", True), ("a", True), ("w", False)]


def test_combo_order():
    out, sent = make()
    out.sync({"escape", "shift"})
    out.sync(set())
    assert sent == [("shift", True), ("escape", True), ("escape", False), ("shift", False)]


def test_release_all():
    out, sent = make()
    out.sync({"w", "space"})
    sent.clear()
    out.release_all()
    assert sorted(sent) == [("space", False), ("w", False)]
    assert out.held == set()
