import json

import pytest

from termagent import provider
from termagent.provider import (
    OpenAICompatibleProvider,
    compact_observations,
    extract_openai_tool_call,
    openai_ssl_context,
    openai_tool_definitions,
    parse_tool_call,
    provider_system_prompt,
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
    schema = response_format["schema"]

    assert response_format["type"] == "json_schema"
    assert response_format["strict"] is True
    assert "code_map" in schema["properties"]["name"]["enum"]
    assert "find_references" in schema["properties"]["name"]["enum"]
    assert "plan_patch" in schema["properties"]["name"]["enum"]
    assert "plan_patch_set" in schema["properties"]["name"]["enum"]
    assert "write_patch_set" in schema["properties"]["name"]["enum"]
    assert_openai_strict_objects(schema)


def test_openai_function_tools_are_strict():
    tools = openai_tool_definitions()

    assert {tool["name"] for tool in tools} == {
        "search",
        "read_file",
        "code_map",
        "find_references",
        "plan_patch",
        "plan_patch_set",
        "write_file",
        "write_patch_set",
        "run_shell",
        "git_diff",
    }
    for tool in tools:
        assert tool["type"] == "function"
        assert tool["strict"] is True
        assert_openai_strict_objects(tool["parameters"])


def assert_openai_strict_objects(schema: dict[str, object]) -> None:
    if schema.get("type") == "object":
        assert schema.get("additionalProperties") is False
        properties = schema.get("properties", {})
        assert isinstance(properties, dict)
        assert set(schema.get("required", [])) == set(properties)
        for value in properties.values():
            if isinstance(value, dict):
                assert_openai_strict_objects(value)

    items = schema.get("items")
    if isinstance(items, dict):
        assert_openai_strict_objects(items)


def test_prompt_profiles_change_live_provider_instructions():
    conservative = provider_system_prompt("conservative")
    benchmark = provider_system_prompt("benchmark")

    assert "validation errors" in conservative
    assert "no &&" in conservative
    assert "Do not use run_shell for file discovery" in conservative
    assert "reproducible benchmark success" in benchmark


def test_compact_observations_caps_prompt_context():
    observations = [f"observation-{index}-" + ("x" * 50) for index in range(5)]

    compacted = compact_observations(observations, limit=3, max_chars=80)

    assert "observation-0" not in compacted
    assert len(compacted) <= 117
    assert compacted.startswith("[older observation content truncated]")


def test_parse_tool_call_requires_json_object():
    with pytest.raises(TypeError, match="arguments"):
        parse_tool_call('{"name": "git_diff", "arguments": []}')


def test_extract_openai_tool_call_reads_native_function_call():
    call = extract_openai_tool_call(
        {
            "output": [
                {
                    "type": "function_call",
                    "name": "run_shell",
                    "arguments": '{"command": "pytest -q", "timeout": null}',
                }
            ]
        }
    )

    assert call == provider.ToolCall("run_shell", {"command": "pytest -q", "timeout": None})


def test_openai_provider_retries_invalid_json_and_tracks_usage(monkeypatch):
    responses = [
        {"output_text": "not json", "usage": {"input_tokens": 10, "output_tokens": 2}},
        {
            "output": [
                {
                    "type": "function_call",
                    "name": "git_diff",
                    "arguments": "{}",
                }
            ],
            "usage": {"input_tokens": 5, "output_tokens": 1},
        },
    ]
    seen_payloads: list[dict[str, object]] = []

    def fake_urlopen(request, timeout: int, context):
        assert timeout == 60
        assert context is not None
        seen_payloads.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse(responses.pop(0))

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(provider.urllib.request, "urlopen", fake_urlopen)

    output = OpenAICompatibleProvider(
        "gpt-5.6-luna",
        test_command="python -m pytest -q",
        max_retries=1,
    ).next_action("Fix tests", [])

    assert output.tool_call.name == "git_diff"
    assert output.usage.input_tokens == 15
    assert output.usage.output_tokens == 3
    assert output.attempts == 2
    assert seen_payloads[0]["tool_choice"] == "required"
    assert seen_payloads[0]["tools"] == openai_tool_definitions()
    assert seen_payloads[0]["store"] is False
    assert "Configured verifier command:\npython -m pytest -q" in seen_payloads[0]["input"][1]["content"]


def test_openai_ssl_context_requires_certificate_validation():
    context = openai_ssl_context()

    assert context.verify_mode == provider.ssl.CERT_REQUIRED


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
