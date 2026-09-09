# Milestone 20: Frozen Terminal-Bench 2 Protocol

## Objective

Measure whether Milestone 19 structured planning changes TermAgent's grader pass
rate on an unseen coding-focused Terminal-Bench 2 subset. The campaign also makes
a descriptive comparison with an established agent. It does not claim a score for
the full benchmark.

## Frozen Subset

The subset was selected on 2026-09-09 from the 89 tasks returned by
`terminal-bench/terminal-bench-2@latest`. Selection used public instructions and
environment metadata. Previous evaluation tasks and workloads outside a trusted
repository coding agent's scope were excluded.

| Task | Category | Purpose |
| --- | --- | --- |
| `cancel-async-tasks` | Python concurrency | New-file implementation and cancellation semantics |
| `fix-code-vulnerability` | Security repair | Existing-repository analysis and regression safety |
| `cobol-modernization` | Legacy modernization | Cross-language comprehension and exact file behavior |

The task hashes and fixed controls are in
[`bench/campaigns/milestone20.json`](../bench/campaigns/milestone20.json). Task
archives, oracle solutions, verifier files, credentials, and raw trajectories are
not committed.

## Preflight Gates

Before model calls, the task bytes and wheel hash must match the manifest. Harbor
`0.22.0` must give reward `1` to oracle and reward `0` to no-op on every task.
A failed control blocks live runs and requires a new manifest revision.

## Live Arms

Each task receives one trial in each arm:

- TermAgent with structured planning enabled.
- TermAgent with structured planning disabled.
- Codex `0.153.4` as the established-agent baseline.

All arms use `openai/gpt-5.6-luna`, one concurrent trial, and zero Harbor retries.
TermAgent fixes high reasoning, a 4,096-token response ceiling, 32 steps, controller
recovery, two allowed stagnation events, and a `$0.05` estimated per-trial ceiling.
Codex does not expose identical controls through this pinned Harbor adapter, so its
results are descriptive rather than a perfectly controlled causal comparison.

## Reporting Rules

- Preserve every failure, timeout, exception, and zero reward.
- Treat unavailable usage or cost as unknown, never zero.
- Report checksums, versions, elapsed time, tokens, and available cost data.
- Do not inspect oracle solutions or hidden verifier files to tune the agent.
- Do not modify agent behavior after looking at campaign outcomes.
- Equal reward with more steps is not a planning improvement.
- Make no leaderboard claim from three tasks and one trial.

## Reproduction

```bash
harbor dataset download terminal-bench/terminal-bench-2 \
  --output-dir .termagent/milestone20-registry --export --overwrite

termagent campaign-verify \
  --manifest bench/campaigns/milestone20.json \
  --dataset-dir .termagent/milestone20-registry/terminal-bench-2
```

Raw job configurations and outputs remain ignored under `.termagent/`. The final
sanitized report contains reproduction commands for every completed arm.

Sources: [Harbor Terminal-Bench tutorial](https://www.harborframework.com/docs/tutorials/running-terminal-bench),
[Harbor eval documentation](https://www.harborframework.com/docs/run-jobs/run-evals).
