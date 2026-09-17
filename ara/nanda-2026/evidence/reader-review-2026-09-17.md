# Reader-first revision — 2026-09-17

Status: AI editorial judgment, not an independent readability study. Prepared in response to the author's report that the previous draft was confusing. No new efficacy finding or empirical result is claimed.

## Diagnosis of the previous draft
1. The abstract introduced profile, digests, provisional resolution and coverage before explaining the agent's task or the recipient's question.
2. The seven-component tuple and five-predicate conjunction summarized implementation fields, but the text never used them to derive a result. They increased the reader's work without making the argument stronger.
3. The worked example arrived after the abstractions and showed a one-point numerical inconsistency, which could be mistaken for an incorrect keep/revert outcome.
4. The evaluation placed development vectors, synthetic packages, retained RSI records, reward A/B and Harvey handoffs next to one another. Distinct evidence purposes and denominators competed for attention.
5. The paper jumped from 2048 code changes to legal-knowledge expiry without explaining why a different implementation and an asymmetric treatment were needed for the main claim.
6. Many limitations were necessary, but repeated local disclaimers displaced the positive statement of what the method actually does.

## Changes made
- New literal title: Auditing Keep-or-Revert Decisions in Self-Improving Agents.
- Start with the editing/testing/selection loop and explain RSI-Exam without assuming prior familiarity; distinguish task-program improvement from updating model weights.
- State the receiver's questions and define decision consistency before describing fields.
- Replace unused formal notation with a compact record description and progressive checking questions.
- Add a three-row synthetic worked example: v2 reverted, v3 initially pending, v3 confirmed and submitted. Table numbers are regression-tested against the unmodified fixture.
- Explain explicitly that recalculation uses supplied per-seed measurements and does not execute the agent's program.
- Say the one-point mutation tests arithmetic consistency and does not change that example's verdict.
- Separate the final unsigned reward from visible-game measurements so its accepted rewrite is intelligible.
- Keep retained real RSI evidence as motivation, with its missing-data ceiling; use no overlapping version labels in that paragraph.
- Move Harvey, historical reward comparisons, the 18/20 cohort summary, TRACE import and detailed development diagnostics out of the manuscript. Their sources and claim/experiment cards remain in the ARA.
- Preserve all 12 controlled outcomes, the 8/9 diagnostic-target caveat, and the authenticity boundary. No verifier, case manifest, fixture or result file was changed.

## Argument the reader should now be able to repeat
An agent tries several programs and selects one. Its recipient cannot audit that choice from the final score alone. We connect the versions, measurements and declared decision rules, then check their consistency offline. Controlled package changes show which checks add value beyond matching hashes. A consistent reward rewrite still passes, so the result is not proof of genuine execution.

## What this does not fix
The scientific evidence is still a single-base, author-designed characterization. Better prose cannot turn it into independent validation or a broad benchmark. Novelty remains a narrow systems contribution. Keeping the real case modest is preferable to suggesting a complete replay that the retained files cannot support.

## Distribution state
This reader-first revision is a local review candidate. The previously published PR #40 ZIP remains the frozen 2026-09-16 draft; it has not been silently replaced. Confirm the narrative before updating the public review bundle or Notion.
