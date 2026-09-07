"""Compare completed Harbor jobs without dropping failed trials."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean


def compare_harbor_jobs(job_dirs: list[Path], *, allow_model_difference: bool = False) -> str:
    if len(job_dirs) < 2:
        raise ValueError("provide at least two completed Harbor jobs")
    matched_tasks = None
    matched_model = None
    rows = []
    provenance = []
    for directory in job_dirs:
        job = json.loads((directory / "result.json").read_text())
        trials = [json.loads(path.read_text()) for path in sorted(directory.glob("*/result.json"))]
        if not job.get("finished_at") or not trials or len(trials) != job.get("n_total_trials"):
            raise ValueError(f"{directory.name}: job is incomplete or has missing trial results")
        if job.get("stats", {}).get("n_retries", 0):
            raise ValueError(f"{directory.name}: retry accounting needs review; compare runs with retries disabled")
        if any(not trial.get("task_checksum") for trial in trials):
            raise ValueError("every trial must include a task checksum")
        tasks = Counter((trial["task_name"], trial["task_checksum"]) for trial in trials)
        if matched_tasks is not None and tasks != matched_tasks:
            raise ValueError("jobs must use identical task checksums and trial counts")
        matched_tasks = tasks
        models = set()
        agents = set()
        versions = set()
        durations = []
        passed = errors = 0
        costs = []
        for trial in trials:
            info = trial.get("agent_info") or {}
            model = info.get("model_info") or {}
            models.add((model.get("provider"), model.get("name")))
            agents.add(info.get("name", "unknown"))
            versions.add(info.get("version", "unknown"))
            exception = trial.get("exception_info")
            rewards = (trial.get("verifier_result") or {}).get("rewards") or {}
            passed += int(not exception and rewards.get("reward") == 1.0)
            errors += int(exception is not None)
            costs.append((trial.get("agent_result") or {}).get("cost_usd"))
            execution = trial.get("agent_execution") or {}
            if execution.get("started_at") and execution.get("finished_at"):
                durations.append((
                    datetime.fromisoformat(execution["finished_at"])
                    - datetime.fromisoformat(execution["started_at"])
                ).total_seconds())
        if not allow_model_difference:
            if len(models) != 1 or any(not provider or not name for provider, name in models):
                raise ValueError("same-model comparisons require one identified provider/model per job")
            if matched_model is not None and models != matched_model:
                raise ValueError("jobs used different models; this is not a same-model comparison")
            matched_model = models
        cost = f"${sum(costs):.6f}" if all(value is not None for value in costs) else "unknown"
        duration = f"{mean(durations):.3f}s" if len(durations) == len(trials) else "unknown"
        model_label = ", ".join(f"{provider or 'unknown'}/{name or 'none'}" for provider, name in sorted(models, key=str))
        rows.append(
            f"| {markdown_cell(directory.name)} | {markdown_cell(', '.join(sorted(agents)))} | "
            f"{markdown_cell(model_label)} | {passed}/{len(trials)} | {errors} | {duration} | {cost} |"
        )
        provenance.append(f"- {markdown_cell(directory.name)}: {markdown_cell(', '.join(sorted(versions)))}")
    mode = "Descriptive comparison; model matching was explicitly disabled." if allow_model_difference else (
        "Task checksums, trial counts, and provider/model IDs match. Reasoning, context, "
        "tool access, and budget differences still require review before attributing causality."
    )
    return "\n".join([
        "# Harbor Comparison", "", mode, "",
        "Every recorded trial, including errors, contributes to the denominator.",
        "Costs are adapter-reported and may be estimates. Missing costs remain unknown.", "",
        "| Job | Agent | Model | Passed | Errors | Mean Agent Time | Reported Cost |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |", *rows, "",
        "## Agent Versions", "", *provenance, "",
        "## Task Checksums", "",
        *[f"- {markdown_cell(name)}: `{checksum}` ({count} trial(s) per job)"
          for (name, checksum), count in sorted(matched_tasks.items())], "",
    ])


def markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").replace("\r", " ")
