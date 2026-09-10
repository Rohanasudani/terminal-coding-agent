import json
import sys
from pathlib import Path

from termagent import harbor_runner, provider


def test_provider_timeout_still_writes_harbor_summary(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    logs = tmp_path / "agent" / "traces"
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "repo": str(repo),
                "log_dir": str(logs),
                "task": "Inspect the repository",
                "provider": "openai",
                "model": "gpt-5.6-luna",
                "provider_retries": 1,
                "max_steps": 1,
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        provider.urllib.request,
        "urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(TimeoutError("request timed out")),
    )
    monkeypatch.setattr(provider.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(sys, "argv", ["termagent-harbor-runner", "--config", str(config)])

    assert harbor_runner.main() == 1
    summary = json.loads((logs.parent / "summary.json").read_text(encoding="utf-8"))
    assert summary["completed"] is False
    assert summary["usage_is_complete"] is False
    assert "TimeoutError" in summary["final_answer"]
