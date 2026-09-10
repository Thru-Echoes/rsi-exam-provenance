#!/usr/bin/env bash
# One instrument-arm trial with a chosen CPU safety margin, for the pilot-8 probe. Outside the campaign's
# stages: it uses its own compose overlay (mount-instrument-margin.yaml) so no file the manifest pins changes.
#
#   RSI_EXAM_ROOT=... AUDIT_ROOT=... JOB=probe-margin-1 MODEL=claude-opus-5 EFFORT=max MULTIPLIER=0.045 \
#   WINDOW=1900 FRACTION=0.9 CEILING=20 RESERVATION=8 RATES=opus run-probe.sh
set -uo pipefail
: "${RSI_EXAM_ROOT:?}"; : "${AUDIT_ROOT:?}"; : "${JOB:?}"; : "${MODEL:?}"; : "${EFFORT:?}"; : "${MULTIPLIER:?}"; : "${WINDOW:?}"; : "${FRACTION:?}"
: "${CEILING:?}"; : "${RESERVATION:?}"; : "${RATES:?}"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); WT=$(cd "$HERE/../../.." && pwd)
stop() { echo "$(date -u +%H:%M:%S) STOP: $*"; exit 1; }
cd "$RSI_EXAM_ROOT" || stop "cannot enter $RSI_EXAM_ROOT"
[ "$(git rev-parse --short=12 HEAD)" = "bc36dadb405b" ] || stop "RSI-Exam checkout is not at bc36dadb405b"
[ -z "$(git -C "$WT" status --porcelain -- runbook gate)" ] || stop "runbook/ or gate/ in the worktree is not clean"
[ -f .env.local ] || stop "missing $RSI_EXAM_ROOT/.env.local"
[ -e "jobs/$JOB" ] && stop "jobs/$JOB already exists; no trial is replaced"
LOCK=$AUDIT_ROOT/probe.lock.d; mkdir -p "$AUDIT_ROOT/ab"; mkdir "$LOCK" 2>/dev/null || stop "another runner holds $LOCK"; trap 'rmdir "$LOCK"' EXIT
COMMIT=$(git -C "$WT" rev-parse --short HEAD)
COST=$WT/runbook/cost.py; TASK=$RSI_EXAM_ROOT/tasks/game2048_policy_search
GATE_DIR=$AUDIT_ROOT/ab/gate-$COMMIT; mkdir -p "$GATE_DIR"; cp "$WT"/gate/*.py "$GATE_DIR"/
MOUNT=$WT/runbook/mount-instrument-margin.yaml
grep -q "PROVENANCE_SAFETY_FRACTION" "$MOUNT" || stop "$MOUNT does not pass PROVENANCE_SAFETY_FRACTION"
# money: this probe's own jobs, priced at its rate card, plus this trial's reservation
SPENT=$(set -- $(ls -d "$RSI_EXAM_ROOT"/jobs/probe-margin* 2>/dev/null); [ $# -eq 0 ] && echo 0 || RATES=$RATES python3 "$COST" "$@" | awk '/^TOTAL/ {print substr($2,2)}') || stop "pricing failed"
python3 -c "import sys; sys.exit(0 if $SPENT + $RESERVATION <= $CEILING else 1)" || stop "money: \$$SPENT spent plus \$$RESERVATION reserved exceeds the \$$CEILING ceiling"
echo "$(date -u +%H:%M:%S) $JOB start: worktree $COMMIT, model $MODEL, effort $EFFORT, window ${WINDOW}s (multiplier $MULTIPLIER), safety fraction $FRACTION, spent \$$SPENT of \$$CEILING"
mkdir -p "$AUDIT_ROOT/ab/$JOB"; rm -f "$AUDIT_ROOT/ab/$JOB/profile.json"
python3 "$WT/runbook/make_profile.py" --task-dir "$TASK" --rollout-id "$JOB" --output "$AUDIT_ROOT/ab/$JOB/profile.json" \
  --floor 8 --max-seeds 16 --min-effect-fraction 0.025 --planning-rule estimate-aware >/dev/null || stop "profile for $JOB"
export ARB_PROVENANCE_PY=$WT/runbook/provenance.py ARB_GATE_DIR=$GATE_DIR ARB_PROFILE=$AUDIT_ROOT/ab/$JOB/profile.json
export PROVENANCE_SAFETY_FRACTION=$FRACTION
if [ "${DRY:-0}" = 1 ]; then echo "DRY: would run harbor for $JOB with PROVENANCE_SAFETY_FRACTION=$FRACTION"; exit 0; fi
( set -a; source .env.local; set +a; unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN GATEWAY_MODEL
  : "${ANTHROPIC_API_KEY:?.env.local must set ANTHROPIC_API_KEY}"
  export ARB_AGENT_TIMEOUT_SEC=$WINDOW ARB_OUTPUT_TOKEN_LIMIT=400000 ARB_PROGRAM=$WT/runbook/autoresearch-instrument.md ARB_BUDGET_PY=$PWD/infra/prompts/budget.py
  harbor run -p tasks/game2048_policy_search -a claude-code -m "$MODEL" -y -n 1 -k 1 --job-name "$JOB" \
    --agent-timeout-multiplier "$MULTIPLIER" --ak prompt_template_path="$WT/runbook/autoresearch-instrument.j2" --extra-docker-compose "$MOUNT" \
    --ak disallowed_tools="WebSearch,WebFetch" --ak reasoning_effort="$EFFORT" --allow-agent-host anthropic.com --allow-agent-host '*.anthropic.com' \
    --ae ANTHROPIC_DEFAULT_OPUS_MODEL=$MODEL --ae ANTHROPIC_DEFAULT_SONNET_MODEL=$MODEL --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=$MODEL --ae CLAUDE_CODE_SUBAGENT_MODEL=$MODEL \
    >> "$AUDIT_ROOT/ab/$JOB.log" 2>&1 )
RC=$?; echo "$(date -u +%H:%M:%S) $JOB harbor exit=$RC"
[ "$RC" -eq 0 ] || stop "harbor exit $RC for $JOB"
[ -d "jobs/$JOB" ] || stop "no job directory for $JOB"
# what the helper told the agent, and what the agent built
MARGIN=$(grep -h -o "safety margins [0-9.]* cpu s per game and [0-9.]* s per move" jobs/$JOB/*/agent/*.txt 2>/dev/null | head -1)
echo "$(date -u +%H:%M:%S) $JOB init stated: ${MARGIN:-NOT FOUND}"
L=$(ls jobs/$JOB/*/artifacts/app/methods/experiment_log.md 2>/dev/null | head -1)
[ -n "$L" ] && { printf "%s %s cpu s per game, by version: " "$(date -u +%H:%M:%S)" "$JOB"; grep -o "cpu s per game [0-9.]*" "$L" | awk '{printf "%s ", $5}'; echo; }
printf "%s %s priced: " "$(date -u +%H:%M:%S)" "$JOB"; RATES=$RATES python3 "$COST" "jobs/$JOB" | grep -E '^TOTAL'
echo "$(date -u +%H:%M:%S) PROBE-$JOB-DONE"
