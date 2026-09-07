import json

import pytest

from termagent.experiments import compare_harbor_jobs


def job(
    tmp_path, name, *, model="model-a", checksum="task-hash", cost=0.01,
    error=False, completed=True, steps=7,
):
    directory = tmp_path / name
    trial = directory / "trial"
    trial.mkdir(parents=True)
    (directory / "result.json").write_text(json.dumps({
        "finished_at": "2026-09-06T00:00:00Z", "n_total_trials": 1,
    }))
    (trial / "result.json").write_text(json.dumps({
        "task_name": "task", "task_checksum": checksum,
        "agent_info": {"name": name, "version": "1", "model_info": {"provider": "openai", "name": model}},
        "verifier_result": {"rewards": {"reward": 1.0}},
        "agent_result": {"cost_usd": cost, "metadata": {
            "completed": completed, "steps": steps, "usage_is_complete": True,
        }},
        "exception_info": {"type": "timeout"} if error else None,
    }))
    return directory


def test_matched_reports_keep_errors_and_unknown_costs(tmp_path):
    report = compare_harbor_jobs([job(tmp_path, "a"), job(tmp_path, "b", cost=None, error=True)])
    assert "1/1 | 0" in report
    assert "0/1 | 1" in report
    assert "unknown" in report
    assert "Task checksums, trial counts, and provider/model IDs match" in report
    assert "Agent Completed" in report
    assert "Mean Steps" in report
    assert "Usage Complete" in report


@pytest.mark.parametrize("changes,message", [
    ({"model": "model-b"}, "different models"),
    ({"model": None}, "identified provider/model"),
    ({"checksum": "different"}, "identical task checksums"),
])
def test_unmatched_reports_are_rejected(tmp_path, changes, message):
    with pytest.raises(ValueError, match=message):
        compare_harbor_jobs([job(tmp_path, "a"), job(tmp_path, "b", **changes)])


def test_model_difference_override_still_checks_tasks(tmp_path):
    with pytest.raises(ValueError, match="identical task checksums"):
        compare_harbor_jobs([job(tmp_path, "a"), job(tmp_path, "b", checksum="other")], allow_model_difference=True)


def test_missing_trial_cannot_disappear_from_denominator(tmp_path):
    a = job(tmp_path, "a")
    (a / "result.json").write_text(json.dumps({"finished_at": "done", "n_total_trials": 2}))
    with pytest.raises(ValueError, match="missing trial"):
        compare_harbor_jobs([a, job(tmp_path, "b")])
