# Problem and research question

[ai-suggested, author requested implementation] Keeping a candidate changes the
starting point for later edits. A receiving agent or researcher can inherit those
choices without access to the producing runtime. It needs to inspect the
relationship between exact versions, measurements, decisions, and final submission.
Hashes identify supplied bytes but do not by themselves establish those relationships.

Historical motivation [input]: docs/PREFLIGHT.md describes visible results that do
not survive artifact export, bytecode-sensitive full-directory hashes, and
ambiguous narrative version logs. These observations are historical and scoped to
the reported task configuration.

**Question:** Which decision inconsistencies does full offline verification detect
beyond structural validation and referenced-file binding?

**Success criterion:** Demonstrate additional, correctly attributed failures on
explicit authored cases, and disclose accepted boundary cases. Do not use gate
reward, test-suite size, successful compilation, or polished formatting as a
substitute for this evidence.

**Scope:** Given the supplied package and an intended verifier, establish only
specified internal-consistency and coverage checks. No authenticity, nominal
statistical validity, global history completeness, or human auditing benefit follows.

The unit of audit is a version-selection decision and its evidence, not every tool
call. Capture, checking, and admission for reuse are distinct responsibilities.
Only the checking mechanism is evaluated here. A consistent decision can still
perform poorly on unseen games; passing the checker does not authorize reuse.

## Evidence roles after case review
H5 motivates submitted-identity capture; retained Opus block 1 illustrates recoverable branch declarations and unavailable measurement support. Neither supplies a new end-to-end verifier trial. Controlled mutations characterize incremental checking; the accepted rewrite bounds authenticity. The legacy Harvey example addresses a different downstream question, current eligibility for reuse, with an explicitly asymmetric treatment.
