# Milestone 23 Runbook

This runbook executes the frozen protocol in
[milestone23-protocol.md](milestone23-protocol.md). Do not change agent code, task
selection, model settings, or verifier commands after starting live trials.

## Completed Preflight

On 2026-09-16:

- all three task tree hashes matched the committed manifest
- the TermAgent wheel matched SHA-256
  `3fdae4d2a481d988609af670e404dbee82c6e9fbde65011fc2ea8912831d521e`
- Harbor reported version `0.22.0`
- oracle passed `3/3`
- no-op passed `0/3`
- all six controls completed without exceptions

Verify the retained controls at any time:

```bash
termagent campaign-controls \
  --manifest bench/campaigns/milestone23.json \
  --jobs-dir .termagent/harbor-jobs
```

To reproduce the key-free controls in a fresh checkout after downloading the dataset:

```bash
.termagent/harbor-venv/bin/harbor run \
  --config bench/campaigns/milestone23-controls.json --yes
```

## Live Campaign

The script requires the key through the process environment and never writes it to a
config, trace, command argument, or committed file. It stops if any target job directory
already exists, preventing accidental replacement of a frozen result.

```bash
cd /path/to/terminal-coding-agent
source .venv/bin/activate
export OPENAI_API_KEY="your-project-key"
./scripts/run_milestone23_live.sh
```

The script runs nine sequential trials: planning on, planning off, and Codex for each
of the three frozen tasks. Harbor retries are disabled. TermAgent's known maximum from
its per-trial ceilings is `$0.30`; Codex does not expose the same cap, so total campaign
cost cannot be guaranteed in advance. Stop before running if the account budget cannot
support all frozen trials.

Raw trajectories remain under ignored `.termagent/harbor-jobs`. After all trials pass
structural validation, the script writes the sanitized public report to
`docs/milestone23-results.md`.
