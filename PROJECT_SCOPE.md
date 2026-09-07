# Project Scope

## Objective

Build a useful terminal coding agent and demonstrate, through controlled experiments,
how its agent loop affects coding performance relative to an existing agent using
the same underlying model. The intended outcome is a defensible flagship engineering
project with reproducible results and practical use on trusted repositories.

## Required Outcomes

1. A working agent that inspects repositories, proposes and applies changes, runs
   verification, respects execution controls, and records its actions and usage.
2. A real Harbor integration and a pinned external benchmark subset. Exporting task
   folders alone does not satisfy this requirement.
3. A comparison against at least one established agent, such as Codex or Pi, using
   the same model where supported. Record differences in reasoning settings, context,
   tools, time limits, and token budgets rather than implying perfect equivalence.
4. Failure analysis followed by general improvements. Evaluate each technique with
   it enabled and disabled, then test on tasks not used to design that improvement.
5. A report containing every trial, successes and failures, latency, available token
   and cost measurements, exact versions, limitations, and reproduction commands.
6. A usable packaged CLI and an honest live demonstration on a nontrivial task.

## Experiment Rules

- Freeze the task revision and agent build before comparing runs.
- Separate public development fixtures from the external evaluation set.
- Keep task-specific fixes only in labeled deterministic baselines and test oracles.
  Never report those as live-model performance or tune directly to hidden answers.
- Change one technique at a time: controller recovery, context selection, prompt
  strategy, verification, or orchestration. Subagents are an experiment, not a requirement.
- Keep failed runs and timeouts in the report. Missing cost data is unknown, not zero.
- A small subset supports a claim about that subset, not the full leaderboard.

## Completion Standard

The project is not complete until the comparison and improvement cycle above has
actually been run and documented. Matching or beating an established agent globally
is not required; identifying a measured strength, a reproducible improvement, and
the remaining weaknesses is a valid result. Commit count and feature count are not
completion criteria.

See [the release checklist](docs/release-readiness.md) for implementation and evidence status.
