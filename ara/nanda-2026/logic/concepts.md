# Concepts

## Decision event

**Definition:**

A typed keep, revert, provisional, or confirmation event over an exact candidate-parent pair and bound evidence files.

## Provenance record

**Definition:**

A portable record that binds snapshots, lineage, the submitted version, reward data, decision lines, and evidence digests. It is evaluated relative to the supplied artifact directory.

## Offline verifier

**Definition:**

A standard-library program that checks schema, digests, lineage, coverage, submitted-version identity, recomputed intervals, and decision-rule conformance without relying on a hosted service.

## Tamper-evident

**Definition:**

A property of the record relative to the pinned digests and supplied files: changes can be detected. It does not prevent modification and does not establish independent witnessing or correctness.

## TRACE

**Definition:**

The runtime decision-provenance representation. In this system, the agent is the proposer and the gate is the resolver. TRACE records do not themselves prove that bound files are valid.

## ProofPress

**Definition:**

A downstream governance layer that can import selected TRACE evidence for human review. Import does not create a claim, approval, admission, or independent verification.

## ARA

**Definition:**

The paper-facing research artifact containing the manuscript scaffold, structured claims, experiment definitions, evidence pointers, and exploration trace. It is not the runtime decision log or governance authority.

## Evidence precedence

**Definition:**

When summaries conflict, the order is: raw job outputs and verifier receipts; generated per-trial tables; preregistered manifest and committed endpoint tables; committed pre-probe summaries; narrative handoffs; working notes. A lower-precedence source cannot silently override a higher-precedence one. If a bounded value is recovered from a weaker source, its evidence class and precision travel with the value.

## Capture--verify--govern evidence contract

**Definition:** A design-level boundary contract, not one universal wire format.
Capture identifies the submitted decision, actors, revision/disposition and
referenced evidence/rule. Verification identifies the exact package and checker,
outcomes, diagnostics and limits. Governance binds a scoped candidate to evidence
and a separate authority decision. TRACE accepted, RSI keep, and Proofpress
admission are not interchangeable statuses. The present TRACE adapter imports
neither all rule fields nor a required bound verifier receipt.
