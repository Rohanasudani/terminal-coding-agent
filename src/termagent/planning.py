from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .models import ToolCall, ToolResult
from .safety import resolve_inside_root


@dataclass(frozen=True)
class TaskPlan:
    summary: str
    expected_paths: tuple[str, ...]
    acceptance_checks: tuple[str, ...]


@dataclass
class ProgressLedger:
    enabled: bool
    phase: str = "discover"
    plan: TaskPlan | None = None
    stagnation_events: int = 0
    discovery_actions: int = 0
    transition_events: int = 0
    transition_required: bool = False
    inspected_paths: list[str] = field(default_factory=list)
    inspected_symbols: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    _last_signature: str | None = field(default=None, init=False)
    _repeat_count: int = field(default=0, init=False)
    _cycle_discovery_actions: int = field(default=0, init=False)
    _cycle_no_new_evidence: int = field(default=0, init=False)
    _evidence_signatures: set[str] = field(default_factory=set, init=False)

    discovery_tools = frozenset({"search", "read_file", "code_map", "find_references"})

    def record_proposal(self, call: ToolCall) -> bool:
        """Return true when an inspection proposal repeats without intervening progress."""
        if not self.enabled:
            return False
        signature = action_signature(call)
        if signature == self._last_signature:
            self._repeat_count += 1
        else:
            self._last_signature = signature
            self._repeat_count = 1
        if call.name not in {
            "search",
            "read_file",
            "code_map",
            "find_references",
            "run_shell",
            "git_diff",
        }:
            return False
        return self._repeat_count >= 3

    def record_discovery(
        self,
        call: ToolCall,
        result: ToolResult,
        repo: Path,
        *,
        max_actions: int,
    ) -> bool:
        """Record successful inspection evidence and return whether transition is now required."""
        if not self.enabled or call.name not in self.discovery_tools or result.status != "ok":
            return False

        self.discovery_actions += 1
        self._cycle_discovery_actions += 1
        if self._record_evidence(call, result, repo):
            self._cycle_no_new_evidence = 0
        else:
            self._cycle_no_new_evidence += 1
        if self._cycle_discovery_actions >= max_actions or self._cycle_no_new_evidence >= 2:
            self.transition_required = True
        return self.transition_required

    def transition_allows(self, call: ToolCall) -> bool:
        if not self.transition_required:
            return True
        if self.plan is None:
            return call.name == "set_task_plan"
        return call.name in {"plan_patch", "plan_patch_set"}

    def record_transition_deferral(self) -> None:
        self.transition_events += 1

    def mark_patch_planned(self) -> None:
        self.reset_discovery_cycle()
        self.mark_progress("implement")

    def reset_discovery_cycle(self) -> None:
        self._cycle_discovery_actions = 0
        self._cycle_no_new_evidence = 0
        self.transition_required = False

    def evidence_summary(self) -> str:
        paths = ", ".join(self.inspected_paths[-6:]) or "none recorded"
        symbols = ", ".join(self.inspected_symbols[-6:]) or "none recorded"
        queries = ", ".join(self.search_queries[-4:]) or "none recorded"
        return f"Inspected paths: {paths}. Symbols: {symbols}. Search queries: {queries}."

    def register_plan(self, metadata: dict[str, object]) -> None:
        summary = metadata.get("summary")
        expected_paths = metadata.get("expected_paths")
        acceptance_checks = metadata.get("acceptance_checks")
        if not isinstance(summary, str):
            return
        if not isinstance(expected_paths, list) or not all(
            isinstance(path, str) for path in expected_paths
        ):
            return
        if not isinstance(acceptance_checks, list) or not all(
            isinstance(check, str) for check in acceptance_checks
        ):
            return
        self.plan = TaskPlan(summary, tuple(expected_paths), tuple(acceptance_checks))
        self.mark_progress("plan")

    def mark_progress(self, phase: str) -> None:
        self.phase = phase
        self._last_signature = None
        self._repeat_count = 0

    def missing_expected_paths(self, repo: Path) -> list[str]:
        if self.plan is None:
            return []
        return [path for path in self.plan.expected_paths if not (repo / path).is_file()]

    def _record_evidence(self, call: ToolCall, result: ToolResult, repo: Path) -> bool:
        signature = hashlib.sha256(result.output.encode("utf-8")).hexdigest()
        is_new = signature not in self._evidence_signatures
        self._evidence_signatures.add(signature)

        if call.name == "read_file":
            path = result.metadata.get("path", call.arguments.get("path"))
            if isinstance(path, str):
                candidate = Path(path)
                try:
                    normalized = os.fspath(candidate.resolve().relative_to(repo.resolve()))
                except ValueError:
                    normalized = str(call.arguments.get("path", path))
                _append_unique(self.inspected_paths, normalized)
        if call.name in {"code_map", "find_references"}:
            value = call.arguments.get("query") or call.arguments.get("symbol")
            if isinstance(value, str) and value.strip():
                _append_unique(self.inspected_symbols, value.strip())
        if call.name == "search":
            value = call.arguments.get("query")
            if isinstance(value, str) and value.strip():
                _append_unique(self.search_queries, value.strip())
        return is_new


def validate_task_plan(
    repo: Path,
    summary: object,
    expected_paths: object,
    acceptance_checks: object,
) -> TaskPlan:
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("task plan summary must be a non-empty string")
    if len(summary) > 2_000:
        raise ValueError("task plan summary exceeds 2000 characters")
    paths = _string_list(expected_paths, "expected_paths", allow_empty=True)
    checks = _string_list(acceptance_checks, "acceptance_checks", allow_empty=False)
    if len(paths) > 20 or len(checks) > 20:
        raise ValueError("task plans support at most 20 paths and 20 acceptance checks")

    normalized_paths: list[str] = []
    for path in paths:
        target = resolve_inside_root(repo, path)
        if target == repo.resolve():
            raise ValueError("expected_paths must name files, not the repository root")
        relative = os.fspath(target.relative_to(repo.resolve()))
        if relative not in normalized_paths:
            normalized_paths.append(relative)
    return TaskPlan(summary.strip(), tuple(normalized_paths), tuple(check.strip() for check in checks))


def action_signature(call: ToolCall) -> str:
    encoded = json.dumps(
        {"name": call.name, "arguments": call.arguments},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _string_list(value: object, name: str, *, allow_empty: bool) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise TypeError(f"{name} must be a list of non-empty strings")
    if not value and not allow_empty:
        raise ValueError(f"{name} must not be empty")
    return value


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
