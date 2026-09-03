# Requirements Traceability

This document maps the original project requirements to implemented TermAgent milestones, verification commands, and current limitations.

## Original Project Requirements

| Requirement | Status | Implementation | Verification |
| --- | --- | --- | --- |
| Repo search | Complete | `search` tool uses ripgrep when available with fallback search | `tests/test_tools.py`, `termagent tools` |
| File read/write tools | Complete | `read_file`, `plan_patch`, `write_file`, `plan_patch_set`, `write_patch_set` | `tests/test_tools.py`, `tests/test_agent.py` |
| Shell execution | Complete | `run_shell` executes parsed argv under the safety classifier | `tests/test_safety.py`, `tests/test_tools.py` |
| Approval gates | Complete | `never`, `suggest`, and `auto` approval modes | `tests/test_safety.py`, `tests/test_agent.py` |
| Git diff previews | Complete | `git_diff` plus snapshot fallback for non-git fixtures | `tests/test_tools.py`, benchmark traces |
| Structured tool interfaces | Complete | Provider output is strict `{name, arguments}` JSON | `tests/test_provider.py`, `src/termagent/provider.py` |
| Command logging | Complete | JSONL trace logger records agent events, tool calls, and tool results | `tests/test_agent.py`, `bench/results/traces` |
| Safety controls | Complete | path sandbox, destructive command blocks, network defaults, planned writes, cost ceiling | `docs/security-audit.md`, full test suite |
| Test-first repair loop | Complete | verifier-first run, failure parsing, targeted read, patch, rerun | local benchmark suite |
| Benchmarking | Complete | `termagent bench`, JSON/Markdown reports, 8 local tasks | `termagent bench --repo-root .` |
| Multi-language repository intelligence | Complete | Python AST plus JavaScript/TypeScript scanner for symbols/imports/references | `tests/test_code_map.py` |
| Live LLM mode | Complete with caveat | OpenAI-compatible provider with strict tool calls and cost accounting | mocked tests; real key smoke run still optional |
| Terminal-Bench direction | Complete with caveat | Harbor-shaped export and comparison reports | `tests/test_harbor.py`, `termagent harbor-export` |
| Interactive agent app | Complete | `termagent app` repeated task loop with `:doctor`, `:help`, `:quit` | `tests/test_interactive.py` |

## Milestone Compliance

| Milestone | Requirement Fit | Evidence |
| --- | --- | --- |
| 1. Agent runtime | Establishes structured agent loop, repo-scoped tools, tracing, benchmark harness | `src/termagent/agent.py`, `src/termagent/tools.py`, `src/termagent/logging.py` |
| 2. Test-first coding loop | Runs verifier before editing and reruns after patching | `src/termagent/provider.py`, `tests/test_agent.py` |
| 3. Real provider mode | Adds live provider boundary without executing free-form model text | `src/termagent/provider.py`, `tests/test_provider.py` |
| 4. Benchmark expansion | Makes quality measurable with repeatable local tasks | `bench/tasks`, `docs/benchmark-report.md` |
| 5. Better coding loop | Adds planned writes and richer completion summaries | `src/termagent/agent.py`, `tests/test_agent.py` |
| 6. Multi-file edit strategy | Supports grouped patch plans and grouped writes | `tests/test_agent.py`, `tests/test_tools.py` |
| 7. Live provider hardening | Caps cost/context and blocks unsafe tool calls before execution | `tests/test_provider.py`, `tests/test_agent.py` |
| 8. Repository intelligence | Adds Python symbol/import/reference awareness | `src/termagent/code_map.py`, `tests/test_code_map.py` |
| 9. Multi-language intelligence | Adds JavaScript/TypeScript discovery and benchmark coverage | `bench/tasks/bugfix_javascript_total`, `tests/test_code_map.py` |
| 10. Terminal-Bench direction | Exports Harbor-shaped local benchmark tasks | `src/termagent/harbor.py`, `docs/harbor-terminal-bench.md` |
| 11. Recruiter polish | Makes the public repo easy to assess | `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `.github` |
| 12. Interactive agent app | Turns the CLI into a reusable local terminal app | `src/termagent/interactive.py`, `docs/interactive-app.md` |
| 13. Requirements audit | Keeps project claims aligned with code and tests | `docs/requirements-traceability.md`, `tests/test_project_requirements.py` |

## Verification Checklist

Run this before resume/GitHub updates:

```bash
ruff check .
pytest -q
termagent bench --repo-root .
python -m compileall -q src tests
termagent doctor --repo .
```

Security smoke scan:

```bash
rg -n "shell=True|eval\(|exec\(|pickle" src
```

Expected result: no matches.

## Honest Boundaries

- The local `repair` provider is deterministic and intentionally uses transparent heuristics for regression testing.
- OpenAI live mode is implemented and tested with mocked HTTP responses, but paid live demos should be run with a real key before making live-performance claims.
- Harbor export produces Harbor-shaped local tasks. It is not a public Terminal-Bench leaderboard score.
- JavaScript and TypeScript indexing is conservative; tree-sitter-backed parsing remains a future deeper implementation.
- TermAgent is a local developer tool with safety controls, not a complete operating-system sandbox.
