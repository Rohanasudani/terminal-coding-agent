from math_ops import divide


def test_divides_whole_numbers():
    assert divide(12, 3) == 4


def test_divides_to_float():
    assert divide(5, 2) == 2.5
