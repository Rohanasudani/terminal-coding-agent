# Milestone 20: Terminal-Bench 2 Results

## Frozen Configuration

- Harbor: `0.22.0`
- Model: `openai/gpt-5.6-luna`
- TermAgent wheel: `7b87b7c68956d8cfb71f2c5b1a89487c75c281f29373e148af07484e56fda157`
- Codex: `0.153.4`
- Trials per task and arm: `1`

## Control Results

| Task | Oracle | No-op | Harbor Task Checksum |
| --- | ---: | ---: | --- |
| `cancel-async-tasks` | 1 | 0 | `accc19bf83c18b56ef638f2fba155cfefc1219e72cd3a59ab326748ae5c5c547` |
| `fix-code-vulnerability` | 1 | 0 | `468031620a5bc5a49dbd43cb739baea9ed77229c4520f2c0b9819a1dd6b0397a` |
| `cobol-modernization` | 1 | 0 | `2afb8c1a641542e2fb97d248e62fe1e80f6d6b0611529b613a2e3f865f6b3bf6` |

All oracle trials passed and all no-op trials failed without exceptions.

## Live Results

| Task | Arm | Reward | Error | Input Tokens | Output Tokens | Cost | Duration |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `cancel-async-tasks` | `codex-baseline` | 0 | no | 56036 | 3671 | $0.008497 | 440.6s |
| `cancel-async-tasks` | `termagent-planning-off` | 0 | no | 43052 | 7938 | $0.018136 | 179.7s |
| `cancel-async-tasks` | `termagent-planning-on` | 0 | no | 21098 | 3241 | $0.008110 | 99.7s |
| `cobol-modernization` | `codex-baseline` | 1 | no | 480080 | 13862 | $0.033489 | 435.7s |
| `cobol-modernization` | `termagent-planning-off` | unknown | yes | unknown | unknown | unknown | 445.6s |
| `cobol-modernization` | `termagent-planning-on` | unknown | yes | unknown | unknown | unknown | 563.7s |
| `fix-code-vulnerability` | `codex-baseline` | 1 | no | 231127 | 2006 | $0.015706 | 271.2s |
| `fix-code-vulnerability` | `termagent-planning-off` | 0 | no | 113627 | 4724 | $0.028395 | 119.7s |
| `fix-code-vulnerability` | `termagent-planning-on` | 0 | no | 116900 | 4641 | $0.028948 | 116.0s |

## Aggregate

| Arm | Passed | Errors | Known Cost |
| --- | ---: | ---: | ---: |
| `codex-baseline` | 2/3 | 0 | $0.057692 |
| `termagent-planning-off` | 0/3 | 1 | $0.046531 (partial) |
| `termagent-planning-on` | 0/3 | 1 | $0.037058 (partial) |

## Interpretation

Structured planning did not improve grader pass rate on this frozen subset. Both
TermAgent arms scored 0/3. Codex scored 2/3. The TermAgent COBOL trials ended
on provider transport failures before Harbor could grade them, so their usage and
cost remain unknown and their outcomes stay in the denominator as errors.

This three-task, one-trial campaign is evidence about this subset only. It is not a
Terminal-Bench leaderboard result or a claim that one agent is globally superior.

## Failure Analysis

- On `cancel-async-tasks`, both TermAgent arms created `run.py` and passed the
  configured syntax check. The planning arm stopped after repeated `git_diff`
  selections, while the non-planning arm exhausted 32 steps after `git_diff` failed
  because the task image does not contain Git. Harbor still assigned reward `0`.
- On `fix-code-vulnerability`, neither TermAgent arm produced a patch before the
  32-step limit. Planning reached the relevant header-normalization functions but did
  not convert inspection into a planned write; planning-off remained in discovery.
- On `cobol-modernization`, both TermAgent trials ended before a summary was written.
  One provider request timed out after 60 seconds and the other connection closed
  without a response. Harbor retained both as `RuntimeError` trials with unknown usage
  and cost. Codex completed the same task and earned reward `1`.

The next engineering work should address repository-independent final review, bounded
inspection-to-edit transitions, and graceful provider transport failures. Those changes
must be tested on development fixtures and a different held-out task set, not rerun on
this frozen subset as though it were still unseen.

## Post-Campaign Note

The Git-independent review and provider transport failure paths identified here were
implemented and regression-tested after this campaign. The original outcomes above
remain unchanged. See [milestone21-reliability.md](milestone21-reliability.md).
