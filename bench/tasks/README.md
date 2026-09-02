# Benchmark Tasks

Each directory is a self-contained coding task with:

- `task.json`: natural-language instruction, verifier command, category, language, and step budget
- `repo/`: fixture repository copied into a temporary workspace before each run

The benchmark harness never edits these fixtures in place. It copies them, runs the agent, persists traces under `bench/results/traces`, and writes JSON plus Markdown reports.

Current deterministic baseline: `7/7` tasks pass with the `repair` provider.
