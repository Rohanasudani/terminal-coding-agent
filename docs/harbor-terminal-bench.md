# Harbor And Terminal-Bench Integration

Milestone 16 adds a tested custom agent adapter for Harbor 0.22.0. See
[controlled-experiments.md](controlled-experiments.md) for installation, real
container checks, same-model comparison templates, and ablations.

Harbor tasks use `task.toml`, `instruction.md`, `environment/Dockerfile`, and
`tests/test.sh`. An oracle solution is optional and is not included in our export.
Harbor verifiers write a numeric reward to `/logs/verifier/reward.txt`.

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

Workspace files are copied inside `environment/`, Harbor's Docker build context.
Authoritative tests are uploaded by Harbor at verification time and grade a fresh
directory containing only allowlisted source changes. Export refuses to overwrite
unmarked directories or overlap source tasks. Choose a new directory for older exports.

You can export a subset:

```bash
termagent harbor-export \
  --task-id bugfix_javascript_total \
  --output-dir bench/harbor-export-js \
  --manifest bench/harbor-export-js/manifest.json \
  --overwrite
```

## Compare Runs

The legacy `compare-bench` command below only summarizes local reports. For
controlled Harbor comparisons use `termagent compare-harbor`; it checks task hashes,
trial counts, identified model IDs, and missing trials before producing a report.

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
- TermAgent's custom adapter was run inside Docker using Harbor 0.22.0. The deterministic calculator repair earned reward 1; the no-op control earned reward 0. See [the integration report](harbor-integration-result.md).
- Reports can be compared without hand-editing spreadsheets.

## What Is Still Future Work

- Run a small Terminal-Bench subset with pinned model, pinned agent version, and documented cost.
- Compare at least one existing agent on the same model and tasks, then measure a general improvement with an ablation.
- Add a true oracle solution for every exported local task before treating the export as a publishable Harbor dataset.
