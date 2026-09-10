# Security And Reliability Audit

Audit date: 2026-09-07

## Milestone Verification

| Milestone | Status | Verification |
| --- | --- | --- |
| 1. Agent runtime | Complete | Structured tools, repo-scoped paths, safety classifier, JSONL tracing, local benchmark harness |
| 2. Test-first coding loop | Complete | Runs verifier first, parses pytest failures, searches, reads, patches, reruns tests |
| 3. Real provider mode | Complete | OpenAI-compatible provider, strict tool-call JSON, retries, config, token/cost tracking |
| 4. Benchmark expansion | Complete | Eight benchmark tasks, JSON/Markdown reports, persisted traces |
| 5. Better coding loop | Complete | Patch previews, planned-write enforcement, reflection after failed tests, richer summaries |
| 6. Multi-file edit strategy | Complete | Grouped patch previews, grouped writes, multi-file benchmark, subsystem summaries |
| 7. Live provider hardening | Complete | Cost ceilings, prompt profiles, observation caps, validation recovery, network blocks |
| 8. Repository intelligence | Complete | Python AST symbol/import/reference map and syntax validation before planned patches |
| 9. Multi-language repository intelligence | Complete | Python, JavaScript, and TypeScript symbol/import/reference map with ignored dependency/build folders |
| 10. Terminal-Bench direction | Complete | Harbor-shaped dataset export, reward-file verifier scripts, benchmark comparison reports |
| 11. Product polish | Complete | CI, issue templates, contribution guide, security policy, project brief, demo docs, health checks |
| 12. Interactive agent app | Complete | Interactive task loop reusing the same provider, safety policy, planned writes, traces, and cost controls |
| 13. Requirements audit | Complete | Requirements traceability matrix, CLI/tool surface checks, public docs checks, honest-boundary assertions |
| 14. Live-provider smoke readiness | Ready | Responses API `store: false`, capped `live-smoke` command, sanitized report, raw traces ignored |
| 15. Evaluation integrity | Complete | Fresh verification, pristine graders, allowlisted solution files, no fixture-specific live patches |
| 16. Harbor integration | Complete | Exact-wheel install, task checksums, oracle/no-op controls, comparison validation |
| 17. Matched live comparison | Complete | Same-model development trials, usage controls, controller ablation |
| 18. Pinned external validation | Complete | External failures retained, required-change guard, untracked diff support |
| 19. Structured planning | Implemented | Plan-before-patch option, declared-path guard, bounded stagnation, ablation control |
| 20. Frozen external campaign | Complete | Three pinned tasks, oracle/no-op controls, planning ablation, Codex comparison, all failures retained |

## Implemented Controls

- File tools resolve every path inside the configured repository root.
- File writes require a matching `plan_patch` or `plan_patch_set` content hash before execution.
- Shell commands run through parsed argv, not `shell=True`.
- Destructive commands such as `rm`, `sudo`, `dd`, `shutdown`, and similar commands are blocked.
- Network commands such as `curl`, `wget`, `ssh`, `scp`, and `rsync` are blocked by default.
- Inline interpreter execution such as `python -c` and `node -e` is blocked.
- Shell control operators such as `;`, `&&`, pipes, backticks, and command substitution are blocked.
- Live provider uses native OpenAI function calls with strict per-tool argument schemas.
- Live provider tool calls are validated before execution.
- Live provider prompts include the configured verifier command and prohibit chained shell snippets.
- Repeated failed verifier commands are redirected by a controller loop guard into inspection or patch planning.
- Controller redirects gather diagnostic evidence only; provider-selected calls must plan and apply patches.
- Live provider fallback structured-output schemas disable additional properties on every object.
- Nullable schema placeholders are removed before tool validation or execution.
- OpenAI-compatible Responses API payloads set `store: false`.
- Live provider HTTPS requests use `certifi` for certificate validation.
- Invalid live-provider tool calls are logged and returned as observations for recovery.
- Live mode caps observation count and character payload size to reduce token waste.
- Live responses have a configurable output-token ceiling; benchmark reasoning effort is explicit.
- Returned usage from failed structured-output retries is retained. Transport failures are marked incomplete.
- Live mode has a configurable model-cost ceiling before tool execution.
- Python patch planning validates syntax before approving planned writes.
- Repository intelligence skips dependency and build folders such as `node_modules`, `dist`, and `build`.
- Harbor export writes generated files under the requested output directory and refuses to overwrite existing output unless `--overwrite` is passed.
- API keys are read from `OPENAI_API_KEY`; no real secrets are committed.
- Benchmark fixtures are copied into temporary workspaces before agent execution.
- Harbor runs require a non-empty final diff, preventing testless tasks from completing without work.
- Untracked-only Git changes are included through the startup snapshot fallback.
- Planning-enabled runs reject patch planning until deliverables and acceptance checks are registered.
- Declared output paths are confined to the repository and must exist before completion.
- Repeated identical discovery calls are blocked at a configurable bound to limit wasted tokens.

## Cost And Token Controls

The live provider sends only the latest bounded observations to the model. Defaults:

- `observation_limit = 6`
- `max_observation_chars = 8000`
- `max_output_tokens = 4096`
- `max_cost_usd = 0.25`
- `provider_retries = 2`

The model price table in `src/termagent/pricing.py` is an estimate used for local reporting. It was checked against official OpenAI model documentation on 2026-09-02 and should be reviewed before relying on it for billing decisions.

## Static Audit Notes

Local scan looked for:

- `shell=True`
- `eval(`
- `exec(`
- `pickle`
- YAML parsing
- hardcoded API keys or secrets
- network command usage
- destructive command usage

No unsafe implementation instances were found after Milestone 7 hardening. Remaining mentions are policy definitions, tests, docs, or the OpenAI authorization header construction using the environment-provided key.

## Known Limitations

- This is still a local developer tool, not a complete OS-level sandbox.
- `approval_mode=auto` allows non-destructive mutating commands after policy checks.
- The shell classifier is conservative and may block legitimate complex commands.
- A historical live smoke passed before Milestone 15. The new model-only patch path and independent grader require a fresh live run.
- The deterministic `repair` provider intentionally uses transparent heuristics for local baseline benchmarks. Generalization should be evaluated with live providers and broader tasks.
- Pricing estimates can become stale and should be checked against official provider docs.
- Provider timeouts, disconnects, and retryable HTTP failures receive bounded retries.
  If recovery fails, the run writes a normal failed summary. Usage remains explicitly
  incomplete when any request ends without a response body.
- Final review falls back to the agent's initial filesystem snapshot when Git is absent
  or the task directory is not a Git repository.

## Milestone 15 Follow-Up

Verification now uses the configured command's exit status rather than matching
success words in output. Writes and shell commands invalidate prior success.
Benchmarks and live smoke use a fresh grading directory with pristine tests and
only allowlisted source changes. Grader subprocesses receive a limited environment
without provider keys. This does not constrain arbitrary code at the OS level.
See [release-readiness.md](release-readiness.md) for outstanding security work.

## Recommended Safe Defaults

Use this for local development:

```bash
termagent run --repo /path/to/repo --task "Fix the failing tests" --approval-mode suggest
```

Use this for controlled benchmark runs:

```bash
termagent bench --repo-root .
```

Use live mode only after setting `OPENAI_API_KEY`, and keep `max_cost_usd` configured.
