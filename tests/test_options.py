import json
from dataclasses import replace
from pathlib import Path

import pytest

from ttcontroller import options as o
from ttcontroller.options import OptionsMapper, OptionsScreen, Row, read_options

FIXTURES = Path(__file__).parent / "fixtures" / "battle"


def replay(name):
    data = json.loads((FIXTURES / f"{name}.json").read_text())
    w, h = data["size"]
    pixels = data["pixels"]
    return read_options(w, h, lambda x, y: tuple(pixels[f"{x},{y}"]))


def px(point, size=(1920, 1009)):
    return point.to_client(*size)


@pytest.mark.parametrize("name,kind,tab", [
    ("options_gameplay_1920x1009", "options", 0), ("options_1533x711", "options", 0),
    ("options_controls_1920x1009", "options", 1), ("options_audio_1920x1009", "options", 2),
    ("options_video_1920x1009", "options", 3), ("startup_options_1920x1009", "options", 0),
    ("options_gameplay_dropdown_1920x1009", "dropdown", 0),
    ("options_gameplay_toonsync_popup_1920x1009", "dialog", 0),
    ("options_gameplay_pronoun_picker_1920x1009", "pronouns", None),
    ("book_options_1920x1009", None, None), ("toon_selection_1920x1009", None, None),
    ("friends_list_1920x1009", None, None), ("battle_waiting_1920x1009", None, None),
])
def test_reads_the_window(name, kind, tab):
    screen = replay(name)
    assert (screen.kind, screen.tab) == (kind, tab)


def test_reads_the_gameplay_rows_at_the_top():
    screen = replay("options_gameplay_1920x1009")
    assert [r.kind for r in screen.rows] == ["button", "dropdown", "dropdown", "toggle"]
    assert [px(r.point)[1] for r in screen.rows] == [492, 587, 662, 745]
    assert px(screen.rows[0].point)[0] == 1254  # Customize!
    assert screen.rows[3].on is True
    # Only Pronouns has a ?.
    assert [r.help is not None for r in screen.rows] == [True, False, False, False]
    assert abs(px(screen.rows[0].help)[0] - 551) <= 1
    # Accept Anyone's Whispers is cut off at the bottom; the list scrolls down, not up.
    assert screen.cut == (False, True)
    assert screen.can_scroll == (False, True)
    # The same at another window size.
    small = replay("options_1533x711")
    assert [r.kind for r in small.rows] == ["button", "dropdown", "dropdown", "toggle"]


def test_reads_toggle_states_and_help_further_down():
    screen = replay("options_gameplay_toonsync_1920x1009")
    assert [r.kind for r in screen.rows] == ["toggle", "toggle", "button", "toggle", "toggle"]
    assert [r.on for r in screen.rows] == [True, False, None, True, True]  # Companion App Support is off
    assert all(r.help is not None for r in screen.rows)
    assert screen.can_scroll == (True, True)


def test_reads_the_bottom_with_its_centered_reset_button():
    screen = replay("options_gameplay_reset_to_default_1920x1009")
    assert [r.kind for r in screen.rows] == ["toggle", "toggle", "toggle", "button"]
    reset = screen.rows[-1]
    assert reset.centered and not screen.rows[0].centered
    assert abs(px(reset.point)[0] - 954) <= 2
    assert screen.can_scroll == (True, False)


def test_greyed_out_rows_are_skipped():
    # Before logging in, the toon's preferences can't be changed.
    screen = replay("startup_options_1920x1009")
    assert screen.rows == ()
    assert screen.can_scroll == (False, True)


def test_reads_an_open_dropdown():
    screen = replay("options_gameplay_dropdown_1920x1009")
    assert [px(p) for p in screen.items] == [(1246, 587), (1246, 632), (1246, 677)]


def test_reads_the_toonsync_popup_as_a_dialog():
    screen = replay("options_gameplay_toonsync_popup_1920x1009")
    assert [px(p) for p in screen.dialog] == [(904, 812), (1015, 812)]


def test_other_tabs_find_their_controls():
    assert [r.kind for r in replay("options_controls_1920x1009").rows] == ["button"] * 6  # keybinds
    assert [r.kind for r in replay("options_video_1920x1009").rows] == ["dropdown", "dropdown"]


# --- Controls ---

GAMEPLAY = replay("options_gameplay_1920x1009")
TOONSYNC = replay("options_gameplay_toonsync_1920x1009")
DROPDOWN = replay("options_gameplay_dropdown_1920x1009")
POPUP = replay("options_gameplay_toonsync_popup_1920x1009")
PRONOUNS = replay("options_gameplay_pronoun_picker_1920x1009")


def press(mapper, button, now, screen):
    commands = mapper.update(frozenset({button}), now, screen)
    return commands + mapper.update(frozenset(), now + 0.01, screen)


