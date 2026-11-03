from ttcontroller.movement import stick_to_movement


def test_deadzone():
    assert stick_to_movement(0.1, -0.1) == set()


def test_full_forward_runs():
    assert stick_to_movement(0.0, -1.0) == {"forward"}


def test_partial_forward_walks():
    assert stick_to_movement(0.0, -0.5) == {"forward", "walk"}


def test_diagonals():
    assert stick_to_movement(0.7, -0.7) == {"forward", "right"}
    assert stick_to_movement(-0.7, 0.7) == {"reverse", "left"}


def test_mostly_sideways_is_turn_only():
    assert stick_to_movement(-1.0, -0.2) == {"left"}
