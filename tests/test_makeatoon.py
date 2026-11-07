import pytest
from test_book import replay

from ttcontroller import makeatoon as mat
from ttcontroller.makeatoon import MakeAToonMapper, MakeAToonScreen, read_make_a_toon


def read(name):
    return replay(name, read_make_a_toon)


def px(point):
    return point.to_client(1920, 1009)


def near(point, x, y, tolerance=3):
    px_, py_ = px(point)
    return abs(px_ - x) <= tolerance and abs(py_ - y) <= tolerance


@pytest.mark.parametrize("name,kind", [
    ("make_a_toon_1_1920x1009", "style"),
    ("make_a_toon_2_1920x1009", "type"), ("make_a_toon_2_shuffle_1920x1009", "type"),
    ("make_a_toon_3_1920x1009", "color"), ("make_a_toon_3_shuffle_1920x1009", "color"),
    ("make_a_toon_4_1920x1009", "clothes"), ("make_a_toon_4_shuffle_1920x1009", "clothes"),
    ("make_a_toon_5_1920x1009", "name"), ("make_a_toon_5_hover_1920x1009", "name"),
    ("make_a_toon_5_type_name_1920x1009", "typename"),
    ("make_a_toon_5_confirm_1920x1009", "confirm"), ("make_a_toon_5_type_name_confirm_1920x1009", "confirm"),
    ("make_a_toon_5_tutorial_1920x1009", "confirm"),
    ("make_a_toon_5_type_name_confirm_2_1920x1009", "submission"),
    ("make_a_toon_bug_1_1920x1009", "submission"),
    ("toon_selection_rename_toon_1920x1009", "name"),  # Name Your Toon!: no back or next arrow  # a longer name, its text across the middle
])
def test_reads_each_screen(name, kind):
    assert read(name).kind == kind


@pytest.mark.parametrize("name", ["toon_selection_1920x1009", "clarabelle_popup_1920x1009",
                                  "elevator_cog_building_1920x1009"])
def test_not_on_other_screens(name):
    assert read(name).kind is None


@pytest.mark.parametrize("name,kind,size,points", [
    ("make_a_toon_2_different_resolution_1_983x331", "type", (983, 331),
     {"close": (25, 307), "back": (908, 307), "next": (958, 307), "row": (654, 108), "right": (697, 108)}),
    ("make_a_toon_2_different_resolution_2_667x534", "type", (667, 534),
     {"close": (40, 495), "back": (546, 496), "next": (626, 496), "row": (595, 175), "right": (664, 175)}),
    ("make_a_toon_5_different_resolution_1_597x534", "name", (597, 534),
     {"close": (40, 495), "back": (476, 496), "next": (556, 417), "list": (243, 282), "check": (268, 206)}),
    ("make_a_toon_5_different_resolution_2_1293x392", "name", (1293, 392),
     {"close": (29, 363), "back": (1204, 364), "next": (1263, 306), "list": (606, 207), "check": (624, 152)}),
])
def test_other_window_sizes(name, kind, size, points):
    screen = read(name)
    assert screen.kind == kind
    found = {"close": mat.CLOSE, "back": screen.back, "next": screen.next}
    if screen.rows:
        found.update(row=screen.rows[0].point, right=screen.rows[0].right)
    if screen.lists:
        found.update(list=screen.lists[2].point, check=screen.lists[2].check)
        assert [n.ticked for n in screen.lists] == [False, False, True, True]
    for key, (x, y) in points.items():
        px_, py_ = found[key].to_client(*size)
        assert abs(px_ - x) <= 2 and abs(py_ - y) <= 2, key


def test_style_step_has_no_back_and_next_is_greyed():
    screen = read("make_a_toon_1_1920x1009")
    assert screen.back is None and screen.next is None
    assert near(screen.style[0], 757, 906) and near(screen.style[1], 1162, 906)


