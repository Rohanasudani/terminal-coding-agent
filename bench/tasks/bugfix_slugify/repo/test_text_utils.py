from text_utils import slugify


def test_slugifies_title():
    assert slugify("Hello World") == "hello-world"


def test_trims_extra_space():
    assert slugify("  Ship   It  ") == "ship-it"
