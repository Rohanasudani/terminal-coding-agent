from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .diagnostics import parse_pytest_failure, tests_passed
from .models import ProviderOutput, TokenUsage, ToolCall


class Provider(ABC):
    @abstractmethod
    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        raise NotImplementedError


class MockProvider(Provider):
    """Deterministic provider for local tests and demos."""

    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        return RepairProvider().next_action(task, observations)


@dataclass
class RepairProvider(Provider):
    """A deterministic test-first repair loop for benchmarks and demos."""

    test_command: str = f"{sys.executable} -m pytest -q"

    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        return ProviderOutput(self._choose_tool(task, observations))

    def _choose_tool(self, task: str, observations: list[str]) -> ToolCall:
        joined = "\n".join(observations).lower()
        latest = observations[-1].lower() if observations else ""

        if not observations:
            return ToolCall("run_shell", {"command": self.test_command, "timeout": 60})

        if latest.startswith("run_shell: ok") and tests_passed(latest):
            return ToolCall("git_diff", {})

        if latest.startswith("run_shell: ok"):
            failure = parse_pytest_failure(observations[-1])
            if failure.symbol:
                return ToolCall("search", {"query": f"def {failure.symbol}", "glob": "*.py"})
            if failure.file_path:
                return ToolCall("read_file", {"path": failure.file_path})
            return ToolCall("search", {"query": "def ", "glob": "*.py"})

        if "calculator.py" in joined and "read_file" not in joined:
            return ToolCall("read_file", {"path": "calculator.py"})

        if latest.startswith("search: ok"):
            path = first_search_path(observations[-1])
            if path:
                return ToolCall("read_file", {"path": path})

        if latest.startswith("write_file: ok"):
            return ToolCall("run_shell", {"command": self.test_command, "timeout": 60})

        if latest.startswith("read_file: ok"):
            patch = patch_from_read_output(task, observations[-1])
            if patch:
                return ToolCall("write_file", patch)

        return ToolCall("git_diff", {})


class OpenAICompatibleProvider(Provider):
    def __init__(self, model: str, max_retries: int = 2) -> None:
        self.model = model
        self.max_retries = max(0, max_retries)
        self.api_key = os.environ.get("OPENAI_API_KEY", "")

    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        invalid_outputs: list[str] = []
        usage = TokenUsage()

        for attempt in range(1, self.max_retries + 2):
            payload = self._payload(task, observations, invalid_outputs)
            data = self._request(payload)
            usage = add_usage(usage, usage_from_response(data))
            text = extract_output_text(data)
            try:
                call = parse_tool_call(text)
                return ProviderOutput(tool_call=call, usage=usage, attempts=attempt)
            except (TypeError, ValueError) as exc:
                invalid_outputs.append(f"{text[:500]}\nerror: {exc}")

        raise RuntimeError("provider returned invalid tool JSON after retries")

    def _payload(self, task: str, observations: list[str], invalid_outputs: list[str]) -> dict[str, object]:
        repair_note = ""
        if invalid_outputs:
            repair_note = "\n\nInvalid previous outputs:\n" + "\n\n".join(invalid_outputs[-2:])

        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": provider_system_prompt()},
                {
                    "role": "user",
                    "content": f"Task:\n{task}\n\nObservations:\n"
                    + "\n\n".join(observations[-8:])
                    + repair_note,
                },
            ],
            "text": {"format": tool_call_response_format()},
        }
        return payload

    def _request(self, payload: dict[str, object]) -> dict[str, object]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the openai provider")

        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:800]
            raise RuntimeError(f"OpenAI API request failed with HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"OpenAI API request failed: {exc.reason}") from exc


def provider_system_prompt() -> str:
    return (
        "You are TermAgent, a terminal coding agent. Choose exactly one tool call. "
        "Start by gathering evidence with run_shell, search, or read_file. Prefer minimal edits. "
        "After writing files, rerun the configured tests. Use git_diff only when the work is done "
        "or you are blocked. Return only the structured tool call."
    )


def tool_call_response_format() -> dict[str, object]:
    return {
        "type": "json_schema",
        "name": "termagent_tool_call",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["name", "arguments"],
            "properties": {
                "name": {
                    "type": "string",
                    "enum": ["search", "read_file", "write_file", "run_shell", "git_diff"],
                },
                "arguments": {
                    "type": "object",
                    "additionalProperties": True,
                },
            },
        },
    }


def extract_output_text(data: dict[str, object]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str):
        return output_text.strip()

    parts: list[str] = []
    output = data.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(str(block["text"]))

    return "\n".join(parts).strip()


def parse_tool_call(text: str) -> ToolCall:
    if not text:
        raise ValueError("empty response")

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("response is not valid JSON") from exc

    if not isinstance(raw, dict):
        raise TypeError("tool call must be a JSON object")
    if not isinstance(raw.get("name"), str):
        raise TypeError("tool call name must be a string")
    if not isinstance(raw.get("arguments"), dict):
        raise TypeError("tool call arguments must be an object")

    return ToolCall(name=str(raw["name"]), arguments=dict(raw["arguments"]))


def usage_from_response(data: dict[str, object]) -> TokenUsage:
    usage = data.get("usage")
    if not isinstance(usage, dict):
        return TokenUsage()

    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0))
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0))
    return TokenUsage(input_tokens=int(input_tokens or 0), output_tokens=int(output_tokens or 0))


def add_usage(left: TokenUsage, right: TokenUsage) -> TokenUsage:
    return TokenUsage(
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
    )


def first_search_path(output: str) -> str | None:
    for line in output.splitlines():
        if ":" not in line:
            continue
        path = line.split(":", 1)[0].strip()
        if path.endswith(".py"):
            return path
    return None


def strip_numbered_lines(output: str) -> str:
    lines: list[str] = []
    for line in output.splitlines():
        if "|" not in line:
            continue
        _, content = line.split("|", 1)
        lines.append(content.removeprefix(" "))
    return "\n".join(lines) + "\n"


def patch_from_read_output(task: str, output: str) -> dict[str, str] | None:
    content = strip_numbered_lines(output)
    lowered_task = task.lower()
    path = read_path_from_observation(output)
    if not path:
        return None

    if "add" in lowered_task and "return a - b" in content:
        return {"path": path, "content": content.replace("return a - b", "return a + b")}

    if "subtract" in lowered_task and "return a + b" in content:
        return {"path": path, "content": content.replace("return a + b", "return a - b")}

    if "multiply" in lowered_task and "return a + b" in content:
        return {"path": path, "content": content.replace("return a + b", "return a * b")}

    return None


def read_path_from_observation(output: str) -> str | None:
    match = re.search(r'"path":\s*"([^"]+)"', output)
    return match.group(1) if match else None


def build_provider(
    name: str,
    model: str | None = None,
    test_command: str | None = None,
    max_retries: int = 2,
) -> Provider:
    if name == "mock":
        return MockProvider()
    if name == "repair":
        return RepairProvider(test_command or f"{sys.executable} -m pytest -q")
    if name == "openai":
        return OpenAICompatibleProvider(
            model or os.environ.get("TERMAGENT_MODEL", "gpt-5.6-luna"),
            max_retries=max_retries,
        )
    raise ValueError(f"unknown provider: {name}")
