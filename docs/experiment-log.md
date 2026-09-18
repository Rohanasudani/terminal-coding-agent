# Experiment Log

This document collects the evaluation history that informed TermAgent's current
runtime. Historical results are preserved even when later changes address the failure.
Every failed or errored trial remains in the denominator, and unknown usage is never
reported as zero.

The bundled fixture suite and the external Harbor campaigns answer different
questions. Fixture results exercise the runtime against transparent scripted repairs.
Harbor results use a live model and independent task verifiers. The local fixture score
is not a Terminal-Bench leaderboard score, and neither are these small external
subsets.

## Evaluation Conventions

- Freeze task bytes, agent build, model, limits, and retry policy before a campaign.
- Verify external tasks with oracle and no-op controls.
- Keep unsuccessful runs and provider/setup errors in the published aggregate.
- Treat one trial per arm as failure analysis, not a stable estimate of performance.
- Record partial known cost when provider usage is incomplete.
- Use a newly frozen task set after controller changes instead of rewriting old results.

## Runtime Regression Baseline

The eight tasks under `bench/tasks` cover Python and JavaScript repair flows,
multi-file edits, planning contracts, verification, tracing, and final-diff handling.
The fixture provider passes all eight tasks. Because that provider contains documented
task-specific transformations, `8/8` is runtime regression evidence only.

## Matched Development Comparison

An early live campaign used `openai/gpt-5.6-luna` for TermAgent and the comparator.
The task set, provider limits, and comparison metadata were frozen before execution.

| Agent | Graded reward | Completion | Mean duration | Known cost |
| --- | ---: | ---: | ---: | ---: |
| TermAgent | 3/3 | 2/3 | 20.149 s | $0.008784 |
| Codex CLI | 3/3 | not comparable | 9.733 s | $0.011622 |

The equal reward did not establish controller equivalence: the tools, context
construction, and completion contracts differed. These tasks also became development
data after the run.

### Recovery ablation

Three repeated development trials compared the same controller with recovery enabled
and disabled. The wheel hash was
`7d520a64b9f19d25c56ed5d04a5f9ce71747e66f0eb35cd2bff40d4c9784d712`.

| Arm | Reward | Completion | Mean steps | Mean duration | Known cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Recovery enabled | 3/3 | 3/3 | 7.33 | 16.980 s | $0.007678 |
| Recovery disabled | 1/3 | 1/3 | 10.33 | 20.137 s | $0.010267 |

The combined smoke, matched baseline, and recovery experiments cost $0.046915 in
recorded model usage. This small result motivated bounded recovery, but it is too small
to claim a general effect.

## First External Probes

Two public external tasks were used to validate packaging and expose integration
failures before a frozen campaign.

### `html-js-filter`

Task checksum:
`f9e9e7276c4b3d6fcf937bc5ad8db4977600eca5902b1e15fbecf3a07413f1c7`.

| Agent | Reward | Duration | Known cost |
| --- | ---: | ---: | ---: |
| TermAgent | 0/1 | 416.158 s | $0.045120 |
| Codex CLI | 0/1 | 202.804 s | $0.036331 |

### `payments` recovery ablation

Task checksum:
`80b19f1f58cc2255e1263da22be52f1edc3aaf4c7a2f2625ace3b9c19abc5b9d`.
The TermAgent wheel hash was
`eaa6c227ab77a783f9d7b40d15fa6d0c0c67b2ff2ab83f6aff02b42a08586616`.

| Arm | Reward | Steps | Known cost |
| --- | ---: | ---: | ---: |
| Recovery enabled | 0/1 | 24 | $0.015889 |
| Recovery disabled | 0/1 | 24 | $0.016211 |

The four external live runs cost $0.113551 in recorded usage. They showed that passing
the agent-selected verifier was not enough when the independent grader checked broader
behavior.

## Planning Ablation

The eight fixture tasks were run with structured planning enabled and disabled.

