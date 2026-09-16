# Architecture

```text
agent rollout
    |
    | candidate, parent, result files
    v
decision gate/helper ----> append-only decision log
    |                              |
    | snapshots + reward           | typed decisions
    v                              v
provenance producer ----------> portable record
                                      |
                                      v
                              offline verifier
                                      |
                         integrity / protocol / coverage
                                      |
                    +-----------------+-----------------+
                    |                                   |
                 TRACE                           paper evidence
          runtime decision view                 ARA package
                    |
                    v
              ProofPress import
       selected confidence-field evidence
```

The arrows describe intended composition, not an automatically enforced execution
sequence or trust inheritance. The historical fixture integration imported selected
confidence fields; it did not run complete verification or create an approved claim.
TRACE does not replace the verifier. Claim proposal and authorized human approval
are separate steps. ARA packages the research argument but does not authenticate
the source files.
