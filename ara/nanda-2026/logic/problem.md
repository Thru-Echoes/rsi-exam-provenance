# Problem

### O01 — Consequential decisions become lineage

A kept candidate becomes the parent of later work, so a weakly supported keep can affect an entire downstream branch.

### O02 — Conventional outputs omit decision bindings

A final method, reward file, and informal log do not necessarily bind:

- the candidate to its exact parent;
- the candidate and parent to exact method bytes;
- the decision to the result files used at that moment;
- the stated interval to a reproducible calculation;
- the submitted method to the lineage claimed by the log; or
- missing or malformed provenance to an explicit refusal.

### O03 — Auditability and efficacy are separable

A record can faithfully expose that a decision policy failed to improve the endpoint. Negative efficacy is compatible with a successful provenance mechanism.

### G01 — Evidence-to-decision gap

An auditor cannot reliably determine whether the evidence named in a log is the exact evidence used for a particular keep-or-revert event.

### G02 — Decision-to-artifact gap

An auditor cannot reliably bind a decision to exact candidate and parent bytes, or the submitted method to the claimed lineage, without additional structure.

### G03 — Summary-to-source gap

Narrative summaries may disagree with generated tables. A paper needs an explicit precedence rule and a frozen, machine-readable result source.

## Key Insight

Treat a keep-or-revert decision—not a whole trajectory or a model explanation—as the auditable unit. Bind its artifacts and evidence by digest, express its resolution separately from its statistical verdict, and make missing provenance a visible refusal state.

## Scope

The work addresses decision provenance for keep-or-revert events in RSI-Exam-style self-improvement loops. It does not attempt to record private chain-of-thought, prompts, transcripts, or arbitrary tool payloads. It does not claim to authenticate activity inside an untrusted rollout container.

## Success criterion

The primary systems criterion is whether an independently runnable verifier can check internal consistency, artifact binding, lineage, coverage, recomputed measurements, and protocol conformance from a record plus the supplied job directory. Improvement in sealed reward is a separate empirical claim and may fail without invalidating the provenance contribution.
