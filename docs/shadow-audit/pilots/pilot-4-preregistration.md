# Pilot 4: two full-length claude-opus-5 trials under the helper-backed overlay, operator's key

Written before the trials started (2026-09-09).

**Question.** At the campaign's own window (agent timeout multiplier 0.030, 1296 s; the helper prints 1200 s as
the run window), does claude-opus-5 at reasoning effort max complete evaluate-and-decide cycles under the
helper-backed loop, leave a record that builds with auditable pairs, and reach sealed rewards in the range of the
six earlier exam-program trials (four above 0.6) rather than the four wording-overlay trials (all 0.0)? The
5.8-minute Opus pilot followed the loop's opening (init first, a direct candidate, no infrastructure) but had no
time for a first evaluate.

**Arm.** `claude-opus-5`, reasoning effort `max`, multiplier 0.030, operator's key; program, template, helper and
mount at commit 664987b of `feat/provenance-helper`; two trials started by one harbor invocation with two
concurrent slots, job `pilot-opus-full`. Two trials cannot establish a rate; they show whether the cycle completes
at this window at all.

**Measures per trial.** Whether `init` ran first; minutes to the first `evaluate` and the first `decide`;
infrastructure actions; snapshots and pairs (kept-or-reverted, and including the submitted head); whether
`finalize` ran; how the agent stopped; the record producer's outcome; priced cost (rate card `opus`); the
verifier's sealed reward.

**Money.** Ceiling $22.00 for the pair, reservation $10.00 per trial (earlier full-length trials cost $6.97 to
$10.71); both trials start together, so the guard runs once, before the start. Both trials are reported whatever
they do; neither is replaced.
