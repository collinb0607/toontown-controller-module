from ttcontroller.cursor import CursorHider


class Calls:
    def __init__(self):
        self.log = []

    def hide(self):
        self.log.append("hide")

    def show(self):
        self.log.append("show")


def make():
    calls = Calls()
    hider = CursorHider(calls.hide, calls.show)
    calls.log.clear()  # the start-up restore
    return hider, calls


def test_hides_once_the_controller_is_used():
    hider, calls = make()
    hider.update(True, False, (100, 100), False, None)
    assert not hider.hidden
    hider.update(True, True, (100, 100), False, None)
    hider.update(True, True, (100, 100), False, None)
    assert hider.hidden and calls.log == ["hide"]


def test_module_moves_keep_it_hidden():
    hider, calls = make()
    hider.update(True, True, (100, 100), False, None)
    hider.update(True, True, (500, 300), True, (500, 300))  # mid-click
    hider.update(True, False, (501, 299), False, (500, 300))  # landed a pixel off
    hider.update(True, False, (100, 100), False, (100, 100))  # put back after a click
    assert hider.hidden and calls.log == ["hide"]


def test_moving_the_mouse_shows_it_until_the_controller_is_used_again():
    hider, calls = make()
    hider.update(True, True, (100, 100), False, None)
    hider.update(True, False, (140, 120), False, (100, 100))
    assert not hider.hidden
    hider.update(True, False, (150, 120), False, (100, 100))
    assert not hider.hidden
    hider.update(True, True, (150, 120), False, (100, 100))
    assert hider.hidden and calls.log == ["hide", "show", "hide"]


def test_shown_when_ttr_loses_focus():
    hider, calls = make()
    hider.update(True, True, (100, 100), False, None)
    hider.update(False, True, (100, 100), False, None)
    assert not hider.hidden and calls.log == ["hide", "show"]


def test_reports_real_mouse_moves_only():
    hider, _ = make()
    assert not hider.update(True, True, (100, 100), False, None)
    assert not hider.update(True, False, (500, 300), True, (500, 300))  # the module moving it
    assert hider.update(True, False, (540, 320), False, (500, 300))
    assert not hider.update(True, False, (540, 320), False, (500, 300))  # still
