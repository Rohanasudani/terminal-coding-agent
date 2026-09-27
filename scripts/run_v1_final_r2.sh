#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
HARBOR="$ROOT/.venv/bin/harbor"
TERMAGENT="$ROOT/.venv/bin/termagent"
DATASET="$ROOT/.termagent/v1-final-registry/terminal-bench-2"
JOBS="$ROOT/.termagent/harbor-jobs"
WHEELS="$ROOT/.termagent/v1-postfix-wheel"
MANIFEST="$ROOT/bench/campaigns/v1-final-r2.json"
REPORT="$ROOT/.termagent/v1-final-r2-results.md"
SOURCE_COMMIT="edc6f548a863e66dcaff85838f08305777c58f71"
WHEEL_SHA256="5c52bee27586d21ea0422c68aefcd8e3c240038127286b85264a2de406d99136"
BUNDLE_SHA256="8cb4059071745f0ed287334c9b1717ca2d9f4908d3e61c1746e0c83278da71eb"
ARM="termagent"
CODEX_MAX_KNOWN_COST_USD="${CODEX_MAX_KNOWN_COST_USD:-1.00}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --arm)
      [[ $# -ge 2 ]] || { echo "--arm requires a value" >&2; exit 2; }
      ARM=$2
      shift 2
      ;;
    --codex-max-known-cost-usd)
      [[ $# -ge 2 ]] || { echo "--codex-max-known-cost-usd requires a value" >&2; exit 2; }
      CODEX_MAX_KNOWN_COST_USD=$2
      shift 2
      ;;
    *)
      echo "Usage: $0 [--arm termagent|codex|all] [--codex-max-known-cost-usd amount]" >&2
      exit 2
      ;;
  esac
done
if [[ "$ARM" != "termagent" && "$ARM" != "codex" && "$ARM" != "all" ]]; then
  echo "Unsupported campaign arm: $ARM" >&2
  exit 2
fi
"$ROOT/.venv/bin/python" -c \
  'import math,sys; value=float(sys.argv[1]); raise SystemExit(0 if math.isfinite(value) and value > 0 else 1)' \
  "$CODEX_MAX_KNOWN_COST_USD" || {
    echo "Codex known-cost threshold must be positive and finite" >&2
    exit 2
  }

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

completed_job() {
  "$ROOT/.venv/bin/python" - "$1" <<'PY'
import json
import sys
from pathlib import Path

job = Path(sys.argv[1])
try:
    parent = json.loads((job / "result.json").read_text(encoding="utf-8"))
    trials = list(job.glob("*/result.json"))
    valid = bool(parent.get("finished_at")) and parent.get("stats", {}).get("n_retries", 0) == 0
    valid = valid and len(trials) == 1
except (OSError, ValueError, TypeError):
    valid = False
raise SystemExit(0 if valid else 1)
PY
}

check_codex_budget() {
  "$ROOT/.venv/bin/python" - "$JOBS" "$CODEX_MAX_KNOWN_COST_USD" <<'PY'
import json
import sys
from pathlib import Path

jobs = Path(sys.argv[1])
limit = float(sys.argv[2])
known = 0.0
completed = 0
for job in sorted(jobs.glob("v1finalr2-*-codex-baseline-1")):
    trials = list(job.glob("*/result.json"))
    if len(trials) != 1:
        print(f"Codex job is incomplete or ambiguous: {job}", file=sys.stderr)
        raise SystemExit(3)
    trial = json.loads(trials[0].read_text(encoding="utf-8"))
    cost = (trial.get("agent_result") or {}).get("cost_usd")
    if cost is None:
        print(f"Codex usage is unknown for {job.name}; refusing another paid trial", file=sys.stderr)
        raise SystemExit(3)
    known += float(cost)
    completed += 1

print(f"Codex completed trials: {completed}; known cost: ${known:.6f}; stop threshold: ${limit:.2f}")
if known >= limit:
    print("Codex known-cost threshold reached; refusing another paid trial", file=sys.stderr)
    raise SystemExit(4)
PY
}

run_termagent() {
  local task=$1
  local repo=$2
  local verifier=$3
  local job="v1finalr2-${task}-termagent-strict-1"
  if [[ -e "$JOBS/$job" ]]; then
    if completed_job "$JOBS/$job"; then
      echo "Skipping completed frozen trial: $JOBS/$job"
      return
    fi
    echo "Refusing incomplete or ambiguous frozen trial: $JOBS/$job" >&2
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
  local job="v1finalr2-${task}-codex-baseline-1"
  if [[ -e "$JOBS/$job" ]]; then
    if completed_job "$JOBS/$job"; then
      echo "Skipping completed frozen trial: $JOBS/$job"
      return
    fi
    echo "Refusing incomplete or ambiguous frozen trial: $JOBS/$job" >&2
    exit 1
  fi
  check_codex_budget

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

run_task gcode-to-text /app "test -s /app/out.txt"
run_task custom-memory-heap-crash /app "valgrind --error-exitcode=1 --leak-check=full /app/release"
run_task distribution-search /app "test -s /app/dist.npy"
run_task git-leak-recovery /app "test -s /app/secret.txt"
run_task llm-inference-batching-scheduler /app "test -s /app/task_file/output_data/plan_b1.jsonl"
run_task pytorch-model-cli /app "/app/cli_tool /app/weights.json /app/image.png"
run_task regex-log /app "test -s /app/regex.txt"
run_task schemelike-metacircular-eval /app "test -s /app/eval.scm"

all_jobs_complete() {
  local task
  for task in \
    gcode-to-text \
    custom-memory-heap-crash \
    distribution-search \
    git-leak-recovery \
    llm-inference-batching-scheduler \
    pytorch-model-cli \
    regex-log \
    schemelike-metacircular-eval; do
    completed_job "$JOBS/v1finalr2-${task}-termagent-strict-1" || return 1
    completed_job "$JOBS/v1finalr2-${task}-codex-baseline-1" || return 1
  done
}

if [[ "$ARM" == "all" ]] || all_jobs_complete; then
  "$TERMAGENT" campaign-report --manifest "$MANIFEST" --jobs-dir "$JOBS" --report "$REPORT"
  echo "V1 final revision 2 campaign complete: $REPORT"
else
  echo "V1 final revision 2 $ARM arm complete. Run the other arm before rendering the report."
fi
