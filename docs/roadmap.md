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

## Milestone 4: Better Coding Loop

- patch planning before writes
- multi-file edit strategy
- retry/reflection after repeated failing tests
- final answer with files changed, tests run, and residual risk

## Milestone 5: Repository Intelligence

- symbol index
- import graph
- call/reference search
- AST-aware edit checks
- tree-sitter exploration

## Milestone 6: Benchmarking

- more local tasks across Python and TypeScript
- baseline comparisons against simple agents
- benchmark report in the README
- Harbor/Terminal-Bench adapter

## Milestone 7: Product Polish

- demo GIF
- richer README
- architecture diagrams
- GitHub repo topics
- packaged CLI release
