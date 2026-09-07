# Harbor Comparison

Task checksums, trial counts, and provider/model IDs match. Reasoning, context, tool access, and budget differences still require review before attributing causality.

Every recorded trial, including errors, contributes to the denominator.
Costs are adapter-reported and may be estimates. Missing costs remain unknown.

| Job | Agent | Model | Grader Passed | Errors | Agent Completed | Mean Steps | Mean Agent Time | Reported Cost | Usage Complete |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| milestone17-recovery-on | termagent | openai/gpt-5.6-luna | 3/3 | 0 | 3/3 | 7.33 | 16.980s | $0.007678 | yes |
| milestone17-recovery-off | termagent | openai/gpt-5.6-luna | 3/3 | 0 | 1/3 | 10.33 | 20.137s | $0.010267 | yes |

## Agent Versions

- milestone17-recovery-on: wheel-sha256:7d520a33a3391341d6ef8cf892746c015c0e7275eaeb3e68dde27a9594f0d712
- milestone17-recovery-off: wheel-sha256:7d520a33a3391341d6ef8cf892746c015c0e7275eaeb3e68dde27a9594f0d712

## Task Checksums

- termagent/bugfix_calculator: `51b12a97682d40277b0855c0ef8f3549508c6c1375c7b71152e7e7b0dab03974` (3 trial(s) per job)