def opened(screen=GAMEPLAY, now=0.0):
    m = OptionsMapper()
    m.update(frozenset(), now, screen)
    return m


def test_opens_with_nothing_hovered_and_the_first_press_hovers_the_top_row():
    m = opened()
    assert not m.hovering(GAMEPLAY)
    (c,) = press(m, "dpad_down", 1.0, GAMEPLAY)
    assert (c.kind, px(c.point)) == ("hover", (1254, 492))
    # The frame goes around the whole row: from left of the ? to past the button.
    left = px(c.frame_at)[0] - c.size[0] * 1009 / 2
    right = px(c.frame_at)[0] + c.size[0] * 1009 / 2
    assert left < 541 and 1357 < right < 1375
    assert m.hovering(GAMEPLAY)


def test_up_and_down_move_between_rows():
    m = opened()
    press(m, "dpad_down", 1.0, GAMEPLAY)
    (c,) = press(m, "ls_down", 2.0, GAMEPLAY)
    assert px(c.point) == (1246, 587)
    (c,) = press(m, "dpad_down", 3.0, GAMEPLAY)
    assert px(c.point) == (1246, 662)
    (c,) = press(m, "dpad_up", 4.0, GAMEPLAY)
    assert px(c.point) == (1246, 587)


def _rows(*ys, kinds=None):
    kinds = kinds or ["toggle"] * len(ys)
    return tuple(Row(k, y, 0.28, 0.36, 0.047) for k, y in zip(kinds, ys))


def test_past_the_last_row_in_view_it_scrolls_and_hovers_the_next_row():
    before = OptionsScreen("options", 0, _rows(-0.10, -0.025, 0.05, 0.125, 0.20, 0.275), can_scroll=(False, True))
    m = opened(before)
    for i in range(6):
        press(m, "dpad_down", 1.0 + i, before)
    assert m.row_y == pytest.approx(0.275)
    (c,) = press(m, "dpad_down", 10.0, before)
    assert c.kind == "scroll" and c.notches < 0  # down
    # The rows moved up by 0.06 and a new one came into view at the bottom.
    after = OptionsScreen("options", 0, _rows(-0.085, -0.01, 0.065, 0.14, 0.215, 0.29), can_scroll=(True, True))
    assert m.update(frozenset(), 10.1, after) == []  # still settling
    (c,) = m.update(frozenset(), 10.5, after)
    assert c.kind == "hover" and m.row_y == pytest.approx(0.29)


def test_a_small_scroll_turns_the_wheel_again_until_a_new_row_shows():
    before = OptionsScreen("options", 0, _rows(0.0, 0.1, 0.2), can_scroll=(False, True))
    m = opened(before)
    for i in range(3):
        press(m, "dpad_down", 1.0 + i, before)
    press(m, "dpad_down", 10.0, before)
    nudged = OptionsScreen("options", 0, _rows(-0.03, 0.07, 0.17), can_scroll=(True, True))
    (c,) = m.update(frozenset(), 10.5, nudged)
    assert c.kind == "scroll"
    shown = OptionsScreen("options", 0, _rows(-0.06, 0.04, 0.14, 0.24), can_scroll=(True, True))
    (c,) = m.update(frozenset(), 11.0, shown)
    assert c.kind == "hover" and m.row_y == pytest.approx(0.24)


def test_scrolling_up_from_the_top_row():
    before = OptionsScreen("options", 0, _rows(0.0, 0.1, kinds=["button", "toggle"]), can_scroll=(True, True))
    m = opened(before)
    press(m, "dpad_down", 1.0, before)
    (c,) = press(m, "dpad_up", 2.0, before)
    assert c.kind == "scroll" and c.notches > 0
    after = OptionsScreen("options", 0, _rows(-0.05, 0.05, 0.15, kinds=["dropdown", "button", "toggle"]),
                          can_scroll=(False, True))
    (c,) = m.update(frozenset(), 2.5, after)
    assert m.row_y == pytest.approx(-0.05)


def test_nothing_happens_past_the_end_of_the_list():
    end = replace(GAMEPLAY, can_scroll=(False, False))
    m = opened(end)
    for i in range(4):
        press(m, "dpad_down", 1.0 + i, end)
    assert press(m, "dpad_down", 6.0, end) == []


def test_greyed_out_rows_scroll_to_find_one():
    screen = replay("startup_options_1920x1009")
    m = opened(screen)
    (c,) = press(m, "dpad_down", 1.0, screen)
    assert c.kind == "scroll"


