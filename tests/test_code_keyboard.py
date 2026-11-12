"""M14: the shticker book's Options & Codes page and its on-screen code keyboard."""

from test_book import options, press

from ttcontroller import book as b
from ttcontroller.book import BookMapper
from ttcontroller.name_keyboard import CLEAR_PRESSES, CodeKeyboard
from ttcontroller.output import type_text


def opened(at=0.0):
    """A book mapper on the Options page with the code keyboard opened (A on the box)."""
    m = BookMapper()
    m.update(frozenset(), at, options())
    out = press(m, "a", at + 1.0, options())
    assert [(c.kind, c.point) for c in out] == [("click", b.CODE_BOX)]
    assert m.showing_keyboard(options())
    return m


def typed(commands):
    return [c.name for c in commands if c.kind == "type"]


def test_submit_isnt_a_row_any_more():
    assert b.SUBMIT not in [point for point, _ in b.OPTIONS_ROWS]
    assert b.OPTIONS_ROWS[0] == (b.CODE_BOX, "code box")


def test_typing_a_code_with_ls_switching_modes():
    m = opened()
    out = press(m, "a", 2.0, options())  # q
    press(m, "ls", 3.0, options())  # capitals
    out += press(m, "a", 4.0, options())
    press(m, "ls", 5.0, options())  # symbols
    out += press(m, "a", 6.0, options())
    press(m, "ls", 7.0, options())  # lowercase again
    out += press(m, "dpad_right", 8.0, options()) + press(m, "a", 9.0, options())
    out += press(m, "x", 10.0, options()) + press(m, "y", 11.0, options())
    assert typed(out) == ["q", "Q", "1", "w", "\b", " "]
    assert m.code_keyboard.mode == "lower"


def test_the_keyboard_keeps_the_page_buttons_to_itself():
    m = opened()
    # B clears, not closes the book; X isn't the page's; Start is blocked from the overworld.
    assert "start" in m.buttons
    out = press(m, "b", 2.0, options())
    assert typed(out) == ["\b" * CLEAR_PRESSES]
    assert [(c.kind, c.point) for c in out if c.kind != "type"] == [("hover", b.CODE_BOX)]
    assert out[-1].size == b.CODE_BOX_SIZE  # the gold frame round the box
    assert not m.take_taps() and not m.showing_keyboard(options()) and "start" not in m.buttons
    # Closed: B closes the book again.
    press(m, "b", 3.0, options())
    assert m.take_taps() == ["stickerBook"]


def test_start_submits_and_comes_back_to_the_box():
    m = opened()
    out = press(m, "start", 2.0, options())
    assert [(c.kind, c.point) for c in out] == [("click", b.SUBMIT)]
    assert not m.showing_keyboard(options())
    out = m.update(frozenset(), 3.0, options())
    assert [(c.kind, c.point) for c in out] == [("hover", b.CODE_BOX)]


def test_page_buttons_still_work_and_close_it():
    m = opened()
    # The box can have TTR's focus, so RB clicks the next page's tab instead of tapping
    # the page key (which typed a "d" into it).
    out = press(m, "rb", 2.0, options())
    assert [(c.kind, c.point) for c in out] == [("click", options().tabs[1])] and not m.take_taps()
    assert not m.typing
    m.update(frozenset(), 3.0, options(dialog=True))  # or a dialog, another page
    assert not m.typing


def test_a_pause_closes_it():
    m = opened()
    m.reset_buttons()
    assert not m.showing_keyboard(options())


def test_hints_follow_the_books_buttons():
    m = opened()
    assert [b_ for b_, _ in m.code_keyboard.hints] == ["A", "X", "Y", "LS", "START", "B"]
    assert dict(m.code_keyboard.hints)["LS"] == "ABC"  # the mode LS switches to
    m.code_keyboard.switch()
    assert dict(m.code_keyboard.hints)["LS"] == "#+="


