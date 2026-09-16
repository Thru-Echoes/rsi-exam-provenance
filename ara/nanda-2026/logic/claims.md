# Claims

## C01 — Offline-verifiable decision provenance

**Statement:** Binding exact artifacts, evidence, lineage, and decision resolutions by digest enables offline checks of internal consistency and protocol conformance.

**Conditions:** The verifier receives the produced record and the corresponding exported job directory; exclusions and schema version match the profile; no claim of external authentication is implied.

**Sources:**

- [input] `README.md:16-20` — «The producer binds every snapshot, the experiment log, the submitted version, the reward file, and each version's decisions by digest; the verifier checks the record offline».
- [input] `docs/overview.md:168-170` — «It does not say the contents are good; that is a separate judgement.»
- [input] `tests/test_rsi_exam_provenance.py:1-1` — «Fault-injection tests for the RSI-Exam rollout provenance verifier and producer.»

**Status:** supported

**Falsification criteria:** A valid-looking record can be accepted after a bound artifact, evidence file, lineage link, submitted-version identity, interval, or required decision rule is changed without the corresponding verifier failure; or the documented fixture workflow does not reproduce an accepted record.

**Proof:** [E01]. The repository contains the producer, a standard-library offline verifier, a valid fixture, and fault-injection tests that mutate the claimed bindings and assert refusal codes. The claim is about internal verification relative to supplied files, not truth of the underlying measurements.

**Evidence basis:** source inspection; executable tests; valid fixture verification.

**Dependencies:** none

**Tags:** provenance, verification, lineage, integrity

## C02 — Native provenance is incomplete in observed cohorts

**Statement:** Unaided agent-authored logs can omit or destabilize the structure needed for a complete machine-checkable decision history, while explicit instrumentation can turn missing structure into a verified record or a visible refusal.

**Conditions:** Limited to the committed cohorts on `game2048_policy_search`; “incomplete” means the producer or verifier cannot construct a complete record from the exported material under the declared profile.

**Sources:**

- [result] `docs/PREFLIGHT.md:254-254` — «Five build and verify. The five refusals are the log's own doing.»
- [result] `docs/PREFLIGHT.md:357-357` — «Records built and verified in 5 of 5».
- [result] `docs/shadow-audit/instrument-ab/haiku/records.md:3-3` — «One row per trial started.»

**Status:** supported

**Falsification criteria:** Reprocessing the same frozen job directories with the pinned producer shows the native cohorts are complete at the same rate and with the same failure visibility as the instrumented path, or the reported refusals cannot be reproduced.

**Proof:** [E02]. The committed cohort notes enumerate missing logs, unclassifiable lines, unsnapshotted submissions, and verified records. The producer fails closed on these cases rather than silently treating the record as complete.

**Evidence basis:** observational cohort summaries; producer/verifier outputs; no population-rate inference.

**Dependencies:** C01

**Tags:** completeness, refusal, observational-study

## C03 — The tested instrument improves sealed reward

**Statement:** Requiring statistically gated confirmation before a keep improves final sealed reward relative to recording provenance without the gate.

**Conditions:** Same task and stage configuration within each block; all started trials retained; primary endpoint interpreted exactly as defined in the campaign manifest.

**Sources:**

- [input] `docs/campaign/2026-09-instrument-ab/manifest.md:89-89` — «Primary, per trial: the sealed reward of the submission».
- [result] `docs/shadow-audit/instrument-ab/haiku/endpoints.md:21-21` — «favouring the instrument: 2; favouring the helper: 2» and «mean difference -0.0186».
- [result] `docs/shadow-audit/instrument-ab/sonnet/endpoints.md:18-18` — «favouring the instrument: 1; favouring the helper: 2» and «mean difference -0.0171».
- [result] `docs/shadow-audit/pilots/pilot-8-preregistration.md:5-6` — «instrument 0.551, 0.346, 0.414 against 0.608, 0.602, 0.533» and «every block favoured the helper».
- [result] `ara/nanda-2026/evidence/results/paper-results.md:26-28` — «Observed blocks: 10», «Favor instrument: 3», and «Favor helper: 7».

**Status:** refuted

**Falsification criteria:** The frozen, fully reconciled endpoint table shows a positive instrument effect under the preregistered estimand with uncertainty adequate for the claim, and the result survives the prespecified sensitivity checks.

**Proof:** [E03]. The generated primary summary covers all ten planned blocks: 3 favor the instrument and 7 favor the helper. Haiku and Sonnet are parsed from machine-generated endpoint tables; Opus block 1 is parsed from digest-bound capsule hidden-evaluation fields; Opus blocks 2 and 3 come from a committed pre-probe summary rounded to three decimals. This is evidence against the improvement claim under tested conditions. Missing block 2--3 receipts and secondary tables remain release blockers and preclude stronger numerical or inferential claims.

**Evidence basis:** preregistered blocked comparison; complete primary direction count; partial final-stage receipt and secondary-source reconciliation.

**Dependencies:** C01, C02

**Tags:** efficacy, negative-result, sealed-reward

## C04 — Confirmation limits suppress later candidates

**Statement:** The confirmation floor/cap and remaining-window rule may prevent some candidates from being kept or evaluated later, changing the downstream search path.

**Conditions:** Applies only to the tested gate configuration and requires separating rule-triggered refusal from agent behavior, task difficulty, model choice, and time-budget effects.

**Sources:**

- [input] `docs/campaign/2026-09-instrument-ab/manifest.md:133-136` — «plan more confirmation seeds than the cap and are reverted as exploratory».
- [result] `docs/PREFLIGHT.md:598-600` — «16 confirmed» under the diagnostic planning rule and «Both Opus pairs and both Sonnet pairs the replay could evaluate confirmed at the floor».

**Status:** hypothesis

**Falsification criteria:** A direct intervention holding candidate sequence and remaining compute fixed shows no material change in later candidate production or selection when confirmation limits are varied; or logged refusals do not occur for the proposed mechanism.

**Proof:** [E04]. Existing summaries show rule states compatible with the mechanism, but the comparison does not isolate it causally. The paper must describe this as a candidate explanation and proposed follow-up experiment.

**Evidence basis:** mechanism-consistent observations; no causal identification.

**Dependencies:** C03

**Tags:** mechanism, confirmation, hypothesis
