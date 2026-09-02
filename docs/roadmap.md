# Roadmap

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

- live run smoke tests with a tiny fixture
- provider-specific prompt profiles
- structured failure recovery when plans do not apply
- cost ceilings per run

## Milestone 8: Repository Intelligence

- symbol index
- import graph
- call/reference search
- AST-aware edit checks
- tree-sitter exploration

## Milestone 9: Terminal-Bench Direction

- baseline comparisons against simple agents
- benchmark report in the README
- Harbor/Terminal-Bench adapter

## Milestone 10: Product Polish

- demo GIF
- richer README
- architecture diagrams
- GitHub repo topics
- packaged CLI release
