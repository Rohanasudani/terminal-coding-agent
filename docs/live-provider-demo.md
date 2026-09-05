# Live Provider Demo

This is a sanitized smoke-test summary for TermAgent's OpenAI-compatible provider.
It does not include raw prompts, raw model output, API keys, or private trace payloads.

- Checked at: 2026-09-05 21:35:33 UTC
- Status: failed
- Model: `gpt-5.6-luna`
- Completed: `False`
- Tests passed: `False`
- Steps: `1`
- Changed files: `none`
- Tokens: `0` input, `0` output
- Estimated model cost: `$0.000000`
- Note: This run reached OpenAI after credits were added, but the provider was still asking the model to emit a tool call as JSON text. Live mode now uses native OpenAI function calls with strict per-tool argument schemas, keeping the old strict JSON parser only as a fallback. Raw trace is intentionally kept under ignored `.termagent/live-smoke` and is not committed.

Run it locally:

```bash
export OPENAI_API_KEY="your-api-key"
termagent live-smoke --repo-root . --max-cost-usd 0.05
```
