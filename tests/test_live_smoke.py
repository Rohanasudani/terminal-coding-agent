from pathlib import Path

from termagent.live_smoke import run_live_smoke


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
