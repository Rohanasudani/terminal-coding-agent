"""Deterministic fixture provider used for regression tests and offline demos.

This module intentionally contains task-specific repair patterns. It validates the
agent loop and tool contracts; it is not a model and must not be used as quality
evidence for arbitrary repository tasks.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from .diagnostics import parse_pytest_failure, tests_passed
from .models import ProviderOutput, ToolCall
from .observations import first_code_map_symbol_path, first_search_path
from .provider import Provider


@dataclass
class FixtureProvider(Provider):
    """Run transparent, task-specific repairs against bundled fixtures."""

    test_command: str = f"{sys.executable} -m pytest -q"
    task_planning: bool = False
    pending_patch: dict[str, str] | None = field(default=None, init=False)
    pending_patch_set: list[dict[str, str]] | None = field(default=None, init=False)
    pending_action_after_plan: ToolCall | None = field(default=None, init=False)

    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        return ProviderOutput(self._choose_tool(task, observations))

    def _choose_tool(self, task: str, observations: list[str]) -> ToolCall:
        joined = "\n".join(observations).lower()
        latest = observations[-1].lower() if observations else ""

        if not observations:
            return ToolCall("run_shell", {"command": self.test_command, "timeout": 60})

        if latest.startswith("set_task_plan: ok") and self.pending_action_after_plan:
            action = self.pending_action_after_plan
            self.pending_action_after_plan = None
            return action

        if latest.startswith("run_shell: ok") and tests_passed(latest):
            return ToolCall("git_diff", {})

        patch_set = patch_set_from_task(task)
        if latest.startswith("run_shell: ok") and patch_set:
            self.pending_patch_set = patch_set
            return self._with_task_plan(
                task,
                ToolCall("plan_patch_set", {"files": patch_set}),
                [item["path"] for item in patch_set],
            )

        if latest.startswith("run_shell: ok"):
            failure = parse_pytest_failure(observations[-1])
            if failure.symbol:
                return ToolCall("code_map", {"query": failure.symbol})
            if failure.file_path:
                return ToolCall("read_file", {"path": failure.file_path})
            task_symbol = symbol_from_task(task)
            if task_symbol:
                return ToolCall("code_map", {"query": task_symbol})
            return ToolCall("code_map", {})

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
                return self._with_task_plan(
                    task,
                    ToolCall("plan_patch", patch),
                    [patch["path"]],
                )

        return ToolCall("git_diff", {})

    def _with_task_plan(self, task: str, action: ToolCall, expected_paths: list[str]) -> ToolCall:
        if not self.task_planning:
            return action
        self.pending_action_after_plan = action
        return ToolCall(
            "set_task_plan",
            {
                "summary": task.strip() or "Complete the requested repository change",
                "expected_paths": expected_paths,
                "acceptance_checks": [f"The configured verifier passes: {self.test_command}"],
            },
        )


@dataclass
class MockProvider(Provider):
    fixture: FixtureProvider = field(default_factory=FixtureProvider)

    def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
        return self.fixture.next_action(task, observations)


def symbol_from_task(task: str) -> str | None:
    match = re.search(r"\bfix\s+([A-Za-z_$][\w$]*)", task, flags=re.IGNORECASE)
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

    replacements = (
        ("add", "return a - b", "return a + b"),
        ("subtract", "return a + b", "return a - b"),
        ("multiply", "return a + b", "return a * b"),
        ("divide", "return a * b", "return a / b"),
        ("clamp", "return score", "return min(max(score, 0), 100)"),
        ("slug", "return text.lower()", 'return "-".join(text.strip().lower().split())'),
        ("email", "return email.strip()", "return email.strip().lower()"),
        ("word", "return len(text)", "return len(text.split())"),
        ("tax", "return subtotal * (1 - taxRate);", "return subtotal * (1 + taxRate);"),
    )
    for task_hint, old, new in replacements:
        if task_hint in lowered_task and old in content:
            return {"path": path, "content": content.replace(old, new)}
    return None


def patch_set_from_task(task: str) -> list[dict[str, str]] | None:
    lowered_task = task.lower()
    if "checkout" not in lowered_task or "discount" not in lowered_task or "tax" not in lowered_task:
        return None
    return [
        {"path": "pricing.py", "content": "def apply_discount(total, rate):\n    return total * (1 - rate)\n"},
        {"path": "tax.py", "content": "def add_tax(total, rate):\n    return total * (1 + rate)\n"},
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
