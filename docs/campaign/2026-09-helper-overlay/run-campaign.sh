#!/usr/bin/env bash
# The helper-overlay campaign (docs/campaign/2026-09-helper-overlay/manifest.md): the nine operator-key trials in the
# manifest's drawn order, then the gateway Opus trials the gateway guard admits. One instance at a time; any harness
# failure stops everything; exit status 0 only when every phase ended by its own rule.
set -uo pipefail
: "${RSI_EXAM_ROOT:?}"; : "${AUDIT_ROOT:?}"
WT=$HOME/rsi-campaign
ORDER="H3 S1 H6 H4 H1 H5 S2 S3 H2"            # drawn once: random.Random(20260909).shuffle, recorded in the manifest
FIRST_TWO_H="H3 H6"; FIRST_TWO_S="S1 S2"       # the first two trials of each arm in that order
LOCAL_CEILING=30.00; H_RESERVE=2.60; S_RESERVE_FIRST=6.00
GATEWAY_CEILING=100.00; O_RESERVE=11.00; O_MAX=2
PROGRAM=$WT/runbook/autoresearch-provenance.md; TEMPLATE=$WT/runbook/autoresearch-provenance.j2
MOUNT=$WT/runbook/mount-provenance.yaml; export ARB_PROVENANCE_PY=$WT/runbook/provenance.py
COST=$WT/runbook/cost.py
stop() { echo "$(date -u +%H:%M:%S) STOP: $*"; echo CAMPAIGN2-STOPPED; exit 1; }
cd "$RSI_EXAM_ROOT" || stop "cannot enter $RSI_EXAM_ROOT"
LOCK=$AUDIT_ROOT/campaign2.lock.d; mkdir "$LOCK" 2>/dev/null || stop "another campaign runner holds the lock ($LOCK)"; trap 'rmdir "$LOCK"' EXIT
[ "$(git rev-parse --short=12 HEAD)" = "bc36dadb405b" ] || stop "RSI-Exam checkout is not at bc36dadb405b"
[ -z "$(git -C "$WT" status --porcelain -- runbook)" ] || stop "runbook/ in the campaign worktree is not clean"
COMMIT=$(git -C "$WT" rev-parse --short HEAD)
for F in "$PROGRAM" "$TEMPLATE" "$MOUNT" "$ARB_PROVENANCE_PY" "$COST" .env.local .env.gateway; do [ -f "$F" ] || stop "missing $F"; done
# RESUME=1 continues an interrupted run: trials whose job directory already holds a finished result are skipped in
# place (never replaced); anything else that already exists still refuses.
for T in $ORDER O1 O2; do
  if [ -e "jobs/campaign-$T" ]; then
    if [ "${RESUME:-0}" = 1 ] && [ -f "$(ls jobs/campaign-$T/game2048_policy_search__*/result.json 2>/dev/null | head -n 1)" ]; then continue; fi
    stop "jobs/campaign-$T already exists; no trial is replaced"
  fi
