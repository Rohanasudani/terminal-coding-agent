# Milestone 23: Frozen Post-Recovery Evaluation Protocol

## Objective

Evaluate whether Milestone 22's bounded inspection-to-edit transition improves
TermAgent behavior on a new Terminal-Bench 2 subset. The campaign compares planning
enabled, planning disabled, and a pinned Codex baseline. It is a small diagnostic
campaign, not a leaderboard score.

## Freeze Boundary

The subset was frozen on 2026-09-16 before controls or model trials. Selection used
only public task instructions, task metadata, and environment definitions. Oracle
solutions and test files were not inspected. Candidates whose public README disclosed
solution or verifier details were excluded before the freeze.

The selected tasks were not used in Milestones 18 or 20:

| Task | Category | Purpose |
| --- | --- | --- |
| `polyglot-c-py` | Cross-language implementation | One deliverable must execute as Python and compile as C |
| `kv-store-grpc` | Multi-file service | Protocol definition, generated interfaces, server implementation, and process behavior |
| `multi-source-data-merger` | Data pipeline | Multi-format schema normalization, conflict handling, and output artifacts |

Exact task hashes and controls are committed in
[`bench/campaigns/milestone23.json`](../bench/campaigns/milestone23.json). Raw tasks,
tests, oracle solutions, credentials, and trajectories remain ignored under
`.termagent/`.

## Preflight Gates

Before model calls:

1. Every task tree must match its committed SHA-256 hash.
2. The TermAgent wheel must match its committed SHA-256 hash.
3. Harbor must report version `0.22.0`.
4. Oracle must earn reward `1` and no-op reward `0` on every task.

Any failed gate blocks live runs. The task set and agent implementation are immutable
after the first control or live result is observed.

## Live Arms

Each task receives one trial in each arm:

- TermAgent with task planning and Milestone 22 transition recovery enabled.
- TermAgent with task planning disabled.
- Codex `0.153.4` as a descriptive established-agent baseline.

All arms use `openai/gpt-5.6-luna`, one concurrent trial, and zero Harbor retries.
TermAgent uses high reasoning, a 4,096-token response limit, 32 steps, a six-action
discovery budget, two allowed transition deferrals, and a `$0.05` estimated cost
ceiling per trial. Codex does not expose identical controller and budget controls, so
the comparison is descriptive rather than a controlled causal estimate.

## Reporting Rules

- Preserve every failure, timeout, exception, and zero reward.
- Treat unavailable usage and cost as unknown, never zero.
- Report task hashes, wheel hash, versions, tokens, cost, duration, discovery actions,
  transition deferrals, and available failure details.
- Do not inspect hidden tests or oracle solutions to tune the agent.
- Do not modify agent behavior after observing campaign outcomes.
- Do not rerun failed trials unless the committed protocol itself is invalidated and a
  new campaign revision is created.
- Make no general performance or leaderboard claim from three one-trial tasks.

## Reproduction

```bash
.termagent/harbor-venv/bin/harbor dataset download \
  terminal-bench/terminal-bench-2 \
  --output-dir .termagent/milestone23-registry --export --overwrite

termagent campaign-verify \
  --manifest bench/campaigns/milestone23.json \
  --dataset-dir .termagent/milestone23-registry/terminal-bench-2

shasum -a 256 \
  .termagent/milestone23-wheel/terminal_coding_agent-0.1.0-py3-none-any.whl
```

The exact Harbor control and live commands are recorded in
[milestone23-runbook.md](milestone23-runbook.md).
