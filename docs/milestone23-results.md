# Milestone 23: Post-Recovery Terminal-Bench 2 Results

## Frozen Configuration

- Harbor: `0.22.0`
- Model: `openai/gpt-5.6-luna`
- TermAgent wheel: `3fdae4d2a481d988609af670e404dbee82c6e9fbde65011fc2ea8912831d521e`
- Codex: `0.153.4`
- Trials per task and arm: `1`

## Control Results

| Task | Oracle | No-op | Harbor Task Checksum |
| --- | ---: | ---: | --- |
| `polyglot-c-py` | 1 | 0 | `a8f31608c78e9fdb853cb9978fa458c59100863343bc477a45c64c6acd9db7a7` |
| `kv-store-grpc` | 1 | 0 | `2081412abc906b638c4e8fd9633deb1cfe12b3047c65917e529a007b41589650` |
| `multi-source-data-merger` | 1 | 0 | `c366c2db9d9ee730326e6a8fe5a9fca86b69a7ca8112f0f8e85a799a5deb70f2` |

All oracle trials passed and all no-op trials failed without exceptions.

## Live Results

| Task | Arm | Reward | Error | Input Tokens | Output Tokens | Cost | Duration | Discovery | Transitions |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `kv-store-grpc` | `codex-baseline` | 1 | no | 151315 | 3483 | $0.010664 | 250.2s | unknown | unknown |
| `kv-store-grpc` | `termagent-planning-off` | 0 | no | 39785 | 4921 | $0.013862 | 100.2s | 0 | 0 |
| `kv-store-grpc` | `termagent-planning-on` | 0 | no | 34280 | 8818 | $0.017437 | 99.7s | 5 | 0 |
| `multi-source-data-merger` | `codex-baseline` | 1 | no | 45012 | 2695 | $0.007239 | 250.8s | unknown | unknown |
| `multi-source-data-merger` | `termagent-planning-off` | 0 | no | 44471 | 5835 | $0.015896 | 125.7s | 0 | 0 |
| `multi-source-data-merger` | `termagent-planning-on` | 0 | no | 43716 | 12123 | $0.023291 | 142.9s | 4 | 0 |
| `polyglot-c-py` | `codex-baseline` | 1 | no | 95411 | 5709 | $0.012585 | 283.1s | unknown | unknown |
| `polyglot-c-py` | `termagent-planning-off` | unknown | yes | unknown | unknown | unknown | 13.3s | unknown | unknown |
| `polyglot-c-py` | `termagent-planning-on` | unknown | yes | unknown | unknown | unknown | 14.6s | unknown | unknown |

## Aggregate

| Arm | Passed | Errors | Known Cost |
| --- | ---: | ---: | ---: |
| `codex-baseline` | 3/3 | 0 | $0.030488 |
| `termagent-planning-off` | 0/3 | 1 | $0.029758 (partial) |
| `termagent-planning-on` | 0/3 | 1 | $0.040728 (partial) |

## Interpretation

This report preserves every frozen trial, including errors and zero rewards. The
campaign is evidence about this subset only; it is not a Terminal-Bench leaderboard
result or a claim that one agent is globally superior.

## Failure Analysis

- Both `polyglot-c-py` TermAgent arms failed during agent setup because the task image
  could not install the Python 3.12+ wheel. Codex completed the same task, so this is
  an adapter portability failure rather than a task-verifier failure.
- On `kv-store-grpc`, both TermAgent arms reached the grader with zero reward. The
  planning-off arm exhausted 32 steps; planning-on declared completion after 14 steps
  and five discovery actions. The configured visible verifier passed in both runs but
  was not sufficient to satisfy the benchmark grader.
- On `multi-source-data-merger`, both TermAgent arms also reached the grader with zero
  reward. Planning-off exhausted 32 steps. Planning-on stopped after 17 steps when the
  stagnation limit was reached during implementation, after four discovery actions.
- No transition events were recorded in either planning-on run. On this three-task,
  one-trial subset, the Milestone 22 inspection-to-edit recovery did not improve pass
  rate over planning-off.

## Next Engineering Targets

1. Make the Harbor agent bootstrap compatible with task images that lack Python 3.12.
2. Replace permissive compile/smoke verifier hints with repository-specific checks when
   available, while keeping the benchmark's independent grader authoritative.
3. Improve completion review so a passing visible verifier is not treated as enough
   evidence when required behavior remains unverified.
4. Re-evaluate only in a newly frozen campaign; these trials remain immutable.
