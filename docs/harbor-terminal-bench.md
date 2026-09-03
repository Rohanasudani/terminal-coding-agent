# Harbor And Terminal-Bench Integration

Milestone 10 adds a local bridge toward Harbor and Terminal-Bench-style evaluation.

Terminal-Bench is now run through Harbor, and current Harbor tasks use a task directory with `task.toml`, `instruction.md`, `environment/Dockerfile`, `solution/solve.sh`, and `tests/test.sh`. Harbor verifiers write a numeric reward to `/logs/verifier/reward.txt`.

TermAgent does not claim a public Terminal-Bench leaderboard score yet. This integration prepares the local benchmark suite for Harbor-shaped parity work and lets you compare benchmark reports from different agents or runs.

## Export Local Tasks

```bash
termagent harbor-export --overwrite
```

This writes:

- `bench/harbor-export/dataset.toml`
- `bench/harbor-export/manifest.json`
- one task directory per local benchmark task
- `tests/test.sh` files that map verifier success to Harbor reward files

You can export a subset:

```bash
termagent harbor-export \
  --task-id bugfix_javascript_total \
  --output-dir bench/harbor-export-js \
  --manifest bench/harbor-export-js/manifest.json \
  --overwrite
```

## Compare Runs

```bash
termagent compare-bench bench/results/latest.json --label repair
```

This writes `bench/results/comparison.md` with pass rate, task count, and estimated model cost for each report.

Compare multiple reports:

```bash
termagent compare-bench \
  bench/results/latest.json \
  bench/results/openai-smoke.json \
  --label repair \
  --label openai-smoke
```

## What This Proves

- The local benchmark suite has the same core pieces as external agent benchmarks: task fixtures, instructions, verifier commands, traces, and machine-readable reports.
- TermAgent can emit Harbor-shaped task folders for local adapter development.
- Reports can be compared without hand-editing spreadsheets.

## What Is Still Future Work

- Install Harbor and run a real local Harbor trial.
- Package TermAgent as a Harbor-compatible custom agent.
- Run a small Terminal-Bench subset with pinned model, pinned agent version, and documented cost.
- Add a true oracle solution for every exported local task before treating the export as a publishable Harbor dataset.
