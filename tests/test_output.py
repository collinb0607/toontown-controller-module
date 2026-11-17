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


def test_hold_keeps_the_button_down_until_release():
    events = []
    clicker = MouseClicker(move=lambda x, y: events.append(("move", x, y)),
                           button=lambda down: events.append(("down" if down else "up",)), get_pos=lambda: (0, 0))
    clicker.hold(10, 20)
    for t in range(5):
        clicker.update(t * 0.05)
    assert events == [("move", 10, 20), ("down",)] and clicker.holding and clicker.busy
    clicker.release()
    assert events[-1] == ("up",) and not clicker.holding and not clicker.busy
    clicker.release()  # nothing held: does nothing
    assert events.count(("up",)) == 1


def test_drag_presses_moves_and_lets_go_in_order():
    events = []
    clicker = MouseClicker(move=lambda x, y: events.append(("move", x, y)),
                           button=lambda down: events.append(("down" if down else "up",)), get_pos=lambda: (0, 0))
    clicker.drag(100, 50, 140, 50)
    clicker.hover(140, 50)  # queued after it, not instead of it
    for t in range(10):
        clicker.update(t * 0.05)
    assert events == [("move", 100, 50), ("down",), ("move", 120, 50), ("move", 140, 50), ("up",), ("move", 140, 50)]
    assert not clicker.busy and not clicker.holding and clicker.moved_to == (140, 50)


def test_posted_keys_walk_with_shift_held():
    # TTR's walk key is Shift: W/A/S/D must still go down and up as keys while it's held,
    # or a key-up is lost and the toon walks on by itself (the user, Nov 13).
    from ttcontroller.output import WM_KEYDOWN, WM_KEYUP, PostedKeys
    posted = []
    send = PostedKeys(1, post=lambda h, m, w, l: posted.append((m, w)), lparam=lambda n, d: 0)
    send("w", True)
    send("shift", True)
    send("a", True)
    send("w", False)
    send("a", False)
    send("shift", False)
    assert [m for m, _ in posted] == [WM_KEYDOWN, WM_KEYDOWN, WM_KEYDOWN, WM_KEYUP, WM_KEYUP, WM_KEYUP]


def test_posted_typing_posts_capitals_as_characters():
    from ttcontroller.output import WM_CHAR, WM_KEYDOWN, WM_KEYUP, PostedKeys, type_text
    posted = []
    send = PostedKeys(1, post=lambda h, m, w, l: posted.append((m, w)), lparam=lambda n, d: 0)
    type_text(send, "Ab!")
    assert posted[0] == (WM_CHAR, ord("A"))
    assert [m for m, _ in posted[1:3]] == [WM_KEYDOWN, WM_KEYUP]
    assert posted[3] == (WM_CHAR, ord("!"))
    assert len(posted) == 4  # no Shift posted


def test_posted_typing_through_the_debug_wrapper():
    from ttcontroller.output import WM_CHAR, posted_output, type_text
    import ttcontroller.output as output
    posted = []
    real = output._post
    output._post = lambda h, m, w, l: posted.append((m, w))
    try:
        PostedKeysInit = output.PostedKeys.__init__.__defaults__
        output.PostedKeys.__init__.__defaults__ = (output._post, lambda n, d: 0)
        try:
            _, _, send = posted_output(1, lambda s: (lambda n, d: s(n, d)))
            type_text(send, "Z")
        finally:
            output.PostedKeys.__init__.__defaults__ = PostedKeysInit
    finally:
        output._post = real
    assert posted == [(WM_CHAR, ord("Z"))]
