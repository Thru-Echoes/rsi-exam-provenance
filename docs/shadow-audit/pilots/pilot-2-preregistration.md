# Pilot 2: the helper-backed overlay on a cheap model

Written before the first trial started (2026-09-09, after the first pilot).

**Question.** Does the revised overlay, whose loop routes snapshotting, logging, deciding and finalizing through
the mounted helper `provenance.py`, yield a verified record and auditable candidate-parent pairs in every trial,
where the first pilot's arms yielded records in 0 of 3 (exam program) and 1 of 3 (earlier overlay)?

**Arm C.** `claude-haiku-4-5-20251001`, reasoning effort `low`, agent timeout multiplier 0.008 (345.6 s), through
the operator's own key; program and template `runbook/autoresearch-provenance.md` and `.j2` at the helper
branch's commit; compose overlay `runbook/mount-provenance.yaml`. Job names `pilot-haiku-C1, C2, C3`. A smoke
trial `pilot-haiku-C0` at multiplier 0.002 (86 s) runs first to confirm the mount and that the agent runs `init`.

**Measures per trial, from the job directory.** Whether `init` ran (a `v0` block written by the helper);
snapshots; log blocks per snapshot; decided versus undecided candidates; `main/` equals a snapshot; the record
producer's outcome; pairs the shadow audit would recover (versions with a snapshotted parent and a kept or
reverted status); minutes to the first `evaluate`; verifier reward (incidental); priced cost.

**Reading it.** Target: 3 of 3 records build and verify and every trial holds at least one pair. Any record
refusal is a finding about the helper or the overlay text and is fixed before any Opus run. An agent that
ignores the helper and copies directories by hand is reported as such, not replaced.

**Money and stopping.** Hard ceiling $8.00 on this pilot including the smoke, reservation $1.50 per trial, the
same loop guard as the first pilot; stop on any harbor non-zero exit or missing job directory. No trial is
replaced; every started trial is reported.
