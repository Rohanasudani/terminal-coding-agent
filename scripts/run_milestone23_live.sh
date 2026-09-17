#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
HARBOR="$ROOT/.termagent/harbor-venv/bin/harbor"
TERMAGENT="$ROOT/.venv/bin/termagent"
DATASET="$ROOT/.termagent/milestone23-registry/terminal-bench-2"
JOBS="$ROOT/.termagent/harbor-jobs"
WHEELS="$ROOT/.termagent/milestone23-wheel"
MANIFEST="$ROOT/bench/campaigns/milestone23.json"
REPORT="$ROOT/docs/milestone23-results.md"

ENV_ARGS=()
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  if [[ -f "$ROOT/.env" ]] && grep -q '^OPENAI_API_KEY=.' "$ROOT/.env"; then
    ENV_ARGS=(--env-file "$ROOT/.env")
  else
    echo "Export OPENAI_API_KEY or add it to the gitignored $ROOT/.env file" >&2
    exit 1
  fi
fi

"$TERMAGENT" campaign-verify --manifest "$MANIFEST" --dataset-dir "$DATASET"
"$TERMAGENT" campaign-controls --manifest "$MANIFEST" --jobs-dir "$JOBS"
test "$("$HARBOR" --version)" = "0.22.0"
test "$(shasum -a 256 "$WHEELS/terminal_coding_agent-0.1.0-py3-none-any.whl" | awk '{print $1}')" = \
  "3fdae4d2a481d988609af670e404dbee82c6e9fbde65011fc2ea8912831d521e"

run_termagent() {
  local task=$1
  local verifier=$2
  local planning=$3
  local suffix="planning-off"
  if [[ "$planning" == "true" ]]; then
    suffix="planning-on"
  fi
  local job="milestone23-${task}-${suffix}"
  if [[ -e "$JOBS/$job" ]]; then
    echo "Refusing to overwrite existing frozen trial: $JOBS/$job" >&2
    exit 1
  fi

  "$HARBOR" run -p "$DATASET/$task" \
    -a termagent.harbor_agent:TermAgentHarbor -m openai/gpt-5.6-luna \
    --ak "wheel_dir=$WHEELS" --ak repo=/app --ak "test_command=$verifier" \
    --ak max_steps=32 --ak max_cost_usd=0.05 --ak max_output_tokens=4096 \
    --ak reasoning_effort=high --ak prompt_profile=benchmark \
    --ak controller_recovery=true --ak "task_planning=$planning" \
    --ak max_stagnation_events=2 --ak max_discovery_actions=6 \
    "${ENV_ARGS[@]}" \
    -k 1 -n 1 --max-retries 0 --yes --jobs-dir "$JOBS" --job-name "$job"
}

run_codex() {
  local task=$1
  local job="milestone23-${task}-codex"
  if [[ -e "$JOBS/$job" ]]; then
    echo "Refusing to overwrite existing frozen trial: $JOBS/$job" >&2
    exit 1
  fi

  "$HARBOR" run -p "$DATASET/$task" \
    -a codex -m openai/gpt-5.6-luna --ak version=0.153.4 \
    "${ENV_ARGS[@]}" \
    -k 1 -n 1 --max-retries 0 --yes --jobs-dir "$JOBS" --job-name "$job"
}

run_task() {
  local task=$1
  local verifier=$2
  run_termagent "$task" "$verifier" true
  run_termagent "$task" "$verifier" false
  run_codex "$task"
}

run_task polyglot-c-py "python3 /app/polyglot/main.py.c 10"
run_task kv-store-grpc "python3 -m compileall -q /app"
run_task multi-source-data-merger "python3 -m compileall -q /app"

"$TERMAGENT" campaign-report --manifest "$MANIFEST" --jobs-dir "$JOBS" --report "$REPORT"
echo "Milestone 23 live campaign complete: $REPORT"
