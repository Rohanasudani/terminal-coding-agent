import json

import pytest

from termagent import provider
from termagent.provider import (
    OpenAICompatibleProvider,
    parse_tool_call,
    symbol_imported_by_test,
    tool_call_response_format,
)


class FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_tool_call_response_format_uses_strict_schema():
    response_format = tool_call_response_format()

    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True


def test_parse_tool_call_requires_json_object():
    with pytest.raises(TypeError, match="arguments"):
        parse_tool_call('{"name": "git_diff", "arguments": []}')


def test_openai_provider_retries_invalid_json_and_tracks_usage(monkeypatch):
    responses = [
        {"output_text": "not json", "usage": {"input_tokens": 10, "output_tokens": 2}},
        {
            "output_text": '{"name": "git_diff", "arguments": {}}',
            "usage": {"input_tokens": 5, "output_tokens": 1},
        },
    ]
    seen_payloads: list[dict[str, object]] = []

    def fake_urlopen(request, timeout: int):
        assert timeout == 60
        seen_payloads.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse(responses.pop(0))

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(provider.urllib.request, "urlopen", fake_urlopen)

    output = OpenAICompatibleProvider("gpt-5.6-luna", max_retries=1).next_action("Fix tests", [])

    assert output.tool_call.name == "git_diff"
    assert output.usage.input_tokens == 15
    assert output.usage.output_tokens == 3
    assert output.attempts == 2
    assert seen_payloads[0]["text"] == {"format": tool_call_response_format()}


def test_symbol_imported_by_test_extracts_imported_function():
    observation = """
read_file: ok
metadata: {"path": "/tmp/repo/test_users.py"}
   1 | from users import normalize_email
   2 |
   3 | def test_lowercases_email():
   4 |     assert normalize_email("MAYA@EXAMPLE.COM") == "maya@example.com"
"""

    assert symbol_imported_by_test(observation) == "normalize_email"
