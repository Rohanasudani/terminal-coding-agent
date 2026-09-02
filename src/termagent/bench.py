from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from shlex import split

from .agent import TerminalAgent
from .models import AgentConfig


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


def run_benchmark(
    repo_root: Path,
    tasks_dir: Path | None = None,
    artifacts_dir: Path | None = None,
) -> list[BenchResult]:
    tasks_dir = tasks_dir or repo_root / "bench" / "tasks"
    artifacts_dir = artifacts_dir or repo_root / "bench" / "results"
    traces_root = artifacts_dir / "traces"
    results: list[BenchResult] = []

    for task_dir in sorted(path for path in tasks_dir.iterdir() if path.is_dir()):
        spec_path = task_dir / "task.json"
        if not spec_path.exists():
            continue

        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix=f"termagent-{task_dir.name}-") as temp:
            workspace = Path(temp) / "repo"
            shutil.copytree(task_dir / "repo", workspace)
            trace_dir = Path(temp) / "traces"
            started = time.perf_counter()

            verify_command = str(spec.get("verify", "{python} -m pytest -q")).format(python=sys.executable)
            config = AgentConfig(
                repo=workspace,
                task=str(spec["instruction"]),
                approval_mode="auto",
                max_steps=int(spec.get("max_steps", 8)),
                log_dir=trace_dir,
                provider=str(spec.get("provider", "repair")),
                model=str(spec.get("model", "gpt-5.6-luna")),
                test_command=verify_command,
                provider_retries=int(spec.get("provider_retries", 2)),
            )
            state = TerminalAgent(config).run()
            verifier = subprocess.run(
                split(verify_command),
                cwd=workspace,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
            duration = time.perf_counter() - started
            output = "\n".join(part for part in [verifier.stdout.strip(), verifier.stderr.strip()] if part)
            persisted_trace_dir = traces_root / task_dir.name
            if persisted_trace_dir.exists():
                shutil.rmtree(persisted_trace_dir)
            shutil.copytree(trace_dir, persisted_trace_dir)
            results.append(
                BenchResult(
                    task=task_dir.name,
                    category=str(spec.get("category", "bugfix")),
                    language=str(spec.get("language", "python")),
                    passed=verifier.returncode == 0,
                    duration_seconds=round(duration, 3),
                    steps=state.steps,
                    provider=config.provider,
                    model=config.model,
                    input_tokens=state.input_tokens,
                    output_tokens=state.output_tokens,
                    estimated_cost_usd=state.estimated_cost_usd,
                    verifier_output=output,
                    trace_dir=str(persisted_trace_dir),
                )
            )

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
        "| Task | Category | Language | Result | Steps | Duration | Provider | Cost |",
        "| --- | --- | --- | --- | ---: | ---: | --- | ---: |",
    ]
    for result in results:
        status = "pass" if result.passed else "fail"
        lines.append(
            f"| {result.task} | {result.category} | {result.language} | {status} | "
            f"{result.steps} | {result.duration_seconds:.3f}s | {result.provider} | "
            f"${result.estimated_cost_usd:.6f} |"
        )

    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
