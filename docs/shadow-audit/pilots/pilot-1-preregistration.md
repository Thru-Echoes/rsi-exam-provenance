# Pilot: the exam's program versus the provenance overlay, on a cheap model

Written before the first pilot trial started (2026-09-09 00:4x UTC).

**Question.** Holding model, reasoning effort, task, harness and agent budget fixed, does the provenance
program overlay (`runbook/autoresearch-provenance.md` and `.j2`) change what the agent does in its first
minutes compared with the exam's own program (`infra/prompts/autoresearch.md` and `.j2`)? The four
claude-opus-5 trials under the overlay all spent their 21.6 minutes building a learned-policy pipeline and
never edited the policy; six earlier claude-opus-5 trials under the exam's program produced four sealed rewards
above 0.6. Program text was the only configuration difference.

**Arms.** A = exam's program and template. B = overlay program and template. Everything else identical:
`claude-haiku-4-5-20251001` through the operator's own Anthropic key (not the collaborator's gateway),
reasoning effort `low`, agent timeout multiplier 0.008 (345.6 s of the task's 43200 s), one trial per
invocation, job names `pilot-haiku-A1, B1, A2, B2, A3, B3`, run in that order so the arms interleave in time.

**Measures per trial, all read from the job directory.** Agent seconds and how it stopped; tool calls;
minutes to the first edit of `methods/main/policy.py`, first `selfcheck.py` run, first snapshot `v>=1`; count
of C-compiler or training-pipeline actions; snapshot directories; `v0` present; experiment log present;
`main/policy.py` differs from the task's starter; verifier reward (incidental); whether the record producer
builds and verifies the rollout; priced spend (`runbook/cost.py`, rate card `haiku`).

**Reading it.** If arm B trials edit the policy and snapshot versions at a rate like arm A, the overlay text
does not reproduce the Opus behaviour on this model, and the next cheap step is one A/B pair on a mid-size
model (needs a rate card first). If arm B trials stop editing the policy or spend their time on
infrastructure while arm A trials do not, the overlay text is implicated, and the fix (move the `v0` snapshot
out of the agent's first act; state the wall-clock budget) is piloted the same way before any Opus spend.
Three pairs cannot establish a rate; they can show whether the failure mode reproduces at all.

**Money and stopping.** Hard ceiling $8.00 on the pilot (well under the operator's $10 cap), reservation
$1.50: a trial starts only while priced spend + 1.50 <= 8.00. Earlier Haiku trials at 216 s to 501 s cost
$0.36 to $2.61. The loop also stops on any harbor non-zero exit or missing job directory, to be inspected
before anything else runs. No trial is replaced; every started trial is reported.

**After the pilot.** Results go to the operator with the table; then adversarial passes over the analysis and
any proposed overlay change; only after the operator agrees does anything run on the collaborator's gateway.
