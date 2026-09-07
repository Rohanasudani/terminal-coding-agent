import shutil
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import termagent.agent as agent_module
from termagent.agent import TerminalAgent, normalize_tool_call, summarize_subsystems
from termagent.models import AgentConfig, ProviderOutput, TokenUsage, ToolCall, ToolResult
from termagent.provider import ProviderError


def test_mock_agent_fixes_calculator_fixture(tmp_path: Path):
    source = Path(__file__).parent / "fixtures" / "sample_repo"
    repo = tmp_path / "repo"
    shutil.copytree(source, repo)

    agent = TerminalAgent(
        AgentConfig(
            repo=repo,
            task="Fix the calculator add bug and run tests",
            approval_mode="auto",
            max_steps=8,
            log_dir=tmp_path / "traces",
            provider="mock",
        )
    )
    state = agent.run()

    assert state.completed is True
    assert state.tests_passed is True
    assert "return a + b" in (repo / "calculator.py").read_text(encoding="utf-8")
    assert "Final diff" in (state.final_answer or "")
    assert list((tmp_path / "traces").glob("*.jsonl"))


def test_repair_agent_stops_when_test_command_needs_approval(tmp_path: Path):
    source = Path(__file__).parent / "fixtures" / "sample_repo"
    repo = tmp_path / "repo"
    shutil.copytree(source, repo)

    state = TerminalAgent(
        AgentConfig(
            repo=repo,
            task="Fix the calculator add bug and run tests",
            approval_mode="suggest",
            max_steps=4,
            provider="repair",
        )
    ).run()

    assert state.completed is False
    assert state.final_answer is not None
    assert "Blocked by safety policy" in state.final_answer


def test_agent_rejects_invalid_provider_tool_call(tmp_path: Path, monkeypatch):
    class BadProvider:
        def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
            return ProviderOutput(ToolCall("unknown_tool", {}))

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: BadProvider())

    state = TerminalAgent(AgentConfig(repo=tmp_path, task="fix tests", provider="openai")).run()

    assert state.completed is False
    assert state.final_answer is not None
    assert "invalid tool calls repeatedly" in state.final_answer


def test_agent_rejects_unplanned_write(tmp_path: Path, monkeypatch):
    class DirectWriteProvider:
        def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
            return ProviderOutput(ToolCall("write_file", {"path": "module.py", "content": "value = 1\n"}))

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: DirectWriteProvider())

    state = TerminalAgent(AgentConfig(repo=tmp_path, task="write a file", provider="openai")).run()

    assert state.completed is False
    assert state.final_answer is not None
    assert "matching plan_patch" in state.final_answer
    assert not (tmp_path / "module.py").exists()


def test_agent_recovers_from_one_invalid_tool_call(tmp_path: Path, monkeypatch):
    class RecoveringProvider:
        def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
            if not observations:
                return ProviderOutput(ToolCall("write_file", {"path": "module.py", "content": "value = 1\n"}))
            return ProviderOutput(ToolCall("git_diff", {}))

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: RecoveringProvider())

    state = TerminalAgent(
        AgentConfig(repo=tmp_path, task="recover", provider="openai", max_validation_errors=2)
    ).run()

    assert state.completed is False
    assert state.validation_errors == 1
    assert "Incomplete" in state.final_answer
    assert not (tmp_path / "module.py").exists()


def test_agent_guides_provider_after_failed_verifier(tmp_path: Path, monkeypatch):
    source = Path(__file__).parent / "fixtures" / "sample_repo"
    repo = tmp_path / "repo"
    shutil.copytree(source, repo)

    class RepeatingTestProvider:
        def __init__(self) -> None:
            self.seen_observations: list[str] = []

        def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
            self.seen_observations = list(observations)
            if not observations:
                return ProviderOutput(ToolCall("run_shell", {"command": f"{sys.executable} -m pytest -q"}))
            return ProviderOutput(ToolCall("run_shell", {"command": f"{sys.executable} -m pytest -q"}))

    provider = RepeatingTestProvider()
    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: provider)

    state = TerminalAgent(
        AgentConfig(
            repo=repo,
            task="Fix the calculator add bug and run tests",
            provider="openai",
            approval_mode="auto",
            test_command="{python} -m pytest -q",
        )
    ).run()

    assert state.completed is False
    assert state.tests_passed is False
    assert state.changed_files == []
    assert any("Do not rerun the same test command" in observation for observation in provider.seen_observations)


