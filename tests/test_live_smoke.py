import shutil
from pathlib import Path

import termagent.live_smoke as smoke_module
from termagent.live_smoke import run_live_smoke
from termagent.models import AgentState


def test_live_smoke_skips_without_api_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = tmp_path / "live.md"

    result = run_live_smoke(tmp_path, report_path=report)

    assert result.status == "skipped"
    assert result.estimated_cost_usd == 0.0
    assert "OPENAI_API_KEY is not set" in result.note
    assert "no live API call was made" in report.read_text(encoding="utf-8")


def test_live_smoke_report_is_sanitized_without_raw_trace(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    report = tmp_path / "live.md"

    run_live_smoke(tmp_path, model="test-model", report_path=report)

    content = report.read_text(encoding="utf-8")
    assert "test-model" in content
    assert "OPENAI_API_KEY=\"your-api-key\"" in content
    assert "Bearer" not in content
    assert "authorization" not in content.lower()


def test_live_smoke_does_not_trust_agent_success_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-only-not-used")
    fixture = tmp_path / "tests" / "fixtures" / "sample_repo"
    shutil.copytree(Path(__file__).parent / "fixtures" / "sample_repo", fixture)

    class FalseSuccessAgent:
        def __init__(self, config):
            self.config = config

        def run(self):
            (self.config.repo / "test_calculator.py").write_text("def test_fake():\n    pass\n")
            return AgentState(completed=True, tests_passed=True, final_answer="private provider payload")

    monkeypatch.setattr(smoke_module, "TerminalAgent", FalseSuccessAgent)
    result = run_live_smoke(tmp_path)
    assert result.status == "failed"
    assert not result.tests_passed
    assert "private provider payload" not in (tmp_path / "docs" / "live-provider-demo.md").read_text()
