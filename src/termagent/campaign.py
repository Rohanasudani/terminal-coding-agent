"""Integrity checks for frozen external benchmark campaigns."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class VerifiedCampaignTask:
    name: str
    content_sha256: str
    path: Path


def task_tree_sha256(task_dir: Path) -> str:
    """Hash regular task files with their relative paths and sizes."""
    if not task_dir.is_dir():
        raise ValueError(f"task directory does not exist: {task_dir}")

    digest = hashlib.sha256()
    files = sorted(path for path in task_dir.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"task directory contains no files: {task_dir}")

    for path in files:
        if path.is_symlink():
            raise ValueError(f"task directory contains a symbolic link: {path}")
        relative = path.relative_to(task_dir).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def verify_campaign(manifest_path: Path, dataset_dir: Path) -> list[VerifiedCampaignTask]:
    """Verify selected task bytes against a committed campaign manifest."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("unsupported campaign manifest schema")

    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("campaign manifest must contain at least one task")

    verified = []
    seen = set()
    for entry in tasks:
        if not isinstance(entry, dict):
            raise TypeError("campaign task entries must be objects")
        name = entry.get("name")
        expected = entry.get("content_sha256")
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError("campaign task names must be non-empty and unique")
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError(f"{name}: invalid content_sha256")

        task_dir = dataset_dir / name
        actual = task_tree_sha256(task_dir)
        if actual != expected:
            raise ValueError(f"{name}: task content hash mismatch")
        verified.append(VerifiedCampaignTask(name, actual, task_dir.resolve()))
        seen.add(name)
    return verified


