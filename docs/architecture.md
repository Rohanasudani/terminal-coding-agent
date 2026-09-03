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

## Provider Modes

The provider boundary returns a structured tool call plus usage metadata. Local modes return zero-token usage, while live OpenAI-compatible mode parses usage from the Responses API result and rolls it into the final report.

- `repair`: deterministic test-first loop for cheap regression tests and benchmark tasks
- `mock`: stable alias for local tests and demos
- `openai`: live provider that requests strict JSON schema output, validates the selected tool, retries malformed responses, and estimates cost from token usage

The live provider does not execute model text directly. It only accepts a structured `{name, arguments}` tool call, and the agent validates that tool call before handing it to the tool registry.

Live mode adds conservative controls around provider cost and context use. The provider receives only a bounded tail of observations, supports prompt profiles for different operating modes, and stops before tool execution if the estimated model cost exceeds the configured ceiling.

## Planned Writes

File edits go through a two-step contract:

1. `plan_patch` previews a single-file diff without modifying the repository.
2. `plan_patch_set` previews a grouped multi-file diff without modifying the repository.
3. `write_file` and `write_patch_set` are allowed only when their path/content hashes match a previously reviewed plan.

This catches accidental direct writes from live providers and makes traces easier to audit. Every successful final answer includes changed files, patch plans reviewed, tests run, failed test attempts, and residual risk.

## Tool Layer

The tool registry exposes a small set of high-leverage operations:

- `search`: find relevant files and symbols
- `read_file`: inspect source with line numbers
- `code_map`: inspect Python, JavaScript, and TypeScript symbols and imports
- `find_references`: find Python, JavaScript, and TypeScript name references for a symbol
- `plan_patch`: preview a single-file edit
- `plan_patch_set`: preview coordinated multi-file edits as one grouped diff
- `write_file`: patch files and return unified diffs
- `write_patch_set`: apply coordinated multi-file edits after a grouped plan
- `run_shell`: execute commands under a safety policy
- `git_diff`: show the final repository diff

The agent does not get raw filesystem access. Every path is resolved inside the repository root. For non-git fixture workspaces, `git_diff` falls back to an internal snapshot diff so benchmarks still get a clean before/after report.

## Repository Intelligence

The repository intelligence layer uses Python's standard library `ast` module for Python files and a conservative JavaScript/TypeScript scanner for common source patterns. It indexes:

- classes, functions, async functions, methods, and parent scopes
- import edges across Python, JavaScript, and TypeScript files
- name references with line numbers
- parse errors for Python files that cannot be indexed

Patch planning performs a Python syntax check for `.py` files before a plan is accepted. JavaScript and TypeScript indexing is intentionally pragmatic today; tree-sitter remains the next step for deeper syntax-aware edits.

## Safety Gates

Shell commands are classified before execution:

- read-only commands run automatically
- mutating commands require approval unless the run is explicitly configured with `approval_mode=auto`
- destructive commands are blocked by default
- network commands are blocked by default
- inline interpreter execution and shell control operators are blocked

Commands are executed as parsed argv lists rather than through a shell. This reduces command-injection risk from live provider outputs while keeping normal commands such as `python -m pytest -q` usable.

This mirrors the safety model expected from a real terminal coding agent: useful by default, cautious around writes, and hostile to accidental destructive operations.

## Benchmark Harness

Local benchmark tasks live under `bench/tasks`. Each task has:

- a fixture repository
- a natural-language instruction
- a verifier command

The harness copies each fixture into a temporary workspace, runs the agent, executes the verifier, persists per-task traces, and writes JSON plus Markdown reports.

## Harbor Bridge

The Harbor bridge exports local benchmark tasks into a Harbor-shaped directory layout with `task.toml`, `instruction.md`, `environment/Dockerfile`, `tests/test.sh`, and `solution/solve.sh`. The generated verifier script runs the local task verifier and writes `1` or `0` to `/logs/verifier/reward.txt`, matching Harbor's reward-file convention.

The bridge also compares benchmark JSON reports so local repair runs, live-provider smoke runs, and future Harbor runs can be summarized side by side.

## Next Technical Bets

- tree-sitter-backed multi-language parsing
- stronger live-provider repair strategies
- sub-agent orchestration experiments
- Harbor-compatible custom agent packaging
- small pinned Terminal-Bench subset run
