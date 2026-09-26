#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
HARBOR="$ROOT/.venv/bin/harbor"
TERMAGENT="$ROOT/.venv/bin/termagent"
DATASET="$ROOT/.termagent/v1-diagnostic-registry/terminal-bench-2"
JOBS="$ROOT/.termagent/harbor-jobs"
WHEELS="$ROOT/.termagent/v1-diagnostic-wheel"
MANIFEST="$ROOT/bench/campaigns/v1-diagnostic.json"
REPORT="$ROOT/.termagent/v1-diagnostic-results.md"
SOURCE_COMMIT="489f4064e717486459e028b9bdbc1ef24c986071"
WHEEL_SHA256="79c3413bfe8b91cf58a3954ce9524668750c6d8a0caae77689cfeb36047f7546"
ARM="termagent"

if [[ $# -gt 0 ]]; then
  if [[ $# -ne 2 || "$1" != "--arm" ]]; then
    echo "Usage: $0 [--arm termagent|codex|all]" >&2
    exit 2
  fi
  ARM=$2
fi
if [[ "$ARM" != "termagent" && "$ARM" != "codex" && "$ARM" != "all" ]]; then
  echo "Unsupported campaign arm: $ARM" >&2
  exit 2
fi

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
git -C "$ROOT" merge-base --is-ancestor "$SOURCE_COMMIT" HEAD
test "$(shasum -a 256 "$WHEELS/terminal_coding_agent-0.1.0-py3-none-any.whl" | awk '{print $1}')" = "$WHEEL_SHA256"

run_termagent() {
  local task=$1
  local repo=$2
  local verifier=$3
  local job="v1diag-${task}-termagent-strict-1"
  if [[ -e "$JOBS/$job" ]]; then
    echo "Refusing to overwrite frozen trial: $JOBS/$job" >&2
    exit 1
  fi

  "$HARBOR" run -p "$DATASET/$task" \
    -a termagent.harbor_agent:TermAgentHarbor -m openai/gpt-5.6-luna \
    --ak "wheel_dir=$WHEELS" --ak "repo=$repo" --ak "test_command=$verifier" \
    --ak max_steps=40 --ak max_cost_usd=0.08 --ak max_output_tokens=4096 \
    --ak reasoning_effort=high --ak prompt_profile=benchmark \
    --ak controller_recovery=true --ak task_planning=true --ak strict_completion=true \
    --ak max_stagnation_events=2 --ak max_discovery_actions=6 \
    "${ENV_ARGS[@]}" \
    -k 1 -n 1 --max-retries 0 --yes --jobs-dir "$JOBS" --job-name "$job"
}

run_codex() {
  local task=$1
  local job="v1diag-${task}-codex-baseline-1"
  if [[ -e "$JOBS/$job" ]]; then
    echo "Refusing to overwrite frozen trial: $JOBS/$job" >&2
    exit 1
  fi

  "$HARBOR" run -p "$DATASET/$task" \
    -a codex -m openai/gpt-5.6-luna --ak version=0.153.4 \
    --ak reasoning_effort=high \
    "${ENV_ARGS[@]}" \
    -k 1 -n 1 --max-retries 0 --yes --jobs-dir "$JOBS" --job-name "$job"
}

run_task() {
  local task=$1
  local repo=$2
  local verifier=$3
  if [[ "$ARM" == "termagent" || "$ARM" == "all" ]]; then
    run_termagent "$task" "$repo" "$verifier"
  fi
  if [[ "$ARM" == "codex" || "$ARM" == "all" ]]; then
    run_codex "$task"
  fi
}

run_task fix-git /app/personal-site "git log --oneline --all -5"
run_task log-summary-date-ranges /app "test -s /app/summary.csv"
run_task modernize-scientific-stack /app "python /app/analyze_climate_modern.py"
run_task query-optimize /app "sqlite3 /app/oewn.sqlite .read /app/sol.sql"
run_task sanitize-git-repo /app/dclm "git status --short"

if [[ "$ARM" == "all" ]]; then
  "$TERMAGENT" campaign-report --manifest "$MANIFEST" --jobs-dir "$JOBS" --report "$REPORT"
  echo "V1 diagnostic campaign complete: $REPORT"
else
  echo "V1 diagnostic $ARM arm complete. Run the other arm before rendering the report."
fi
