import json
import stat
from pathlib import Path

import pytest

from termagent.harbor import (
    compare_benchmark_reports,
    export_harbor_dataset,
    safe_task_name,
    write_comparison_markdown,
    write_harbor_export_manifest,
)


def test_safe_task_name_normalizes_harbor_ids():
    assert safe_task_name("Bug Fix / JS Total!") == "bug-fix-js-total"


def test_export_harbor_dataset_writes_required_task_shape(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    task_dir = tasks_dir / "bugfix_sample"
    repo = task_dir / "repo"
    repo.mkdir(parents=True)
    (repo / "app.py").write_text("print('ok')\n", encoding="utf-8")
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "instruction": "Keep the sample passing.",
                "category": "smoke",
                "language": "python",
                "verify": "{python} app.py",
            }
        ),
        encoding="utf-8",
    )

    exports = export_harbor_dataset(tasks_dir, tmp_path / "harbor", overwrite=True)

    assert len(exports) == 1
    exported = tmp_path / "harbor" / "bugfix_sample"
    assert (exported / "task.toml").exists()
    assert (exported / "instruction.md").read_text(encoding="utf-8") == "Keep the sample passing.\n"
    assert (exported / "environment" / "Dockerfile").exists()
    assert (exported / "workspace" / "app.py").exists()
    assert (exported / "tests" / "test.sh").stat().st_mode & stat.S_IXUSR
    assert "/logs/verifier/reward.txt" in (exported / "tests" / "test.sh").read_text(encoding="utf-8")
    assert (tmp_path / "harbor" / "dataset.toml").exists()


def test_export_harbor_dataset_refuses_to_overwrite(tmp_path: Path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    output_dir = tmp_path / "harbor"
    output_dir.mkdir()
    (output_dir / "existing.txt").write_text("keep me", encoding="utf-8")

    with pytest.raises(FileExistsError):
        export_harbor_dataset(tasks_dir, output_dir)


def test_harbor_manifest_and_comparison_report(tmp_path: Path):
    report = tmp_path / "latest.json"
    report.write_text(
        json.dumps({"passed": 8, "total": 10, "pass_rate": 0.8, "estimated_cost_usd": 0.0123}),
        encoding="utf-8",
    )

    comparisons = compare_benchmark_reports([report], ["termagent"])
    manifest = tmp_path / "manifest.json"
    markdown = tmp_path / "comparison.md"

    write_harbor_export_manifest([], manifest)
    write_comparison_markdown(comparisons, markdown)

    assert json.loads(manifest.read_text(encoding="utf-8")) == []
    assert "| termagent | 10 | 8 | 80.0% | $0.012300 |" in markdown.read_text(encoding="utf-8")
