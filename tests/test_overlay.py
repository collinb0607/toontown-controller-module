from ttcontroller.overlay import frame_image


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
