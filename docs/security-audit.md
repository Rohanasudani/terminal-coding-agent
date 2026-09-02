# Security And Reliability Audit

Audit date: 2026-09-02

## Milestone Verification

| Milestone | Status | Verification |
| --- | --- | --- |
| 1. Agent runtime | Complete | Structured tools, repo-scoped paths, safety classifier, JSONL tracing, local benchmark harness |
| 2. Test-first coding loop | Complete | Runs verifier first, parses pytest failures, searches, reads, patches, reruns tests |
| 3. Real provider mode | Complete | OpenAI-compatible provider, strict tool-call JSON, retries, config, token/cost tracking |
| 4. Benchmark expansion | Complete | Seven benchmark tasks, JSON/Markdown reports, persisted traces |
| 5. Better coding loop | Complete | Patch previews, planned-write enforcement, reflection after failed tests, richer summaries |
| 6. Multi-file edit strategy | Complete | Grouped patch previews, grouped writes, multi-file benchmark, subsystem summaries |
| 7. Live provider hardening | Complete | Cost ceilings, prompt profiles, observation caps, validation recovery, network blocks |

## Implemented Controls

- File tools resolve every path inside the configured repository root.
- File writes require a matching `plan_patch` or `plan_patch_set` content hash before execution.
- Shell commands run through parsed argv, not `shell=True`.
- Destructive commands such as `rm`, `sudo`, `dd`, `shutdown`, and similar commands are blocked.
- Network commands such as `curl`, `wget`, `ssh`, `scp`, and `rsync` are blocked by default.
- Inline interpreter execution such as `python -c` and `node -e` is blocked.
- Shell control operators such as `;`, `&&`, pipes, backticks, and command substitution are blocked.
- Live provider tool calls are validated before execution.
- Invalid live-provider tool calls are logged and returned as observations for recovery.
- Live mode caps observation count and character payload size to reduce token waste.
- Live mode has a configurable model-cost ceiling before tool execution.
- API keys are read from `OPENAI_API_KEY`; no real secrets are committed.
- Benchmark fixtures are copied into temporary workspaces before agent execution.

## Cost And Token Controls

The live provider sends only the latest bounded observations to the model. Defaults:

- `observation_limit = 6`
- `max_observation_chars = 8000`
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
- Live OpenAI mode is covered by mocked provider tests and missing-key smoke tests; a real API-key smoke run should be performed before publishing a paid live-provider demo claim.
- The deterministic `repair` provider intentionally uses transparent heuristics for local baseline benchmarks. Generalization should be evaluated with live providers and broader tasks.
- Pricing estimates can become stale and should be checked against official provider docs.

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
