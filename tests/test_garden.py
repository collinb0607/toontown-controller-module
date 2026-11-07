from test_book import replay

from ttcontroller.garden import (BEAN_SIZE, PLANT, PLANT_CANCEL, PLANT_RESET, SELL_ALL, SELL_CANCEL, GardenMapper,
                                 GardenScreen, bean_point, read_garden)

SIZE = (1920, 1009)


def at(point):
    return point.to_client(*SIZE) if point is not None else None


def near(point, x, y, tolerance=3):
    px, py = at(point)
    return abs(px - x) <= tolerance and abs(py - y) <= tolerance


def test_two_buttons():
    for name in ("gardening_hud_1_1920x1009", "gardening_hud_3_1920x1009"):  # Pick and Water, Full and Water
        screen = replay(name, read_garden)
        assert near(screen.top, 66, 234) and near(screen.bottom, 66, 330), name


def test_a_label_wider_than_the_panel():
    # Remove's letters cross the column the panel is found down.
    screen = replay("gardening_hud_bug_1920x1009", read_garden)
    assert near(screen.top, 66, 234) and near(screen.bottom, 66, 330)


def test_one_button():
    screen = replay("gardening_hud_2_1920x1009", read_garden)  # Plant Flower
    assert near(screen.top, 66, 234) and screen.bottom is None


def test_other_window_sizes():
    for name, size, (x, y) in (("gardening_hud_4_1379x348", (1379, 348), (23, 81)),
                               ("gardening_hud_5_405x820", (405, 820), (26, 94))):
        screen = replay(name, read_garden)
        px, py = screen.top.to_client(*size)
        assert abs(px - x) <= 2 and abs(py - y) <= 2 and screen.bottom is None, name


def test_not_the_books_gardening_page_or_a_plain_screen():
    assert not replay("book_gardening_basket_1920x1009", read_garden).is_open
    assert read_garden(1920, 1009, lambda x, y: (90, 70, 50)) == GardenScreen()


def press(m, screen, button, now):
    commands = m.update(frozenset({button}), now, screen)
    m.update(frozenset(), now + 0.05, screen)
    return [(c.kind, c.point) for c in commands]


def test_y_clicks_the_top_button_and_x_the_bottom():
    screen = replay("gardening_hud_1_1920x1009", read_garden)
    m = GardenMapper()
    assert m.buttons(screen) == {"x", "y"}  # A still jumps, B still closes menus
    assert press(m, screen, "y", 0.0) == [("click", screen.top)]
    assert press(m, screen, "x", 1.0) == [("click", screen.bottom)]


def test_x_does_nothing_without_a_bottom_button():
    screen = replay("gardening_hud_2_1920x1009", read_garden)
    assert press(GardenMapper(), screen, "x", 0.0) == []


def test_the_sell_popup():
    screen = replay("gardening_sell_popup_1920x1009", read_garden)
    assert screen.selling and screen.is_open
    assert not replay("gardening_hud_1_1920x1009", read_garden).selling
    assert near(SELL_CANCEL, 1110, 794) and near(SELL_ALL, 1262, 793)


def test_a_sells_and_b_cancels():
    screen = replay("gardening_sell_popup_1920x1009", read_garden)
    m = GardenMapper()
    assert m.buttons(screen) == {"a", "b"}  # Y and X show gags and tasks again
    assert press(m, screen, "a", 0.0) == [("click", SELL_ALL)]
    assert press(m, screen, "b", 1.0) == [("click", SELL_CANCEL)]
    assert press(m, screen, "y", 2.0) == []


def test_the_bean_picker():
    picker = replay("gardening_bean_picker_1920x1009", read_garden)
    assert picker.planting and picker.beans and not picker.selling
    full = replay("gardening_bean_picker_no_beans_1920x1009", read_garden)
    assert full.planting and not full.beans  # as many beans in as can be planted
    assert near(bean_point(0), 751, 451) and near(bean_point(8), 1173, 451)
    assert near(PLANT_CANCEL, 808, 678) and near(PLANT_RESET, 959, 678) and near(PLANT, 1110, 677)
    assert not replay("gardening_sell_popup_1920x1009", read_garden).planting


