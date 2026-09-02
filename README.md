# Terminal Coding Agent

A benchmarkable terminal coding agent inspired by tools like Claude Code and Codex. The goal is not just to call an LLM from a terminal; the goal is to build an agent that can inspect a repository, plan changes, use structured tools, preview diffs, obey safety gates, and produce reproducible benchmark logs.

## Why This Project Exists

Terminal agents are becoming the default interface for AI-assisted software work. The hard part is not a chat loop. The hard part is reliability: knowing what to read, when to edit, how to verify, how to avoid unsafe commands, and how to measure whether the agent is improving.

This project treats the agent as an engineering system:

- structured tools instead of free-form shell guessing
- repo search and file reads before edits
- write tools with diff previews
- approval gates for risky shell commands
- JSONL command logs for every tool call
- a local benchmark harness for regression testing
- provider abstraction for mock, OpenAI-compatible, or future model backends

## Current Features

- `termagent run`: execute a task against a repository
- `termagent tools`: inspect available structured tools
- `termagent bench`: run local benchmark tasks and write a report
- repo search powered by `rg` when available
- file read/write with path sandboxing
- shell execution with deny/approval policy
- git diff preview
- deterministic mock provider for tests and demos
- JSONL traces for tool calls, observations, and final answers

## Quickstart

```bash
cd /Users/apple/.codex/workspaces/default/terminal-coding-agent
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
termagent tools
termagent run --repo tests/fixtures/sample_repo --task "Fix the calculator add bug and run tests"
termagent bench --repo-root .
```

## Example

```bash
termagent run \
  --repo /path/to/repo \
  --task "Find the failing test, patch the bug, and show the final diff" \
  --approval-mode suggest
```

## Safety Model

The agent runs inside a repository root and rejects file access outside that root. Shell commands are classified before execution:

- safe read-only commands can run
- commands that modify files require approval mode
- destructive commands are blocked by default

This is intentionally conservative. A real terminal agent should make it harder to do dangerous things by accident.

## Benchmarking

The local benchmark harness copies each task fixture into an isolated temporary workspace, runs the agent, then runs the task verifier. Reports include pass/fail status, duration, trace path, and verifier output.

This is the bridge to Terminal-Bench-style evaluation: the agent is designed around reproducible tasks and execution logs from day one.

## Roadmap

- OpenAI-compatible live provider
- richer planning and reflection loop
- benchmark adapter for Terminal-Bench/Harbor
- sub-agent orchestration experiments
- AST-aware code map using tree-sitter
- token/cost accounting
- interactive TUI
- GitHub-ready demo GIF and benchmark report

