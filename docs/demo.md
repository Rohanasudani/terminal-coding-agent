# Demo

## Local Repair Run

For the most recruiter-friendly demo, start with the interactive app:

```bash
termagent app --repo tests/fixtures/sample_repo --approval-mode auto
```

Then enter:

```text
Fix the calculator add bug and run tests
```

For a single command version, run:

```bash
termagent run \
  --repo tests/fixtures/sample_repo \
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
