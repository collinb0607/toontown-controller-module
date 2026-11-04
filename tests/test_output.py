from ttcontroller.output import KeyboardOutput, MouseClicker


def test_click_moves_clicks_and_restores_cursor():
    events = []
    clicker = MouseClicker(
        move=lambda x, y: events.append(("move", x, y)),
        button=lambda down: events.append(("down" if down else "up",)),
        get_pos=lambda: (5, 6),
    )
    clicker.click(100, 200)
    t = 0.0
    while clicker.busy:
        clicker.update(t)
        t += 0.01
    assert events == [("move", 100, 200), ("down",), ("up",), ("move", 5, 6)]


def test_hover_and_click_without_restore():
    events = []
    clicker = MouseClicker(
        move=lambda x, y: events.append(("move", x, y)),
        button=lambda down: events.append(("down" if down else "up",)),
        get_pos=lambda: (5, 6),
    )
    clicker.hover(1, 1)
    clicker.hover(2, 2)  # replaces the waiting hover
    clicker.click(3, 3, restore=False)
    t = 0.0
    while clicker.busy:
        clicker.update(t)
        t += 0.01
    assert events == [("move", 2, 2), ("move", 3, 3), ("down",), ("up",)]


def test_scroll_moves_then_turns_wheel():
    events = []
    clicker = MouseClicker(
        move=lambda x, y: events.append(("move", x, y)),
        button=lambda down: events.append(("down" if down else "up",)),
        get_pos=lambda: (5, 6),
        wheel=lambda n: events.append(("wheel", n)),
    )
    clicker.scroll(7, 8, -1)
    clicker.hover(9, 9)  # doesn't replace the scroll
    t = 0.0
    while clicker.busy:
        clicker.update(t)
        t += 0.01
    assert events == [("move", 7, 8), ("wheel", -1), ("move", 9, 9)]


def test_click_delay_waits_after_the_previous_click():
    events = []
    clicker = MouseClicker(
        move=lambda x, y: events.append(("move", x, y)),
        button=lambda down: events.append(("down" if down else "up",)),
        get_pos=lambda: (5, 6),
    )
    clicker.click(1, 1, restore=False)
    clicker.click(2, 2, restore=False, delay=0.1)
    times = {}
    t = 0.0
    while clicker.busy:
        before = len(events)
        clicker.update(t)
        if len(events) > before and events[-1] == ("move", 2, 2):
            times["second"] = t
        if len(events) > before and events[-1] == ("up",) and "first_up" not in times:
            times["first_up"] = t
        t = round(t + 0.01, 2)
    assert events == [("move", 1, 1), ("down",), ("up",), ("move", 2, 2), ("down",), ("up",)]
    assert times["second"] - times["first_up"] >= 0.1 - 1e-9


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
