# Live Provider Demo

This is a sanitized smoke-test summary for TermAgent's OpenAI-compatible provider.
It does not include raw prompts, raw model output, API keys, or private trace payloads.

- Checked at: 2026-09-05 21:39:54 UTC
- Status: failed
- Model: `gpt-5.6-luna`
- Completed: `False`
- Tests passed: `False`
- Steps: `1`
- Changed files: `none`
- Tokens: `543` input, `178` output
- Estimated model cost: `$0.000322`
- Note: This run reached OpenAI and produced a native `run_shell` tool call, but the model attempted a chained inspection command with shell control operators. The safety layer correctly blocked execution. Live mode now includes the configured verifier command in provider context and explicitly tells the model that `run_shell` accepts one argv-style command only. Raw trace is intentionally kept under ignored `.termagent/live-smoke` and is not committed.

Run it locally:

```bash
export OPENAI_API_KEY="your-api-key"
termagent live-smoke --repo-root . --max-cost-usd 0.05
```
