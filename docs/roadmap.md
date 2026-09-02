# Roadmap

This project should become a credible terminal-agent system, not just a demo wrapper around an LLM.

## Milestone 1: Agent Runtime

Status: in progress

- structured tool calls
- repo-scoped file access
- command safety classifier
- JSONL tracing
- deterministic mock provider
- local benchmark harness

## Milestone 2: Real Provider Mode

- OpenAI-compatible tool-call provider
- retry loop when tool JSON is invalid
- token and cost accounting
- model configuration through `termagent.toml`

## Milestone 3: Better Coding Loop

- test failure summarization
- targeted search after failing tests
- patch planning before writes
- final answer with files changed, tests run, and residual risk

## Milestone 4: Repository Intelligence

- symbol index
- import graph
- call/reference search
- AST-aware edit checks
- tree-sitter exploration

## Milestone 5: Benchmarking

- more local tasks across Python and TypeScript
- baseline comparisons against simple agents
- benchmark report in the README
- Harbor/Terminal-Bench adapter

## Milestone 6: Product Polish

- demo GIF
- richer README
- architecture diagrams
- GitHub repo topics
- packaged CLI release

