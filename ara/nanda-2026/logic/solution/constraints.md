# Constraints and trust boundary

- The gate and profile code use the Python standard library; operator tooling may have separate dependencies.
- The decision log contains numbers, dispositions, identifiers, and digests, not prompts, private reasoning, transcripts, or arbitrary tool payloads.
- A digest identifies bytes; it does not establish truth, quality, authorship, or independent witnessing.
- The verifier is authoritative for whether the record checks against the supplied files. A downstream evidence importer must not claim to have repeated those checks unless it actually did so.
- Modified-program and reduced-window rollouts must never be described as official RSI-Exam results.
- Author-run results are not independent results.
- Missing evidence is an explicit unresolved or refused state, never a zero and never an inferred success.
- Narrative summaries cannot override source tables or verifier receipts.
- Public release, authorship order, and artifact licensing require joint human approval.
