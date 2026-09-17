# Capture--verify--govern architecture

This is a framework design with a partial reference instantiation, not an
automatically enforced pipeline. Recording is not verification; consistency is
not authenticity; neither grants reuse authority.

| Boundary | Required transferable information | Current implementation and gap |
| --- | --- | --- |
| Capture | Decision identity, proposer/resolver, disposition, revision links, referenced artifacts/rule | RSI decision log to TRACE 0.5.1; only explicitly submitted decisions, with a system gate as resolver |
| Verify | Exact supplied package, checker/profile revision, outcomes, diagnostics and coverage limits | Full capsule verifier with raw files; ARA results bind source and input digests |
| Govern | Bounded candidate, evidence/check references, intended scope, separate human authority and current eligibility | Proofpress TRACE intake creates evidence only; explicit proposal remains unadmitted in E07. No required verifier-receipt binding or approval-to-next-agent run is demonstrated |

## Actual implemented paths

The gate writes a decision log. The producer packages that log with snapshots,
measurements and submission identity for the full offline verifier. Separately,
the converter creates a TRACE session from the log. Proofpress imports a bounded
projection of that TRACE session. The converter is not downstream of a mandatory
full verification step, and import is not conditional on a verifier pass.

E07 runs clean-package verification before conversion/import as an explicit test
sequence. That ordering in the runner is not an enforced adapter contract. Its
negative example demonstrates the difference: a verifier-rejected numerical error
is still first-importable as evidence.

## Statuses cannot be promoted across boundaries

RSI keep/revert/pending describes selection under the task rule. TRACE
accepted/rejected/proposed records that disposition and its resolver. Proofpress
admission requires a distinct governance decision. None authenticates the producing
runtime. An actor string is not an authenticated identity or human approval.

The framework requires exact check-result binding before a policy can rely on it;
the current TRACE projection alone is insufficient. Receipt-enforced admission,
human review quality, approved-context retrieval, expiry and a downstream agent
handoff are not tested by E07. ARA preserves the argument and evidence but does not
certify them.
