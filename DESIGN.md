# Design

## Problem

A terminal coding agent has to do more than generate plausible source code. It must
locate relevant context, choose bounded actions, preview changes, verify behavior, and
stop safely when it cannot make progress. Those runtime decisions are difficult to
evaluate when the agent exposes only a final answer.

TermAgent makes those decisions observable. Every model action is a structured tool
call, every write has a preview contract, and every evaluation records enough metadata
to reproduce or challenge the result.

## Goals

- provide a useful local CLI for trusted repositories
- make model actions inspectable through structured tools and JSONL traces
- enforce repository, command, network, and cost boundaries before execution
- separate runtime regression fixtures from live-model quality evaluation
- compare controller changes through frozen, reproducible experiments
- retain failures and incomplete usage instead of silently dropping them

## Non-Goals

- replacing an operating-system sandbox
- claiming general coding performance from scripted fixture tasks
- claiming a public Terminal-Bench rank from small local campaigns
- embedding task answers in the live provider or controller
- automatically approving arbitrary network or destructive commands

## Design Principles

### Structured actions

Providers return a tool name and validated arguments. Model prose is never executed as
a shell script. The tool registry is the only route to repository reads, writes, shell
commands, code maps, and final diffs.

### Planned writes

`plan_patch` and `plan_patch_set` produce diffs and content hashes without changing the
workspace. A write succeeds only when its paths and contents match an approved plan.
This makes accidental or stale writes visible in the trace.

### Verification is state, not text

The runtime tracks verifier exit status after the latest mutation. Success words in
model output do not mark a task complete, and a previous passing check is invalidated by
later writes or shell commands.

### Bounded recovery

Repeated discovery and verifier calls consume explicit budgets. Planning-enabled runs
record expected outputs and acceptance checks, then require a transition from evidence
gathering to a model-authored patch. The controller can reject repetition but does not
construct source code on the model's behalf.

### Honest evaluation boundaries

The fixture provider contains transparent task-specific patterns and is isolated from
the live provider module. Its `8/8` result is a runtime regression check. Live quality
claims come only from provider-backed runs with frozen tasks and independent graders.

## Runtime Lifecycle

1. Resolve the target repository and load configuration.
2. Capture the initial workspace state for fallback diffing.
3. Ask the selected provider for one structured tool call.
4. Validate the call against planning, safety, and progress state.
5. Execute the tool and append a bounded observation to the trace.
6. Update cost, token, verifier, patch, and progress metadata.
7. Repeat until verified completion or a safety, cost, stagnation, transport, or step
   limit stops the run.
8. Produce a summary with changed files, checks run, residual risk, and final diff.

## Provider Boundary

`OpenAICompatibleProvider` owns API request construction, strict function schemas,
bounded retries, TLS validation, usage extraction, and observation compaction. The
fixture provider is a separate module used by offline tests and demos. A compatibility
alias preserves old experiment manifests without advertising the legacy name in the
CLI.

## Evaluation Policy

- freeze task bytes, model, agent build, limits, and retry policy before a campaign
- verify each external task with oracle and no-op controls
- keep development tasks separate from held-out campaign tasks
- compare one controller change at a time when possible
- include failures, exceptions, timeouts, and unknown usage in reports
- report exact versions, known cost, and limitations
- treat one-trial subsets as failure analysis, not population estimates
- never rewrite historical outcomes after a runtime improvement

Machine-readable campaign definitions are stored under `bench/campaigns`. Consolidated
outcomes and failure analysis are in [docs/experiment-log.md](docs/experiment-log.md).

## Current Tradeoffs

- repository snapshot fallback reads every eligible text file and will need an
  incremental index for large repositories
- JavaScript and TypeScript indexing uses a conservative scanner rather than a complete
  parser
- the command classifier reduces common risk but cannot provide process isolation
- model cost is estimated from recorded usage and can differ from provider billing
- a configured verifier may be weaker than an external task grader
- Harbor installation currently assumes a compatible Python toolchain in the task image

These limitations are tracked as engineering work, not hidden behind successful local
fixtures.
