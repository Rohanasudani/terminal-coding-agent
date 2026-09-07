# Milestone 17 Results

## Scope

Milestone 17 ran a same-model Harbor comparison and a controlled development
ablation. Every trial used `openai/gpt-5.6-luna`, Harbor `0.22.0`, retries disabled,
and task checksum
`51b12a97682d40277b0855c0ef8f3549508c6c1375c7b71152e7e7b0dab03974`.
Codex was pinned to `0.153.4`. TermAgent used high reasoning, a 4,096-token
per-response limit, and a `$0.05` estimated per-trial ceiling.

## Same-Model Baseline

| Agent | Grader pass | Agent completion | Mean agent time | Reported cost |
| --- | ---: | ---: | ---: | ---: |
| TermAgent | 3/3 | 2/3 | 20.149s | $0.008784 |
| Codex | 3/3 | not exposed | 9.733s | $0.011622 |

Both agents solved all three trials. On this task, TermAgent's reported model cost
was 24.4% lower and its mean agent time was 107.0% higher. One correct TermAgent
trial exhausted its 12-step limit by repeatedly invoking an already-passing verifier,
so independent grading passed while the agent's own completion state remained false.

This is a repeated result on one small development task, not evidence that either
agent is generally better. The agents expose different tools and context behavior,
and Codex does not expose internal completion or step metadata through this adapter.

## Controller-Recovery Ablation

The repeated-verifier failure motivated one general controller rule: after a current
successful verifier result, redirect another identical verifier request to `git_diff`.
The rule stays behind the existing `controller_recovery` switch. Both arms used the
same rebuilt wheel:
`7d520a33a3391341d6ef8cf892746c015c0e7275eaeb3e68dde27a9594f0d712`.

| Recovery | Grader pass | Agent completion | Mean steps | Mean agent time | Reported cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| Enabled | 3/3 | 3/3 | 7.33 | 16.980s | $0.007678 |
| Disabled | 3/3 | 1/3 | 10.33 | 20.137s | $0.010267 |

On the development task, recovery improved internal completion by 66.7 percentage
points, reduced mean steps by 29.0%, reduced mean agent time by 15.7%, and reduced
reported model cost by 25.2%. Grader pass remained 3/3 in both arms.

These results identify a useful mechanism but do not establish generalization. The
task was used to diagnose and design the rule, the sample size is three trials per
arm, and no confidence interval or significance claim is appropriate. The next
milestone must repeat the frozen-build ablation on tasks not used for this change.

## Spend

The smoke, baseline, and ablation jobs reported `$0.046915` in combined model cost.
This is adapter-reported cost and may differ from provider billing. Raw traces and
credentials remain under ignored `.termagent/`; the checked-in reports are sanitized.

Detailed tables: [matched smoke](matched-smoke-result.md),
[matched baseline](matched-baseline-result.md), and
[controller ablation](controller-recovery-ablation.md).
