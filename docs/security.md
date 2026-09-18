# Security Model

TermAgent executes model-selected actions against source repositories. Its controls are
designed to make those actions explicit, bounded, and reviewable. TermAgent is not an operating-system sandbox. Running untrusted repositories still requires a container or
virtual machine with separate filesystem, process, and network isolation.

## Threat Model

The runtime assumes that model output, repository text, test output, and task
instructions can all be incorrect or adversarial. It protects against common accidental
or model-induced actions such as:

- reading or writing outside the selected repository
- applying contents that were not shown in a patch preview
- passing shell syntax through an implicit shell
- treating a mutating command as read-only because of its executable name
- silently retrying non-retryable provider errors and losing cost accounting
- declaring success from output text without a current passing verifier
- publishing secrets or raw provider traces by default

It does not defend the host from arbitrary code executed by a repository's test suite.

## Trust Boundaries

### Provider boundary

The live provider can request only registered tools with validated arguments. OpenAI
function definitions use strict object schemas, responses are parsed before execution,
and malformed calls become bounded observations rather than code.

### Repository boundary

File paths are resolved against the configured repository root. Absolute paths and
parent traversal that escape the root are rejected. Search and code-map operations skip
dependency, build, trace, and version-control directories.

### Command boundary

Commands are tokenized with `shlex` and executed with `shell=False`. Shell control
operators, command substitution, inline interpreter execution, destructive executables,
and network utilities are blocked or require explicit policy changes.

The classifier examines flags as well as command names. In-place `sed`, mutating
`find`, and Git output options cannot pass through the read-only path. Destructive
`find -delete` remains blocked in automatic approval mode.

### Evaluation boundary

The local benchmark grader starts from a pristine fixture and overlays only allowlisted
solution files. Changes to tests or benchmark configuration in the agent workspace do
not enter the grading copy. Harbor tasks use their own external verifier.

## Implemented Controls

- Repository-scoped path resolution for every file tool
- Patch previews with SHA-256 content hashes before writes
- Grouped write contracts for multi-file changes
- Python syntax validation during patch planning
- Structured tool-call validation before execution
- Parsed argv execution without `shell=True`
- Destructive, network, shell-control, and inline-interpreter policies
- Approval modes for commands that are mutating but not categorically blocked
- Verifier state invalidation after every write or shell action
- Required-change checks for tasks that must modify the workspace
- Bounded repeated verifier and discovery calls
- Maximum step, observation, output-token, and estimated-cost limits
- TLS certificate validation through `certifi`
- Responses API requests with `store: false`
- Explicit complete/incomplete provider usage metadata
- Bounded retries for retryable transport failures
- No retry for billing, authentication, or malformed-request failures
- JSONL traces and final summaries for later review

## Secrets And Artifacts

`OPENAI_API_KEY` is read from the environment. The repository contains no required
provider credential. Do not put keys in command arguments, task text, committed config,
or benchmark fixtures.

Raw live traces, generated wheels, Harbor jobs, and smoke reports belong under
`.termagent/`, which is ignored. These files can contain repository contents, provider
responses, local paths, and error details. Review and sanitize any artifact before
publishing it.

The model price table is an estimate for local controls and reporting. Provider pricing
can change, and an API response may exceed the remaining local budget before its usage
is known.

## Known Limitations

- Candidate tests run with the current process user's permissions.
- Command classification is policy enforcement, not process isolation.
- An allowed executable may still have an unsafe option that is not yet classified.
- `approval_mode=auto` permits policy-approved mutating commands.
- Network access is a command-level policy and not a host firewall.
- Prompt injection in repository text can influence the model even though it cannot
  bypass tool validation directly.
- The filesystem snapshot fallback reads eligible files and can be expensive on large
  repositories.
- JavaScript and TypeScript indexing uses a conservative scanner rather than a complete
  parser.
- The configured verifier can be weaker than the independent grader.
- Cost estimates may differ from provider billing.

For untrusted code, run TermAgent in a disposable container or VM with a read-only base
image, restricted credentials, explicit CPU and memory limits, disabled outbound
networking, and a narrowly mounted working directory.

## Safe Defaults

For normal local work, keep interactive approval enabled:

```bash
termagent run \
  --repo /path/to/repo \
  --task "Fix the failing tests" \
  --approval-mode suggest
```

Before enabling a live provider, inspect the repository and configuration, set a small
cost ceiling, and use a scoped API key where the provider supports it.

## Verification

Run the security-relevant unit and integration checks with the full suite:

```bash
ruff check .
pytest -q
python -m compileall -q src tests
termagent bench --repo-root .
```

Static review should continue to search for `shell=True`, dynamic evaluation,
unscoped filesystem access, leaked credentials, newly allowed network commands, and
command-specific mutation flags. A passing test suite is not a security proof.

## Reporting A Vulnerability

Use a private GitHub security advisory when available. Otherwise, provide a minimal
reproduction without API keys, private source code, or full trace files. The active
development version is the `main` branch.
