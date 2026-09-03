from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .diagnostics import parse_pytest_failure, tests_passed
from .models import PromptProfile, ProviderOutput, TokenUsage, ToolCall


class Provider(ABC):
    @abstractmethod
    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        raise NotImplementedError


@dataclass
class RepairProvider(Provider):
    """A deterministic test-first repair loop for benchmarks and demos."""

    test_command: str = f"{sys.executable} -m pytest -q"
    pending_patch: dict[str, str] | None = field(default=None, init=False)
    pending_patch_set: list[dict[str, str]] | None = field(default=None, init=False)

    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        return ProviderOutput(self._choose_tool(task, observations))

    def _choose_tool(self, task: str, observations: list[str]) -> ToolCall:
        joined = "\n".join(observations).lower()
        latest = observations[-1].lower() if observations else ""

        if not observations:
            return ToolCall("run_shell", {"command": self.test_command, "timeout": 60})

        if latest.startswith("run_shell: ok") and tests_passed(latest):
            return ToolCall("git_diff", {})

        patch_set = patch_set_from_task(task)
        if latest.startswith("run_shell: ok") and patch_set:
            self.pending_patch_set = patch_set
            return ToolCall("plan_patch_set", {"files": patch_set})

        if latest.startswith("run_shell: ok"):
            failure = parse_pytest_failure(observations[-1])
            if failure.symbol:
                return ToolCall("code_map", {"query": failure.symbol})
            if failure.file_path:
                return ToolCall("read_file", {"path": failure.file_path})
            return ToolCall("search", {"query": "def ", "glob": "*.py"})

        if "calculator.py" in joined and "read_file" not in joined:
            return ToolCall("read_file", {"path": "calculator.py"})

        if latest.startswith("search: ok"):
            path = first_search_path(observations[-1])
            if path:
                return ToolCall("read_file", {"path": path})

        if latest.startswith("code_map: ok"):
            path = first_code_map_symbol_path(observations[-1])
            if path:
                return ToolCall("read_file", {"path": path})

        if latest.startswith("write_file: ok"):
            self.pending_patch = None
            return ToolCall("run_shell", {"command": self.test_command, "timeout": 60})

        if latest.startswith("write_patch_set: ok"):
            self.pending_patch_set = None
            return ToolCall("run_shell", {"command": self.test_command, "timeout": 60})

        if latest.startswith("plan_patch: ok") and self.pending_patch:
            return ToolCall("write_file", self.pending_patch)

        if latest.startswith("plan_patch_set: ok") and self.pending_patch_set:
            return ToolCall("write_patch_set", {"files": self.pending_patch_set})

        if latest.startswith("read_file: ok"):
            imported_symbol = symbol_imported_by_test(observations[-1])
            if imported_symbol:
                return ToolCall("search", {"query": f"def {imported_symbol}", "glob": "*.py"})
            patch = patch_from_read_output(task, observations[-1])
            if patch:
                self.pending_patch = patch
                return ToolCall("plan_patch", patch)

        return ToolCall("git_diff", {})


@dataclass
class MockProvider(Provider):
    """Deterministic provider for local tests and demos."""

    repair: RepairProvider = field(default_factory=RepairProvider)

    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        return self.repair.next_action(task, observations)


