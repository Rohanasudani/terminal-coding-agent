# Milestone 18 External Validation

## Method

Milestone 18 used public tasks resolved from Harbor's Terminal-Bench registry and
stored their concrete task checksums. Selection inspected only public instructions
and environment metadata. Agents did not receive reference solutions or hidden
verifier files. All model runs used `openai/gpt-5.6-luna` with Harbor retries disabled.

`terminal-bench/legacy-utility-triage` was compatibility-probed without model calls
and excluded because it requires VNC computer use rather than terminal coding.

## HTML JavaScript Filter

- Package cache revision: `f211960f1f7c66ace91c3d079db073ed0f841d458db4cad1f2f943cba6cc79f3`
- Task checksum: `f9e9f9f97cc4ed197e51c0f79218cba93a9dac01e736e1c1076d7ac91f41f1c7`
- Category: AppSec HTML sanitization

| Agent | Grader pass | Agent time | Reported cost |
| --- | ---: | ---: | ---: |
| TermAgent | 0/1 | 416.158s | $0.045120 |
| Codex 0.153.4 | 0/1 | 202.804s | $0.036331 |

TermAgent exhausted 24 steps without creating the requested file. Its controller
repeated inspection against an intentionally empty workspace. Codex created an
artifact but also failed the separate browser verifier. Neither result supports a
performance advantage claim.

This failure produced two general runtime changes: Harbor tasks require an actual
change before TermAgent can report completion, and the provider prompt now explains
that explicitly requested missing files may be planned after an empty code map. No
task-specific sanitizer logic or hidden verifier detail was added.

## Payments Pipeline

- Package cache revision: `ed92bf0b59203522407a2f628f186ccd11ee300a7a1ee04641f9510e46db1f14`
- Task checksum: `80b19b18f9138fdcefdc2c69d66c1b69c698679de75b7dc3e80fb771b3ec5b9d`
- Category: distributed-systems code repair
- Frozen TermAgent wheel: `eaa6a5e0d1a7527d9121397fb22c0c4a1897fae3d61a99e79663bb4a89816616`

| Controller recovery | Grader pass | Agent completion | Steps | Reported cost |
| --- | ---: | ---: | ---: | ---: |
| Enabled | 0/1 | 0/1 | 24 | $0.015889 |
| Disabled | 0/1 | 0/1 | 24 | $0.016211 |

Both arms exhausted the step limit without proposing a code change. The required-change
guard prevented a false success after the visible syntax smoke check passed, but the
Milestone 17 repeated-verifier recovery did not generalize into a solution for this
testless systems task. One trial per arm is enough to reject a success claim, not to
estimate a stable effect size.

## Conclusion

Milestone 18 successfully exercised two pinned external tasks and falsified the idea
that the development-task controller improvement was sufficient for broad tasks.
The next engineering priority is a bounded planning transition for testless and
empty-workspace tasks, followed by validation on a different frozen external task.

The four live external runs reported `$0.113551` combined model cost. Raw trajectories
and credentials remain ignored under `.termagent/`. Detailed generated tables are in
[html-js-filter](milestone18-html-js-filter.md) and
[payments ablation](milestone18-payments-ablation.md).

Sources: [Harbor Terminal-Bench tutorial](https://www.harborframework.com/docs/tutorials/running-terminal-bench),
[Harbor eval documentation](https://www.harborframework.com/docs/run-jobs/run-evals).
