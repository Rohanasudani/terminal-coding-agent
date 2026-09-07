# Demo

## Local Repair Run

Use a temporary fixture copy so repeated demos do not alter the checked-in task:

```bash
demo_repo="$(mktemp -d)"
cp tests/fixtures/sample_repo/*.py "$demo_repo/"
termagent app --repo "$demo_repo" --provider repair --approval-mode auto
```

Then enter:

```text
Fix the calculator add bug and run tests
```

For a single command version, run:

```bash
termagent run \
  --repo "$demo_repo" \
  --task "Fix the calculator add bug and run tests" \
  --approval-mode auto
```

Expected behavior:

- runs the verifier first
- discovers the failing function
- reads the source file
- previews the patch
- writes only after the plan is reviewed
- reruns the verifier
- prints the final diff summary

This demo uses deterministic repair heuristics. It is not a live-model result.

## Installed-Package Recording

`demo.cast` is an asciicast v2 recording of actual command output from the
deterministic JavaScript repair run in a fresh virtual environment. Replay with
`asciinema play docs/demo.cast` when asciinema is installed. Regenerate it with:

```bash
python -m pip wheel . --wheel-dir .termagent/release-wheels
python scripts/check_wheel.py --record docs/demo.cast
```

The check installs the wheel and its dependency offline from the wheel directory,
runs outside the source checkout, and independently verifies the changed file.
The recording captures the command and final output; a live tool-by-tool video
remains on the release checklist.

## Benchmark Run

```bash
termagent bench --repo-root .
```

Current checked-in baseline:

```text
8/8 tasks passed
bench/results/latest.json
bench/results/latest.md
```

## Live Provider Smoke

```bash
export OPENAI_API_KEY="your-api-key"
termagent live-smoke --repo-root . --max-cost-usd 0.05
```

The smoke command runs a tiny fixture task with the OpenAI-compatible provider and writes a sanitized summary to `docs/live-provider-demo.md`. Raw traces stay under ignored `.termagent/live-smoke`.

## Harbor-Shaped Export

```bash
termagent harbor-export --overwrite
```

This generates a local Harbor-shaped dataset under `bench/harbor-export`. The generated directory is ignored by git because it is reproducible from `bench/tasks`.

## Health Check

```bash
termagent doctor
```

This checks Python version, git, optional `rg`, optional Node.js, repository status, and live-provider key availability.
