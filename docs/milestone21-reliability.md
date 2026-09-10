# Post-Campaign Reliability Recovery

Milestone 20 exposed two infrastructure failures independently of solution quality:
final review failed in a task image without Git, and two disconnected provider requests
ended before Harbor could collect an agent summary. This follow-up fixes those general
failure paths without changing task-specific prompts or source patches.

## Changes

- `git_diff` checks whether Git is available and falls back to the repository snapshot
  captured at agent startup when it is not.
- The OpenAI-compatible provider retries timeouts, dropped HTTP connections, URL errors,
  and selected transient HTTP statuses. Retry count is bounded by `provider_retries` and
  delay is capped exponential backoff.
- HTTP 400-class request failures are not retried, except retryable conflict, timeout,
  and rate-limit statuses. A 429 billing or insufficient-quota response is not retried.
- Any failed request without usage data marks accounting incomplete, even when a later
  retry succeeds, because the provider may have processed part of the failed request.
- Exhausted retries raise a structured `ProviderError`; the agent records the failure
  and the Harbor runner writes a gradeable `summary.json` with a nonzero exit status.

## Verification

Focused tests cover snapshot fallback with Git unavailable, disconnect recovery,
timeout exhaustion, billing error classification, incomplete usage propagation, and
summary creation after exhausted retries. The full unit suite and deterministic local
benchmark are run before release.

No Milestone 20 task was rerun. Its 0/3 TermAgent results and unknown transport-failure
costs remain the historical record. Quality improvements will be evaluated on a new
held-out set.
