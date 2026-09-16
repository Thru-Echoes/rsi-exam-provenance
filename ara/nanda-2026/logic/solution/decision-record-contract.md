# Decision-record contract

Each resolved decision must identify:

- candidate version and exact parent version;
- statistic, direction, estimate, interval, and confidence level;
- measurement method and deterministic algorithm identifier;
- sample size and minimum effect;
- statistical verdict and operational disposition as separate fields;
- evidence roles, paths, and digests;
- rule state needed to reproduce the disposition; and
- any later confirmation event that revises a provisional decision.

The producer binds this event stream to the rollout's snapshots, submitted method, and reward artifact. The verifier recomputes measurements from the bound files and reports integrity failures, protocol failures, and coverage downgrades separately.

The normative implementation contract is `docs/decision-log-contract.md`; this ARA file is a paper-facing summary and must not become a second schema authority.
