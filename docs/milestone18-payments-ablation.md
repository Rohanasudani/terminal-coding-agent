# Harbor Comparison

Task checksums, trial counts, and provider/model IDs match. Reasoning, context, tool access, and budget differences still require review before attributing causality.

Every recorded trial, including errors, contributes to the denominator.
Costs are adapter-reported and may be estimates. Missing costs remain unknown.

| Job | Agent | Model | Grader Passed | Errors | Agent Completed | Mean Steps | Mean Agent Time | Reported Cost | Usage Complete |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| milestone18-payments-recovery-on | termagent | openai/gpt-5.6-luna | 0/1 | 0 | 0/1 | 24.00 | 46.744s | $0.015889 | yes |
| milestone18-payments-recovery-off | termagent | openai/gpt-5.6-luna | 0/1 | 0 | 0/1 | 24.00 | 51.110s | $0.016211 | yes |

## Agent Versions

- milestone18-payments-recovery-on: wheel-sha256:eaa6a5e0d1a7527d9121397fb22c0c4a1897fae3d61a99e79663bb4a89816616
- milestone18-payments-recovery-off: wheel-sha256:eaa6a5e0d1a7527d9121397fb22c0c4a1897fae3d61a99e79663bb4a89816616

## Task Checksums

- terminal-bench/payments-pipeline-fix: `80b19b18f9138fdcefdc2c69d66c1b69c698679de75b7dc3e80fb771b3ec5b9d` (1 trial(s) per job)
