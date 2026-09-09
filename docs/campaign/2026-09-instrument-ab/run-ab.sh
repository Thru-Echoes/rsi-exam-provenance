#!/usr/bin/env bash
# The instrument A/B (manifest.md beside this file): one stage per invocation, its trials in the order the manifest
# drew, one at a time, under the stage's money rule, the mechanism rule and the harness rule. Exit 0 only when every
# trial of the stage ended by its own rule. DRY=1 prints what would run and starts nothing.
#
#   RSI_EXAM_ROOT=<RSI-Exam checkout> AUDIT_ROOT=<dir under $HOME> STAGE=haiku|sonnet|opus run-ab.sh
#
# Per trial: arm H runs runbook/autoresearch-provenance.md with the helper mounted; arm I runs
# runbook/autoresearch-instrument.md with the helper, a clean copy of gate/*.py and a task profile written for that
# trial (floor, cap, planning rule and minimum-effect fraction from stages.json; a fresh replication key) mounted
# read-only. The profile stays under the audit root; it is committed after the stage by post-ab.sh.
set -uo pipefail
: "${RSI_EXAM_ROOT:?}"; : "${AUDIT_ROOT:?}"; : "${STAGE:?haiku, sonnet or opus}"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); WT=$(cd "$HERE/../../.." && pwd)
STAGES=$HERE/stages.json
stop() { echo "$(date -u +%H:%M:%S) STOP: $*"; echo "AB-$STAGE-STOPPED"; exit 1; }
field() { python3 - "$STAGES" "$STAGE" "$1" <<'PY'
import json, sys
value = json.load(open(sys.argv[1]))[sys.argv[2]][sys.argv[3]]
if value is None:
    raise SystemExit(f"stages.json: {sys.argv[2]}.{sys.argv[3]} is null; fill it in from the pilot before this stage runs")
print(" ".join(value) if isinstance(value, list) else value)
PY
}
for NAME in model rates effort multiplier window key ceiling reservation floor cap planning_rule min_effect_fraction order; do
  VALUE=$(field "$NAME") || stop "stages.json is incomplete for $STAGE ($NAME)"
  declare "$(echo "$NAME" | tr '[:lower:]' '[:upper:]')=$VALUE"
done
CAMPAIGN_CEILING=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['_campaign']['ceiling'])" "$STAGES") || stop "stages.json lacks _campaign.ceiling"
CUTOFF_UTC=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['_campaign']['cutoff_utc'])" "$STAGES") || stop "stages.json lacks _campaign.cutoff_utc"
cd "$RSI_EXAM_ROOT" || stop "cannot enter $RSI_EXAM_ROOT"
LOCK=$AUDIT_ROOT/ab-$STAGE.lock.d; mkdir -p "$AUDIT_ROOT/ab"; mkdir "$LOCK" 2>/dev/null || stop "another runner holds $LOCK"; trap 'rmdir "$LOCK"' EXIT
[ "$(git rev-parse --short=12 HEAD)" = "bc36dadb405b" ] || stop "RSI-Exam checkout is not at bc36dadb405b"
if [ "${DRY:-0}" != 1 ]; then [ -z "$(git -C "$WT" status --porcelain -- runbook gate)" ] || stop "runbook/ or gate/ in the worktree is not clean"; fi
COMMIT=$(git -C "$WT" rev-parse --short HEAD)
GATE_DIR=$AUDIT_ROOT/ab/gate-$COMMIT; mkdir -p "$GATE_DIR"; cp "$WT"/gate/*.py "$GATE_DIR"/
PROGRAM_H=$WT/runbook/autoresearch-provenance.md; TEMPLATE_H=$WT/runbook/autoresearch-provenance.j2; MOUNT_H=$WT/runbook/mount-provenance.yaml
PROGRAM_I=$WT/runbook/autoresearch-instrument.md; TEMPLATE_I=$WT/runbook/autoresearch-instrument.j2; MOUNT_I=$WT/runbook/mount-instrument.yaml
export ARB_PROVENANCE_PY=$WT/runbook/provenance.py
COST=$WT/runbook/cost.py; TASK=$RSI_EXAM_ROOT/tasks/game2048_policy_search
for F in "$PROGRAM_H" "$TEMPLATE_H" "$MOUNT_H" "$PROGRAM_I" "$TEMPLATE_I" "$MOUNT_I" "$ARB_PROVENANCE_PY" "$COST" "$GATE_DIR/decide.py" "$GATE_DIR/evaluate_suite.py"; do [ -f "$F" ] || stop "missing $F"; done
# The manifest's digests, when the manifest exists (the pilots run before it): every file it pins must be what runs.
if [ -f "$HERE/manifest-digests.txt" ]; then (cd "$WT" && shasum -a 256 -c "$HERE/manifest-digests.txt" --status) || stop "a file the manifest pins differs from what would run (manifest-digests.txt)"; fi
case $KEY in
  operator) [ -f .env.local ] || stop "missing $RSI_EXAM_ROOT/.env.local";;
  gateway) [ -f .env.gateway ] || stop "missing $RSI_EXAM_ROOT/.env.gateway";;
  *) stop "unknown key $KEY";;
esac
for T in $ORDER; do
  if [ -e "jobs/ab-$STAGE-$T" ]; then
    if [ "${RESUME:-0}" = 1 ] && [ -f "$(ls jobs/ab-$STAGE-$T/game2048_policy_search__*/result.json 2>/dev/null | head -n 1)" ]; then continue; fi
    stop "jobs/ab-$STAGE-$T already exists; no trial is replaced"
  fi
