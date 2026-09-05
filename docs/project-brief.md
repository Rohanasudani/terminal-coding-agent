# Project Brief

## One-Line Summary

TermAgent is a benchmarkable terminal coding agent with structured tools, safety gates, repository intelligence, cost tracking, and reproducible eval reports.

## Recruiter Pitch

Most terminal agents are impressive demos but hard to evaluate. TermAgent treats agent behavior like an engineering system: every run is tool-mediated, traceable, cost-aware, and benchmarked. It can inspect repositories, plan patches before writing, run verifiers, enforce safety rules, and export tasks into a Harbor-shaped benchmark format.

## Resume Bullets

- Built a benchmarkable terminal coding agent in Python with interactive app mode, structured repo search, file read/write tools, shell execution, approval gates, diff previews, JSONL traces, live-provider smoke tooling, and safe OpenAI-compatible integration.
- Implemented a test-first repair loop with planned patch enforcement, token/cost accounting, Python/JavaScript/TypeScript repository intelligence, and an 8/8 local benchmark baseline.
- Added Harbor/Terminal-Bench-style benchmark export tooling, comparison reports, CI coverage, and security documentation for reproducible agent evaluation.

## Interview Talking Points

- Why structured tool calls are safer than free-form command generation.
- How planned-write hashes prevent unreviewed live-provider file writes.
- How benchmark fixtures, verifier commands, traces, and cost reports make agent progress measurable.
- Why deterministic local providers are useful for regression testing even when live LLM providers are the real target.
- What remains before claiming a public Terminal-Bench score: packaged Harbor custom agent, pinned model run, documented cost, and external benchmark results.
