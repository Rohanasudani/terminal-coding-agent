from copy import deepcopy

from service import create_service
from settings import resolve_settings


def test_precedence_is_per_key():
    assert resolve_settings(
        {"port": 80, "name": "default", "debug": True},
        {"port": 8080, "name": "env"},
        {"port": 9000},
    ) == {"port": 9000, "name": "env", "debug": True}


def test_falsey_overrides_are_explicit_values():
    assert resolve_settings(
        {"enabled": True, "retries": 3, "prefix": "app"}, {},
        {"enabled": False, "retries": 0, "prefix": ""},
    ) == {"enabled": False, "retries": 0, "prefix": ""}


def test_inputs_are_not_modified():
    inputs = [{"port": 80}, {"port": 8080}, {"port": 9000}]
    before = deepcopy(inputs)
    result = resolve_settings(*inputs)
    result["extra"] = "local"
    assert inputs == before


def test_service_forwards_overrides():
    assert create_service({"port": 80}, {"port": 8080}, {"port": 0}) == {
        "settings": {"port": 0},
    }
