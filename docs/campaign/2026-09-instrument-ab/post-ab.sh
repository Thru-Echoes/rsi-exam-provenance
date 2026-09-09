#!/usr/bin/env bash
# After one A/B stage has ended: records and inventory, the inputs manifests (committed and pushed before any
# evaluation), the shadow replays, the sealed-suite retrospective, then the tables and the endpoints. Nothing is
# written into a job directory. STAGE=<name> runs one stage's cohort; STEP=<records|manifests|replays|sealed|tables>
# runs one step (default: all, in that order); COMMIT=1 lets the records, manifests and tables steps commit (the
# manifests step also pushes and records the anchor commit). Run from the worktree that carries this file.
#
#   RSI_EXAM_ROOT=... AUDIT_ROOT=... STAGE=haiku [STEP=...] [COMMIT=1] post-ab.sh
set -uo pipefail
: "${RSI_EXAM_ROOT:?}"; : "${AUDIT_ROOT:?}"; : "${STAGE:?}"
HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd); WT=$(cd "$HERE/../../.." && pwd); cd "$WT"
TASK=$RSI_EXAM_ROOT/tasks/game2048_policy_search
IMAGE=$(cat "$AUDIT_ROOT/image.txt"); export IMAGE
COHORT=docs/shadow-audit/instrument-ab/$STAGE; mkdir -p "$COHORT"
RECORDS=$AUDIT_ROOT/ab
STEP=${STEP:-all}
step() { [ "$STEP" = all ] || [ "$STEP" = "$1" ]; }
stop() { echo "STOP: $*"; exit 1; }
model() { python3 -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]]['model'])" "$HERE/stages.json" "$STAGE"; }
rates() { python3 -c "import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]]['rates'])" "$HERE/stages.json" "$STAGE"; }
jobdir() { ls -d "$RSI_EXAM_ROOT"/jobs/ab-$STAGE-*/game2048_policy_search__"${1: -7}"; }
MODEL=$(model); RATES=$(rates)

if step records; then
  CODE=$(git log -1 --format=%h -- profile gate runbook)
  { echo "# Records over the instrument A/B, stage $STAGE"; echo
    echo "Producer and verifier at commit $CODE; records built into an audit root outside the job directories. One row per trial started."; echo
    echo "| rollout | arm | producer and verifier |"; echo "|---|---|---|"
    for J in "$RSI_EXAM_ROOT"/jobs/ab-$STAGE-*/game2048_policy_search__*; do
      ID="$(basename "$(dirname "$J")")-$(basename "$J" | tail -c 8)"; ARM=$(basename "$(dirname "$J")" | sed 's/.*-//')
      mkdir -p "$RECORDS/$ID"; rm -f "$RECORDS/$ID/capsule.json"
      out=$(python3 profile/build_capsule.py --job-dir "$J" --task-dir "$TASK" --release "0.1@bc36dadb405b" --capsule-id "$ID" \
            --model "$MODEL" --harness claude-code --output "$RECORDS/$ID/capsule.json" 2>&1 | tail -1)
      case "$out" in *"wrote "*) out="$(python3 profile/verify_capsule.py "$RECORDS/$ID/capsule.json" --artifact-root "$J" | head -1)";; esac
      printf "| %s | %s | %s |\n" "$ID" "$ARM" "$out"
    done; } > "$COHORT/records.md"
  python3 - "$RSI_EXAM_ROOT/jobs" "ab-$STAGE-" > "$COHORT/inventory.json" <<'PY'
import hashlib, json, pathlib, sys
root, prefix = pathlib.Path(sys.argv[1]), sys.argv[2]
rows = []
for trial in sorted(root.glob(f"{prefix}*/game2048_policy_search__*")):
    methods = trial / "artifacts/app/methods"
    entry = {"rollout": f"{trial.parent.name}-{trial.name[-7:]}", "log_present": (methods / "experiment_log.md").is_file(),
             "decision_log_present": (methods / "decisions.jsonl").is_file(), "snapshots": [], "symlinks": [], "non_python_files": []}
    versions = methods / "versions"
    if versions.is_dir():
        for snap in sorted(versions.iterdir()):
            if snap.is_symlink():
                entry["symlinks"].append(snap.name); continue
            if not snap.is_dir():
                continue
            entry["snapshots"].append(snap.name)
            for child in sorted(snap.rglob("*")):
                rel = child.relative_to(versions).as_posix()
                if child.is_symlink():
                    entry["symlinks"].append(rel)
                elif child.is_file() and child.suffix not in (".py", ".pyc", ".pyo") and "__pycache__" not in child.parts:
                    entry["non_python_files"].append({"path": rel, "bytes": child.stat().st_size, "sha256": hashlib.sha256(child.read_bytes()).hexdigest()})
    rows.append(entry)
