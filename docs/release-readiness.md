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

- Repeat the live smoke after Milestone 15 and record all trials on the broader suite.
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
- A matched TermAgent-versus-Codex development baseline and a controller-recovery
  ablation are complete. External validation produced honest negative results and
  identified the next planning gap. See [milestone18-results.md](milestone18-results.md).

## Milestone 19 Evidence

- Structured plans separate requested deliverables from verifier status.
- Declared output paths must exist before completion.
- Repeated identical discovery is detected and bounded.
- Planning can be enabled or disabled in local and Harbor runs.
- Both local ablation arms retained an 8/8 deterministic pass rate; the planning arm
  added 0.625 mean steps.
- No external quality claim is made until the Milestone 20 live campaign.

## Milestone 20 Evidence

- Froze three unseen coding-focused Terminal-Bench 2 tasks by content hash before runs.
- Oracle passed 3/3 and no-op passed 0/3, establishing working verifier controls.
- Compared planning enabled, planning disabled, and Codex `0.153.4` with
  `openai/gpt-5.6-luna`, one trial per task and no Harbor retries.
- Planning-on and planning-off each scored 0/3; Codex scored 2/3.
- Preserved two provider transport errors, unknown usage, all zero rewards, exact
  versions, task checksums, known costs, and limitations.
- Added machine-checkable campaign verification and report generation commands.

## Post-Campaign Reliability Recovery

- Final review now uses the internal before/after snapshot when the Git executable is
  unavailable, covering the failure observed in the frozen campaign.
- Timeouts, disconnects, URL errors, and selected transient HTTP responses receive at
  most `provider_retries + 1` total attempts with capped exponential backoff.
- Billing and malformed-request failures are not retried.
- A recovered request remains marked with incomplete usage because a failed request
  without usage data may still have incurred provider-side cost.
- Exhausted transport failures become ordinary incomplete agent states, allowing the
  Harbor runner to write `summary.json` and retain the trial for grading.
- These changes were tested on local fixtures only. The frozen Milestone 20 results were
  not rerun or rewritten.

## Optional After First Release

Subagents, a graphical website, more providers, tree-sitter indexing, and a richer
terminal UI are separate enhancements. They are not substitutes for the required
evaluation and reliability evidence.
