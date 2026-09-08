from pathlib import Path

import pytest

from termagent.bench import run_benchmark, write_markdown_report, write_report


def test_benchmark_persists_trace_dirs_and_reports_metadata(tmp_path: Path):
    repo_root = Path(__file__).parents[1]
    tasks_dir = repo_root / "bench" / "tasks"
    artifacts_dir = tmp_path / "artifacts"

    results = run_benchmark(repo_root, tasks_dir=tasks_dir, artifacts_dir=artifacts_dir)

    assert len(results) >= 7
    assert all(result.passed for result in results)
    assert all(Path(result.trace_dir).exists() for result in results)
    assert {"python", "javascript"}.issubset({result.language for result in results})


def test_benchmark_writes_json_and_markdown_reports(tmp_path: Path):
    repo_root = Path(__file__).parents[1]
    results = run_benchmark(
        repo_root,
        tasks_dir=repo_root / "bench" / "tasks",
        artifacts_dir=tmp_path / "artifacts",
    )
    json_path = tmp_path / "latest.json"
    markdown_path = tmp_path / "latest.md"

    write_report(results, json_path)
    write_markdown_report(results, markdown_path)

    assert '"pass_rate": 1.0' in json_path.read_text(encoding="utf-8")
    assert "| bugfix_calculator |" in markdown_path.read_text(encoding="utf-8")


def test_benchmark_trials_keep_separate_traces_and_provider_override(tmp_path):
    root = Path(__file__).parents[1]
    results = run_benchmark(
        root, tasks_dir=root / "bench" / "tasks", artifacts_dir=tmp_path,
        provider="mock", repeats=2,
    )
    assert len(results) == 16
    assert all(result.provider == "mock" for result in results)
    assert {result.trial for result in results} == {1, 2}
    assert all(result.task_planning is False for result in results)
    assert len({result.trace_dir for result in results}) == 16
    assert all(not result.baseline_passed for result in results)


@pytest.mark.parametrize("kwargs", [{"repeats": 0}, {"max_cost_usd": -1}, {"max_total_cost_usd": float("nan")}])
def test_benchmark_rejects_invalid_limits(tmp_path, kwargs):
    with pytest.raises(ValueError):
        run_benchmark(tmp_path, **kwargs)


def test_empty_benchmark_is_not_a_success(tmp_path):
    with pytest.raises(ValueError, match="no benchmark tasks"):
        run_benchmark(tmp_path, tasks_dir=tmp_path)