def test_rows_and_shuffle_arrows():
    plain = read("make_a_toon_2_1920x1009")
    assert len(plain.rows) == 5 and plain.rows[-1].shuffle and plain.rows[-1].left is None
    assert near(plain.rows[0].left, 1322, 330) and near(plain.rows[1].right, 1545, 444)
    assert plain.back is not None and plain.next is not None
    shuffled = read("make_a_toon_2_shuffle_1920x1009")
    assert near(shuffled.rows[-1].left, 1353, 797)
    clothes = read("make_a_toon_4_1920x1009")
    assert [round(px(r.point)[1]) for r in clothes.rows] == [330, 444, 570, 683, 797]


def test_name_lists_and_checkboxes():
    screen = read("make_a_toon_5_1920x1009")
    assert [n.ticked for n in screen.lists] == [False, True, False, False]
    assert [n.ticked for n in read("make_a_toon_5_hover_1920x1009").lists] == [True, True, False, False]
    assert near(screen.lists[1].up, 653, 425) and near(screen.lists[1].down, 653, 640)
    assert screen.done is not None and near(screen.buttons[0], 748, 707)


def test_yes_no_dialogs_are_found_wherever_they_are():
    for name, yes, no in (("make_a_toon_5_confirm_1920x1009", (821, 636), (1098, 636)),
                          ("make_a_toon_5_type_name_confirm_1920x1009", (683, 714), (793, 714)),
                          ("make_a_toon_5_tutorial_1920x1009", (821, 666), (1098, 666))):
        screen = read(name)
        assert near(screen.buttons[0], *yes, tolerance=6) and near(screen.buttons[1], *no, tolerance=6), name


# The mapper.

def press(m, screen, *buttons, at=0.0):
    out = m.update(frozenset(buttons), at, screen)
    out += m.update(frozenset(), at + 0.05, screen)
    return out


def names(commands):
    return [(c.kind, c.name) for c in commands]


def test_rows_start_on_the_top_row_then_move_and_click_arrows():
    m = MakeAToonMapper()
    screen = read("make_a_toon_2_1920x1009")
    out = m.update(frozenset(), 0.0, screen)  # the step opens: its top row, straight away
    assert names(out) == [("hover", "row 1")] and out[0].size == mat._ROW_SIZE[True] and out[0].pointer
    assert m.hovering(screen)
    assert names(press(m, screen, "dpad_down", at=1.0)) == [("hover", "row 2")]
    out = press(m, screen, "dpad_right", at=2.0)
    assert names(out) == [("click", "row 2 right")] and near(out[0].point, 1545, 444)
    # Down to Shuffle: A shuffles; it has no arrows yet.
    for t in (3.0, 4.0, 5.0):
        press(m, screen, "dpad_down", at=t)
    assert m.row == 4
    assert names(press(m, screen, "a", at=6.0)) == [("click", "shuffle")]
    assert press(m, screen, "dpad_left", at=7.0) == []
    assert names(press(m, screen, "x", at=8.0)) == [("click", "shuffle")]


def test_bumpers_b_and_start_change_steps():
    m = MakeAToonMapper()
    color = read("make_a_toon_3_1920x1009")
    m.update(frozenset(), 0.0, color)
    press(m, color, "dpad_down", at=1.0)
    assert names(press(m, color, "rb", at=2.0)) == [("click", "next step")]
    # The next step opens on its top row.
    assert names(m.update(frozenset(), 3.0, read("make_a_toon_4_1920x1009"))) == [("hover", "row 1")]
    assert names(m.update(frozenset(), 4.0, color)) == [("hover", "row 1")]
    assert names(press(m, color, "lb", at=5.0)) == [("click", "back a step")]
    assert names(press(m, color, "b", at=6.0)) == [("click", "back a step")]
    assert names(press(m, color, "start", at=7.0)) == [("click", "next step")]


