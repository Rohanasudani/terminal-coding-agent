# First Release Checklist

The release target is a local coding assistant for trusted repositories with
explicit verification commands. It is not an unrestricted replacement for a
mature coding agent. The showcase submission waits until the remaining evidence
and reliability requirements below are complete.

## Implemented In Milestone 15

- Completion requires the configured verifier's successful exit code.
- Writes and shell commands invalidate earlier verification, including failures.
- A final diff without current verification reports incomplete and exits nonzero.
- Live controller recovery performs inspection only; models must produce and apply patches.
- Benchmark grading uses pristine tests and explicitly allowed solution files.
- Live smoke independently grades the calculator change before reporting success.
- Benchmark trials preserve distinct traces, expose provider/model overrides, and track estimated budgets.
- Three broader public tasks exercise pagination, multiple files, and JavaScript state.
- README setup uses a public clone command instead of a developer-specific directory.

## Required Before Showcase Submission

- Complete the same-model competitor comparison and general improvement cycle in
  [PROJECT_SCOPE.md](../PROJECT_SCOPE.md); these are required outcomes, not optional polish.
- Repeat the live smoke after Milestone 15 and record all trials on the broader suite.
- Run a pinned external task subset against at least one existing coding agent.
- Review process isolation, credential access, shell policy, and stale patch previews;
  add regression tests for concrete bypasses. The current classifier is not a sandbox.
- Verify accounting for unsuccessful provider retries and per-response output limits.
- Test installation and a repair on another machine or clean CI runner.
- Have another developer try an unfamiliar trusted repository and record the failures.
- Record a live demonstration of task, inspection, patch, verifier, and final diff.
- Publish a tagged alpha release with accurate results and known limitations.

## Milestone 16 Evidence

- Pinned Harbor 0.22.0 adapter implemented and exercised in Docker.
- Corrected export build context and independent grader delivery.
- Deterministic repair reward 1 and no-op reward 0 on the same task checksum.
- Strict Harbor report comparison and controller-recovery ablation setting added.
- Per-response output caps, explicit reasoning effort, and failed-retry usage accounting added.
- The rebuilt wheel passed a key-free Harbor control with all comparison settings recorded.
- Live competitor trials, matched reasoning controls, and the external benchmark
  improvement cycle remain pending. See [matched-comparison-readiness.md](matched-comparison-readiness.md).

## Optional After First Release

Subagents, a graphical website, more providers, tree-sitter indexing, and a richer
terminal UI are separate enhancements. They are not substitutes for the required
evaluation and reliability evidence.
