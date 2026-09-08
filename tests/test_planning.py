import sys
from pathlib import Path

import pytest

import termagent.agent as agent_module
from termagent.agent import TerminalAgent
from termagent.models import AgentConfig, ProviderOutput, ToolCall
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
