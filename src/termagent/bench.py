from __future__ import annotations

import json
import math
import shutil
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from shlex import quote
from uuid import uuid4

from .agent import TerminalAgent
from .grading import grade_workspace
from .models import AgentConfig, ReasoningEffort


@dataclass(frozen=True)
class BenchResult:
    task: str
    category: str
    language: str
    passed: bool
    duration_seconds: float
    steps: int
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    verifier_output: str
    trace_dir: str
    trial: int = 1
    agent_completed: bool = False
    baseline_passed: bool = False
    task_planning: bool = False


def run_benchmark(
    repo_root: Path,
    tasks_dir: Path | None = None,
    artifacts_dir: Path | None = None,
    *,
    provider: str | None = None,
    model: str | None = None,
    repeats: int = 1,
    max_cost_usd: float = 0.05,
    max_total_cost_usd: float = 0.25,
    max_output_tokens: int = 4_096,
    reasoning_effort: ReasoningEffort | None = None,
    task_planning: bool = False,
) -> list[BenchResult]:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    if any(not math.isfinite(cost) or cost <= 0 for cost in (max_cost_usd, max_total_cost_usd)):
        raise ValueError("cost limits must be finite positive numbers")
    tasks_dir = tasks_dir or repo_root / "bench" / "tasks"
    artifacts_dir = artifacts_dir or repo_root / "bench" / "results"
    traces_root = artifacts_dir / "traces" / uuid4().hex
    results: list[BenchResult] = []
    spent = 0.0

    task_dirs = sorted(path for path in tasks_dir.iterdir() if path.is_dir() and (path / "task.json").exists())
    if not task_dirs:
        raise ValueError("no benchmark tasks found")
    for task_dir, trial in ((path, trial) for path in task_dirs for trial in range(1, repeats + 1)):
        spec_path = task_dir / "task.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        solution_files = spec.get("solution_files")
        if not isinstance(solution_files, list) or not solution_files or not all(
            isinstance(name, str) and name for name in solution_files
        ):
            raise ValueError(f"{task_dir.name}: solution_files must list the editable source files")
        if spent >= max_total_cost_usd:
            raise RuntimeError(f"benchmark total cost limit reached; partial report: {traces_root / 'partial.json'}")
        with tempfile.TemporaryDirectory(prefix=f"termagent-{task_dir.name}-") as temp:
            workspace = Path(temp) / "repo"
            shutil.copytree(task_dir / "repo", workspace)
            trace_dir = Path(temp) / "traces"
            started = time.perf_counter()

            verify_command = str(spec.get("verify", "{python} -m pytest -q")).format(python=quote(sys.executable))
            baseline = grade_workspace(task_dir / "repo", workspace, solution_files, verify_command)
            config = AgentConfig(
                repo=workspace,
                task=str(spec["instruction"]),
                approval_mode="auto",
                max_steps=int(spec.get("max_steps", 8)),
                log_dir=trace_dir,
                provider=provider or str(spec.get("provider", "repair")),
                model=model or str(spec.get("model", "gpt-5.6-luna")),
                test_command=verify_command,
                provider_retries=int(spec.get("provider_retries", 2)),
                max_cost_usd=min(max_cost_usd, max_total_cost_usd - spent),
                max_output_tokens=max_output_tokens,
                reasoning_effort=reasoning_effort,
                task_planning=task_planning,
            )
            state = TerminalAgent(config).run()
            spent += state.estimated_cost_usd
            verifier = grade_workspace(task_dir / "repo", workspace, solution_files, verify_command)
            duration = time.perf_counter() - started
            persisted_trace_dir = traces_root / task_dir.name / str(trial)
            shutil.copytree(trace_dir, persisted_trace_dir)
            results.append(
                BenchResult(
                    task=task_dir.name,
                    category=str(spec.get("category", "bugfix")),
                    language=str(spec.get("language", "python")),
                    passed=verifier.passed and not baseline.passed,
                    duration_seconds=round(duration, 3),
                    steps=state.steps,
                    provider=config.provider,
                    model=config.model,
                    input_tokens=state.input_tokens,
                    output_tokens=state.output_tokens,
                    estimated_cost_usd=state.estimated_cost_usd,
                    verifier_output=verifier.output,
                    trace_dir=str(persisted_trace_dir),
                    trial=trial,
                    agent_completed=state.completed,
                    baseline_passed=baseline.passed,
                    task_planning=task_planning,
                )
            )
            write_report(results, traces_root / "partial.json")

    return results


def write_report(results: list[BenchResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for result in results if result.passed)
    payload = {
        "passed": passed,
        "total": len(results),
        "pass_rate": round(passed / len(results), 4) if results else 0.0,
        "estimated_cost_usd": round(sum(result.estimated_cost_usd for result in results), 6),
        "results": [asdict(result) for result in results],
        "grading": "pristine fixture with allowlisted solution files; baseline must fail",
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_markdown_report(results: list[BenchResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for result in results if result.passed)
    pass_rate = passed / len(results) if results else 0.0
    total_cost = sum(result.estimated_cost_usd for result in results)
    lines = [
        "# TermAgent Benchmark Report",
        "",
        f"- Tasks: {len(results)}",
        f"- Passed: {passed}",
        f"- Pass rate: {pass_rate:.1%}",
        f"- Estimated model cost: ${total_cost:.6f}",
        "",
        "| Task | Trial | Category | Language | Result | Steps | Planning | Duration | Provider | Cost |",
        "| --- | ---: | --- | --- | --- | ---: | --- | ---: | --- | ---: |",
    ]
    for result in results:
        status = "pass" if result.passed else "fail"
        lines.append(
            f"| {result.task} | {result.trial} | {result.category} | {result.language} | {status} | "
            f"{result.steps} | {'on' if result.task_planning else 'off'} | "
            f"{result.duration_seconds:.3f}s | {result.provider} | "
            f"${result.estimated_cost_usd:.6f} |"
        )

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
