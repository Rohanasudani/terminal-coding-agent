# Matched Comparison Record

Milestone 17's paid development comparison was run after this preflight passed.
The frozen settings were:

- Harbor `0.22.0`
- Codex `0.153.4`
- model `openai/gpt-5.6-luna`
- high TermAgent reasoning effort
- 4,096 TermAgent output tokens per response
- `$0.05` TermAgent estimated per-trial ceiling
- Harbor retries disabled
- three trials per agent
- task checksum `51b12a97682d40277b0855c0ef8f3549508c6c1375c7b71152e7e7b0dab03974`

The preflight wheel passed isolated installation and a key-free Harbor container
trial before paid execution. Credentials and raw traces remain under ignored
`.termagent/` and are not included in the repository.

See [milestone17-results.md](milestone17-results.md) for outcomes and limitations.
External-task validation remains required before making a general performance claim.

Sources: [OpenAI Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create),
[Codex non-interactive mode](https://developers.openai.com/codex/noninteractive).
