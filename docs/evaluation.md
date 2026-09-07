# Evaluation

## What Is Measured

`bench/tasks` contains eight small deterministic repair regression tasks.
`bench/evaluation` contains three broader public development tasks. They have no
repair heuristics in the agent runtime. Reference fixes in `tests/test_grading.py`
validate that their tests distinguish the broken fixture from a correct solution;
those fixes are never supplied to the agent by the harness.

Every task declares `solution_files`. After a run, the grader copies the original
fixture into a new temporary directory and overlays only those files. Changes to
the agent's copy of tests or test configuration do not enter that directory.
The original fixture must fail and the graded solution must pass. Agent completion
is reported separately from the independent grade. An empty suite is an error.

These directories are not an OS sandbox. Only execute trusted tasks. Candidate
code still runs as your user; isolation does not stop deliberately hostile code.

## Commands

From an activated development environment at the repository root:

```bash
termagent bench --repo-root .
termagent bench --tasks-dir bench/evaluation --provider repair --report .termagent/evaluation/repair.json --markdown-report .termagent/evaluation/repair.md
```

The second command may fail tasks. Preserve those failures as the baseline.
For a paid live run, set `OPENAI_API_KEY` locally, then:

```bash
termagent bench --tasks-dir bench/evaluation --provider openai --repeats 3 --reasoning-effort high --max-output-tokens 4096 --max-cost-usd 0.05 --max-total-cost-usd 0.45 --report .termagent/evaluation/live.json --markdown-report .termagent/evaluation/live.md
```

Cost limits are estimates checked after provider responses, not a prepaid billing
guarantee. A response may overshoot the remaining allowance. Pricing and unsuccessful
provider retries also need review before relying on these estimates for strict budgets.
The harness stops starting trials once recorded usage reaches the total limit.
Each invocation preserves separate traces and a partial JSON report beneath its
report directory, including when the total budget stops the suite.

Reports include raw verifier output and local paths. Keep these under `.termagent`
and review/redact before publishing. A failed run must remain in the denominator.

## Comparison Protocol Still Required For Release

Measured on 2026-09-06, one deterministic `repair` trial per development task:

| Task | Result | Steps |
| --- | --- | ---: |
| cache_expiry | fail | 4 |
| config_precedence | fail | 4 |
| pagination | fail | 3 |

Total: 0/3, no API calls. This is the deterministic baseline only. Current live
results are pending; do not interpret the reference-solution tests as agent success.

Freeze a task set and commit before further tuning. Record task revision, model ID,
agent revision, command, limits, and all repeated trials. Use identical tasks,
verifiers, models where supported, and budgets for the comparator agent. Report
pass rate, latency, cost, and failure categories. Never put evaluator answers or
task-specific repair code into the runtime.

The public development tasks above do not establish performance on unseen work.
A pinned external task subset and a real comparator run remain release work.
