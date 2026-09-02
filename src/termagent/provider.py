from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .diagnostics import parse_pytest_failure, tests_passed
from .models import ToolCall


class Provider(ABC):
    @abstractmethod
    def next_action(self, task: str, observations: list[str]) -> ToolCall:
        raise NotImplementedError


class MockProvider(Provider):
    """Deterministic provider for local tests and demos."""

    def next_action(self, task: str, observations: list[str]) -> ToolCall:
        return RepairProvider().next_action(task, observations)


@dataclass
class RepairProvider(Provider):
    """A deterministic test-first repair loop for benchmarks and demos."""

    test_command: str = f"{sys.executable} -m pytest -q"

    def next_action(self, task: str, observations: list[str]) -> ToolCall:
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
    def __init__(self, model: str) -> None:
        self.model = model
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required for the openai provider")

    def next_action(self, task: str, observations: list[str]) -> ToolCall:
        system = (
            "You are a terminal coding agent. Choose exactly one tool call as JSON with keys "
            "name and arguments. Prefer search/read before write. Use git_diff when finished."
        )
        payload = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": f"Task:\n{task}\n\nObservations:\n" + "\n\n".join(observations[-8:]),
                },
            ],
        }
        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "authorization": f"Bearer {self.api_key}",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))

        text = data.get("output_text", "").strip()
        try:
            raw = json.loads(text)
            return ToolCall(str(raw["name"]), dict(raw.get("arguments", {})))
        except Exception as exc:
            raise RuntimeError(f"provider returned invalid tool JSON: {text[:500]}") from exc


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


def build_provider(name: str, model: str | None = None, test_command: str | None = None) -> Provider:
    if name == "mock":
        return MockProvider()
    if name == "repair":
        return RepairProvider(test_command or f"{sys.executable} -m pytest -q")
    if name == "openai":
        return OpenAICompatibleProvider(model or os.environ.get("TERMAGENT_MODEL", "gpt-4.1-mini"))
    raise ValueError(f"unknown provider: {name}")
