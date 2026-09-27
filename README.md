# TermAgent

[![CI](https://github.com/Rohanasudani/terminal-coding-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Rohanasudani/terminal-coding-agent/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

TermAgent is a local terminal coding agent for repository repair tasks. It searches
code, previews patches, runs verification commands, and keeps a JSONL trace of the
actions and model usage behind each result.

TermAgent 1.0 is intended for trusted local repositories. It is not an
operating-system sandbox and should not be pointed at untrusted code without container
or VM isolation.

## Quick Start

```bash
git clone https://github.com/Rohanasudani/terminal-coding-agent.git
cd terminal-coding-agent
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
export OPENAI_API_KEY="your-api-key"
termagent doctor
```

Start an interactive session in a repository:

```bash
termagent app --repo /path/to/repo
```

Or run one task:

```bash
termagent run \
  --repo /path/to/repo \
  --task "Find the failing test, fix the bug, rerun the tests, and show the diff" \
  --approval-mode suggest \
  --max-cost-usd 0.25
```

Both commands use the live OpenAI provider by default. The `fixture` provider is kept
for offline regression tests and the recorded demo; it is not a general coding model.

## How A Run Works

1. The provider requests one structured tool call.
2. The controller validates the call against repository, command, and progress rules.
3. File changes are previewed and hashed before they can be written.
4. Verification after the latest change determines whether the task can complete.
5. The final answer reports changed files, checks, token usage, estimated cost, and any
   remaining risk.

Available tools cover bounded file listing and search, Python/JavaScript/TypeScript
symbol lookup, file reads, single- and multi-file patch planning, repository-scoped
writes, shell commands, and final diffs.

For stricter benchmark-style completion checks, add `--strict-completion`. This
requires task planning, final-diff review, and evidence for each declared acceptance
check.

## Safety Boundaries

TermAgent resolves file paths inside the selected repository and rejects symlink
escapes. Live-provider writes must match a previously previewed content hash. Commands
are parsed into argument lists and run without a shell; destructive commands, shell
control syntax, mutating variants of otherwise read-only tools, and inline interpreter
execution are blocked by policy.

These controls make model actions reviewable, but they do not isolate executed tests
from the host. Use a disposable container or VM for unfamiliar repositories. The full
threat model is in [docs/security.md](docs/security.md).

## Configuration And Traces

Copy [termagent.example.toml](termagent.example.toml) to `termagent.toml` inside a
target repository to keep repeatable settings. Command-line options override that
file.

Traces and local configuration belong under `.termagent/` or `termagent.toml`; both are
ignored by Git. A trace can contain repository text, command output, provider
responses, and local paths, so review it before sharing it.

## Evaluation

The project uses two separate kinds of tests:

- Eight scripted repair fixtures exercise the controller, tools, grading, and trace
  format offline. The fixture provider currently passes `8/8`.
- Frozen Harbor tasks use a live model and independent graders. On the latest
  eight-task campaign, TermAgent passed `4/8` and Codex CLI passed `7/8` using the same
  model. Neither arm had a setup exception.

TermAgent used 391,639 recorded input tokens and $0.161075, compared with 3,056,788
input tokens and $0.216275 for Codex. It also finished the eight trials in 1,451.5
seconds versus 4,670.7 seconds. That efficiency came with lower task completion: cost
per passing task was about $0.0403 for TermAgent and $0.0309 for Codex.

There was one trial per task, so this is an engineering checkpoint rather than a
leaderboard score or a stable population estimate. Task checksums, settings, individual
results, and failure analysis are in [docs/experiment-log.md](docs/experiment-log.md).

## Offline Demo

The committed asciicast installs the wheel into a clean environment and repairs a
small JavaScript fixture without making API calls:

```bash
asciinema play docs/demo.cast
```

Rebuild it with:

```bash
python scripts/check_wheel.py --record docs/demo.cast
```

## Development

```bash
ruff check .
pytest -q
termagent bench --repo-root .
python -m compileall -q src tests scripts
python -m pip wheel . --wheel-dir .termagent/release-wheels
python scripts/check_wheel.py
python scripts/check_harbor_runtime.py
```

The local benchmark uses the fixture provider unless another provider is selected.
Live runs should use explicit cost limits and keep raw outputs under `.termagent/`.

## Project Map

- [`src/termagent`](src/termagent): controller, tools, providers, CLI, and tracing
- [`tests`](tests): unit, integration, security, packaging, and adapter tests
- [`bench`](bench): local tasks and frozen external campaign manifests
- [`docs/architecture.md`](docs/architecture.md): module boundaries and runtime flow
- [`docs/benchmarking.md`](docs/benchmarking.md): evaluation and reproduction commands
- [`DESIGN.md`](DESIGN.md): design decisions and current tradeoffs
- [`CONTRIBUTING.md`](CONTRIBUTING.md): local development workflow
