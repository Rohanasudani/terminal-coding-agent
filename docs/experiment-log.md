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
- a pure-Python Harbor wheel runtime that no longer depends on task-image pip or venv
- strict completion review that checks declared diff paths and rejects smoke-only evidence

The next meaningful quality campaign should use a newly frozen public task set, a
compatible Python 3.11+ task image, the strict completion policy, and more than one trial
per arm. The historical zero-reward runs should remain available as the baseline.

## V1 Held-Out Diagnostic, TermAgent Arm

Five tasks were selected from public instructions and metadata without inspecting their
grader implementations. All had oracle reward 1, no-op reward 0, and no control
exceptions. The exact manifest is `bench/campaigns/v1-diagnostic.json`. This table is a
partial campaign: the same-model Codex arm has not run, so no comparative conclusion is
available.

| Task | Reward | Error | Input tokens | Output tokens | Known cost | Duration |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `fix-git` | 0 | no | 22,256 | 2,436 | $0.007374 | 71.6 s |
| `log-summary-date-ranges` | 0 | no | 89,343 | 18,018 | $0.039494 | 225.5 s |
| `modernize-scientific-stack` | 1 | no | 29,945 | 3,172 | $0.009795 | 73.1 s |
| `query-optimize` | unknown | yes | unknown | unknown | unknown | 13.8 s |
| `sanitize-git-repo` | 0 | no | 14,223 | 3,410 | $0.006937 | 70.5 s |
| **Aggregate** | **1/5** | **1** | **155,767** | **27,036** | **$0.063600 partial** | **454.5 s** |

The run exposed four distinct problems. A verifier that passed before any change pushed
the Git-recovery task toward completion too early. The no-`rg` search fallback treated
alternation as literal text, so credential discovery returned false negatives. The log
task inferred exhaustive counts from truncated evidence instead of executing a program
over every input. The SQL image lacked Python 3.11+, causing setup to fail before a model
call. The scientific modernization task passed its independent grader.

The resulting changes are general runtime work rather than fixture answers: baseline
passes no longer satisfy required-change completion, Git diffs anchor to the starting
commit, fallback search uses extended regular expressions, ignored-file search and file
listing are explicit bounded tools, search truncation is reported, completion checks use
stable criterion IDs, and Harbor can bootstrap Python through a supported package
manager. These changes require a newly frozen post-improvement set; the `1/5` result
remains unchanged.

## V1 Final Campaign, Revision 2

The first final-campaign freeze was rejected before paid trials. Its official
`build-cython-ext` oracle scored zero while the no-op scored zero, so that task could
not distinguish agent quality from benchmark failure. The frozen manifest remains at
`bench/campaigns/v1-final.json`. Revision 2 replaced only that task with
`gcode-to-text`, selected from public task material, and reran the complete control
matrix. All eight revision-2 oracles scored 1, all eight no-op controls scored 0, and
none raised an exception.

The revision-2 TermAgent arm used Harbor 0.22.0, `openai/gpt-5.6-luna`, source commit
`edc6f548a863e66dcaff85838f08305777c58f71`, TermAgent wheel
`5c52bee27586d21ea0422c68aefcd8e3c240038127286b85264a2de406d99136`,
strict completion, no retries, 50 steps, and a $0.10 estimated-cost ceiling per trial.
Tasks were selected from public instructions, metadata, and container manifests before
grader inspection. The exact manifest is `bench/campaigns/v1-final-r2.json`.

| Task | Reward | Error | Input tokens | Output tokens | Known cost | Duration |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gcode-to-text` | 0 | no | 103,988 | 6,921 | $0.029105 | 133.8 s |
| `custom-memory-heap-crash` | 1 | no | 56,792 | 7,834 | $0.020759 | 158.0 s |
| `distribution-search` | 1 | no | 54,051 | 12,300 | $0.025571 | 192.6 s |
| `git-leak-recovery` | 1 | no | 36,120 | 9,946 | $0.019159 | 204.6 s |
| `llm-inference-batching-scheduler` | 0 | no | 67,438 | 6,707 | $0.021536 | 130.3 s |
| `pytorch-model-cli` | 0 | no | 9,055 | 1,748 | $0.003909 | 177.5 s |
| `regex-log` | 1 | no | 25,188 | 5,530 | $0.011673 | 165.6 s |
| `schemelike-metacircular-eval` | 0 | no | 39,007 | 17,968 | $0.029363 | 289.1 s |
| **Aggregate** | **4/8** | **0** | **391,639** | **68,954** | **$0.161075** | **1,451.5 s** |

Python bootstrap was exercised successfully on `git-leak-recovery` and `regex-log`.
The passes establish independent evidence across C++ memory debugging, numerical
optimization, Git security recovery, and parsing. The failures remain in the
denominator and identify harder work in spatial/file interpretation, constrained
scheduling, cross-language model conversion, and language implementation.

The retained outputs make those failures more specific. The G-code trial wrote an
incorrect decoded value. The scheduler repeatedly violated the final-diff-before-review
ordering contract. The native model trial tried inline interpreter execution, which the
safety policy blocks, instead of writing and running a reviewable script. The Scheme
trial ended after repeated responses without a structured tool call. These are v1
limitations; none was patched or rerun against this held-out set.

This table is a partial campaign until the frozen same-model Codex arm is run. One
trial per task supports a broad engineering checkpoint, not a stable leaderboard score
or a claim that TermAgent matches another agent.