def test_style_step():
    m = MakeAToonMapper()
    screen = read("make_a_toon_1_1920x1009")
    assert names(m.update(frozenset(), 0.0, screen)) == [("hover", "style 1")]
    assert names(press(m, screen, "dpad_right", at=1.0)) == [("hover", "style 2")]
    assert names(press(m, screen, "dpad_left", at=2.0)) == [("hover", "style 1")]
    assert names(press(m, screen, "a", at=3.0)) == [("click", "pick style 1")]
    assert press(m, screen, "rb", at=4.0) == []  # next is greyed until a style is picked
    assert press(m, screen, "lb", at=5.0) == []
    out = press(m, screen, "b", at=6.0)
    assert names(out) == [("click", "leave make-a-toon")] and out[0].point == mat.CLOSE


def test_right_stick_holds_a_turn_arrow():
    m = MakeAToonMapper()
    screen = read("make_a_toon_2_1920x1009")
    m.update(frozenset(), 0.0, screen)
    out = m.update(frozenset({"rs_left"}), 1.0, screen)
    assert names(out) == [("hold", "turn left")] and out[0].point == mat.ROTATE[0]
    assert m.update(frozenset({"rs_left"}), 1.1, screen) == []
    # Let go: back on the row hovered.
    assert names(m.update(frozenset(), 1.2, screen)) == [("release", "stop turning"), ("hover", "row 1")]


def test_name_step():
    m = MakeAToonMapper()
    screen = read("make_a_toon_5_1920x1009")
    out = m.update(frozenset(), 0.0, screen)  # opens on First (ticked from the start)
    assert names(out) == [("hover", "name list 2")] and out[0].size == mat.LIST_SIZE and out[0].pointer
    assert names(press(m, screen, "dpad_left", at=1.0)) == [("hover", "name list 1")]
    assert press(m, screen, "dpad_down", at=2.0) == []  # Title isn't ticked: no arrows
    assert names(press(m, screen, "a", at=3.0)) == [("click", "checkbox 1"), ("hover", "name list 1")]
    press(m, screen, "dpad_right", at=4.0)
    out = press(m, screen, "dpad_down", at=5.0)
    assert names(out) == [("click", "name list 2 down")] and near(out[0].point, 653, 640)
    assert names(press(m, screen, "x", at=6.0)) == [("click", "shuffle")]
    assert names(press(m, screen, "start", at=7.0)) == [("click", "done")]
    assert press(m, screen, "rb", at=8.0) == []  # RB isn't the arrow above the check mark
    out = press(m, screen, "rt", at=8.5)  # that's RT: submit without a name
    assert names(out) == [("click", "no name yet")] and out[0].point == mat.NAME_NEXT
    assert names(press(m, screen, "lb", at=9.0)) == [("click", "back a step")]


def test_holding_down_on_a_name_list_holds_its_arrow():
    m = MakeAToonMapper()
    screen = read("make_a_toon_5_1920x1009")
    m.update(frozenset(), 0.0, screen)
    assert names(m.update(frozenset({"dpad_down"}), 1.0, screen)) == [("click", "name list 2 down")]
    assert names(m.update(frozenset({"dpad_down"}), 1.5, screen)) == [("hold", "hold scroll")]
    assert names(m.update(frozenset(), 2.0, screen)) == [("release", "stop scrolling"), ("hover", "name list 2")]


def test_type_a_name_and_back_to_the_same_list():
    m = MakeAToonMapper()
    name = read("make_a_toon_5_1920x1009")
    typing = read("make_a_toon_5_type_name_1920x1009")
    m.update(frozenset(), 0.0, name)
    press(m, name, "dpad_right", at=1.0)
    assert names(press(m, name, "y", at=2.0)) == [("click", "type-a-name")]
    assert m.update(frozenset(), 3.0, typing) == []
    assert names(press(m, typing, "a", at=4.0)) == [("click", "submit")]
    assert names(press(m, typing, "b", at=5.0)) == [("click", "pick-a-name")]
    assert names(m.update(frozenset(), 6.0, name)) == [("hover", "name list 3")]
    # Y toggles: Type-A-Name, then Y again is Pick-A-Name.
    assert names(press(m, name, "y", at=7.0)) == [("click", "type-a-name")]
    m.update(frozenset(), 8.0, typing)
    assert names(press(m, typing, "y", at=9.0)) == [("click", "pick-a-name")]


