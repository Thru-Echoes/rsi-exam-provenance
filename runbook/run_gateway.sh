#!/usr/bin/env bash
# One RSI-Exam rollout (or k repeats of it) through an Anthropic-compatible gateway.
#
#   RSI_EXAM_ROOT=/path/to/RSI-Exam runbook/run_gateway.sh <job-name> <agent-seconds> \
#       <agent-timeout-multiplier> <k-repeats> <reasoning-effort> [program.md] [template.j2]
#
# For a campaign with a spend ceiling pass k=1 and a distinct job name per trial, and price the
# finished job with runbook/cost.py before starting the next one: harbor starts every repeat of a
# single invocation before any of them can be priced.
#
# Reads $RSI_EXAM_ROOT/.env.gateway, which must set ANTHROPIC_BASE_URL and ANTHROPIC_AUTH_TOKEN.
# The task's agent timeout is 43200 s; the multiplier times that is when harbor stops the agent, so
# pick it a little above <agent-seconds>/43200. Reduced budgets mean nothing here is a score, and a
# run under a program other than the exam's own is a modified-program run.
set -euo pipefail

: "${RSI_EXAM_ROOT:?set RSI_EXAM_ROOT to the RSI-Exam checkout}"
cd "$RSI_EXAM_ROOT"

JOB_NAME="$1"; SECONDS_BUDGET="$2"; MULT="$3"; K="${4:-1}"; EFFORT="${5:-max}"
PROGRAM="${6:-$PWD/infra/prompts/autoresearch.md}"
TEMPLATE="${7:-$PWD/infra/prompts/autoresearch.j2}"
RUNBOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# A program that tells the agent to run /app/provenance.py needs the helper mounted; the runbook's compose
# overlay is RSI-Exam's mount.yaml plus that one read-only mount. MOUNT_YAML overrides the choice.
if [ -z "${MOUNT_YAML:-}" ] && grep -q '/app/provenance.py' "$PROGRAM"; then MOUNT_YAML="$RUNBOOK/mount-provenance.yaml"; fi
MOUNT_YAML="${MOUNT_YAML:-$PWD/infra/prompts/mount.yaml}"
export ARB_PROVENANCE_PY="${ARB_PROVENANCE_PY:-$RUNBOOK/provenance.py}"

[ -f .env.gateway ] || { echo "no $RSI_EXAM_ROOT/.env.gateway" >&2; exit 2; }
set -a; source .env.gateway; set +a
# Both of these outrank ANTHROPIC_AUTH_TOKEN in the claude-code adapter; a leftover key would win.
unset ANTHROPIC_API_KEY CLAUDE_CODE_OAUTH_TOKEN
: "${ANTHROPIC_BASE_URL:?.env.gateway must set ANTHROPIC_BASE_URL}"
: "${ANTHROPIC_AUTH_TOKEN:?.env.gateway must set ANTHROPIC_AUTH_TOKEN}"
[ -f "$PROGRAM" ] || { echo "program text not found: $PROGRAM" >&2; exit 2; }
[ -f "$TEMPLATE" ] || { echo "prompt template not found: $TEMPLATE" >&2; exit 2; }

MODEL="${GATEWAY_MODEL:-anthropic/claude-opus-5}"
HOST="${ANTHROPIC_BASE_URL#https://}"; HOST="${HOST%%/*}"
export ARB_AGENT_TIMEOUT_SEC="$SECONDS_BUDGET"
export ARB_OUTPUT_TOKEN_LIMIT="${ARB_OUTPUT_TOKEN_LIMIT:-400000}"
export ARB_PROGRAM="$PROGRAM"
export ARB_BUDGET_PY="$PWD/infra/prompts/budget.py"

echo "job=$JOB_NAME model=$MODEL budget=${SECONDS_BUDGET}s mult=$MULT k=$K effort=$EFFORT program=$(basename "$PROGRAM") mount=$(basename "$MOUNT_YAML") via $HOST"
set -x
# With ANTHROPIC_BASE_URL set the adapter pins its four model aliases itself.
harbor run -p tasks/game2048_policy_search -a claude-code -m "$MODEL" -y -n 1 -k "$K" \
  --job-name "$JOB_NAME" \
  --agent-timeout-multiplier "$MULT" \
  --ak prompt_template_path="$TEMPLATE" \
  --extra-docker-compose "$MOUNT_YAML" \
  --ak disallowed_tools="WebSearch,WebFetch" \
  --ak reasoning_effort="$EFFORT" \
  --allow-agent-host "$HOST"