def hovers(commands):
    return [(c.point, c.size) for c in commands if c.kind == "hover"]


def test_the_picker_opens_on_red_and_the_dpad_wraps():
    picker = replay("gardening_bean_picker_1920x1009", read_garden)
    m = GardenMapper()
    assert hovers(m.update(frozenset(), 0.0, picker)) == [(bean_point(0), BEAN_SIZE)]
    assert {"dpad_left", "dpad_right", "a", "b", "x", "y"} <= m.buttons(picker)
    assert hovers(m.update(frozenset({"dpad_left"}), 1.0, picker)) == [(bean_point(8), BEAN_SIZE)]
    m.update(frozenset(), 1.1, picker)
    assert hovers(m.update(frozenset({"dpad_right"}), 2.0, picker)) == [(bean_point(0), BEAN_SIZE)]
    m.update(frozenset(), 2.1, picker)
    assert hovers(m.update(frozenset({"dpad_right"}), 3.0, picker)) == [(bean_point(1), BEAN_SIZE)]


def test_picker_buttons():
    picker = replay("gardening_bean_picker_1920x1009", read_garden)
    m = GardenMapper()
    m.update(frozenset(), 0.0, picker)
    assert press(m, picker, "a", 1.0) == [("click", bean_point(0))]  # the hovered bean
    assert press(m, picker, "y", 2.0) == [("click", PLANT)]
    assert press(m, picker, "x", 3.0) == [("click", PLANT_RESET)]
    assert press(m, picker, "b", 4.0) == [("click", PLANT_CANCEL)]


def test_a_plants_once_the_beans_are_gone_and_reset_brings_back_the_last_bean():
    picker = replay("gardening_bean_picker_1920x1009", read_garden)
    full = replay("gardening_bean_picker_no_beans_1920x1009", read_garden)
    m = GardenMapper()
    m.update(frozenset(), 0.0, picker)
    press(m, picker, "dpad_right", 1.0)
    press(m, picker, "dpad_right", 2.0)  # the orange bean
    assert m.update(frozenset(), 3.0, full) == []
    assert not m.hovering
    assert press(m, full, "a", 4.0) == [("click", PLANT)]
    assert press(m, full, "dpad_right", 5.0) == []
    assert hovers(m.update(frozenset(), 6.0, picker)) == [(bean_point(2), BEAN_SIZE)]  # reset: the beans are back


def test_a_new_picker_starts_on_red_again():
    picker = replay("gardening_bean_picker_1920x1009", read_garden)
    m = GardenMapper()
    m.update(frozenset(), 0.0, picker)
    press(m, picker, "dpad_right", 1.0)
    m.update(frozenset(), 2.0, GardenScreen())  # closed
    assert hovers(m.update(frozenset(), 3.0, picker)) == [(bean_point(0), BEAN_SIZE)]


def test_the_failed_combination_popup():
    screen = replay("gardening_failed_combo_popup_1920x1009", read_garden)
    assert near(screen.ok, 960, 641) and screen.popup
    assert not screen.planting and not screen.selling and screen.top is None
    assert replay("gardening_hud_1_1920x1009", read_garden).ok is None


def test_a_or_b_clicks_ok():
    screen = replay("gardening_failed_combo_popup_1920x1009", read_garden)
    m = GardenMapper()
    assert m.buttons(screen) == {"a", "b"}
    assert press(m, screen, "a", 0.0) == [("click", screen.ok)]
    assert press(m, screen, "b", 1.0) == [("click", screen.ok)]
    assert press(m, screen, "y", 2.0) == []


def test_the_new_toon_tutorials_ok_popup_is_read_too():
    # The same OK-only card (and not a gag shop dialog: its red picture isn't a Cancel).
    from ttcontroller.shop import read_shop
    assert replay("new_toon_popup_1920x1009", read_shop).kind is None
    screen = replay("new_toon_popup_1920x1009", read_garden)
    assert near(screen.ok, 960, 817) and screen.popup
    assert press(GardenMapper(), screen, "a", 0.0) == [("click", screen.ok)]
