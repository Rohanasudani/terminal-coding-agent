from pathlib import Path

from termagent.bench import run_benchmark, write_markdown_report, write_report


def test_benchmark_persists_trace_dirs_and_reports_metadata(tmp_path: Path):
    repo_root = Path(__file__).parents[1]
    tasks_dir = repo_root / "bench" / "tasks"
    artifacts_dir = tmp_path / "artifacts"

    results = run_benchmark(repo_root, tasks_dir=tasks_dir, artifacts_dir=artifacts_dir)

    assert len(results) >= 6
    assert all(result.passed for result in results)
    assert all(Path(result.trace_dir).exists() for result in results)
    assert {result.language for result in results} == {"python"}


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