def test_controller_diagnoses_bad_path_without_inventing_a_patch(tmp_path: Path, monkeypatch):
    source = Path(__file__).parent / "fixtures" / "sample_repo"
    repo = tmp_path / "repo"
    shutil.copytree(source, repo)

    class BadPathThenRepeatProvider:
        def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
            if not observations:
                return ProviderOutput(ToolCall("run_shell", {"command": f"{sys.executable} -m pytest -q"}))
            if observations[-1].startswith("code_map: ok"):
                return ProviderOutput(
                    ToolCall("read_file", {"path": "tests/fixtures/sample_repo/calculator.py"})
                )
            return ProviderOutput(ToolCall("run_shell", {"command": f"{sys.executable} -m pytest -q"}))

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: BadPathThenRepeatProvider())

    state = TerminalAgent(
        AgentConfig(
            repo=repo,
            task="Fix the calculator add bug and run tests",
            provider="openai",
            approval_mode="auto",
            test_command="{python} -m pytest -q",
            max_steps=12,
        )
    ).run()

    assert state.completed is False
    assert state.tests_passed is False
    assert state.changed_files == []


def test_controller_does_not_write_a_plan_without_a_provider_write_call(tmp_path: Path, monkeypatch):
    source = Path(__file__).parent / "fixtures" / "sample_repo"
    repo = tmp_path / "repo"
    shutil.copytree(source, repo)

    class PlanThenRepeatProvider:
        def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
            if not observations:
                return ProviderOutput(ToolCall("run_shell", {"command": f"{sys.executable} -m pytest -q"}))
            if observations[-1].startswith("run_shell: ok"):
                return ProviderOutput(
                    ToolCall("plan_patch", {"path": "calculator.py", "content": "def add(a, b):\n    return a + b\n"})
                )
            return ProviderOutput(ToolCall("run_shell", {"command": f"{sys.executable} -m pytest -q"}))

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: PlanThenRepeatProvider())

    state = TerminalAgent(
        AgentConfig(
            repo=repo,
            task="Fix the calculator add bug and run tests",
            provider="openai",
            approval_mode="auto",
            test_command="{python} -m pytest -q",
            max_steps=8,
        )
    ).run()

    assert state.completed is False
    assert state.tests_passed is False
    assert state.changed_files == []
    assert "return a - b" in (repo / "calculator.py").read_text()


def test_normalize_tool_call_removes_nullable_schema_placeholders():
    call = normalize_tool_call(
        ToolCall(
            "git_diff",
            {
                "query": None,
                "path": None,
                "command": None,
                "timeout": None,
            },
        )
    )

    assert call.arguments == {}


def test_agent_rejects_unexpected_tool_arguments(tmp_path: Path, monkeypatch):
    class BadArgumentProvider:
        def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
            return ProviderOutput(ToolCall("git_diff", {"path": "module.py"}))

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: BadArgumentProvider())

    state = TerminalAgent(AgentConfig(repo=tmp_path, task="inspect diff", provider="openai")).run()

    assert state.completed is False
    assert state.final_answer is not None
    assert "unexpected argument" in state.final_answer


def test_agent_stops_before_tool_execution_when_cost_limit_is_exceeded(tmp_path: Path, monkeypatch):
    class ExpensiveProvider:
        def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
            return ProviderOutput(
                ToolCall("write_file", {"path": "module.py", "content": "value = 1\n"}),
                usage=TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000),
            )

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: ExpensiveProvider())

    state = TerminalAgent(
        AgentConfig(repo=tmp_path, task="too expensive", provider="openai", max_cost_usd=0.01)
    ).run()

    assert state.completed is False
    assert state.stopped_by_cost_limit is True
    assert state.final_answer is not None
    assert "cost ceiling" in state.final_answer
    assert not (tmp_path / "module.py").exists()


