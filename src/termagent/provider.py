from __future__ import annotations

import json
import os
import sys
import urllib.request
from abc import ABC, abstractmethod

from .models import ToolCall


class Provider(ABC):
    @abstractmethod
    def next_action(self, task: str, observations: list[str]) -> ToolCall:
        raise NotImplementedError


class MockProvider(Provider):
    """Deterministic provider for local tests and demos."""

    def next_action(self, task: str, observations: list[str]) -> ToolCall:
        joined = "\n".join(observations).lower()
        latest = observations[-1].lower() if observations else ""

        if not observations:
            return ToolCall("search", {"query": "def add", "glob": "*.py"})

        if "calculator.py" in joined and "read_file" not in joined:
            return ToolCall("read_file", {"path": "calculator.py"})

        if latest.startswith("run_shell: ok"):
            return ToolCall("git_diff", {})

        if "file unchanged" in latest or "--- a/calculator.py" in latest:
            return ToolCall("run_shell", {"command": f"{sys.executable} -m pytest -q", "timeout": 60})

        if "return a - b" in joined:
            return ToolCall("write_file", {"path": "calculator.py", "content": "def add(a, b):\n    return a + b\n"})

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


def build_provider(name: str, model: str | None = None) -> Provider:
    if name == "mock":
        return MockProvider()
    if name == "openai":
        return OpenAICompatibleProvider(model or os.environ.get("TERMAGENT_MODEL", "gpt-4.1-mini"))
    raise ValueError(f"unknown provider: {name}")
