# Benchmarking Plan

The project is benchmark-first. The local harness is small today, but it is shaped to grow toward Terminal-Bench-style evaluation.

## Local Benchmarks

Run:

```bash
termagent bench --repo-root .
```

The harness writes:

- `bench/results/latest.json`: machine-readable pass/fail, runtime, verifier output, usage, and trace metadata
- `bench/results/latest.md`: GitHub-readable summary table
- `bench/results/traces/<task>`: persisted JSONL traces for each benchmark task

Each task can define its own verifier command. The default command uses the current Python executable:

```bash
{python} -m pytest -q
```

That placeholder makes benchmarks more portable across virtual environments and CI.

Reports also include provider, model, token usage, and estimated model cost. Deterministic local providers report zero model tokens; live provider runs include usage returned by the model API.

## Current Suite

| Task | Bug Shape |
| --- | --- |
| `bugfix_calculator` | arithmetic operator repair |
| `bugfix_clamp_score` | bounds checking |
| `bugfix_divide` | arithmetic operator repair |
| `bugfix_email_normalization` | string normalization |
| `bugfix_slugify` | whitespace and separator normalization |
| `bugfix_word_count` | character count vs. token count |

Current deterministic baseline: `6/6` tasks pass with the `repair` provider.

## Why Start Local

Local tasks are cheap, deterministic, and fast. They help catch regressions in:

- tool execution
- path sandboxing
- write behavior
- shell safety policy
- agent loop completion
- trace logging
- test-first repair behavior
- report generation
- trace persistence

## Terminal-Bench Direction

Terminal-Bench evaluates AI agents in real terminal environments with end-to-end tasks. Its current Harbor-based workflow runs agents against published datasets and measures resolution rates, cost, tokens, and runtime.

This project should eventually provide an adapter that lets Harbor invoke `termagent` as an agent backend. The local benchmark harness is the stepping stone: it already models isolated tasks, verifier commands, and machine-readable reports.

## Anti-Cheating Rule

Do not hardcode benchmark answers as the final strategy. The deterministic `repair` provider uses small, transparent heuristics as a local baseline. Real improvement should come from better planning, repository intelligence, live-provider behavior, and broader benchmark coverage.
