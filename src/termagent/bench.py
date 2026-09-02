from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .agent import TerminalAgent
from .models import AgentConfig


@dataclass(frozen=True)
class BenchResult:
    task: str
    passed: bool
    duration_seconds: float
    steps: int
    verifier_output: str
    trace_dir: str


def run_benchmark(repo_root: Path, tasks_dir: Path | None = None) -> list[BenchResult]:
    tasks_dir = tasks_dir or repo_root / "bench" / "tasks"
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

            config = AgentConfig(
                repo=workspace,
                task=str(spec["instruction"]),
                approval_mode="auto",
                max_steps=int(spec.get("max_steps", 8)),
                log_dir=trace_dir,
                provider="mock",
            )
            state = TerminalAgent(config).run()
            verify_command = str(spec.get("verify", "{python} -m pytest -q")).format(python=sys.executable)
            verifier = subprocess.run(
                verify_command,
                cwd=workspace,
                shell=True,
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
            duration = time.perf_counter() - started
            output = "\n".join(part for part in [verifier.stdout.strip(), verifier.stderr.strip()] if part)
            results.append(
                BenchResult(
                    task=task_dir.name,
                    passed=verifier.returncode == 0,
                    duration_seconds=round(duration, 3),
                    steps=state.steps,
                    verifier_output=output,
                    trace_dir=str(trace_dir),
                )
            )

    return results


def write_report(results: list[BenchResult], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "passed": sum(1 for result in results if result.passed),
        "total": len(results),
        "results": [asdict(result) for result in results],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