class OpenAICompatibleProvider(Provider):
    def __init__(
        self,
        model: str,
        max_retries: int = 2,
        prompt_profile: PromptProfile = "conservative",
        observation_limit: int = 6,
        max_observation_chars: int = 8_000,
    ) -> None:
        self.model = model
        self.max_retries = max(0, max_retries)
        self.prompt_profile = prompt_profile
        self.observation_limit = max(1, observation_limit)
        self.max_observation_chars = max(1_000, max_observation_chars)
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
                {"role": "system", "content": provider_system_prompt(self.prompt_profile)},
                {
                    "role": "user",
                    "content": f"Task:\n{task}\n\nObservations:\n"
                    + compact_observations(
                        observations,
                        limit=self.observation_limit,
                        max_chars=self.max_observation_chars,
                    )
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


def provider_system_prompt(profile: PromptProfile = "conservative") -> str:
    base = (
        "You are TermAgent, a terminal coding agent. Choose exactly one tool call. "
        "Start by gathering evidence with run_shell, code_map, find_references, search, or read_file. "
        "Prefer code_map for Python symbol discovery and find_references before broad edits. "
        "Prefer minimal edits. "
        "Before writing a file, call plan_patch with the exact path and content you intend to write. "
        "For coordinated multi-file edits, call plan_patch_set with all files in the group. Only call "
        "write_file or write_patch_set after reviewing the matching plan diff. After writing files, "
        "rerun the configured tests. Use git_diff only when the work is done or you are blocked. "
        "Return only the structured tool call."
    )
    profiles = {
        "conservative": (
            " Avoid broad rewrites, avoid network commands unless explicitly configured, and recover from "
            "tool validation errors by choosing a safer evidence-gathering step."
        ),
        "benchmark": (
            " Optimize for reproducible benchmark success: run the verifier early, keep edits minimal, "
            "and finish only after a clean verifier result or a clear blocker."
        ),
        "fast": " Prefer the shortest safe path to a verified diff.",
    }
    return base + profiles[profile]


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
                    "enum": [
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
                    ],
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


def compact_observations(observations: list[str], limit: int, max_chars: int) -> str:
    selected = observations[-limit:]
    text = "\n\n".join(selected)
    if len(text) <= max_chars:
        return text
    marker = "[older observation content truncated]\n"
    tail_size = max(0, max_chars - len(marker))
    return marker + text[-tail_size:]


def first_search_path(output: str) -> str | None:
    for line in output.splitlines():
        if ":" not in line:
            continue
        path = line.split(":", 1)[0].strip()
        if path.endswith(".py"):
            return path
    return None


def first_code_map_symbol_path(output: str) -> str | None:
    match = re.search(r"-\s+\w+\s+\w+\s+at\s+([^:\n]+\.py):\d+", output)
    return match.group(1) if match else None


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

    if "divide" in lowered_task and "return a * b" in content:
        return {"path": path, "content": content.replace("return a * b", "return a / b")}

    if "clamp" in lowered_task and "return score" in content:
        return {"path": path, "content": content.replace("return score", "return min(max(score, 0), 100)")}

    if "slug" in lowered_task and "return text.lower()" in content:
        return {
            "path": path,
            "content": content.replace(
                "return text.lower()",
                'return "-".join(text.strip().lower().split())',
            ),
        }

    if "email" in lowered_task and "return email.strip()" in content:
        return {"path": path, "content": content.replace("return email.strip()", "return email.strip().lower()")}

    if "word" in lowered_task and "return len(text)" in content:
        return {"path": path, "content": content.replace("return len(text)", "return len(text.split())")}

    return None


def patch_set_from_task(task: str) -> list[dict[str, str]] | None:
    lowered_task = task.lower()
    if "checkout" not in lowered_task or "discount" not in lowered_task or "tax" not in lowered_task:
        return None

    return [
        {
            "path": "pricing.py",
            "content": "def apply_discount(total, rate):\n    return total * (1 - rate)\n",
        },
        {
            "path": "tax.py",
            "content": "def add_tax(total, rate):\n    return total * (1 + rate)\n",
        },
    ]


def symbol_imported_by_test(output: str) -> str | None:
    path = read_path_from_observation(output)
    if not path or not path.rsplit("/", maxsplit=1)[-1].startswith("test_"):
        return None

    content = strip_numbered_lines(output)
    match = re.search(r"^from\s+\w+\s+import\s+([A-Za-z_]\w*)", content, flags=re.MULTILINE)
    return match.group(1) if match else None


def read_path_from_observation(output: str) -> str | None:
    match = re.search(r'"path":\s*"([^"]+)"', output)
    return match.group(1) if match else None


def build_provider(
    name: str,
    model: str | None = None,
    test_command: str | None = None,
    max_retries: int = 2,
    prompt_profile: PromptProfile = "conservative",
    observation_limit: int = 6,
    max_observation_chars: int = 8_000,
) -> Provider:
    if name == "mock":
        return MockProvider()
    if name == "repair":
        return RepairProvider(test_command or f"{sys.executable} -m pytest -q")
    if name == "openai":
        return OpenAICompatibleProvider(
            model or os.environ.get("TERMAGENT_MODEL", "gpt-5.6-luna"),
            max_retries=max_retries,
            prompt_profile=prompt_profile,
            observation_limit=observation_limit,
            max_observation_chars=max_observation_chars,
        )
    raise ValueError(f"unknown provider: {name}")
