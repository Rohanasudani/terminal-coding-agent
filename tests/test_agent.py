import shutil
import sys
from pathlib import Path

import termagent.agent as agent_module
from termagent.agent import TerminalAgent, normalize_tool_call, summarize_subsystems
from termagent.models import AgentConfig, ProviderOutput, TokenUsage, ToolCall


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

    assert state.completed is True
    assert state.validation_errors == 1
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
            return ProviderOutput(ToolCall("git_diff", {}))

    provider = RepeatingTestProvider()
    monkeypatch.setattr(agent_module, "build_provider", lambda *args, **kwargs: provider)

    state = TerminalAgent(
        AgentConfig(
            repo=repo,
            task="fix tests",
            provider="openai",
            approval_mode="auto",
            test_command="{python} -m pytest -q",
        )
    ).run()

    assert state.completed is True
    assert any("Do not rerun the same test command" in observation for observation in provider.seen_observations)


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

    assert state.completed is True
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
