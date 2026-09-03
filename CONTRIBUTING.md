# Contributing

TermAgent is benchmark-first. Changes should either improve capability, improve safety, improve observability, or make benchmark behavior easier to reproduce.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
termagent doctor
```

## Before Opening A Pull Request

```bash
ruff check .
pytest -q
termagent bench --repo-root .
python -m compileall -q src tests
```

## Development Principles

- Prefer structured tools over free-form shell access.
- Keep file operations scoped to the configured repository root.
- Add benchmark coverage for new repair behavior.
- Keep live-provider changes covered by mocked tests when possible.
- Do not commit API keys, private traces, or generated benchmark artifacts.

## Adding A Benchmark Task

Create a directory under `bench/tasks` with:

- `task.json`
- `repo/`
- a verifier command that exits `0` only when the task is solved

Then run:

```bash
termagent bench --repo-root .
```
