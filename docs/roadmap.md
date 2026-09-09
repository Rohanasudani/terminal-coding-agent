# Roadmap

Completion is governed by [PROJECT_SCOPE.md](../PROJECT_SCOPE.md). In particular,
competitor comparisons and measured improvements are required even though earlier
milestones labeled their narrower implementation work complete.

This project should become a credible terminal-agent system, not just a demo wrapper around an LLM.

## Milestone 1: Agent Runtime

Status: complete

- structured tool calls
- repo-scoped file access
- command safety classifier
- JSONL tracing
- deterministic mock provider
- local benchmark harness

## Milestone 2: Test-First Coding Loop

Status: complete

- run verifier command before editing
- parse pytest failure output
- search likely failing symbols
- read targeted source files
- apply narrow patches through the write tool
- rerun tests after edits
- final answer with test status and diff

## Milestone 3: Real Provider Mode

Status: complete

- OpenAI-compatible tool-call provider
- retry loop when tool JSON is invalid
- token and cost accounting
- model configuration through `termagent.toml`

## Milestone 4: Benchmark Expansion

Status: complete

- expanded local benchmark suite to seven tasks
- JSON and Markdown benchmark reports
- persistent per-task traces
- pass-rate and cost summary
- regression tests for benchmark report generation

## Milestone 5: Better Coding Loop

Status: complete

- patch planning before writes
- planned-write enforcement before file writes
- retry/reflection after failed test runs
- final answer with files changed, tests run, and residual risk

## Milestone 6: Multi-File Edit Strategy

Status: complete

- coordinated plans across multiple files
- grouped diffs before applying edits
- rollback guidance for partial failures
- final summary by changed subsystem

## Milestone 7: Live Provider Hardening

Status: complete

- live-mode smoke tests for provider errors and tool-call recovery
- mocked live-provider tests without spending API credits
- missing-key live-mode smoke test
- provider-specific prompt profiles
- structured failure recovery when plans do not apply
- cost ceilings per run

## Milestone 8: Repository Intelligence

Status: complete

- symbol index
- import graph
- call/reference search
- AST-aware Python syntax checks before patches

## Milestone 9: Multi-Language Repository Intelligence

Status: complete

- TypeScript/JavaScript code map
- cross-language symbol search
- import visibility for Python, JavaScript, and TypeScript files
- JavaScript benchmark task covering code-map-driven repair
- tree-sitter kept as the next deeper parser upgrade

## Milestone 10: Terminal-Bench Direction

Status: complete

- baseline comparisons against simple agents
- benchmark report in the README
- Harbor-shaped dataset export
- benchmark report comparison command
- documented path toward a real Terminal-Bench subset run

## Milestone 11: Product Polish

Status: complete

- richer README
- architecture diagrams
- CI workflow
- issue and pull request templates
- contribution and security docs
- project brief with resume bullets
- local health-check command

Milestone 11 completed the public repository polish layer: CI, issue templates, PR template, contribution guide, security policy, project brief, demo commands, architecture diagram, package metadata, and local health checks.

Future public-launch improvements:

- demo GIF
- packaged CLI release
- Harbor-compatible custom agent packaging
- real pinned Terminal-Bench subset run

## Milestone 12: Interactive Agent App

Status: complete

- `termagent app` interactive terminal session
- repeated natural-language coding tasks against one repository
- built-in `:doctor`, `:help`, and `:quit` commands
- same safety, tracing, provider, and cost controls as one-shot runs
- tests for interactive command flow and config mapping

## Milestone 13: Requirements Audit

Status: complete

- requirements traceability matrix from original project goals to implementation
- automated checks for public CLI commands and required tool registry surface
- automated checks that public docs exist and mention project boundaries
- updated README link to the traceability doc

## Milestone 14: Live Provider Smoke Run

Status: historical smoke passed; rerun required after Milestone 15

- Responses API payloads set `store: false`
- `termagent live-smoke` runs a tiny capped OpenAI-compatible provider demo
- sanitized report writes to `docs/live-provider-demo.md`
- raw traces stay under ignored `.termagent/live-smoke`
- mocked tests cover no-key behavior and sanitized reports

## Milestone 15: Verification And Evaluation Integrity

Status: implemented; live evidence pending

- invalidate stale test success after writes and commands
- require the configured verifier's exit code for completion
- remove fixture-specific patches from live controller recovery
- independently grade allowlisted solution files with original fixture tests
- add pagination, configuration, and cache lifecycle development tasks
- preserve repeated trial reports and traces
- portable installation instructions and an explicit first-release checklist

See [release-readiness.md](release-readiness.md) for the remaining release gates.

## Milestone 16: Real Benchmark Integration

Status: adapter and container controls tested; paid comparative evidence pending

- Harbor 0.22.0 custom agent installs the exact built wheel in task containers
- corrected export layout and preserved authoritative grading tests
- actual key-free Harbor runs: deterministic repair reward 1, no-op reward 0
- comparison reports validate task checksums, repeat counts, and model identity
- controller recovery can be disabled for a controlled ablation
- competitor trials and an external evaluation-and-improvement cycle remain required

## Milestone 17: Matched Live Comparison

Status: same-model development baseline and controller ablation complete

- explicit reasoning-effort control for Responses API calls
- configurable per-response output-token ceiling
- usage from malformed structured-output retries retained in run totals
- incomplete accounting identified when transport failures return no usage body
- controls recorded in Harbor result metadata
- rebuilt wheel passed an isolated installation and a key-free Harbor container trial
- TermAgent and Codex each passed 3/3 matched development trials
- the controller-recovery ablation improved internal completion from 1/3 to 3/3
- unseen external-task validation remains Milestone 18

## Milestone 18: Pinned External Validation

Status: complete with negative results

- resolved and pinned two public Terminal-Bench coding tasks by checksum
- compared TermAgent and Codex once on `html-js-filter`; both scored zero
- ran the recovery on/off validation on `payments-pipeline-fix`; both scored zero
- added a required-change invariant to prevent false completion on testless tasks
- preserved all failures, costs, versions, and limitations
- established that a bounded planning transition is required before broader claims

## Milestone 19: Structured Planning And Progress Control

Status: implementation and local ablation complete; external validation pending

- first-class task plan with expected files and acceptance checks
- plan-before-patch enforcement when planning is enabled
- completion guard for missing declared deliverables
- bounded repeated-discovery detection
- progress phases in traces, summaries, and Harbor metadata
- planning enabled/disabled controls for matched experiments
- local ablation retained 8/8 pass rate with 0.625 additional mean steps

The mechanism is implemented without task-specific source patches. Milestone 20 must
test whether it improves pass rate on a frozen unseen Terminal-Bench 2 subset.

## Milestone 20: Terminal-Bench 2 Campaign

Status: protocol and subset frozen; control and live runs in progress

- select and checksum a representative unseen coding subset before live runs
- verify oracle and no-op controls
- compare TermAgent with planning on/off and one established agent
- retain all failures, timeouts, costs, tokens, and exact versions
- publish the experiment protocol before interpreting results

The frozen three-task protocol and content hashes are recorded in
[milestone20-protocol.md](milestone20-protocol.md) and
[`bench/campaigns/milestone20.json`](../bench/campaigns/milestone20.json).
