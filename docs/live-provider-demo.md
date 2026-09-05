# Live Provider Demo

This is a sanitized smoke-test summary for TermAgent's OpenAI-compatible provider.
It does not include raw prompts, raw model output, API keys, or private trace payloads.

- Checked at: 2026-09-05 22:16:33 UTC
- Status: failed
- Model: `gpt-5.6-luna`
- Completed: `False`
- Tests passed: `False`
- Steps: `8`
- Changed files: `none`
- Tokens: `10911` input, `741` output
- Estimated model cost: `$0.003072`
- Note: This run reached OpenAI, used a native `run_shell` tool call, and correctly ran the verifier, but the live model repeated the same failing test command instead of inspecting code. The agent now has a controller loop guard: repeated failed verifier commands are redirected into code-map, file-read, patch-preview, and write steps before tests can run again. Raw trace is intentionally kept under ignored `.termagent/live-smoke` and is not committed.

Run it locally:

```bash
export OPENAI_API_KEY="your-api-key"
termagent live-smoke --repo-root . --max-cost-usd 0.05
```
