# Milestone 22: Inspection-To-Edit Recovery

Milestone 20 showed that TermAgent could locate relevant code yet continue inspecting
until the step limit instead of proposing an edit. Milestone 22 adds a general bounded
transition from repository evidence to a model-authored patch plan.

## Implementation

- The progress ledger counts successful `search`, `read_file`, `code_map`, and
  `find_references` calls.
- It records inspected paths, inspected symbols, and search queries for traces and
  Harbor metadata.
- Required-change runs request a patch transition after six discovery actions by
  default, or earlier after repeated observations that add no evidence.
- If no task plan exists, the provider must call `set_task_plan`. Once a plan exists,
  it must submit exact source contents through `plan_patch` or `plan_patch_set`.
- Further inspection is rejected rather than executed. Two ignored transition requests
  stop the run by default, limiting wasted model calls and tool output.
- The discovery cycle resets after a patch plan or when a failed verifier begins a new
  diagnosis cycle.

The controller does not select replacements, generate source text, or apply edits.
Every file byte remains provider-authored and passes the existing preview/hash contract.

## Development Ablation

Both arms used the deterministic repair provider on the eight local regression tasks.
These fixtures check compatibility and accounting, not live-model generalization.

| Planning | Passed | Mean steps | Mean discovery actions | Transition deferrals | Cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| disabled | 8/8 | 7.125 | 0.000 | 0 | $0.000000 |
| enabled | 8/8 | 7.750 | 2.125 | 0 | $0.000000 |

The easy deterministic tasks did not exhaust the six-action budget. Separate scripted
regression tests force the boundary and verify both successful transition to a patch and
bounded failure when a provider keeps inspecting.

The full source-tree suite passed with `136 passed, 1 skipped`; the skip is the optional
Harbor SDK integration in the normal Python environment. A fresh wheel was then built,
installed offline with its pinned `certifi` dependency, and passed the independent
JavaScript repair verifier in 10 steps with four recorded discovery actions.

## Reproduction

```bash
termagent bench --repo-root . --no-task-planning \
  --report /tmp/milestone22-off.json \
  --markdown-report /tmp/milestone22-off.md

termagent bench --repo-root . --task-planning --max-discovery-actions 6 \
  --report /tmp/milestone22-on.json \
  --markdown-report /tmp/milestone22-on.md
```

## Interpretation

Milestone 22 closes the specific control-flow gap observed in Milestone 20 without
encoding any benchmark solution. It does not prove a quality improvement. The frozen
Milestone 20 tasks were not rerun. Milestone 23 should select and checksum a different
held-out subset before live evaluation.