print(json.dumps(rows, indent=2))
PY
  mkdir -p "$COHORT/profiles"
  for P in "$RECORDS"/ab-$STAGE-*-I/profile.json; do [ -f "$P" ] && cp "$P" "$COHORT/profiles/$(basename "$(dirname "$P")").json"; done
  chmod 644 "$COHORT"/profiles/*.json 2>/dev/null
  cat "$COHORT/records.md"
  if [ "${COMMIT:-0}" = 1 ]; then
    git add "$COHORT/records.md" "$COHORT/inventory.json" "$COHORT/profiles"
    git commit -q -F - <<MSG
docs(shadow-audit): records, inventory and profiles of the instrument A/B, stage $STAGE

The producer's outcome for each trial of the stage, verified where it built; the
inventory of every snapshot directory as it sits in the job directories; and the
task profile each instrument-arm trial ran under, so the profile digest every
decision line and receipt carries can be checked against the file. The profile's
replication key was readable inside the rollout and is not a secret.
MSG
    git log --oneline -1
  fi
fi

if step manifests; then
  for CAP in "$RECORDS"/ab-$STAGE-*/capsule.json; do
    [ -f "$CAP" ] || continue
    ID=$(basename "$(dirname "$CAP")"); J=$(jobdir "$ID")
    rm -f "$RECORDS/$ID/replay-profile.json"
    # The replay configuration selects the instrument's own planning rule (floor 16, cap 64 as the host's CPU budget), so
    # both arms are audited under the rule the instrument decided by; a fresh host key the agent never had.
    python3 runbook/make_profile.py --task-dir "$TASK" --rollout-id "$ID" --planning-rule estimate-aware --output "$RECORDS/$ID/replay-profile.json" >/dev/null || { echo "PROFILE-FAILED $ID"; continue; }
    mkdir -p "$COHORT/$ID"; rm -rf "$RECORDS/$ID/manifest-work"
    python3 gate/shadow_replay.py --job-dir "$J" --task-dir "$TASK" --profile "$RECORDS/$ID/replay-profile.json" \
      --capsule "$CAP" --workdir "$RECORDS/$ID/manifest-work" --container "$IMAGE" --inputs-only \
      --output "$COHORT/$ID/inputs.json" || echo "MANIFEST-FAILED $ID"
  done
  ls "$COHORT"/*/inputs.json
  if [ "${COMMIT:-0}" = 1 ]; then
    git add "$COHORT"/*/inputs.json
    git commit -q -F - <<MSG
docs(shadow-audit): inputs manifests for the instrument A/B, stage $STAGE

Written before any evaluation of the stage's trials, in the same form as the
earlier cohorts' manifests: the record's digest and per-version method-tree
digests, the replay configuration's digest, the evaluator and visible-suite
digests, the task starter's digest, the digest of every gate source file, the
gate's commit, the evaluation image and its resolved digest. Each run refuses
unless its own manifest matches the committed one.
MSG
    git push -q -u origin "$(git branch --show-current)" && git rev-parse HEAD | tee "$AUDIT_ROOT/anchor-commit-ab-$STAGE.txt"
  fi
fi

