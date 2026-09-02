import shutil
from pathlib import Path

from termagent.agent import TerminalAgent
from termagent.models import AgentConfig


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
