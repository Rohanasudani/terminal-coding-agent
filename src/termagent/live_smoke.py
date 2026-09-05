from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .agent import TerminalAgent
from .models import AgentConfig


@dataclass(frozen=True)
class LiveSmokeResult:
    status: str
    model: str
    completed: bool
    tests_passed: bool
    steps: int
    changed_files: list[str]
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    report_path: str
    note: str


def run_live_smoke(
    repo_root: Path,
    *,
    model: str = "gpt-5.6-luna",
    max_cost_usd: float = 0.05,
    report_path: Path | None = None,
) -> LiveSmokeResult:
    repo_root = repo_root.resolve()
    report_path = report_path or repo_root / "docs" / "live-provider-demo.md"

    if not os.environ.get("OPENAI_API_KEY"):
        result = LiveSmokeResult(
            status="skipped",
            model=model,
            completed=False,
            tests_passed=False,
            steps=0,
            changed_files=[],
            input_tokens=0,
            output_tokens=0,
            estimated_cost_usd=0.0,
            report_path=str(report_path),
            note="OPENAI_API_KEY is not set; no live API call was made.",
        )
        write_live_smoke_report(result, report_path)
        return result

    source = repo_root / "tests" / "fixtures" / "sample_repo"
    with tempfile.TemporaryDirectory(prefix="termagent-live-smoke-") as temp:
        workspace = Path(temp) / "repo"
        shutil.copytree(source, workspace)
        state = TerminalAgent(
            AgentConfig(
                repo=workspace,
                task="Fix the calculator add bug and run tests",
                approval_mode="auto",
                max_steps=8,
                log_dir=repo_root / ".termagent" / "live-smoke",
                provider="openai",
                model=model,
                test_command="{python} -m pytest -q",
                prompt_profile="benchmark",
                max_cost_usd=max_cost_usd,
                observation_limit=4,
                max_observation_chars=4000,
            )
        ).run()

    status = "passed" if state.completed and state.tests_passed else "failed"
    result = LiveSmokeResult(
        status=status,
        model=model,
        completed=state.completed,
        tests_passed=state.tests_passed,
        steps=state.steps,
        changed_files=state.changed_files,
        input_tokens=state.input_tokens,
        output_tokens=state.output_tokens,
        estimated_cost_usd=round(state.estimated_cost_usd, 6),
        report_path=str(report_path),
        note="Raw trace is intentionally kept under ignored .termagent/live-smoke and is not committed.",
    )
    write_live_smoke_report(result, report_path)
    return result


def write_live_smoke_report(result: LiveSmokeResult, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    files = ", ".join(result.changed_files) if result.changed_files else "none"
    lines = [
        "# Live Provider Demo",
        "",
        "This is a sanitized smoke-test summary for TermAgent's OpenAI-compatible provider.",
        "It does not include raw prompts, raw model output, API keys, or private trace payloads.",
        "",
        f"- Checked at: {checked_at}",
        f"- Status: {result.status}",
        f"- Model: `{result.model}`",
        f"- Completed: `{result.completed}`",
        f"- Tests passed: `{result.tests_passed}`",
        f"- Steps: `{result.steps}`",
        f"- Changed files: `{files}`",
        f"- Tokens: `{result.input_tokens}` input, `{result.output_tokens}` output",
        f"- Estimated model cost: `${result.estimated_cost_usd:.6f}`",
        f"- Note: {result.note}",
        "",
        "Run it locally:",
        "",
        "```bash",
        "export OPENAI_API_KEY=\"your-api-key\"",
        "termagent live-smoke --repo-root . --max-cost-usd 0.05",
        "```",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def live_smoke_result_as_dict(result: LiveSmokeResult) -> dict[str, object]:
    return asdict(result)
