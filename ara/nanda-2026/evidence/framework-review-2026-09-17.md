# Framework-first revision rationale

Requested by the author; framing and prose are AI-suggested, E07 is AI-executed.
Scientific approval remains pending. This revision supersedes the earlier
reader-first hierarchy, while retaining its worked example and evidence limits.

## Decision

Lead with capture--verify--govern and use RSI-Exam as the first domain instantiation.
The reusable contribution is the separation of responsibilities and the information
needed to cross their boundaries, not a claim that three product descriptions form
a validated general system. The title is **Capture, Verify, Govern: Decision
Provenance for Agent Artifact Handoffs**.

## Necessary corrections to the proposed direction

- The RSI resolver in TRACE is a system gate, not the human who authorizes reuse.
- Keep/pending/confirmation semantics originate in the RSI contract; TRACE carries
  the submitted decisions, not every latent choice or complete execution history.
- The converter and full verifier consume related source data on separate paths.
  The Proofpress TRACE adapter imports a bounded projection, not the complete
  package or verifier report. It does not require successful verification.
- Human approval and a next agent's governed-context use are not demonstrated.
  The paper describes these as governance requirements and keeps the integration
  evidence at the intake/unadmitted-candidate boundary.

## Evidence ladder

1. C09: framework design and contract; no broad empirical validation.
2. C07/E06: retained real RSI case motivates evidence capture; missing files remain missing.
3. C01/C05/C06/E05: unchanged verifier and unchanged twelve-package characterization.
4. C10/E07: new local pinned integration demonstration. The mean-error fault is
   rejected by full verification but can be first imported as evidence. Import
   creates no claim/admission; an explicit candidate remains outside context.
5. C08/Harvey and C03/reward comparison stay in the companion, not pooled evidence.

## Review risks still open

Separation of concerns is not intrinsically new. Reviewers must judge whether the
executable profile and explicit intake counterexample make the composition useful.
The framework lacks mandatory receipt binding, a completed human-reviewed handoff,
independent cases, another domain checker, and measurements of audit or downstream
benefit. The manuscript discloses these instead of treating local tests as proof.

The paper keeps an anonymous author block, but named systems and public history
can identify contributors. No full anonymization or venue-policy compliance is
claimed; authors must resolve this before submission.