def test_agent_accounts_for_usage_when_provider_retries_fail(tmp_path: Path, monkeypatch):
    class FailedProvider:
        def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
            raise ProviderError(
                "invalid output",
                usage=TokenUsage(input_tokens=1000, output_tokens=200),
                attempts=2,
                usage_is_complete=True,
            )

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: FailedProvider())

    state = TerminalAgent(
        AgentConfig(repo=tmp_path, task="fix tests", provider="openai", model="gpt-5.6-luna")
    ).run()

    assert state.input_tokens == 1000
    assert state.output_tokens == 200
    assert state.estimated_cost_usd > 0
    assert state.usage_is_complete is True


def test_agent_accepts_grouped_plan_before_grouped_write(tmp_path: Path, monkeypatch):
    class GroupedWriteProvider:
        def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
            files = [
                {"path": "src/one.py", "content": "value = 1\n"},
                {"path": "tests/test_one.py", "content": "def test_value():\n    assert 1 == 1\n"},
            ]
            if not observations:
                return ProviderOutput(ToolCall("plan_patch_set", {"files": files}))
            if observations[-1].startswith("plan_patch_set: ok"):
                return ProviderOutput(ToolCall("write_patch_set", {"files": files}))
            return ProviderOutput(ToolCall("git_diff", {}))

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: GroupedWriteProvider())

    state = TerminalAgent(AgentConfig(repo=tmp_path, task="write grouped files", provider="openai")).run()

    assert state.completed is False
    assert sorted(state.changed_files) == ["src/one.py", "tests/test_one.py"]
    assert state.patch_plans == 2
    assert "Subsystems changed: src, tests." in (state.final_answer or "")


def test_agent_rejects_unplanned_grouped_write(tmp_path: Path, monkeypatch):
    class DirectGroupedWriteProvider:
        def next_action(self, task: str, observations: list[str]) -> ProviderOutput:
            return ProviderOutput(
                ToolCall("write_patch_set", {"files": [{"path": "module.py", "content": "value = 1\n"}]})
            )

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: DirectGroupedWriteProvider())

    state = TerminalAgent(AgentConfig(repo=tmp_path, task="write grouped files", provider="openai")).run()

    assert state.completed is False
    assert state.final_answer is not None
    assert "matching plan_patch_set" in state.final_answer
    assert not (tmp_path / "module.py").exists()


def test_summarize_subsystems_names_root_files():
    assert summarize_subsystems(["pricing.py", "tax.py"]) == "root"
    assert summarize_subsystems(["src/agent.py", "tests/test_agent.py"]) == "src, tests"


def scripted_agent(tmp_path, monkeypatch, calls, results):
    actions = iter(calls)

    class ScriptedProvider:
        def next_action(self, task, observations):
            return ProviderOutput(next(actions))

    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: ScriptedProvider())
    agent = TerminalAgent(AgentConfig(
        repo=tmp_path, task="repair", provider="openai", test_command="node --test",
        log_dir=tmp_path / "traces", max_steps=len(calls),
    ))
    outcomes = iter(results)
    monkeypatch.setattr(agent.tools, "call", lambda *args: next(outcomes))
    return agent


@pytest.mark.parametrize("output,returncode,expected", [
    ("2 passed", 1, False),
    ("", 0, True),
    ("# tests 2\n# pass 2\n# fail 0", 0, True),
    ("no tests ran", 5, False),
])
def test_completion_uses_verifier_exit_code(tmp_path, monkeypatch, output, returncode, expected):
    agent = scripted_agent(tmp_path, monkeypatch, [
        ToolCall("run_shell", {"command": "node --test"}), ToolCall("git_diff", {}),
    ], [ToolResult("ok", output, {"returncode": returncode}), ToolResult("ok", "diff")])
    state = agent.run()
    assert state.completed is expected
    assert state.tests_passed is expected


