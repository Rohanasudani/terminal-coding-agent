import sys
from pathlib import Path

import pytest

import termagent.agent as agent_module
from termagent.agent import TerminalAgent
from termagent.models import AgentConfig, ProviderOutput, ToolCall, ToolResult
from termagent.planning import ProgressLedger, validate_task_plan


def test_task_plan_normalizes_paths_inside_repository(tmp_path: Path):
    plan = validate_task_plan(
        tmp_path,
        "Create a small module",
        ["src/module.py", "src/module.py"],
        ["The module compiles"],
    )

    assert plan.expected_paths == ("src/module.py",)
    assert plan.acceptance_checks == ("The module compiles",)


def test_task_plan_rejects_paths_outside_repository(tmp_path: Path):
    with pytest.raises(ValueError, match="escapes repository root"):
        validate_task_plan(tmp_path, "Escape", ["../outside.py"], ["File exists"])


def test_agent_rejects_nonpositive_discovery_budget(tmp_path: Path):
    with pytest.raises(ValueError, match="max_discovery_actions"):
        TerminalAgent(
            AgentConfig(repo=tmp_path, task="Fix the bug", max_discovery_actions=0)
        )


def test_planning_mode_requires_plan_before_patch(tmp_path: Path, monkeypatch):
    class PrematurePatchProvider:
        def next_action(self, task, observations):
            return ProviderOutput(
                ToolCall("plan_patch", {"path": "module.py", "content": "value = 1\n"})
            )

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: PrematurePatchProvider())
    state = TerminalAgent(
        AgentConfig(
            repo=tmp_path,
            task="Create module.py",
            provider="openai",
            task_planning=True,
            max_validation_errors=1,
        )
    ).run()

    assert not state.completed
    assert "set_task_plan is required" in (state.final_answer or "")
    assert not (tmp_path / "module.py").exists()


def test_required_change_plan_needs_expected_output_path(tmp_path: Path, monkeypatch):
    class EmptyDeliverablesProvider:
        def next_action(self, task, observations):
            return ProviderOutput(
                ToolCall(
                    "set_task_plan",
                    {
                        "summary": "Create the requested file",
                        "expected_paths": [],
                        "acceptance_checks": ["Verifier passes"],
                    },
                )
            )

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: EmptyDeliverablesProvider())
    state = TerminalAgent(
        AgentConfig(
            repo=tmp_path,
            task="Create output.txt",
            provider="openai",
            task_planning=True,
            require_changes=True,
            max_validation_errors=1,
        )
    ).run()

    assert not state.completed
    assert "at least one expected output path" in (state.final_answer or "")


def test_planned_empty_repository_task_reaches_verified_diff(tmp_path: Path, monkeypatch):
    verifier = f"{sys.executable} -m compileall -q module.py"
    content = "def answer():\n    return 42\n"
    calls = iter(
        [
            ToolCall(
                "set_task_plan",
                {
                    "summary": "Create the requested module",
                    "expected_paths": ["module.py"],
                    "acceptance_checks": ["module.py compiles"],
                },
            ),
            ToolCall("plan_patch", {"path": "module.py", "content": content}),
            ToolCall("write_file", {"path": "module.py", "content": content}),
            ToolCall("run_shell", {"command": verifier}),
            ToolCall("git_diff", {}),
        ]
    )

    class PlannedProvider:
        def next_action(self, task, observations):
            return ProviderOutput(next(calls))

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: PlannedProvider())
    state = TerminalAgent(
        AgentConfig(
            repo=tmp_path,
            task="Create module.py",
            provider="openai",
            approval_mode="auto",
            test_command=verifier,
            task_planning=True,
            require_changes=True,
            max_steps=5,
        )
    ).run()

    assert state.completed
    assert state.phase == "complete"
    assert state.task_plan_summary == "Create the requested module"
    assert state.expected_paths == ["module.py"]
    assert state.stagnation_events == 0
    assert "def answer" in (tmp_path / "module.py").read_text()


@pytest.mark.parametrize("enabled,expected_events", [(True, 2), (False, 0)])
def test_repeated_discovery_is_an_ablatable_bounded_behavior(
    tmp_path: Path,
    monkeypatch,
    enabled: bool,
    expected_events: int,
):
    class RepeatingProvider:
        def next_action(self, task, observations):
            return ProviderOutput(ToolCall("code_map", {}))

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: RepeatingProvider())
    state = TerminalAgent(
        AgentConfig(
            repo=tmp_path,
            task="Create the requested file",
            provider="openai",
            task_planning=enabled,
            max_steps=4,
            max_stagnation_events=2,
        )
    ).run()

    assert state.stagnation_events == expected_events
    if enabled:
        assert "repeated no-progress" in (state.final_answer or "")


