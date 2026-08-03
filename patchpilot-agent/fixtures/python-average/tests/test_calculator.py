from calculator import average


def test_average_values():
    assert average([2.0, 4.0, 6.0]) == 4.0


def test_average_empty_returns_zero():
    assert average([]) == 0.0

