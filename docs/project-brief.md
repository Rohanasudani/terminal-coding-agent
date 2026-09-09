# Project Rationale

## Summary

TermAgent is a benchmarkable terminal coding agent with structured tools, safety gates, repository intelligence, cost tracking, and reproducible eval reports.

## Project Motivation

Coding-agent quality depends on more than whether a model can generate a plausible
patch. The surrounding system must select useful context, constrain tool execution,
distinguish test success from task completion, and preserve enough evidence to explain
both successful and failed runs.

TermAgent treats those behaviors as testable engineering components. Repository reads,
writes, shell commands, verification, and final review pass through structured tools.
Runs produce bounded traces and usage records, while local fixtures and Harbor tasks
provide independent grading paths.

## Key Design Decisions

- **Structured execution:** provider output is validated as one typed tool call instead
  of being passed directly to a shell.
- **Two-phase writes:** file contents must receive a matching patch preview and content
  hash before the corresponding write is accepted.
- **Fresh verification:** any write or shell command invalidates earlier verifier
  success, and completion requires the configured verifier to pass afterward.
- **Task-aware completion:** optional structured plans record expected output files and
  acceptance checks so a passing smoke command cannot hide missing deliverables.
- **Bounded recovery:** repeated no-progress discovery is detected and stopped at a
  configurable limit instead of consuming the remaining token and step budget.
- **Separated evaluation:** deterministic fixtures catch runtime regressions, while live
  model behavior is measured independently through pinned Harbor tasks.
- **Explicit boundaries:** command classification, repository path checks, cost limits,
  and network defaults reduce risk but are not presented as an operating-system sandbox.

## Evaluation Status

- The deterministic local provider passes all eight regression tasks without API calls.
- A packaged Harbor custom agent installs an exact wheel inside task containers and
  records task checksums, model settings, usage, cost estimates, and agent metadata.
- Matched development trials compared TermAgent and Codex with the same model; those
  small fixtures are integration evidence, not a general ranking.
- Two pinned external Terminal-Bench tasks produced zero reward and are retained as
  negative results. Their traces motivated the structured-planning transition.
- The planning-enabled and planning-disabled local arms both remain at 8/8, with a
  measured 0.625-step mean overhead for explicit plan registration.
- A frozen three-task Terminal-Bench 2 campaign found no planning improvement:
  both TermAgent arms scored 0/3 and Codex scored 2/3. The project makes no full
  benchmark or leaderboard claim from this limited result.

Detailed methods, controls, failures, and reproduction commands are linked from the
main README and the milestone result documents.
