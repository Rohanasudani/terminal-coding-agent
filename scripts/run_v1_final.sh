#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
HARBOR="$ROOT/.venv/bin/harbor"
TERMAGENT="$ROOT/.venv/bin/termagent"
DATASET="$ROOT/.termagent/v1-final-registry/terminal-bench-2"
JOBS="$ROOT/.termagent/harbor-jobs"
WHEELS="$ROOT/.termagent/v1-postfix-wheel"
MANIFEST="$ROOT/bench/campaigns/v1-final.json"
REPORT="$ROOT/.termagent/v1-final-results.md"
SOURCE_COMMIT="edc6f548a863e66dcaff85838f08305777c58f71"
WHEEL_SHA256="5c52bee27586d21ea0422c68aefcd8e3c240038127286b85264a2de406d99136"
BUNDLE_SHA256="8cb4059071745f0ed287334c9b1717ca2d9f4908d3e61c1746e0c83278da71eb"
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
ACTUAL_BUNDLE_SHA256=$("$ROOT/.venv/bin/python" -c \
  'import sys; from pathlib import Path; from termagent.harbor_runtime import load_runtime_bundle; print(load_runtime_bundle(Path(sys.argv[1])).bundle_sha256)' \
  "$WHEELS")
test "$ACTUAL_BUNDLE_SHA256" = "$BUNDLE_SHA256"

run_termagent() {
  local task=$1
  local repo=$2
  local verifier=$3
  local job="v1final-${task}-termagent-strict-1"
  if [[ -e "$JOBS/$job" ]]; then
    echo "Refusing to overwrite frozen trial: $JOBS/$job" >&2
    exit 1
  fi

  "$HARBOR" run -p "$DATASET/$task" \
    -a termagent.harbor_agent:TermAgentHarbor -m openai/gpt-5.6-luna \
    --ak "wheel_dir=$WHEELS" --ak "repo=$repo" --ak "test_command=$verifier" \
    --ak max_steps=50 --ak max_cost_usd=0.10 --ak max_output_tokens=4096 \
    --ak reasoning_effort=high --ak prompt_profile=benchmark \
    --ak controller_recovery=true --ak task_planning=true --ak strict_completion=true \
    --ak bootstrap_python=true --ak max_stagnation_events=2 --ak max_discovery_actions=8 \
    "${ENV_ARGS[@]}" \
    -k 1 -n 1 --max-retries 0 --yes --jobs-dir "$JOBS" --job-name "$job"
}

run_codex() {
  local task=$1
  local job="v1final-${task}-codex-baseline-1"
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

run_task build-cython-ext /app "python -m pytest -q /app/pyknotid/tests --ignore=/app/pyknotid/tests/test_random_curves.py --ignore=/app/pyknotid/tests/test_catalogue.py"
run_task custom-memory-heap-crash /app "valgrind --error-exitcode=1 --leak-check=full /app/release"
run_task distribution-search /app "test -s /app/dist.npy"
run_task git-leak-recovery /app "test -s /app/secret.txt"
run_task llm-inference-batching-scheduler /app "test -s /app/task_file/output_data/plan_b1.jsonl"
run_task pytorch-model-cli /app "/app/cli_tool /app/weights.json /app/image.png"
run_task regex-log /app "test -s /app/regex.txt"
run_task schemelike-metacircular-eval /app "test -s /app/eval.scm"

if [[ "$ARM" == "all" ]]; then
  "$TERMAGENT" campaign-report --manifest "$MANIFEST" --jobs-dir "$JOBS" --report "$REPORT"
  echo "V1 final campaign complete: $REPORT"
else
  echo "V1 final $ARM arm complete. Run the other arm before rendering the report."
fi
