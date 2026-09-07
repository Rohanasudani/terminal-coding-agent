import pytest
from pagination import collect_records


def test_empty_page_can_have_more_records():
    pages = {
        None: {"items": [1], "next_cursor": "second"},
        "second": {"items": [], "next_cursor": "third"},
        "third": {"items": [2, 3], "next_cursor": None},
    }
    assert collect_records(pages.__getitem__) == [1, 2, 3]


def test_empty_string_is_a_valid_cursor():
    pages = {
        None: {"items": [], "next_cursor": ""},
        "": {"items": [7], "next_cursor": None},
    }
    assert collect_records(pages.__getitem__) == [7]


def test_terminal_empty_page():
    assert collect_records(lambda _: {"items": [], "next_cursor": None}) == []


def test_cursor_cycle_raises():
    calls = []

    def fetch(cursor):
        calls.append(cursor)
        assert len(calls) <= 4, "cursor cycle was not detected"
        return {"items": [1], "next_cursor": "again"}

    with pytest.raises(ValueError):
        collect_records(fetch)
