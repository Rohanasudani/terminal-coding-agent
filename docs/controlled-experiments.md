# Controlled Agent Experiments

The core objective is defined in [PROJECT_SCOPE.md](../PROJECT_SCOPE.md): a useful
agent plus reproducible competitor comparisons and measured general improvements.
The number of features or commits does not satisfy that objective.

## Pinned Integration

Harbor 0.22.0 is an optional dependency requiring Python 3.12+. Its actual package
interface was inspected and tested; online Harbor docs may describe newer commands.
The normal TermAgent CLI does not import Harbor.

```bash
python3 -m venv .termagent/harbor-venv
source .termagent/harbor-venv/bin/activate
python -m pip install -e ".[dev,harbor]"
python -m pip wheel . --wheel-dir .termagent/release-wheels
docker info
```

The adapter uploads built wheels and installs offline in a container virtual
environment. It exposes the task image's system Python packages to retain its
test dependencies. The image must provide Python, pip, venv, and visible test
dependencies. There is no host source checkout or Docker socket mounted by the adapter.

## Key-Free Integration Trial

```bash
termagent harbor-export --task-id bugfix_calculator --output-dir .termagent/harbor-smoke --manifest .termagent/harbor-smoke/manifest.json --overwrite
harbor run -p .termagent/harbor-smoke/bugfix_calculator \
  -a termagent.harbor_agent:TermAgentHarbor \
  --ak "wheel_dir=$PWD/.termagent/release-wheels" \
  --ak "test_command=python -m pytest -q" --ak provider=repair \
  --ak max_steps=12 -n 1 --jobs-dir .termagent/harbor-jobs
harbor run -p .termagent/harbor-smoke/bugfix_calculator -a nop \
  -n 1 --jobs-dir .termagent/harbor-jobs
```

The [measured report](harbor-integration-result.md) records reward 1 for deterministic
repair and reward 0 for no-op, with no model calls. This verifies integration only.
It is not an existing-agent comparison or Terminal-Bench score.

## Same-Model Comparison Templates

Before paid trials, select a model supported by both agents, pin the competitor
version, freeze the task revision and wheel, and allocate a combined budget.
The pinned Codex adapter defaults to high reasoning; this experiment explicitly sets
TermAgent to high reasoning too. Confirm both adapters' effective reasoning and output
limits in their recorded configurations before attributing differences to the agent
architecture. Model-ID matching alone is insufficient.

For the exported Python development task:

```bash
: "${MODEL_ID:?Set a model supported by both agents}"
: "${CODEX_VERSION:?Set an exact tested Codex CLI version}"
: "${OPENAI_API_KEY:?Set the API key locally}"

harbor run -p .termagent/harbor-smoke/bugfix_calculator \
  -a termagent.harbor_agent:TermAgentHarbor -m "openai/$MODEL_ID" \
  --ak "wheel_dir=$PWD/.termagent/release-wheels" \
  --ak "test_command=python -m pytest -q" --ak max_cost_usd=0.05 \
  --ak max_output_tokens=4096 --ak reasoning_effort=high \
  -k 3 -n 1 --jobs-dir .termagent/harbor-jobs --job-name termagent-live

harbor run -p .termagent/harbor-smoke/bugfix_calculator \
  -a codex -m "openai/$MODEL_ID" --ak "version=$CODEX_VERSION" \
  -k 3 -n 1 --jobs-dir .termagent/harbor-jobs --job-name codex-live

termagent compare-harbor .termagent/harbor-jobs/termagent-live \
  .termagent/harbor-jobs/codex-live
```

These paid templates have not been run. TermAgent uses high reasoning and a 4,096-token
per-response ceiling in this template. Confirm the pinned Codex adapter's effective
reasoning and output controls in its recorded configuration before treating the run as
matched. TermAgent's per-trial estimated cost limit
does not limit Codex or total Harbor spend. Failed structured-output retries now retain
their returned token usage; transport failures remain marked as incomplete accounting
because the provider returns no usage body. For external tasks, set their actual
container repository path with `--ak repo=...` and a visible verification command.
Never point the agent at hidden benchmark grader scripts.

## Ablations

Repeat a frozen TermAgent run with `--ak controller_recovery=false` to disable
diagnostic redirects. Leave model, tasks, prompts, and limits unchanged. The setting
is recorded in run configuration and context metadata. In a separate experiment,
compare prompt profiles with `--ak prompt_profile=benchmark`. Change one factor at
a time and keep failed trials. No improvement is claimed until measured.

`compare-harbor` rejects incomplete jobs, missing trials, mismatched task checksums
or trial counts, different/unidentified models, and retries needing separate review.
It retains errors in the denominator and missing costs as unknown. Use
`--allow-model-difference` only for an explicitly descriptive report, such as a
no-op control. Review reasoning, tools, context limits, and actual budgets separately.

## Required External Evidence

Freeze a published Terminal-Bench subset compatible with the adapter's task-image
requirements and run a competitor on those exact tasks. Preserve Harbor's task
checksums, agent versions, settings, and every result. Analyze failure traces,
implement a general technique, and evaluate it on tasks not used for tuning.
This comparison-and-improvement cycle is required before showcase submission.

Sources: [Harbor agents](https://www.harborframework.com/docs/agents),
[Harbor task structure](https://www.harborframework.com/docs/tasks),
[Codex non-interactive execution](https://developers.openai.com/codex/noninteractive),
[OpenAI Responses API](https://developers.openai.com/api/reference/cli/resources/responses/methods/create).
