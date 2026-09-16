# Problem and research question

[ai-suggested] A recipient of an agent's improved program needs to inspect the
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