if step replays; then
  ANCHOR=$(cat "$AUDIT_ROOT/anchor-commit-ab-$STAGE.txt") || stop "no anchor commit; run the manifests step with COMMIT=1 first"
  : > "$COHORT/exits.txt"
  for M in "$COHORT"/*/inputs.json; do
    ID=$(basename "$(dirname "$M")"); J=$(jobdir "$ID")
    rm -rf "$RECORDS/$ID/work"
    python3 gate/shadow_replay.py --job-dir "$J" --task-dir "$TASK" --profile "$RECORDS/$ID/replay-profile.json" \
      --capsule "$RECORDS/$ID/capsule.json" --workdir "$RECORDS/$ID/work" --container "$IMAGE" \
      --expect-inputs "$M" --anchor-commit "$ANCHOR" --output "$COHORT/$ID/report.json" > "$RECORDS/$ID/replay.log" 2>&1
    echo "$ID exit=$?" | tee -a "$COHORT/exits.txt"
  done
  echo REPLAYS-DONE
fi

if step sealed; then
  SEALED=$COHORT/sealed; mkdir -p "$SEALED"; : > "$SEALED/exits.txt"
  for J in "$RSI_EXAM_ROOT"/jobs/ab-$STAGE-*/game2048_policy_search__*; do
    ID="$(basename "$(dirname "$J")")-$(basename "$J" | tail -c 8)"; mkdir -p "$RECORDS/$ID" "$SEALED/$ID"
    [ -f "$RECORDS/$ID/replay-profile.json" ] || python3 runbook/make_profile.py --task-dir "$TASK" --rollout-id "$ID" --output "$RECORDS/$ID/replay-profile.json" >/dev/null
    CAP=(); [ -f "$RECORDS/$ID/capsule.json" ] && CAP=(--capsule "$RECORDS/$ID/capsule.json")
    rm -rf "$RECORDS/$ID/sealed-work"; rm -f "$SEALED/$ID/report.json"
    python3 gate/sealed_eval.py --job-dir "$J" --task-dir "$TASK" --profile "$RECORDS/$ID/replay-profile.json" ${CAP[@]+"${CAP[@]}"} \
      --workdir "$RECORDS/$ID/sealed-work" --container "$IMAGE" --output "$SEALED/$ID/report.json" > "$RECORDS/$ID/sealed.log" 2>&1
    echo "$ID exit=$?" | tee -a "$SEALED/exits.txt"
  done
  echo SEALED-DONE
fi

if step tables; then
  if [ "$(grep -c 'exit=1' "$COHORT/exits.txt")" = 0 ]; then
    echo 'No run exited 1; every pair reached a gate disposition.' > "$COHORT/dispositions.md"
  else
    [ -f "$COHORT/dispositions.md" ] && ! grep -q 'DISPOSITIONS NEEDED' "$COHORT/dispositions.md" \
      || { echo "DISPOSITIONS NEEDED" > "$COHORT/dispositions.md"; stop "some replay exited 1; write $COHORT/dispositions.md naming every failed pair before committing"; }
  fi
  python3 "$HERE/ab_tables.py" "$COHORT" "Shadow audit over the instrument A/B, stage $STAGE" > "$COHORT/audit-summary.md"
  python3 "$HERE/ab_measures.py" --jobs-root "$RSI_EXAM_ROOT/jobs" --prefix "ab-$STAGE-" --records "$RECORDS" --rates "$RATES" \
    --sealed "$COHORT/sealed" --profiles "$COHORT/profiles" > "$COHORT/endpoints.md"
  { for J in "$RSI_EXAM_ROOT"/jobs/ab-$STAGE-*; do printf "%s " "$(basename "$J")"; RATES=$RATES python3 runbook/cost.py "$J" | grep -E '^TOTAL'; done
    printf "STAGE-%s " "$STAGE"; RATES=$RATES python3 runbook/cost.py "$RSI_EXAM_ROOT"/jobs/ab-$STAGE-* | grep -E '^TOTAL'; } > "$COHORT/spend.md"
  cat "$COHORT/endpoints.md" "$COHORT/spend.md"
  if [ "${COMMIT:-0}" = 1 ]; then
    git add "$COHORT"
    git commit -q -F - <<MSG
docs(shadow-audit): reports, retrospective, endpoints and spend of the instrument A/B, stage $STAGE

The shadow audit's report for every trial with a verified record, each against
its committed inputs manifest, with exit statuses and dispositions; the sealed
suite retrospective over every snapshot; the pre-registered endpoints as counts,
paired by block; and the priced spend against the stage's ceiling.
MSG
    git push -q
  fi
fi
