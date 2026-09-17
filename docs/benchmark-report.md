# Benchmark Report

Latest checked-in runtime regression result for the deterministic `fixture` provider.

- Tasks: 8
- Passed: 8
- Pass rate: 100.0%
- Estimated model cost: $0.000000

| Task | Category | Language | Result | Steps | Provider | Cost |
| --- | --- | --- | --- | ---: | --- | ---: |
| `bugfix_calculator` | bugfix | python | pass | 7 | fixture | $0.000000 |
| `bugfix_checkout_pipeline` | multi-file bugfix | python | pass | 5 | fixture | $0.000000 |
| `bugfix_clamp_score` | bugfix | python | pass | 7 | fixture | $0.000000 |
| `bugfix_divide` | bugfix | python | pass | 7 | fixture | $0.000000 |
| `bugfix_email_normalization` | bugfix | python | pass | 8 | fixture | $0.000000 |
| `bugfix_javascript_total` | javascript bugfix | javascript | pass | 8 | fixture | $0.000000 |
| `bugfix_slugify` | bugfix | python | pass | 8 | fixture | $0.000000 |
| `bugfix_word_count` | bugfix | python | pass | 7 | fixture | $0.000000 |

The fixture provider contains transparent task-specific repair patterns. This result
checks orchestration, grading, tracing, and tool contracts; it does not measure model
quality or generalization to arbitrary repositories.