def test_modes_cycle():
    k = CodeKeyboard()
    assert k.letter == "q"
    k.switch()
    assert k.letter == "Q"
    k.switch()
    assert k.letter == "1" and k.keys[1][4] == "!"
    k.switch()
    assert k.mode == "lower"


def test_symbols_are_typed_with_shift_where_needed():
    sent = []
    type_text(lambda name, down: sent.append((name, down)), "!-")
    assert sent == [("shift", True), ("1", True), ("1", False), ("shift", False), ("-", True), ("-", False)]


def test_the_code_box_hover_has_the_gold_frame():
    m = BookMapper()
    [hover] = m.update(frozenset(), 0.0, options())
    assert hover.point == b.CODE_BOX and hover.size == b.CODE_BOX_SIZE
    [hover] = press(m, "dpad_down", 1.0, options())
    assert hover.size is None  # the other rows show their own hover


def test_lb_on_the_first_page_does_nothing():
    m = BookMapper()
    m.update(frozenset(), 0.0, options())
    assert press(m, "lb", 1.0, options()) == [] and not m.take_taps()


def test_the_book_panel_fits_the_right_page():
    from ttcontroller import name_keyboard as nk
    from ttcontroller.hint_draw import find_sheet
    sheet = nk.find_sheet()
    if sheet is None:
        return
    x, y = b.CODE_PANEL_TOP.to_client(1920, 1009)
    w, h = (round(v * 1009) for v in b.CODE_PANEL_SIZE)
    assert x - w // 2 > 965 and x + w // 2 < 1404  # off the seam and the page tabs
    assert y > 321 and y + h < 507  # under the code box's frame, above "SpeedChat Color"
    image = nk.KeyboardDrawer(sheet, find_sheet()).image(CodeKeyboard(), 1009, b.CODE_PANEL_SIZE)
    assert image.shape[:2] == (h, w)


def test_the_code_card_reads():
    from test_book import replay
    card = replay("book_options_invalid_code_1920x1009")
    assert card.page == "options" and card.code_card
    assert not replay("book_options_1920x1009").code_card


def test_a_or_b_close_the_code_card_and_go_back_to_typing_in_an_empty_box():
    from dataclasses import replace
    for button in ("a", "b"):
        m = opened()
        press(m, "start", 2.0, options())
        card = replace(options(), code_card=True)
        m.update(frozenset(), 3.0, card)
        out = press(m, button, 4.0, card)
        assert [(c.kind, c.point) for c in out] == [("click", b.CODE_CARD_CLOSE)] and not m.take_taps()
        out = m.update(frozenset(), 5.0, options())  # the card's gone: the box clicked, keyboard up
        assert ("click", b.CODE_BOX) in [(c.kind, c.point) for c in out] and m.showing_keyboard(options())
        assert typed(out) == []  # the box is emptied once the click has given it focus
        assert typed(m.update(frozenset(), 5.5, options())) == ["" * CLEAR_PRESSES]


def test_start_stays_the_books_until_let_go():
    # Submitting closes the keyboard, but Start mustn't reach the overworld (it closes the
    # book) while it's still held.
    m = opened()
    m.update(frozenset({"start"}), 2.0, options())
    assert not m.typing and "start" in m.buttons
    m.update(frozenset({"start"}), 2.5, options())
    assert "start" in m.buttons
    m.update(frozenset(), 3.0, options())
    assert "start" not in m.buttons


def test_the_b_hint_moves_onto_the_cards_red_x():
    from dataclasses import replace
    from ttcontroller import hints
    plain = hints.hints_for(hints.Context(mode="book", book=options()))
    card = hints.hints_for(hints.Context(mode="book", book=replace(options(), code_card=True)))
    b_plain = [h for h in plain if h.sprite == "B"]
    b_card = [h for h in card if h.sprite == "B"]
    assert len(b_plain) == 1 and not b_plain[0].cover  # on the book icon
    assert len(b_card) == 1 and b_card[0].cover and b_card[0].at == b.CODE_CARD_CLOSE
