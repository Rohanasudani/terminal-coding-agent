# Milestone 19: Structured Planning And Progress Control

Milestone 19 adds a general planning transition without encoding solutions for any
benchmark task. The purpose is to address the repeated empty-workspace inspection
observed during Milestone 18 while keeping the behavior independently switchable.

## Implementation

- `set_task_plan` records a concise goal, expected repository-relative output paths,
  and acceptance checks.
- Planning-enabled runs require a task plan before file patch planning.
- Completion checks that every declared output path exists.
- A progress ledger records `discover`, `plan`, `implement`, `verify`, `review`, and
  `complete` phases in traces and Harbor metadata.
- Repeating the same discovery action three times triggers controller guidance. Two
  continued no-progress selections stop the run instead of spending the remaining
  step and token budget on duplicate observations.
- `task_planning` is configurable in TOML and through `--task-planning` or
  `--no-task-planning`, allowing a controlled ablation.

The controller does not invent source code, select file contents, or apply writes.
All edits remain provider-selected and must pass the existing patch-preview contract.

## Development Ablation

Both arms used the deterministic repair provider on the same eight local tasks. This
checks compatibility and overhead; it is not evidence of live-model generalization.

| Planning | Passed | Mean steps | Model cost |
| --- | ---: | ---: | ---: |
| enabled | 8/8 | 7.750 | $0.000000 |
| disabled | 8/8 | 7.125 | $0.000000 |

Planning preserved the pass rate and added 0.625 mean steps, primarily the explicit
plan registration. Unit tests separately confirm that planning prevents premature
writes, validates output paths, detects missing deliverables, and bounds repeated
discovery. The full local suite passed with `120 passed, 1 skipped`; the skip is the
optional Harbor integration under the normal development environment.
The Harbor-enabled environment passed all `124` tests.

The final wheel was then installed offline inside the Harbor task container. The
key-free `bugfix_calculator` control earned reward `1.0` in 8 steps with planning
and required-change enforcement enabled. Harbor recorded zero exceptions, phase
`complete`, and zero stagnation events. The exact wheel SHA-256 was
`29c9ebe185d6ca9c8447a59425fe7d8ac8f48ce31a27fd586e8dbcfc263d42be`.

## Interpretation

This milestone implements the proposed mechanism and establishes a reproducible
ablation switch. It does not yet establish that the mechanism raises external pass
rate. Milestone 20 must freeze a new Terminal-Bench 2 subset before any live runs,
then compare planning enabled and disabled without tuning on held-out answers.

## Reproduction

```bash
termagent bench --repo-root . --task-planning \
  --report /tmp/termagent-planning.json \
  --markdown-report /tmp/termagent-planning.md

termagent bench --repo-root . --no-task-planning \
  --report /tmp/termagent-baseline.json \
  --markdown-report /tmp/termagent-baseline.md
```
