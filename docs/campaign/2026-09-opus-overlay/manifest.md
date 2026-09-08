# Campaign manifest: six claude-opus-5 trials under the provenance overlay

Written and pushed before the first trial starts. Modified-program runs; nothing here is an official RSI-Exam result.

## What runs

- Task `game2048_policy_search`, RSI-Exam commit `bc36dadb405b`; harness `harbor` 0.22.0, `claude-code` adapter; model `anthropic/claude-opus-5` through an Anthropic-compatible gateway; reasoning effort `max`; agent budget 1200 s with timeout multiplier 0.030.
- Program overlay `runbook/autoresearch-provenance.md` (sha256 `00705dfce0eb262bd3d0255b8ba0de826335df545794969fb0d5b60bf728b397`) with template `runbook/autoresearch-provenance.j2` (sha256 `b5bc10cbae67f468ea0b61854d84152ce9ae606f1f0d8fe84a7eef81d51397bf`); repository commit `af486c05ddb8571a69e698ecc1a013b768f2b272`.
- Six trials planned, started one at a time, named `opus-overlay-01` to `opus-overlay-06`. No trial is replaced. Every started trial is reported, including one stopped by the timeout, one that leaves no artifact, or one whose verifier fails. A trial the spend guard never starts is reported as not started; the denominator of every count is the number of trials started.
- Trials run sequentially with no other agent trial on the machine, as the earlier six did. A sealed-suite retrospective (one single-threaded evaluation at a time) may run on the host during the campaign; it does not touch the trial containers.

## Spend

- Ceiling $100.00 on the gateway token. Verified spend before this campaign: $41.1805 (`runbook/cost.py`, rate card `opus`, over the three earlier Opus jobs).
- Reservation for one trial: $10.00 (the most expensive earlier trial cost under $7). A trial starts only while verified spend + 10.00 <= 100.00. The reservation is an allowance from observed costs, not a hard maximum: a single trial that cost more than $10.00 could carry the total past the ceiling, and the report would say so. Budget exhaustion is the only early stop, and a campaign stopped early is reported as such with the number of trials started.

## Endpoints (counts, not rates)

- Primary: records built and verified with the producer at the commit above (`integrity=pass`), over trials started.
- Secondary: the number with a `versions/v0` snapshot; the number with an `experiment_log.md`; per trial, the number of snapshots and of logged versions.
- Shadow audit over every trial with a verified record, reported exactly as for the development cohort: per-pair outcomes, comparable record-backed pairs, agree, disagree, exploratory count, with the inputs manifests committed before evaluation.
- Sealed-suite retrospective over every trial's snapshots, reported as for the development cohort: per-version sealed scores and rewards under the grader's mapping and the paired delta against the recorded parent. Descriptive; the sealed suite becomes analysis data and is never used to tune the rule.
- The six earlier Opus trials (two of six built a record) are context, not a comparator: they ran under a different program text and were recorded with an earlier producer.

## What is not claimed

No rate, reliability, efficacy or sealed-performance claim; no comparison of rates between the two cohorts; no statement that the overlay improves anything. Sealed rewards are listed per trial as incidental harness output, without aggregation or interpretation.