def test_progress_ledger_reports_missing_declared_outputs(tmp_path: Path):
    ledger = ProgressLedger(enabled=True)
    ledger.register_plan(
        {
            "summary": "Create output",
            "expected_paths": ["output.txt"],
            "acceptance_checks": ["output exists"],
        }
    )

    assert ledger.phase == "plan"
    assert ledger.missing_expected_paths(tmp_path) == ["output.txt"]


def test_discovery_ledger_tracks_evidence_and_requires_transition(tmp_path: Path):
    source = tmp_path / "module.py"
    source.write_text("def normalize(value):\n    return value.strip()\n", encoding="utf-8")
    ledger = ProgressLedger(enabled=True)

    assert not ledger.record_discovery(
        ToolCall("read_file", {"path": "module.py"}),
        ToolResult("ok", "1 | def normalize(value):", {"path": str(source)}),
        tmp_path,
        max_actions=2,
    )
    assert ledger.record_discovery(
        ToolCall("find_references", {"symbol": "normalize"}),
        ToolResult("ok", "module.py:1"),
        tmp_path,
        max_actions=2,
    )

    assert ledger.discovery_actions == 2
    assert ledger.inspected_paths == ["module.py"]
    assert ledger.inspected_symbols == ["normalize"]
    assert not ledger.transition_allows(ToolCall("search", {"query": "more"}))


def test_repeated_empty_evidence_requires_transition_before_full_budget(tmp_path: Path):
    ledger = ProgressLedger(enabled=True)

    for query in ("first", "second"):
        assert not ledger.record_discovery(
            ToolCall("search", {"query": query}),
            ToolResult("ok", "no matches"),
            tmp_path,
            max_actions=10,
        )
    assert ledger.record_discovery(
        ToolCall("search", {"query": "third"}),
        ToolResult("ok", "no matches"),
        tmp_path,
        max_actions=10,
    )


def test_agent_moves_from_bounded_discovery_to_model_authored_patch(tmp_path: Path, monkeypatch):
    source = tmp_path / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    verifier = f"{sys.executable} -m compileall -q module.py"
    updated = "value = 2\n"
    calls = iter(
        [
            ToolCall(
                "set_task_plan",
                {
                    "summary": "Update module value",
                    "expected_paths": ["module.py"],
                    "acceptance_checks": ["module.py compiles"],
                },
            ),
            ToolCall("read_file", {"path": "module.py"}),
            ToolCall("code_map", {"query": "value"}),
            ToolCall("search", {"query": "value", "glob": "*.py"}),
            ToolCall("plan_patch", {"path": "module.py", "content": updated}),
            ToolCall("write_file", {"path": "module.py", "content": updated}),
            ToolCall("run_shell", {"command": verifier}),
            ToolCall("git_diff", {}),
        ]
    )

    class TransitionProvider:
        def __init__(self) -> None:
            self.observations: list[str] = []

        def next_action(self, task, observations):
            self.observations = list(observations)
            return ProviderOutput(next(calls))

    provider = TransitionProvider()
    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: provider)
    state = TerminalAgent(
        AgentConfig(
            repo=tmp_path,
            task="Update module.py",
            provider="openai",
            approval_mode="auto",
            test_command=verifier,
            task_planning=True,
            require_changes=True,
            max_discovery_actions=3,
            max_steps=8,
        )
    ).run()

    assert state.completed
    assert state.discovery_actions == 3
    assert state.transition_events == 0
    assert state.inspected_paths == ["module.py"]
    assert state.inspected_symbols == ["value"]
    assert state.search_queries == ["value"]
    assert any("controller_transition: required" in item for item in provider.observations)
    assert source.read_text(encoding="utf-8") == updated


def test_agent_stops_provider_that_ignores_required_patch_transition(
    tmp_path: Path, monkeypatch,
):
    source = tmp_path / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")

    class DeferringProvider:
        def next_action(self, task, observations):
            if not observations:
                return ProviderOutput(
                    ToolCall(
                        "set_task_plan",
                        {
                            "summary": "Update module",
                            "expected_paths": ["module.py"],
                            "acceptance_checks": ["module updated"],
                        },
                    )
                )
            if len(observations) == 1:
                return ProviderOutput(ToolCall("read_file", {"path": "module.py"}))
            return ProviderOutput(ToolCall("search", {"query": f"value-{len(observations)}"}))

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: DeferringProvider())
    state = TerminalAgent(
        AgentConfig(
            repo=tmp_path,
            task="Update module.py",
            provider="openai",
            task_planning=True,
            require_changes=True,
            max_discovery_actions=2,
            max_stagnation_events=2,
            max_steps=8,
        )
    ).run()

    assert not state.completed
    assert state.transition_events == 2
    assert state.patch_plans == 0
    assert state.changed_files == []
    assert "required patch plan" in (state.final_answer or "")
    assert source.read_text(encoding="utf-8") == "value = 1\n"
