# Live Provider Demo

This is a sanitized smoke-test summary for TermAgent's OpenAI-compatible provider.
It does not include raw prompts, raw model output, API keys, or private trace payloads.

- Checked at: 2026-09-05 22:28:36 UTC
- Status: passed
- Model: `gpt-5.6-luna`
- Completed: `True`
- Tests passed: `True`
- Steps: `7`
- Changed files: `calculator.py`
- Tokens: `7517` input, `905` output
- Estimated model cost: `$0.002589`
- Note: Raw trace is intentionally kept under ignored .termagent/live-smoke and is not committed.

Run it locally:

```bash
export OPENAI_API_KEY="your-api-key"
termagent live-smoke --repo-root . --max-cost-usd 0.05
```