| Arm | Reward | Mean steps | Cost |
| --- | ---: | ---: | ---: |
| Planning disabled | 8/8 | 7.125 | $0 |
| Planning enabled | 8/8 | 7.750 | $0 |

The wheel hash was
`29c9b2cd2faf9ea2396d8acf787d97c2d1428cc337692360457868e4d2aa42be`.
The result found no benefit on the scripted fixture suite. It was useful as a plumbing
check, not evidence about live-model generalization.

## Frozen External Campaign 1

This campaign used Harbor 0.22.0, `openai/gpt-5.6-luna`, Codex CLI 0.153.4, and
TermAgent wheel
`7b87bdd9b50c0f4ed49fb6cc9d83cb0f60903dce1500e86a11ed6bd30bc8a157`.
There was one trial per task and arm. The exact manifest is
`bench/campaigns/milestone20.json`.

| Task | Codex | TermAgent, planning off | TermAgent, planning on |
| --- | ---: | ---: | ---: |
| cancel-async-tasks | 0 | 0 | 0 |
| cobol-modernization | 1 | error | error |
| fix-code-vulnerability | 1 | 0 | 0 |
| **Aggregate** | **2/3** | **0/3, 1 error** | **0/3, 1 error** |

Known cost was $0.057692 for Codex, $0.046531 for the planning-off arm, and
$0.037058 for the planning-on arm. TermAgent cost is partial because the errored runs
did not return complete usage.

The failures exposed weak agent-selected syntax checks, missing-Git assumptions,
insufficient task discovery, and provider transport errors. They led to a startup
snapshot fallback, structured provider errors, bounded retries, and explicit incomplete
usage reporting.

## Bounded Discovery Experiment

After adding an evidence ledger and an inspection-to-edit transition, the fixture suite
was repeated.

| Arm | Reward | Mean steps | Mean discovery calls |
| --- | ---: | ---: | ---: |
| Transition disabled | 8/8 | 7.125 | not recorded |
| Transition enabled | 8/8 | 7.750 | 2.125 |

Both arms cost $0. The experiment confirmed the controller telemetry and preserved the
baseline, but it did not show a fixture-quality improvement.

## Frozen External Campaign 2

The follow-up campaign used Harbor 0.22.0, `openai/gpt-5.6-luna`, Codex CLI 0.153.4,
and TermAgent wheel
`3fdae22aa295150db68db592934e628915d3da5977effde3b07ec25ccf8e021e`.
The exact manifest is `bench/campaigns/milestone23.json`.

| Task | Codex | TermAgent, transition off | TermAgent, transition on |
| --- | ---: | ---: | ---: |
| kv-store-grpc | 1 | 0 | 0 |
| merger | 1 | 0 | 0 |
| polyglot-c-py | 1 | error | error |
| **Aggregate** | **3/3** | **0/3, 1 error** | **0/3, 1 error** |

Known cost was $0.030488 for Codex, $0.029758 for transition off, and $0.040728 for
transition on. TermAgent usage is partial because the setup errors returned no model
usage.

On `kv-store-grpc` and `merger`, TermAgent satisfied a visible verifier but failed the
independent grader. The transition-on arm made five and four discovery calls
respectively without improving reward. `polyglot-c-py` failed during environment setup
because the task image could not install the required Python 3.12+ wheel; the error was
retained rather than retried away.

## What The Results Changed

The unsuccessful campaigns drove concrete runtime work:

- Git-independent startup snapshots and final diffs
- required-change checks that reject empty solutions
- independent grading from pristine fixtures
- usage-completeness metadata for transport failures
- bounded provider retries with non-retryable billing and schema errors
- evidence and discovery limits before patch planning
- separate fixture and live provider implementations
- stricter command mutation classification

The next meaningful quality campaign should use a newly frozen public task set, a
compatible prebuilt wheel, stronger task-aware verification, and more than one trial
per arm. The historical zero-reward runs should remain available as the baseline.
