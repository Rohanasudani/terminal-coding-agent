# Live Provider Demo

This is a sanitized smoke-test summary for TermAgent's OpenAI-compatible provider.
It does not include raw prompts, raw model output, API keys, or private trace payloads.

- Checked at: 2026-09-05 21:20:03 UTC
- Status: failed before token spend; fixed in code
- Model: `gpt-5.6-luna`
- Completed: `False`
- Tests passed: `False`
- Steps: `1`
- Changed files: `none`
- Tokens: `0` input, `0` output
- Estimated model cost: `$0.000000`
- Note: This run reached OpenAI and failed because the nested tool `arguments` schema was not strict enough for Structured Outputs. The provider now sets `additionalProperties: false` on every object in the response schema, represents optional tool arguments as nullable fields, and strips nullable placeholders before tool validation/execution. Raw trace is intentionally kept under ignored `.termagent/live-smoke` and is not committed.

Run it locally:

```bash
export OPENAI_API_KEY="your-api-key"
termagent live-smoke --repo-root . --max-cost-usd 0.05
```
