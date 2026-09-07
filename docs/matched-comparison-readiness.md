# Matched Comparison Readiness

## Status

The paid TermAgent-versus-Codex comparison is prepared but has not been run. The
current shell did not contain `OPENAI_API_KEY`, so no provider request or API charge
was made during this milestone.

## Frozen Controls

- Harbor: `0.22.0`
- Codex CLI observed locally: `0.153.4`
- Task: `bugfix_calculator`
- Task checksum: `51b12a97682d40277b0855c0ef8f3549508c6c1375c7b71152e7e7b0dab03974`
- TermAgent reasoning effort: `high`
- TermAgent output ceiling: `4096` tokens per response
- TermAgent per-trial estimated cost ceiling: `$0.05`
- Harbor retries: disabled
- Planned repetitions: `3` per agent

The output ceiling follows the OpenAI Responses API `max_output_tokens` contract.
Returned usage from malformed structured-output attempts is retained. A transport
failure without a provider usage body is marked as incomplete accounting rather than
silently reported as zero usage.

## Packaging Check

The rebuilt wheel had SHA-256
`413aa9664aaae511706e9e4e52a18c91b139d3ae3a97ed788cba1b69f6d1debd`.
A key-free Harbor trial using that wheel and the controls above completed with reward
`1.0`, no exception, and complete usage accounting. This validates packaging and
control propagation only; it is not live-model or competitor evidence.

## Execution Gate

Before running the paid comparison:

1. Export `OPENAI_API_KEY` in the current shell without committing it.
2. Set `MODEL_ID` to an exact model available to both adapters.
3. Confirm Codex's effective reasoning effort, output limit, and authentication route.
4. Approve a combined experiment budget. TermAgent's local ceiling cannot constrain
   Codex's spend, so the combined budget must be monitored separately.
5. Preserve all six trials, including failures and timeouts, then generate the report
   with `termagent compare-harbor`.

See [controlled-experiments.md](controlled-experiments.md) for the commands and
[PROJECT_SCOPE.md](../PROJECT_SCOPE.md) for the claim standard.

Sources: [OpenAI Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create),
[Codex non-interactive mode](https://developers.openai.com/codex/noninteractive).
