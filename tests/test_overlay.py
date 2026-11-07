from ttcontroller.overlay import POINTER_PULSE, frame_image, pointer_image, pointer_scale


def test_frame_is_clear_inside_and_solid_on_the_outline():
    image = frame_image(60, 40, thickness=4, glow=6, radius=6)
    pad = 8  # half the outline plus the glow
    assert image.shape == (40 + 2 * pad, 60 + 2 * pad, 4)
    alpha = image[..., 3]
    assert alpha[pad + 20, pad + 30] == 0 and alpha[pad + 20, pad + 4] == 0  # the item shows through
    # The outline sits on the item's edge, half in and half out.
    assert alpha[pad + 20, pad] == 255 and alpha[pad + 20, pad - 1] == 255
    # The glow fades out away from the outline.
    assert 0 < alpha[pad + 20, pad - 5] < alpha[pad + 20, pad - 3] < 255
    assert alpha[pad + 20, 0] < 20


def test_frame_is_premultiplied():
    image = frame_image(30, 30, thickness=3, glow=4, radius=4).astype(int)
    for channel in range(3):
        assert (image[..., channel] <= image[..., 3]).all()


def test_pointer_is_a_gold_triangle_pointing_right():
    image = pointer_image(40).astype(int)
    h, w = image.shape[:2]
    assert h > w  # taller than long
    middle = h // 2
    # Opaque gold inside, with its tip at the right middle and nothing at the right corners.
    b, g, r, a = image[middle, w // 3]
    assert a == 255 and r > 200 and g > 150 and b < 100
    assert image[middle, w - 4, 3] > 0 and image[1, w - 3, 3] == 0 and image[h - 2, w - 3, 3] == 0


def test_pointer_pulses_and_repeats():
    sizes = {round(pointer_scale(t / 100), 3) for t in range(0, 90)}
    assert min(sizes) >= 1 - POINTER_PULSE - 1e-9 and max(sizes) <= 1 + POINTER_PULSE + 1e-9
    assert len(sizes) > 3
    assert pointer_scale(0.1) == pointer_scale(0.1 + 0.9)
