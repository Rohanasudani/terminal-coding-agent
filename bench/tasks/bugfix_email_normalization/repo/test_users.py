from users import normalize_email


def test_trims_email():
    assert normalize_email(" user@example.com ") == "user@example.com"


def test_lowercases_email():
    assert normalize_email("MAYA@EXAMPLE.COM") == "maya@example.com"
