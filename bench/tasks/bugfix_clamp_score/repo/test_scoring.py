from scoring import clamp_score


def test_keeps_valid_score():
    assert clamp_score(87) == 87


def test_clamps_low_score():
    assert clamp_score(-4) == 0


def test_clamps_high_score():
    assert clamp_score(140) == 100
