import json
from pathlib import Path

import pytest

from termagent.campaign import render_campaign_report, task_tree_sha256, verify_campaign


def write_manifest(path: Path, name: str, digest: str) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "tasks": [{"name": name, "content_sha256": digest}],
            }
        ),
        encoding="utf-8",
    )


def test_verify_campaign_accepts_exact_task_bytes(tmp_path: Path):
    task = tmp_path / "dataset" / "sample"
    task.mkdir(parents=True)
    (task / "instruction.md").write_text("Repair the project.\n", encoding="utf-8")
    manifest = tmp_path / "campaign.json"
    digest = task_tree_sha256(task)
    write_manifest(manifest, "sample", digest)

    verified = verify_campaign(manifest, tmp_path / "dataset")

    assert [(entry.name, entry.content_sha256) for entry in verified] == [("sample", digest)]


def test_verify_campaign_rejects_changed_task_bytes(tmp_path: Path):
    task = tmp_path / "dataset" / "sample"
    task.mkdir(parents=True)
    instruction = task / "instruction.md"
    instruction.write_text("Repair the project.\n", encoding="utf-8")
    manifest = tmp_path / "campaign.json"
    write_manifest(manifest, "sample", task_tree_sha256(task))
    instruction.write_text("A changed task.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="task content hash mismatch"):
        verify_campaign(manifest, tmp_path / "dataset")


def test_task_tree_hash_includes_relative_paths(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    (first / "a.txt").write_text("same", encoding="utf-8")
    (second / "b.txt").write_text("same", encoding="utf-8")

    assert task_tree_sha256(first) != task_tree_sha256(second)


def write_trial(
    job: Path,
    *,
    agent: str,
    checksum: str,
    reward: float | None,
    planning: bool | None = None,
) -> None:
    job.mkdir(parents=True)
    (job / "result.json").write_text(
        json.dumps({"finished_at": "2026-01-01T00:00:02+00:00", "stats": {"n_retries": 0}}),
        encoding="utf-8",
    )
    trial = job / "trial"
    trial.mkdir()
    metadata = {} if planning is None else {"task_planning": planning}
    (trial / "result.json").write_text(
        json.dumps(
            {
                "task_name": "terminal-bench/sample",
                "task_checksum": checksum,
                "agent_info": {
                    "name": agent,
                    "version": "wheel-sha256:wheel-hash" if agent == "termagent" else "1.0",
                    "model_info": {"provider": "openai", "name": "model-a"},
                },
                "agent_result": {
                    "n_input_tokens": 10,
                    "n_output_tokens": 2,
                    "cost_usd": 0.01,
                    "metadata": metadata,
                },
                "verifier_result": {"rewards": {"reward": reward}},
                "exception_info": None,
                "started_at": "2026-01-01T00:00:00+00:00",
                "finished_at": "2026-01-01T00:00:02+00:00",
            }
        ),
        encoding="utf-8",
    )


def test_render_campaign_report_requires_and_summarizes_all_arms(tmp_path: Path):
    jobs = tmp_path / "jobs"
    controls = jobs / "milestone20-controls"
    for agent, reward in (("oracle", 1.0), ("nop", 0.0)):
        trial = controls / f"sample-{agent}"
        trial.mkdir(parents=True)
        (trial / "result.json").write_text(
            json.dumps(
                {
                    "task_name": "terminal-bench/sample",
                    "task_checksum": "task-hash",
                    "agent_info": {"name": agent},
                    "verifier_result": {"rewards": {"reward": reward}},
                    "exception_info": None,
                }
            ),
            encoding="utf-8",
        )
    write_trial(
        jobs / "milestone20-sample-planning-on",
        agent="termagent", checksum="task-hash", reward=0.0, planning=True,
    )
    write_trial(
        jobs / "milestone20-sample-planning-off",
        agent="termagent", checksum="task-hash", reward=1.0, planning=False,
    )
    write_trial(
        jobs / "milestone20-sample-codex",
        agent="codex", checksum="task-hash", reward=1.0,
    )
    manifest = tmp_path / "campaign.json"
    manifest.write_text(
        json.dumps(
            {
                "model": {"provider": "openai", "name": "model-a"},
                "job_prefix": "milestone20",
                "harbor": {"version": "0.22.0"},
                "termagent": {"wheel_sha256": "wheel-hash"},
                "trials_per_task": 1,
                "tasks": [{"name": "sample"}],
                "arms": [
                    {"name": "termagent-planning-on", "agent": "termagent"},
                    {"name": "termagent-planning-off", "agent": "termagent"},
                    {"name": "codex-baseline", "agent": "codex", "version": "1.0"},
                ],
            }
        ),
        encoding="utf-8",
    )

    report = render_campaign_report(manifest, jobs)

    assert "| `codex-baseline` | 1/1 | 0 | $0.010000 |" in report
    assert "| `termagent-planning-on` | 0/1 | 0 | $0.010000 |" in report
    assert "`task-hash`" in report