done
RECORDS=$AUDIT_ROOT/ab/$STAGE-records.txt; touch "$RECORDS"
echo "$(date -u +%H:%M:%S) stage $STAGE start: worktree commit $COMMIT, harbor $(harbor --version 2>/dev/null | head -n 1), model $MODEL, window ${WINDOW}s (multiplier $MULTIPLIER), key $KEY, order $ORDER"
priced() { local out; [ $# -gt 0 ] || { echo 0; return 0; }; out=$(RATES=$RATES python3 "$COST" "$@") || return 1; echo "$out" | awk '/^TOTAL/ {print substr($2,2)}'; }
campaign_spend() {  # every ab-* job on this machine, each stage priced at its own rate card; fails loud
  python3 - "$STAGES" "$RSI_EXAM_ROOT/jobs" "$COST" <<'PY'
import glob, json, os, subprocess, sys
stages, jobs, cost = json.load(open(sys.argv[1])), sys.argv[2], sys.argv[3]
total = 0.0
for name, cfg in stages.items():
    if name.startswith("_"):
        continue
    dirs = sorted(glob.glob(os.path.join(jobs, f"ab-{name}-*")))
    if not dirs:
        continue
    out = subprocess.run([sys.executable, cost, *dirs], capture_output=True, text=True, env={**os.environ, "RATES": cfg["rates"]})
    if out.returncode != 0:
        raise SystemExit(f"pricing failed for stage {name}: {out.stderr.strip()[:200]}")
    total += float([l for l in out.stdout.splitlines() if l.startswith("TOTAL")][-1].split("$")[1])
print(f"{total:.4f}")
PY
}
gate_blocked() {  # the instrument trial ended with the gate blocked (a runner refusal during a confirmation)
  python3 - "$1" <<'PY'
import glob, json, sys
paths = glob.glob(sys.argv[1] + "/game2048_policy_search__*/artifacts/app/methods/.provenance/state.json")
state = json.load(open(paths[0])) if paths else {}
sys.exit(0 if state.get("gate_blocked") else 1)
PY
}
done_already() { [ "${RESUME:-0}" = 1 ] && [ -f "$(ls jobs/ab-$STAGE-$1/game2048_policy_search__*/result.json 2>/dev/null | head -n 1)" ]; }
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
record_verified() {  # builds the trial's record into the audit root; 0 when it builds and verifies
  local J ID; J=$(ls -d "jobs/ab-$STAGE-$1"/game2048_policy_search__* | head -n 1); ID="ab-$STAGE-$1-$(basename "$J" | tail -c 8)"
  mkdir -p "$AUDIT_ROOT/ab/$ID"; rm -f "$AUDIT_ROOT/ab/$ID/capsule.json"
  python3 "$WT/profile/build_capsule.py" --job-dir "$J" --task-dir "$TASK" --release "0.1@bc36dadb405b" --capsule-id "$ID" \
    --model "$MODEL" --harness claude-code --output "$AUDIT_ROOT/ab/$ID/capsule.json" >/dev/null 2>&1 || return 1
  python3 "$WT/profile/verify_capsule.py" "$AUDIT_ROOT/ab/$ID/capsule.json" --artifact-root "$J" | head -n 1 | grep -q 'integrity=pass'
}
mechanism_stopped() {  # the first two instrument trials of the stage both ended without a verified record
  [ "$(grep -c . "$RECORDS")" -ge 2 ] && [ "$(head -n 2 "$RECORDS" | grep -c ' fail$')" -eq 2 ]
}
admit_block() {  # the rules, judged once per block before its first trial: every trial of the block is reserved, or none starts
  local BLOCK=$1 SPENT CAMPAIGN NEED TRIALS NOW
  NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  if [ "$NOW" \> "$CUTOFF_UTC" ]; then RULE="calendar: no block starts after $CUTOFF_UTC"; echo "$(date -u +%H:%M:%S) SKIP block $BLOCK and the rest of the stage: $RULE"; return 2; fi
  TRIALS=$(echo "$ORDER" | tr ' ' '\n' | grep -c "^$BLOCK-")
  SPENT=$(priced $(ls -d "$RSI_EXAM_ROOT"/jobs/ab-$STAGE-* 2>/dev/null)) || stop "pricing failed ($RATES)"
  CAMPAIGN=$(campaign_spend) || stop "campaign pricing failed"
  NEED=$(python3 -c "print($TRIALS * $RESERVATION)")
  echo "$(date -u +%H:%M:%S) block $BLOCK: stage spend so far \$$SPENT (admission threshold \$$CEILING); campaign spend \$$CAMPAIGN (threshold \$$CAMPAIGN_CEILING); reservation for the block's $TRIALS trial(s) \$$NEED"
  python3 -c "import sys; sys.exit(0 if $SPENT + $NEED <= $CEILING else 1)" || { RULE="money: the stage's ceiling"; echo "$(date -u +%H:%M:%S) SKIP block $BLOCK and the rest of the stage: $RULE"; return 2; }
  python3 -c "import sys; sys.exit(0 if $CAMPAIGN + $NEED <= $CAMPAIGN_CEILING else 1)" || { RULE="money: the campaign's ceiling"; echo "$(date -u +%H:%M:%S) SKIP block $BLOCK and the rest of the stage: $RULE"; return 2; }
  if mechanism_stopped; then RULE="mechanism: the first two instrument trials left no verified record"; echo "$(date -u +%H:%M:%S) SKIP block $BLOCK and the rest of the stage: $RULE"; return 2; fi
  if [ -n "$BLOCKED" ]; then RULE="blocked gate: the runner refused a policy during a confirmation in $BLOCKED"; echo "$(date -u +%H:%M:%S) SKIP block $BLOCK and the rest of the stage: $RULE"; return 2; fi
  return 0
}
run_trial() {
  local T=$1 ARM=${1##*-} JOB=ab-$STAGE-$1 PROGRAM TEMPLATE MOUNT
  if [ "$ARM" = I ]; then
    PROGRAM=$PROGRAM_I; TEMPLATE=$TEMPLATE_I; MOUNT=$MOUNT_I
    mkdir -p "$AUDIT_ROOT/ab/$JOB"; rm -f "$AUDIT_ROOT/ab/$JOB/profile.json"
    python3 "$WT/runbook/make_profile.py" --task-dir "$TASK" --rollout-id "$JOB" --output "$AUDIT_ROOT/ab/$JOB/profile.json" \
      --floor "$FLOOR" --max-seeds "$CAP" --min-effect-fraction "$MIN_EFFECT_FRACTION" --planning-rule "$PLANNING_RULE" >/dev/null || stop "profile for $JOB"
    export ARB_GATE_DIR=$GATE_DIR ARB_PROFILE=$AUDIT_ROOT/ab/$JOB/profile.json
  else
    PROGRAM=$PROGRAM_H; TEMPLATE=$TEMPLATE_H; MOUNT=$MOUNT_H; unset ARB_GATE_DIR ARB_PROFILE
  fi
  echo "$(date -u +%H:%M:%S) $JOB start: arm $ARM program=$(basename "$PROGRAM") mount=$(basename "$MOUNT") model=$MODEL mult=$MULTIPLIER effort=$EFFORT window=${WINDOW}s key=$KEY commit=$COMMIT"
  if [ "${DRY:-0}" = 1 ]; then echo "DRY: would run harbor for $JOB (arm $ARM)$([ "$ARM" = I ] && echo ", profile $ARB_PROFILE, gate $ARB_GATE_DIR")"; return 0; fi
  if [ "$KEY" = operator ]; then
    ( set -a; source .env.local; set +a; unset ANTHROPIC_BASE_URL ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_OAUTH_TOKEN GATEWAY_MODEL
      : "${ANTHROPIC_API_KEY:?.env.local must set ANTHROPIC_API_KEY}"
      export ARB_AGENT_TIMEOUT_SEC=$WINDOW ARB_OUTPUT_TOKEN_LIMIT=400000 ARB_PROGRAM=$PROGRAM ARB_BUDGET_PY=$PWD/infra/prompts/budget.py
      harbor run -p tasks/game2048_policy_search -a claude-code -m "$MODEL" -y -n 1 -k 1 --job-name "$JOB" \
        --agent-timeout-multiplier "$MULTIPLIER" --ak prompt_template_path="$TEMPLATE" --extra-docker-compose "$MOUNT" \
        --ak disallowed_tools="WebSearch,WebFetch" --ak reasoning_effort="$EFFORT" --allow-agent-host anthropic.com --allow-agent-host '*.anthropic.com' \
        --ae ANTHROPIC_DEFAULT_OPUS_MODEL=$MODEL --ae ANTHROPIC_DEFAULT_SONNET_MODEL=$MODEL --ae ANTHROPIC_DEFAULT_HAIKU_MODEL=$MODEL --ae CLAUDE_CODE_SUBAGENT_MODEL=$MODEL \
        >> "$AUDIT_ROOT/ab/$JOB.log" 2>&1 )
  else
    RSI_EXAM_ROOT=$RSI_EXAM_ROOT MOUNT_YAML=$MOUNT GATEWAY_MODEL=anthropic/$MODEL "$WT/runbook/run_gateway.sh" "$JOB" "$WINDOW" "$MULTIPLIER" 1 "$EFFORT" "$PROGRAM" "$TEMPLATE" >> "$AUDIT_ROOT/ab/$JOB.log" 2>&1
  fi
  local RC=$?; echo "$(date -u +%H:%M:%S) $JOB harbor exit=$RC"
  [ "$RC" -eq 0 ] || stop "harbor exit $RC for $JOB"
  [ -d "jobs/$JOB" ] || stop "no job directory for $JOB"
  reached_api "jobs/$JOB" || stop "$JOB did not end normally or never reached the API"
  if [ "$ARM" = I ]; then
    if record_verified "$T"; then echo "$T ok" >> "$RECORDS"; else echo "$T fail" >> "$RECORDS"; fi
    if gate_blocked "jobs/$JOB"; then BLOCKED=$JOB; echo "$(date -u +%H:%M:%S) $JOB ended with the gate blocked; the block completes and no later block starts"; fi
  fi
  return 0
}
STARTED=0; RULE=""; BLOCKED=""; CURRENT_BLOCK=""
for T in $ORDER; do
  BLOCK=${T%%-*}
  if [ "$BLOCK" != "$CURRENT_BLOCK" ]; then       # the first trial of a block: the rules are judged here and only here
    if done_already "$T" && done_already "$(echo "$ORDER" | tr ' ' '\n' | grep "^$BLOCK-" | grep -v "^$T\$")"; then CURRENT_BLOCK=$BLOCK; continue; fi
    admit_block "$BLOCK" || break
    CURRENT_BLOCK=$BLOCK
  fi
  if done_already "$T"; then echo "$(date -u +%H:%M:%S) ab-$STAGE-$T already finished; not replaced"; continue; fi
  if [ -n "${LIMIT:-}" ] && [ "$STARTED" -ge "$LIMIT" ]; then echo "$(date -u +%H:%M:%S) LIMIT=$LIMIT reached; the rest of the order is not started"; break; fi
  STARTED=$((STARTED + 1))
  run_trial "$T"
done
# One terminal line, distinct by outcome: COMPLETE when every trial of the order ran (or LIMIT ended it), else the rule.
if [ -n "$RULE" ]; then echo "$(date -u +%H:%M:%S) AB-$STAGE-STOPPED-BY-RULE ($RULE)"; exit 3; fi
echo "$(date -u +%H:%M:%S) AB-$STAGE-COMPLETE"
