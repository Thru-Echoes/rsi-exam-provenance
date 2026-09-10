# Pilot 3: one claude-opus-5 trial under the helper-backed overlay, operator's key

Written before the trial started (2026-09-09).

**Question.** Does claude-opus-5 at reasoning effort max follow the helper-backed loop (init first, a first
evaluate early, decide before editing again) inside a 345.6 s window, and does its record hold at least one
auditable pair? The four earlier Opus trials under the wording-only overlay built infrastructure for the whole
window and left v0 only.

**Arm.** `claude-opus-5`, reasoning effort `max`, agent timeout multiplier 0.008 (345.6 s), operator's key;
program, template, helper and mount at commit 664987b of `feat/provenance-helper`; job `pilot-opus-C1`. One trial.

**Measures.** Whether `init` ran first; minutes to the first `evaluate`; infrastructure actions (C compiler,
training scripts, weight files); snapshots and pairs; record outcome; whether `finalize` ran; priced cost (rate
card `opus`); the verifier's sealed reward as an incidental number.

**Money.** Ceiling $5.00, reservation $4.00: exactly one trial can start. Any harbor error stops for inspection.
The trial is reported whatever it does; it is not replaced.
