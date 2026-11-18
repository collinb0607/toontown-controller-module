from ttcontroller import display_version


def test_display_version():
    assert display_version("0.9.0b1") == "0.9 beta"
    assert display_version("0.9.0b2") == "0.9 beta 2"
    assert display_version("1.0.0") == "1.0"
    assert display_version("1.2.3") == "1.2.3"
    assert display_version("1.0.0rc1") == "1.0 release candidate"
