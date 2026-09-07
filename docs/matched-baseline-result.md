# Harbor Comparison

Task checksums, trial counts, and provider/model IDs match. Reasoning, context, tool access, and budget differences still require review before attributing causality.

Every recorded trial, including errors, contributes to the denominator.
Costs are adapter-reported and may be estimates. Missing costs remain unknown.

| Job | Agent | Model | Grader Passed | Errors | Agent Completed | Mean Steps | Mean Agent Time | Reported Cost | Usage Complete |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| milestone17-termagent-baseline | termagent | openai/gpt-5.6-luna | 3/3 | 0 | 2/3 | 8.67 | 20.149s | $0.008784 | yes |
| milestone17-codex-baseline | codex | openai/gpt-5.6-luna | 3/3 | 0 | unknown | unknown | 9.733s | $0.011622 | unknown |

## Agent Versions

- milestone17-termagent-baseline: wheel-sha256:413aa9664aaae511706e9e4e52a18c91b139d3ae3a97ed788cba1b69f6d1debd
- milestone17-codex-baseline: 0.153.4

## Task Checksums

- termagent/bugfix_calculator: `51b12a97682d40277b0855c0ef8f3549508c6c1375c7b71152e7e7b0dab03974` (3 trial(s) per job)
