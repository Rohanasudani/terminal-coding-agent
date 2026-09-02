# Architecture

## Goal

Terminal Coding Agent is built around one question:

> Can a terminal agent inspect, edit, verify, and report on code changes in a way that is measurable?

The first version is intentionally small but structured like a serious agent runtime. It separates the agent loop, model provider, tool registry, safety policy, and benchmark harness so each part can improve independently.

## Agent Loop

1. Receive a repository path and natural-language task.
2. Ask the provider for the next structured tool call.
3. Execute that tool through the registry.
4. Log the call and result as JSONL.
5. Feed observations back into the provider.
6. Stop when the provider asks for `git_diff` or the step budget is exhausted.

The default repair provider is deterministic so tests and benchmarks can run without API credits.

## Test-First Repair Loop

The Milestone 2 loop starts by running the configured verifier command. When tests fail, the agent parses pytest output for the failing file, assertion, and symbol name. It then searches the repository, reads the likely implementation file, applies a narrow patch, reruns the verifier, and only finishes after producing a final diff.

This keeps the agent behavior measurable: each improvement should increase benchmark pass rate, reduce unnecessary tool calls, or improve the final trace.

## Tool Layer

The tool registry exposes a small set of high-leverage operations:

- `search`: find relevant files and symbols
- `read_file`: inspect source with line numbers
- `write_file`: patch files and return unified diffs
- `run_shell`: execute commands under a safety policy
- `git_diff`: show the final repository diff

The agent does not get raw filesystem access. Every path is resolved inside the repository root. For non-git fixture workspaces, `git_diff` falls back to an internal snapshot diff so benchmarks still get a clean before/after report.

## Safety Gates

Shell commands are classified before execution:

- read-only commands run automatically
- mutating commands require approval unless the run is explicitly configured with `approval_mode=auto`
- destructive commands are blocked by default

This mirrors the safety model expected from a real terminal coding agent: useful by default, cautious around writes, and hostile to accidental destructive operations.

## Benchmark Harness

Local benchmark tasks live under `bench/tasks`. Each task has:

- a fixture repository
- a natural-language instruction
- a verifier command

The harness copies each fixture into a temporary workspace, runs the agent, executes the verifier, and writes a JSON report. This design makes it straightforward to add Terminal-Bench/Harbor adapters later.

## Next Technical Bets

- AST/code-map indexing with tree-sitter
- OpenAI-compatible live provider with strict tool-call JSON
- retry/reflection loop after repeated failing tests
- sub-agent orchestration experiments
- cost/token accounting
- Harbor/Terminal-Bench adapter
