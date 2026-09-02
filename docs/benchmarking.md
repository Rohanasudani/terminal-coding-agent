# Benchmarking Plan

The project is benchmark-first. The local harness is small today, but it is shaped to grow toward Terminal-Bench-style evaluation.

## Local Benchmarks

Run:

```bash
termagent bench --repo-root .
```

The harness writes `bench/results/latest.json` with pass/fail counts, runtime, verifier output, trace location, and task name.

Each task can define its own verifier command. The default command uses the current Python executable:

```bash
{python} -m pytest -q
```

That placeholder makes benchmarks more portable across virtual environments and CI.

## Why Start Local

Local tasks are cheap, deterministic, and fast. They help catch regressions in:

- tool execution
- path sandboxing
- write behavior
- shell safety policy
- agent loop completion
- trace logging
- test-first repair behavior

## Terminal-Bench Direction

Terminal-Bench evaluates AI agents in real terminal environments with end-to-end tasks. Its current Harbor-based workflow runs agents against published datasets and measures resolution rates, cost, tokens, and runtime.

This project should eventually provide an adapter that lets Harbor invoke `termagent` as an agent backend. The local benchmark harness is the stepping stone: it already models isolated tasks, verifier commands, and machine-readable reports.

## Anti-Cheating Rule

Do not hardcode benchmark answers as the final strategy. Small targeted heuristics can be useful experiments, but the project should document them clearly and measure whether they generalize.