def test_triggers_click_the_tabs_and_a_new_tab_starts_unhovered():
    m = opened()
    assert press(m, "lt", 1.0, GAMEPLAY) == []  # already the first tab
    (c,) = press(m, "rt", 2.0, GAMEPLAY)
    assert (c.kind, px(c.point)) == ("click", (652 + 205, 175))
    press(m, "dpad_down", 3.0, GAMEPLAY)
    controls = replay("options_controls_1920x1009")
    m.update(frozenset(), 4.0, controls)
    assert not m.hovering(controls)
    (c,) = press(m, "lt", 5.0, controls)
    assert px(c.point) == (652, 175)


def test_a_clicks_the_setting_and_b_closes():
    m = opened()
    press(m, "dpad_down", 1.0, GAMEPLAY)
    (c,) = press(m, "a", 2.0, GAMEPLAY)
    assert (c.kind, px(c.point)) == ("click", (1254, 492))
    (c,) = press(m, "b", 3.0, GAMEPLAY)
    assert (c.kind, px(c.point)) == ("click", px(o.CLOSE))
    (c,) = press(OptionsMapper(), "start", 4.0, GAMEPLAY)
    assert px(c.point) == px(o.CLOSE)


def test_left_and_right_turn_a_toggle_off_and_on():
    m = opened()
    for i in range(4):
        press(m, "dpad_down", 1.0 + i, GAMEPLAY)  # Accept New Friends: on
    assert press(m, "dpad_right", 6.0, GAMEPLAY) == []
    (c,) = press(m, "dpad_left", 7.0, GAMEPLAY)
    assert (c.kind, px(c.point)) == ("click", (1278, 745))


def test_y_shows_the_setting_help_and_again_goes_back():
    m = opened(TOONSYNC)
    (row,) = press(m, "dpad_down", 1.0, TOONSYNC)
    (c,) = press(m, "y", 2.0, TOONSYNC)
    assert c.kind == "hover" and abs(px(c.point)[0] - 551) <= 1 and abs(px(c.point)[1] - 400) <= 2
    assert (c.frame_at, c.size) == (row.frame_at, row.size)  # the frame stays on the row
    (c,) = press(m, "y", 3.0, TOONSYNC)
    assert px(c.point) == px(row.point)
    # A row without a ? does nothing.
    m = opened()
    press(m, "dpad_down", 1.0, GAMEPLAY)
    press(m, "dpad_down", 2.0, GAMEPLAY)
    assert press(m, "y", 3.0, GAMEPLAY) == []


def test_dropdown_starts_on_its_current_choice_and_b_clicks_off_it():
    m = opened()
    press(m, "dpad_down", 1.0, GAMEPLAY)
    press(m, "dpad_down", 2.0, GAMEPLAY)  # Accept Teleports From
    press(m, "a", 3.0, GAMEPLAY)
    (c,) = m.update(frozenset(), 4.0, DROPDOWN)
    assert px(c.point) == (1246, 587) and c.size is not None
    (c,) = press(m, "dpad_down", 5.0, DROPDOWN)
    assert px(c.point) == (1246, 632)
    assert press(m, "dpad_down", 6.0, DROPDOWN)[0].point == DROPDOWN.items[2]
    assert press(m, "dpad_down", 7.0, DROPDOWN)[0].point == DROPDOWN.items[2]  # the last
    (c,) = press(m, "b", 8.0, DROPDOWN)
    assert c.kind == "click" and px(c.point)[0] < 700
    # Closed: back on the dropdown it came from.
    (c,) = m.update(frozenset(), 9.0, GAMEPLAY)
    assert px(c.point) == (1246, 587)


def test_a_picks_the_dropdown_item():
    m = opened()
    press(m, "dpad_down", 1.0, GAMEPLAY)
    press(m, "dpad_down", 2.0, GAMEPLAY)
    m.update(frozenset(), 3.0, DROPDOWN)
    press(m, "dpad_down", 4.0, DROPDOWN)
    (c,) = press(m, "a", 5.0, DROPDOWN)
    assert (c.kind, px(c.point)) == ("click", (1246, 632))


def test_popup_hovers_ok_and_returns_to_its_button():
    m = opened(TOONSYNC)
    for i in range(3):
        press(m, "dpad_down", 1.0 + i, TOONSYNC)  # ToonSync's Get a Code
    (c,) = m.update(frozenset(), 5.0, POPUP)
    assert (c.kind, px(c.point)) == ("hover", (904, 812))
    (c,) = press(m, "b", 6.0, POPUP)
    assert px(c.point) == (1015, 812)
    (c,) = m.update(frozenset(), 7.0, TOONSYNC)
    assert px(c.point) == (1254, 564)


