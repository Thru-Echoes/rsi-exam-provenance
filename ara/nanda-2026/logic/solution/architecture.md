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
       downstream human-governance candidate
```

The arrows denote data flow, not trust inheritance. TRACE does not replace the verifier. ProofPress import does not approve the evidence. ARA packages the research argument but does not authenticate the source files.