def test_dialogs_a_yes_b_no():
    for capture in ("make_a_toon_5_confirm_1920x1009", "make_a_toon_5_tutorial_1920x1009",
                    "make_a_toon_5_type_name_confirm_2_1920x1009"):
        m = MakeAToonMapper()
        screen = read(capture)
        m.update(frozenset(), 0.0, screen)
        assert names(press(m, screen, "a", at=1.0)) == [("click", "yes")]
        out = press(m, screen, "b", at=2.0)
        assert names(out) == [("click", "no")] and out[0].point == screen.buttons[1]


def test_closed_does_nothing():
    m = MakeAToonMapper()
    assert press(m, MakeAToonScreen(), "a", "dpad_down") == []


def test_pointer_moves_out_past_shuffles_arrows_once_they_show():
    m = MakeAToonMapper()
    plain = read("make_a_toon_2_1920x1009")
    shuffled = read("make_a_toon_2_shuffle_1920x1009")
    m.update(frozenset(), 0.0, plain)
    for t in range(1, 6):
        press(m, plain, "dpad_down", at=float(t))
    assert m.row == 4
    assert names(press(m, plain, "a", at=6.0)) == [("click", "shuffle")]
    assert m.update(frozenset(), 6.5, plain) == []  # not redrawn yet: nothing to move
    out = m.update(frozenset(), 7.0, shuffled)  # now with its arrows
    assert names(out) == [("hover", "shuffle")] and out[0].size == mat.SHUFFLE_ARROWS_SIZE and out[0].pointer
    left_edge = out[0].point.to_client(1920, 1009)[0] - out[0].size[0] * 1009 / 2
    assert left_edge < 1330  # left of the back arrow (its blue edge starts about 1330)
    assert m.update(frozenset(), 7.5, shuffled) == []  # once


def test_shuffles_arrows_count_when_greyed():
    # Back at the first shuffle, the back arrow is greyed: Shuffle still has its arrows (both
    # clickable, the frame round them unchanged).
    pixels = {}
    screen = read("make_a_toon_2_shuffle_1920x1009")
    assert screen.rows[-1].left is not None
    import json
    from test_book import FIXTURES
    data = json.loads((FIXTURES / "make_a_toon_2_shuffle_1920x1009.json").read_text())
    pixels = {k: tuple(v) for k, v in data["pixels"].items()}
    x, y = mat._pt("c", mat._SHUFFLE_ARROWS[0], mat._SHUFFLE_Y).to_client(1920, 1009)
    pixels[f"{x},{y}"] = (90, 90, 90)  # greyed back arrow
    greyed = read_make_a_toon(1920, 1009, lambda px_, py_: pixels[f"{px_},{py_}"])
    assert greyed.rows[-1].left is not None and greyed.rows[-1].size == mat.SHUFFLE_ARROWS_SIZE
    m = MakeAToonMapper()
    m.update(frozenset(), 0.0, greyed)
    for t in range(1, 6):
        press(m, greyed, "dpad_down", at=float(t))
    assert names(press(m, greyed, "dpad_right", at=6.0)) == [("click", "shuffle right")]


def test_renaming_b_cancels():
    screen = read("toon_selection_rename_toon_1920x1009")
    assert screen.back is None and screen.next is None and screen.done is not None
    m = MakeAToonMapper()
    m.update(frozenset(), 0.0, screen)
    assert press(m, screen, "lb", at=1.0) == []
    out = press(m, screen, "b", at=2.0)
    assert names(out) == [("click", "cancel naming")] and out[0].point == mat.CLOSE
    assert names(press(m, screen, "start", at=3.0)) == [("click", "done")]
