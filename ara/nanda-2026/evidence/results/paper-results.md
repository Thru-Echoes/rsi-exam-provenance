# Generated paper results

**Status:** `provisional_primary_complete_secondary_partial`

**Pinned input revision:** `727b9b821d7814d7467a29c1e740ce92eea7e219`

The primary direction count covers all ten preregistered blocks. Haiku and Sonnet come from machine-generated endpoint tables. Opus block 1 comes from digest-bound capsule hidden-evaluation fields; Opus blocks 2 and 3 come from a committed pre-probe summary rounded to three decimals. Their raw reward receipts and the remaining Opus secondary tables remain freeze blockers.

## Primary endpoint by block

| Stage | Block | Instrument reward | Helper reward | I - H | Favors | Evidence class |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Haiku | 1 | 0.14003888 | 0.07764052 | 0.06239836 | instrument | machine_generated_endpoint_table |
| Haiku | 2 | 0.1808063 | 0.21636209 | -0.03555579 | helper | machine_generated_endpoint_table |
| Haiku | 3 | 0.09345836 | 0.04347278 | 0.04998558 | instrument | machine_generated_endpoint_table |
| Haiku | 4 | 0.0 | 0.15123168 | -0.15123168 | helper | machine_generated_endpoint_table |
| Sonnet | 1 | 0.3327198 | 0.38678773 | -0.05406793 | helper | machine_generated_endpoint_table |
| Sonnet | 2 | 0.4350452 | 0.4697557 | -0.0347105 | helper | machine_generated_endpoint_table |
| Sonnet | 3 | 0.46113606 | 0.4235464 | 0.03758966 | instrument | machine_generated_endpoint_table |
| Opus | 1 | 0.5510569 | 0.60840837 | -0.05735147 | helper | digest_bound_capsule_hidden_evaluation |
| Opus | 2 | 0.346 | 0.602 | -0.256 | helper | committed_pre_probe_summary |
| Opus | 3 | 0.414 | 0.533 | -0.119 | helper | committed_pre_probe_summary |

## Bounded summary

- Observed blocks: 10.
- Favor instrument: 3.
- Favor helper: 7.
- Ties: 0.
- Interpretation: direction counts for these modified-program, reduced-window runs; no rate, efficacy, or significance claim.

## Record yield recomputed from per-trial tables

- All arms: 18 verified records from 20 started trials.
- Instrument: 9 of 10.
- Helper: 9 of 10.
- Explicit refusals:
  - `ab-haiku-4-H-CkZZrtb` (H): `submitted_not_snapshotted`.
  - `ab-sonnet-1-I-xtakhda` (I): `submitted_not_snapshotted`.

## Release blockers

- Opus blocks 2 and 3 remain summary-backed and rounded; bind their raw reward receipts before the final freeze.
- Opus secondary endpoint, spend, and complete sealed-retrospective tables are not committed.
- Do not convert the ten observed blocks into an efficacy, significance, or population-rate claim.

This file is generated. Do not edit aggregate values by hand.