def test_pronoun_picker_columns_arrows_and_buttons():
    m = opened()
    press(m, "dpad_down", 1.0, GAMEPLAY)
    (c,) = m.update(frozenset(), 2.0, PRONOUNS)
    assert c.kind == "hover" and px(c.point)[0] == 700 and c.size == o.PRONOUN_BOX_SIZE
    assert press(m, "dpad_left", 3.0, PRONOUNS) == []
    (c,) = press(m, "dpad_right", 4.0, PRONOUNS)
    assert px(c.point)[0] == 964
    click, back = press(m, "dpad_down", 5.0, PRONOUNS)
    assert click.kind == "click" and px(click.point) == (964, 533)
    assert back.kind == "hover" and back.point == c.point
    (c, _) = press(m, "dpad_up", 6.0, PRONOUNS)
    assert px(c.point)[1] < 330
    (c,) = press(m, "x", 7.0, PRONOUNS)
    assert px(c.point) == (832, 752)
    (c,) = press(m, "a", 8.0, PRONOUNS)
    assert px(c.point) == (1088, 752)
    # Back on Customize! once it closes.
    (c,) = m.update(frozenset(), 9.0, GAMEPLAY)
    assert px(c.point) == (1254, 492)


def test_holding_down_on_a_pronoun_list_holds_its_arrow():
    m = opened(PRONOUNS)
    m.update(frozenset({"dpad_down"}), 1.0, PRONOUNS)
    commands = m.update(frozenset({"dpad_down"}), 1.5, PRONOUNS)
    assert [c.kind for c in commands] == ["hold"]
    commands = m.update(frozenset(), 2.0, PRONOUNS)
    assert [c.kind for c in commands] == ["release", "hover"]


def test_right_stick_scrolls_and_then_hovers_the_row_under_the_cursor():
    m = opened(TOONSYNC)
    press(m, "dpad_down", 1.0, TOONSYNC)
    (c,) = m.update(frozenset({"rs_down"}), 2.0, TOONSYNC)
    assert c.kind == "scroll" and c.notches == -1
    m.update(frozenset(), 2.05, TOONSYNC)
    moved = replace(TOONSYNC, rows=tuple(replace(r, y=r.y - 0.03) for r in TOONSYNC.rows))
    assert m.update(frozenset(), 2.1, moved) == []
    (c,) = m.update(frozenset(), 2.3, moved)
    assert c.kind == "hover" and m.row_y == pytest.approx(TOONSYNC.rows[0].y - 0.03)


def test_closing_forgets_the_tab_and_row():
    m = opened()
    press(m, "dpad_down", 1.0, GAMEPLAY)
    m.update(frozenset(), 2.0, OptionsScreen())
    assert m.row_y is None
    assert m.update(frozenset(), 3.0, GAMEPLAY) == []  # opened again: nothing hovered


# --- Audio sliders and the frame's color ---

AUDIO = replay("options_audio_1920x1009")


def test_reads_the_audio_sliders():
    assert [r.kind for r in AUDIO.rows] == ["toggle", "slider", "toggle"]
    music = AUDIO.rows[1]
    assert abs(px(music.point)[0] - 1135) <= 2 and px(music.point)[1] == 563  # the knob
    assert abs(px(_center_x(music.left))[0] - 1012) <= 3 and abs(px(_center_x(music.right))[0] - 1318) <= 3
    assert AUDIO.cut == (False, True)  # Sound Effects Volume, below


def _center_x(x):
    return o._center(x, 0.0)


def test_left_and_right_drag_a_slider_knob_a_step():
    m = opened(AUDIO)
    press(m, "dpad_down", 1.0, AUDIO)
    (c,) = press(m, "dpad_down", 2.0, AUDIO)
    assert px(c.point)[0] == px(AUDIO.rows[1].point)[0]  # hovered on its knob
    (c,) = press(m, "dpad_right", 3.0, AUDIO)
    start, end = px(c.point)[0], px(c.to)[0]
    assert c.kind == "drag" and 10 < end - start < 20  # 5% of the track
    # Pressed again before the screen shows it moved: on from where it was left.
    (c,) = press(m, "dpad_right", 3.2, AUDIO)
    assert px(c.point)[0] == end and px(c.to)[0] > end
    (c,) = press(m, "dpad_left", 5.0, AUDIO)
    assert px(c.to)[0] < px(c.point)[0]


def test_a_slider_at_its_end_does_nothing():
    music = AUDIO.rows[1]
    full = replace(AUDIO, rows=(replace(music, knob=music.right - o.SLIDER_KNOB[0] / 2),))
    m = opened(full)
    press(m, "dpad_down", 1.0, full)
    assert press(m, "dpad_right", 2.0, full) == []


def test_frames_in_options_are_the_tabs_blue():
    m = opened()
    (c,) = press(m, "dpad_down", 1.0, GAMEPLAY)
    assert c.color == o.FRAME_BLUE
    (c,) = OptionsMapper().update(frozenset(), 0.0, PRONOUNS)
    assert c.color == o.FRAME_BLUE
