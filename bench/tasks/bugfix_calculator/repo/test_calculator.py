from calculator import add


def test_adds_numbers():
    assert add(4, 6) == 10


def test_adds_zero():
    assert add(0, 9) == 9

