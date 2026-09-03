# Security Policy

TermAgent is a local developer tool. It is designed to reduce risk from agent-generated actions, but it is not a complete OS sandbox.

## Supported Version

The `main` branch is the active development version.

## Reporting Security Issues

Open a private report if GitHub security advisories are enabled for the repository. Otherwise, open an issue with a minimal reproduction and avoid including secrets, tokens, private repository content, or full trace files that contain confidential data.

## Current Controls

- File tools resolve paths inside the configured repository root.
- Writes require patch previews and matching content hashes.
- Shell commands are executed as parsed argv, not through a shell.
- Destructive commands are blocked by default.
- Network commands are blocked unless explicitly enabled.
- Live model output is accepted only as structured tool calls.
- Observation context is bounded to reduce token waste and accidental data exposure.

See `docs/security-audit.md` for the current audit notes and limitations.
