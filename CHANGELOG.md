# Changelog

All notable changes to TermAgent are recorded here.

## 1.0.0 - Unreleased

### Added

- Interactive and one-shot terminal agent modes with OpenAI-compatible live execution.
- Structured repository search, bounded file listing, multi-language symbol indexing,
  patch planning, grouped writes, shell execution, and final-diff tools.
- Task plans and strict completion reviews tied to declared outputs and acceptance checks.
- JSONL traces with token, cost, retry, discovery, transition, and completion telemetry.
- Local fixture benchmarks plus frozen Harbor/Terminal-Bench campaign tooling with
  oracle/no-op controls, checksums, pinned wheels, and same-model comparator support.
- Portable Harbor wheel loading and bounded Python bootstrap for minimal task images.

### Changed

- Baseline verifier passes no longer count as completion evidence for required-change
  tasks.
- Git diffs anchor to the run's starting commit, including changes committed mid-run.
- Search fallbacks use consistent extended regular expressions and report truncation.
- The deterministic fixture provider is separated from the live provider and documented
  as runtime regression support rather than model-quality evidence.

### Security

- Repository-root path confinement and symbolic-link rejection for file operations.
- Patch-plan hashes required before live-provider writes.
- Shell control operators, destructive commands, mutating read-command flags, and inline
  interpreter execution blocked by policy.
- Private credential paths excluded at both search-command and parsed-output layers.
- Provider schema validation, bounded observations, output limits, and cost accounting.

### Evaluation

- The local deterministic suite passes 8/8 tasks.
- The frozen v1 revision-2 TermAgent arm passes 4/8 independent graders with zero setup
  errors and $0.161075 recorded model usage. The same-model comparator remains pending
  until the final release report is generated.
