from __future__ import annotations

import json
import re
import shutil
import stat
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class HarborExport:
    task: str
    output_dir: str
    verifier: str


@dataclass(frozen=True)
class BenchmarkComparison:
    label: str
    total: int
    passed: int
    pass_rate: float
    estimated_cost_usd: float


def export_harbor_dataset(
    tasks_dir: Path,
    output_dir: Path,
    *,
    limit: int | None = None,
    task_ids: set[str] | None = None,
    overwrite: bool = False,
) -> list[HarborExport]:
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(f"{output_dir} is not empty; pass overwrite=True to replace generated files")

    if output_dir.exists() and overwrite:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    exports: list[HarborExport] = []
    selected = [
        task_dir
        for task_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir())
        if (task_dir / "task.json").exists() and (task_ids is None or task_dir.name in task_ids)
    ]
    if limit is not None:
        selected = selected[: max(0, limit)]

    for task_dir in selected:
        spec = json.loads((task_dir / "task.json").read_text(encoding="utf-8"))
        task_name = safe_task_name(task_dir.name)
        target = output_dir / task_name
        target.mkdir(parents=True, exist_ok=True)

        shutil.copytree(task_dir / "repo", target / "workspace")
        write_text(target / "task.toml", harbor_task_toml(task_name, spec))
        write_text(target / "instruction.md", str(spec["instruction"]).strip() + "\n")
        write_text(target / "environment" / "Dockerfile", dockerfile_for_task(spec))
        write_executable(target / "tests" / "test.sh", verifier_script(str(spec.get("verify", "python -m pytest -q"))))
        write_executable(target / "solution" / "solve.sh", oracle_placeholder(task_name))
        exports.append(HarborExport(task_name, str(target), str(spec.get("verify", "python -m pytest -q"))))

    write_text(output_dir / "dataset.toml", dataset_toml())
    write_text(output_dir / "README.md", harbor_dataset_readme(exports))
    return exports


def write_harbor_export_manifest(exports: list[HarborExport], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(export) for export in exports], indent=2), encoding="utf-8")


def compare_benchmark_reports(report_paths: list[Path], labels: list[str] | None = None) -> list[BenchmarkComparison]:
    comparisons: list[BenchmarkComparison] = []
    for index, path in enumerate(report_paths):
        payload = json.loads(path.read_text(encoding="utf-8"))
        label = labels[index] if labels and index < len(labels) else path.stem
        total = int(payload.get("total", 0))
        passed = int(payload.get("passed", 0))
        pass_rate = float(payload.get("pass_rate", passed / total if total else 0.0))
        estimated_cost_usd = float(payload.get("estimated_cost_usd", 0.0))
        comparisons.append(BenchmarkComparison(label, total, passed, pass_rate, estimated_cost_usd))
    return comparisons


def write_comparison_markdown(comparisons: list[BenchmarkComparison], path: Path) -> None:
    lines = [
        "# Benchmark Comparison",
        "",
        "| Run | Tasks | Passed | Pass Rate | Estimated Cost |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for comparison in comparisons:
        lines.append(
            f"| {comparison.label} | {comparison.total} | {comparison.passed} | "
            f"{comparison.pass_rate:.1%} | ${comparison.estimated_cost_usd:.6f} |"
        )
    lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def safe_task_name(raw: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw.strip()).strip("-").lower()
    return sanitized or "task"


def harbor_task_toml(task_name: str, spec: dict[str, object]) -> str:
    category = toml_string(str(spec.get("category", "programming")))
    language = toml_string(str(spec.get("language", "unknown")))
    return "\n".join(
        [
            'version = "1.0"',
            "",
            "[task]",
            f'name = "termagent/{task_name}"',
            "",
            "[metadata]",
            'author_name = "Rohan Asudani"',
            'difficulty = "small"',
            f"category = {category}",
            f"tags = [{language}, \"terminal-agent\", \"local-benchmark\"]",
            "",
            "[agent]",
            "timeout_sec = 1800.0",
            "",
            "[verifier]",
            "timeout_sec = 120.0",
            "",
            "[environment]",
            "build_timeout_sec = 600.0",
            "cpus = 1",
            "memory_mb = 2048",
            "storage_mb = 10240",
            "",
        ]
    )


def dockerfile_for_task(spec: dict[str, object]) -> str:
    language = str(spec.get("language", "")).lower()
    install_node = "javascript" in language or "typescript" in language
    packages = "git nodejs npm" if install_node else "git"
    return "\n".join(
        [
            "FROM python:3.13-slim",
            "WORKDIR /workspace",
            "RUN apt-get update && apt-get install -y --no-install-recommends \\",
            f"    {packages} \\",
            "    && rm -rf /var/lib/apt/lists/*",
            "COPY workspace/ /workspace/",
            "COPY tests/test.sh /tests/test.sh",
            "RUN chmod +x /tests/test.sh",
            "",
        ]
    )


def verifier_script(command: str) -> str:
    normalized = command.replace("{python}", "python")
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -u",
            "mkdir -p /logs/verifier",
            "cd /workspace",
            f"if {normalized}; then",
            "  echo 1 > /logs/verifier/reward.txt",
            "else",
            "  echo 0 > /logs/verifier/reward.txt",
            "  exit 1",
            "fi",
            "",
        ]
    )


def oracle_placeholder(task_name: str) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f'echo "No embedded oracle for {task_name}; run TermAgent or add task-specific solution steps."',
            "",
        ]
    )


def dataset_toml() -> str:
    return (
        'name = "termagent-local"\n'
        'version = "0.1.0"\n'
        'description = "Harbor-shaped export of the TermAgent local benchmark suite."\n'
    )


def harbor_dataset_readme(exports: list[HarborExport]) -> str:
    lines = [
        "# TermAgent Local Harbor Export",
        "",
        "This directory is generated from `bench/tasks` for Harbor-style local evaluation work.",
        "It is not a Terminal-Bench leaderboard submission and does not claim parity with Terminal-Bench.",
        "",
        "Each task includes `task.toml`, `instruction.md`, `environment/Dockerfile`, `tests/test.sh`, and `solution/solve.sh`.",
        "",
        "| Task | Verifier |",
        "| --- | --- |",
    ]
    for export in exports:
        lines.append(f"| `{export.task}` | `{export.verifier}` |")
    lines.append("")
    return "\n".join(lines)


def toml_string(value: str) -> str:
    return json.dumps(value)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_executable(path: Path, content: str) -> None:
    write_text(path, content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
