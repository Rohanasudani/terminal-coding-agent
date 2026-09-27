# Security Policy

TermAgent is a local developer tool. It is designed to reduce risk from agent-generated actions, but it is not a complete OS sandbox.

## Supported Versions

Security fixes are applied to the latest `1.x` release and the `main` branch.

## Reporting Security Issues

Open a private report if GitHub security advisories are enabled for the repository. Otherwise, open an issue with a minimal reproduction and avoid including secrets, tokens, private repository content, or full trace files that contain confidential data.

## Current Controls

- File tools resolve paths inside the configured repository root.
- Common local credential files are blocked from file tools and direct shell references.
- Writes require patch previews and matching content hashes.
- Shell commands are executed as parsed argv, not through a shell.
- Destructive commands are blocked by default.
- Known file-mutating command options are blocked even in automatic approval mode.
- Network commands are blocked unless explicitly enabled.
- Live model output is accepted only as structured tool calls.
- Observation context is bounded to reduce token waste and accidental data exposure.
- Unpriced models are rejected before a run so cost ceilings cannot silently report zero.

See `docs/security.md` for the threat model, implemented controls, and limitations.
