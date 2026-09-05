# Live Provider Demo

This is a sanitized smoke-test summary for TermAgent's OpenAI-compatible provider.
It does not include raw prompts, raw model output, API keys, or private trace payloads.

- Checked at: 2026-09-05 22:21:50 UTC
- Status: failed
- Model: `gpt-5.6-luna`
- Completed: `False`
- Tests passed: `False`
- Steps: `8`
- Changed files: `none`
- Tokens: `8776` input, `861` output
- Estimated model cost: `$0.002789`
- Note: This run reached OpenAI, inspected the repository, and produced the correct patch preview, but the live smoke ended at the step limit before writing the planned patch and rerunning tests. The smoke test now allows 12 steps, remembers provider-created patch plans for controller follow-through, and redirects bad read paths back through search/code-map recovery. Raw trace is intentionally kept under ignored `.termagent/live-smoke` and is not committed.

Run it locally:

```bash
export OPENAI_API_KEY="your-api-key"
termagent live-smoke --repo-root . --max-cost-usd 0.05
```