@pytest.mark.parametrize("mutation", ["write_file", "write_patch_set", "run_shell"])
def test_mutations_invalidate_earlier_verification(tmp_path, monkeypatch, mutation):
    from termagent.tools import sha256_text

    patch = {"path": "module.py", "content": "value = 2\n"}
    arguments = {"files": [patch]} if mutation == "write_patch_set" else patch
    if mutation == "run_shell":
        arguments = {"command": "npm run build"}
    agent = scripted_agent(tmp_path, monkeypatch, [
        ToolCall("run_shell", {"command": "node --test"}),
        ToolCall(mutation, arguments), ToolCall("git_diff", {}),
    ], [ToolResult("ok", "", {"returncode": 0}), ToolResult("ok", "changed"), ToolResult("ok", "diff")])
    agent.planned_writes.add(("module.py", sha256_text(patch["content"])))
    state = agent.run()
    assert not state.completed
    assert not state.tests_passed


def test_unrelated_command_cannot_claim_test_success(tmp_path, monkeypatch):
    agent = scripted_agent(tmp_path, monkeypatch, [
        ToolCall("run_shell", {"command": "echo '2 passed'"}), ToolCall("git_diff", {}),
    ], [ToolResult("ok", "2 passed", {"returncode": 0}), ToolResult("ok", "diff")])
    state = agent.run()
    assert not state.completed
    assert state.test_runs == []


def test_failed_verifier_replaces_earlier_success(tmp_path, monkeypatch):
    agent = scripted_agent(tmp_path, monkeypatch, [
        ToolCall("run_shell", {"command": "node --test"}),
        ToolCall("run_shell", {"command": "node --test"}), ToolCall("git_diff", {}),
    ], [ToolResult("ok", "", {"returncode": 0}), ToolResult("error", "timeout"), ToolResult("ok", "diff")])
    agent.config = replace(agent.config, controller_recovery=False)
    state = agent.run()
    assert not state.completed
    assert state.failed_test_runs == 1


def test_controller_finishes_instead_of_repeating_passing_verifier(tmp_path, monkeypatch):
    agent = scripted_agent(tmp_path, monkeypatch, [
        ToolCall("run_shell", {"command": "node --test"}),
        ToolCall("run_shell", {"command": "node --test"}),
    ], [ToolResult("ok", "", {"returncode": 0}), ToolResult("ok", "diff")])

    state = agent.run()

    assert state.completed
    assert state.steps == 2
    assert state.test_runs == ["node --test"]


def test_diff_without_verification_is_incomplete(tmp_path, monkeypatch):
    agent = scripted_agent(tmp_path, monkeypatch, [ToolCall("git_diff", {})], [ToolResult("ok", "diff")])
    assert not agent.run().completed


def test_malformed_provider_arguments_fail_without_crashing(tmp_path, monkeypatch):
    agent = scripted_agent(tmp_path, monkeypatch, [ToolCall("run_shell", [])], [])
    state = agent.run()
    assert state.validation_errors == 1
    assert not state.completed


def test_verification_after_write_allows_completion(tmp_path, monkeypatch):
    from termagent.tools import sha256_text

    patch = {"path": "module.py", "content": "value = 2\n"}
    agent = scripted_agent(tmp_path, monkeypatch, [
        ToolCall("write_file", patch),
        ToolCall("run_shell", {"command": "node --test"}), ToolCall("git_diff", {}),
    ], [ToolResult("ok", "changed"), ToolResult("ok", "", {"returncode": 0}), ToolResult("ok", "diff")])
    agent.planned_writes.add(("module.py", sha256_text(patch["content"])))
    assert agent.run().completed


@pytest.mark.parametrize("enabled,second_tool", [(True, "code_map"), (False, "run_shell")])
def test_controller_recovery_can_be_ablated(tmp_path, monkeypatch, enabled, second_tool):
    agent = scripted_agent(tmp_path, monkeypatch, [
        ToolCall("run_shell", {"command": "node --test"}),
        ToolCall("run_shell", {"command": "node --test"}), ToolCall("git_diff", {}),
    ], [])
    agent.config = replace(agent.config, controller_recovery=enabled)
    called = []

    def execute(name, arguments):
        called.append(name)
        return ToolResult("ok", "failed", {"returncode": 1})

    monkeypatch.setattr(agent.tools, "call", execute)
    agent.run()
    assert called[1] == second_tool