def render_campaign_report(manifest_path: Path, jobs_dir: Path) -> str:
    """Validate and summarize one-trial Harbor jobs from a frozen campaign."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_model = manifest["model"]
    expected_arms = {entry["name"] for entry in manifest["arms"]}
    job_prefix = manifest["job_prefix"]
    controls, checksums = _load_controls(jobs_dir / f"{job_prefix}-controls")
    expected_tasks = {entry["name"] for entry in manifest["tasks"]}
    if set(controls) != expected_tasks:
        raise ValueError("control campaign tasks do not match the frozen manifest")
    trials = []

    for task in manifest["tasks"]:
        name = task["name"]
        task_trials = []
        for job_dir in sorted(jobs_dir.glob(f"{job_prefix}-{name}-*")):
            trial = _load_single_trial(job_dir)
            arm = _campaign_arm(trial)
            if arm in {entry["arm"] for entry in task_trials}:
                raise ValueError(f"{name}: duplicate {arm} trial")
            info = trial["agent_info"]
            model = info.get("model_info") or {}
            if model.get("provider") != expected_model["provider"] or model.get("name") != expected_model["name"]:
                raise ValueError(f"{name}: model does not match the frozen campaign")
            _validate_agent_version(info, arm, manifest)
            if trial.get("task_checksum") != checksums.get(name):
                raise ValueError(f"{name}: live and control task checksums differ")
            task_trials.append({"arm": arm, "trial": trial})
        if {entry["arm"] for entry in task_trials} != expected_arms:
            raise ValueError(f"{name}: campaign arms are incomplete")
        trials.extend(task_trials)

    lines = [
        "# Milestone 20: Terminal-Bench 2 Results", "",
        "## Frozen Configuration", "",
        f"- Harbor: `{manifest['harbor']['version']}`",
        f"- Model: `{expected_model['provider']}/{expected_model['name']}`",
        f"- TermAgent wheel: `{manifest['termagent']['wheel_sha256']}`",
        f"- Codex: `{next(arm['version'] for arm in manifest['arms'] if arm['agent'] == 'codex')}`",
        f"- Trials per task and arm: `{manifest['trials_per_task']}`", "",
        "## Control Results", "",
        "| Task | Oracle | No-op | Harbor Task Checksum |",
        "| --- | ---: | ---: | --- |",
    ]
    for task in manifest["tasks"]:
        name = task["name"]
        values = controls[name]
        lines.append(f"| `{name}` | {values['oracle']:.0f} | {values['nop']:.0f} | `{checksums[name]}` |")

    lines.extend([
        "", "All oracle trials passed and all no-op trials failed without exceptions.", "",
        "## Live Results", "",
        "| Task | Arm | Reward | Error | Input Tokens | Output Tokens | Cost | Duration |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for entry in sorted(trials, key=lambda item: (item["trial"]["task_name"], item["arm"])):
        trial = entry["trial"]
        result = trial.get("agent_result") or {}
        reward = ((trial.get("verifier_result") or {}).get("rewards") or {}).get("reward")
        duration = _duration_seconds(trial)
        lines.append(
            f"| `{trial['task_name'].split('/')[-1]}` | `{entry['arm']}` | "
            f"{_number(reward, 0)} | {'yes' if trial.get('exception_info') else 'no'} | "
            f"{_number(result.get('n_input_tokens'), 0)} | {_number(result.get('n_output_tokens'), 0)} | "
            f"{_money(result.get('cost_usd'))} | {_number(duration, 1)}s |"
        )

    lines.extend(["", "## Aggregate", "", "| Arm | Passed | Errors | Known Cost |", "| --- | ---: | ---: | ---: |"])
    for arm in sorted(expected_arms):
        arm_trials = [entry["trial"] for entry in trials if entry["arm"] == arm]
        passed = sum(
            ((trial.get("verifier_result") or {}).get("rewards") or {}).get("reward") == 1.0
            for trial in arm_trials
        )
        errors = sum(trial.get("exception_info") is not None for trial in arm_trials)
        costs = [(trial.get("agent_result") or {}).get("cost_usd") for trial in arm_trials]
        known_cost = sum(cost for cost in costs if cost is not None)
        suffix = " (partial)" if any(cost is None for cost in costs) else ""
        lines.append(f"| `{arm}` | {passed}/{len(arm_trials)} | {errors} | ${known_cost:.6f}{suffix} |")

    lines.extend([
        "", "## Interpretation", "",
        "Structured planning did not improve grader pass rate on this frozen subset. Both",
        "TermAgent arms scored 0/3. Codex scored 2/3. The TermAgent COBOL trials ended",
        "on provider transport failures before Harbor could grade them, so their usage and",
        "cost remain unknown and their outcomes stay in the denominator as errors.", "",
        "This three-task, one-trial campaign is evidence about this subset only. It is not a",
        "Terminal-Bench leaderboard result or a claim that one agent is globally superior.", "",
    ])
    return "\n".join(lines)


def _load_controls(job_dir: Path) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    controls = {}
    checksums = {}
    for path in sorted(job_dir.glob("*/result.json")):
        trial = json.loads(path.read_text(encoding="utf-8"))
        if trial.get("exception_info"):
            raise ValueError("control campaign contains an exception")
        name = trial["task_name"].split("/")[-1]
        agent = trial["agent_info"]["name"]
        reward = trial["verifier_result"]["rewards"]["reward"]
        controls.setdefault(name, {})[agent] = reward
        checksum = trial["task_checksum"]
        if name in checksums and checksums[name] != checksum:
            raise ValueError(f"{name}: control task checksums differ")
        checksums[name] = checksum
    if not controls or any(values != {"oracle": 1.0, "nop": 0.0} for values in controls.values()):
        raise ValueError("oracle/no-op control gate failed")
    return controls, checksums


def _load_single_trial(job_dir: Path) -> dict[str, object]:
    job = json.loads((job_dir / "result.json").read_text(encoding="utf-8"))
    trials = sorted(job_dir.glob("*/result.json"))
    if not job.get("finished_at") or len(trials) != 1 or job.get("stats", {}).get("n_retries", 0):
        raise ValueError(f"{job_dir.name}: expected one finished trial with zero retries")
    return json.loads(trials[0].read_text(encoding="utf-8"))


def _campaign_arm(trial: dict[str, object]) -> str:
    info = trial["agent_info"]
    if info["name"] == "codex":
        return "codex-baseline"
    if info["name"] != "termagent":
        raise ValueError(f"unexpected campaign agent: {info['name']}")
    metadata = trial.get("agent_result", {}).get("metadata") or {}
    planning = metadata.get("task_planning")
    if not isinstance(planning, bool):
        config = trial["config"]["agent"]["kwargs"]
        planning = config.get("task_planning")
    if not isinstance(planning, bool):
        raise TypeError("TermAgent trial does not identify its planning arm")
    return f"termagent-planning-{'on' if planning else 'off'}"


def _validate_agent_version(info: dict[str, object], arm: str, manifest: dict[str, object]) -> None:
    if arm == "codex-baseline":
        expected = next(entry["version"] for entry in manifest["arms"] if entry["agent"] == "codex")
    else:
        expected = f"wheel-sha256:{manifest['termagent']['wheel_sha256']}"
    if info.get("version") != expected:
        raise ValueError(f"{arm}: agent version does not match the frozen campaign")


def _duration_seconds(trial: dict[str, object]) -> float | None:
    started = trial.get("started_at")
    finished = trial.get("finished_at")
    if not isinstance(started, str) or not isinstance(finished, str):
        return None
    return (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()


def _number(value: float | None, precision: int) -> str:
    return "unknown" if value is None else f"{value:.{precision}f}"


def _money(value: float | None) -> str:
    return "unknown" if value is None else f"${value:.6f}"