done
done_already() { [ "${RESUME:-0}" = 1 ] && [ -f "$(ls jobs/campaign-$1/game2048_policy_search__*/result.json 2>/dev/null | head -n 1)" ]; }
echo "$(date -u +%H:%M:%S) campaign start: worktree commit $COMMIT, harbor $(harbor --version 2>/dev/null | head -n 1), RSI-Exam $(git rev-parse --short=12 HEAD)"
priced() {  # exact priced spend over the given job directories with one rate card; fails loud
  local rates=$1; shift; local out
  [ $# -gt 0 ] || { echo 0; return 0; }
  out=$(RATES=$rates python3 "$COST" "$@") || return 1
  echo "$out" | awk '/^TOTAL/ {print substr($2,2)}'
}
snapshots_of() {  # number of snapshot directories, or "unknown" when the versions directory is absent
  local d; d=$(ls -d "$RSI_EXAM_ROOT"/jobs/campaign-$1/game2048_policy_search__* 2>/dev/null | head -n 1)
  [ -n "$d" ] && [ -d "$d/artifacts/app/methods/versions" ] || { echo unknown; return; }
  find "$d/artifacts/app/methods/versions" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' '
}
arm_stopped() {  # the first two trials of the arm both finished with at most one snapshot (no pair)
  local a b t n; read -r a b <<< "$2"
  for t in $a $b; do [ -f "$(ls "$RSI_EXAM_ROOT"/jobs/campaign-$t/game2048_policy_search__*/result.json 2>/dev/null | head -n 1)" ] || return 1; done
  for t in $a $b; do n=$(snapshots_of "$t"); [ "$n" != unknown ] && [ "$n" -le 1 ] || return 1; done
  return 0
}
reached_api() {  # the trial ended normally or by the harness timeout, and its session log carries assistant usage
  python3 - "$1" <<'PYCHK'
import glob, json, sys
d = glob.glob(sys.argv[1] + "/game2048_policy_search__*")[0]
r = json.load(open(d + "/result.json"))
ex = (r.get("exception_info") or {}).get("exception_type")
ok = ex in (None, "AgentTimeoutError")
usage = any('"usage"' in line and '"assistant"' in line for f in glob.glob(d + "/agent/sessions/**/*.jsonl", recursive=True) for line in open(f, errors="ignore"))
sys.exit(0 if ok and usage else 1)
PYCHK
}
run_local() {
  local T=$1 MODEL RATES EFFORT=low MULT=0.008 SECONDS_BUDGET=340 RESERVE H_SPENT S_SPENT SPENT
  case $T in H*) MODEL=claude-haiku-4-5-20251001; RATES=haiku;; S*) MODEL=claude-sonnet-5; RATES=sonnet;; *) stop "unknown trial $T";; esac
  H_SPENT=$(priced haiku $(ls -d "$RSI_EXAM_ROOT"/jobs/campaign-H* 2>/dev/null)) || stop "pricing failed (haiku)"
  S_SPENT=$(priced sonnet $(ls -d "$RSI_EXAM_ROOT"/jobs/campaign-S* 2>/dev/null)) || stop "pricing failed (sonnet)"
  SPENT=$(python3 -c "print($H_SPENT + $S_SPENT)")
  if [ "${T:0:1}" = H ]; then RESERVE=$H_RESERVE; else
    local FIRST="$RSI_EXAM_ROOT/jobs/campaign-S1"
    if [ -d "$FIRST" ]; then RESERVE=$(python3 -c "import math; print(math.ceil($(priced sonnet "$FIRST") * 1.7 * 100) / 100)"); else RESERVE=$S_RESERVE_FIRST; fi
  fi
  echo "$(date -u +%H:%M:%S) $T: operator-key spend so far \$$SPENT (haiku \$$H_SPENT, sonnet \$$S_SPENT); reservation \$$RESERVE"
  python3 -c "import sys; sys.exit(0 if $SPENT + $RESERVE <= $LOCAL_CEILING else 1)" || { echo "$(date -u +%H:%M:%S) SKIP $T: operator-key ceiling (money rule)"; return 2; }
  if [ "${T:0:1}" = H ] && arm_stopped H "$FIRST_TWO_H"; then echo "$(date -u +%H:%M:%S) SKIP $T: arm H stopped, its first two trials recovered no pair"; return 2; fi
  if [ "${T:0:1}" = S ] && arm_stopped S "$FIRST_TWO_S"; then echo "$(date -u +%H:%M:%S) SKIP $T: arm S stopped, its first two trials recovered no pair"; return 2; fi
  echo "$(date -u +%H:%M:%S) $T start: model=$MODEL mult=$MULT effort=$EFFORT window=${SECONDS_BUDGET}s commit=$COMMIT"
  ( set -a; source .env.local; set +a; unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN GATEWAY_MODEL
    : "${ANTHROPIC_API_KEY:?.env.local must set ANTHROPIC_API_KEY}"
    export ARB_AGENT_TIMEOUT_SEC=$SECONDS_BUDGET ARB_OUTPUT_TOKEN_LIMIT=400000 ARB_PROGRAM=$PROGRAM ARB_BUDGET_PY=$PWD/infra/prompts/budget.py
    harbor run -p tasks/game2048_policy_search -a claude-code -m "$MODEL" -y -n 1 -k 1 --job-name "campaign-$T" \
      --agent-timeout-multiplier "$MULT" --ak prompt_template_path="$TEMPLATE" --extra-docker-compose "$MOUNT" \
      --ak disallowed_tools="WebSearch,WebFetch" --ak reasoning_effort="$EFFORT" --allow-agent-host anthropic.com --allow-agent-host '*.anthropic.com' \
      --ae ANTHROPIC_DEFAULT_OPUS_MODEL=$MODEL --ae ANTHROPIC_DEFAULT_SONNET_MODEL=$MODEL --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=$MODEL --ae CLAUDE_CODE_SUBAGENT_MODEL=$MODEL \
      >> "$AUDIT_ROOT/campaign-$T.log" 2>&1 )
  local RC=$?; echo "$(date -u +%H:%M:%S) $T harbor exit=$RC"
  [ "$RC" -eq 0 ] || stop "harbor exit $RC for $T"
  [ -d "jobs/campaign-$T" ] || stop "no job directory for $T"
  reached_api "jobs/campaign-$T" || stop "$T did not end normally or never reached the API"
  return 0
}
for T in $ORDER; do if done_already "$T"; then echo "$(date -u +%H:%M:%S) $T already finished; not replaced"; continue; fi; run_local "$T"; done
echo "$(date -u +%H:%M:%S) LOCAL-ARMS-DONE"
for N in $(seq 1 $O_MAX); do
  SPENT=$(priced opus "$RSI_EXAM_ROOT"/jobs/opus-cal-01 "$RSI_EXAM_ROOT"/jobs/opus-probe-20m "$RSI_EXAM_ROOT"/jobs/opus-batch-k5 $(ls -d "$RSI_EXAM_ROOT"/jobs/opus-overlay-* "$RSI_EXAM_ROOT"/jobs/campaign-O* 2>/dev/null)) || stop "pricing failed (gateway)"
  if done_already "O$N"; then echo "$(date -u +%H:%M:%S) O$N already finished; not replaced"; continue; fi
  echo "$(date -u +%H:%M:%S) O$N: gateway verified spend so far \$$SPENT; reservation \$$O_RESERVE"
  python3 -c "import sys; sys.exit(0 if $SPENT + $O_RESERVE <= $GATEWAY_CEILING else 1)" || { echo "$(date -u +%H:%M:%S) SKIP O$N: gateway ceiling (money rule)"; break; }
  echo "$(date -u +%H:%M:%S) O$N start: gateway anthropic/claude-opus-5 mult=0.030 effort=max window=1200s commit=$COMMIT"
  RSI_EXAM_ROOT=$RSI_EXAM_ROOT MOUNT_YAML=$MOUNT ARB_PROVENANCE_PY=$ARB_PROVENANCE_PY "$WT/runbook/run_gateway.sh" campaign-O$N 1200 0.030 1 max "$PROGRAM" "$TEMPLATE" >> "$AUDIT_ROOT/campaign-O$N.log" 2>&1
  RC=$?; echo "$(date -u +%H:%M:%S) O$N harbor exit=$RC"
  [ "$RC" -eq 0 ] || stop "harbor exit $RC for O$N"
  [ -d "jobs/campaign-O$N" ] || stop "no job directory for O$N"
  reached_api "jobs/campaign-O$N" || stop "O$N did not end normally or never reached the API"
done
echo "$(date -u +%H:%M:%S) CAMPAIGN2-DONE"
