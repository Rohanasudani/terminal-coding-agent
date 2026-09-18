# Benchmarking

TermAgent uses three evaluation layers. They answer different questions and should not
be combined into one headline score.

## Runtime Regression Fixtures

`bench/tasks` contains eight small tasks for tool and controller regression. The
`fixture` provider has transparent task-specific patterns, so its `8/8` result checks:

- verifier-first execution
- search and code-map plumbing
- single-file and grouped patch contracts
- write enforcement and final diffs
- Python and JavaScript fixture support
- trace and report generation

It does not measure live-model quality or generalization.

```bash
termagent bench --repo-root .
```

Reports are written to `bench/results/latest.json` and `bench/results/latest.md`.
Per-run traces stay under the ignored trace directory.

## Development Tasks

`bench/evaluation` contains broader public development tasks without corresponding
fixture-provider answers. They are useful for debugging live behavior, but repeated
tuning on them makes them development data rather than held-out evidence.

```bash
termagent bench \
  --tasks-dir bench/evaluation \
  --provider openai \
  --repeats 3 \
  --reasoning-effort high \
  --max-output-tokens 4096 \
  --max-cost-usd 0.05 \
  --max-total-cost-usd 0.45 \
  --report .termagent/evaluation/live.json \
  --markdown-report .termagent/evaluation/live.md
```

Cost ceilings are checked after provider responses and are not prepaid billing limits.
A response can exceed the remaining estimate. Raw outputs may include local paths or
repository content and should be reviewed before publication.

## External Harbor Campaigns

Harbor runs package TermAgent as a custom agent inside the task environment. Campaigns
use public Terminal-Bench tasks resolved from Harbor's registry. Before live calls:

1. Select tasks using public instructions and environment metadata only.
2. Save exact task-tree hashes in a committed manifest.
3. Pin the TermAgent wheel hash, source commit, Harbor version, model, comparator, and
   all controller limits.
4. Run oracle and no-op controls against the same task checksums.
5. Refuse retries and existing job directories unless the protocol says otherwise.
6. Preserve every failed, errored, and unknown-usage result.

The committed manifests are:

- `bench/campaigns/milestone20.json`
- `bench/campaigns/milestone23.json`

The names are historical identifiers. Consolidated outcomes are in
[experiment-log.md](experiment-log.md).

## Campaign Commands

Verify task bytes:

```bash
termagent campaign-verify \
  --manifest bench/campaigns/milestone23.json \
  --dataset-dir .termagent/milestone23-registry/terminal-bench-2
```

Verify oracle/no-op controls:

```bash
termagent campaign-controls \
  --manifest bench/campaigns/milestone23.json \
  --jobs-dir .termagent/harbor-jobs
```

Render a report from completed jobs:

```bash
termagent campaign-report \
  --manifest bench/campaigns/milestone23.json \
  --jobs-dir .termagent/harbor-jobs \
  --report .termagent/milestone23-results.md
```

Run output remains ignored because Harbor trajectories can contain provider responses,
repository content, and local paths.

## Independent Grading

Local tasks declare allowlisted `solution_files`. Grading starts from a pristine copy
of the broken fixture and overlays only those files from the agent workspace. The
original fixture must fail and the reconstructed candidate must pass. Empty test suites
are errors.

Harbor uses each external task's independent verifier. A passing syntax or compile
command selected for agent feedback does not guarantee external reward. This distinction
explains several retained zero-reward trials.

## Metrics

Reports distinguish:

- grader reward
- agent completion state
- exceptions and incomplete usage
- steps and duration
- input and output tokens
- known estimated cost
- planning, discovery, and transition telemetry

Unknown usage is never converted to zero. Model estimates may differ from provider
billing.

## Interpretation Rules

- A fixture-provider pass is runtime evidence only.
- A development-task result is not held-out after it influences implementation.
- One trial per arm supports failure analysis, not a stable effect estimate.
- Different tools or context strategies prevent a claim of perfect agent equivalence,
  even when the underlying model label matches.
- A small Terminal-Bench subset is not a Terminal-Bench leaderboard score.
- Improvements must be tested on a newly frozen set rather than rewriting old results.
