# Live Provider Demo

This is a sanitized smoke-test summary for TermAgent's OpenAI-compatible provider.
It does not include raw prompts, raw model output, API keys, or private trace payloads.

- Checked at: pending rerun after local TLS fix
- Status: pending
- Model: `gpt-5.6-luna`
- Completed: `false`
- Tests passed: `false`
- Steps: `0`
- Changed files: `none`
- Tokens: `0` input, `0` output
- Estimated model cost: `$0.000000`
- Note: A local run initially failed before spending tokens because Python could not verify the TLS certificate chain. The provider now uses `certifi` for HTTPS certificate validation; rerun the command below from a shell where `OPENAI_API_KEY` is set.

Run it locally:

```bash
export OPENAI_API_KEY="your-api-key"
termagent live-smoke --repo-root . --max-cost-usd 0.05
```
