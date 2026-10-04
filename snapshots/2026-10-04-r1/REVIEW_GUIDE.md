# External Review Guide

Review round: `2026-10-04-r1`

Separate these questions:

1. **Vision quality** — is the problem worth solving this way?
2. **Architecture quality** — do the boundaries have distinct invariants?
3. **Implementation truth** — does selected code/tests substantiate the claims?
4. **Product usefulness** — would a single Founder actually benefit operationally?

## Highest-value challenges

### Over-engineering

Which objects are necessary and which are only organizational vocabulary?

Pay special attention to Mission, Work, Artifact, Evidence, Proposal, Decision, Concept, Claim, Relation, Action Binding, Lab, Initiative, and Ledger objects.

### Multi-agent ROI

Compare against:

```text
one strong reasoning model
+ deterministic tools
+ persistent structured state
+ targeted reviewer calls
```

Demand evidence in correctness, cost, latency, failure recovery, and user intervention.

### Memory correctness

Ask about:

- stale claims;
- bad supersession;
- unresolved contradictions;
- scope leakage;
- provenance loss;
- action-state drift;
- retrieval failure;
- incorrect semantic linking.

### Authority illusion

Trace whether A0–A4 authority is enforced in code or only named in documents.

### Source-of-truth drift

Ask what happens when architecture docs, decisions, tasks, code, tests, deployment, and knowledge projection disagree.

### Test quality

Do tests validate invariants and failure modes, or mostly mirror implementation?

### Operability

Assess stuck work, retries, provider outages, persistence, idempotency, observability, cost ceilings, and mobile-first Founder operation.

### Security / isolation

Assess external-content ingestion, prompt-injection paths, tool permissions, authentication assumptions, and private/shared memory boundaries.

### Founder bottleneck

Does the system really reduce Founder coordination, or merely move it into more approval and interpretation surfaces?

### QuanTrade fit

Does Holdings infrastructure create measurable client value, or consume time that should go to the Private Investment Office?

## Review output requested

Please return:

1. your 5-sentence understanding;
2. strongest design decisions — top 3;
3. highest-risk problems — top 5;
4. unsupported/unverified claims;
5. layers to remove/merge/defer;
6. memory failure modes;
7. governance failure modes;
8. multi-agent ROI verdict;
9. QuanTrade help vs distraction;
10. operability/security risks;
11. next four weeks — max 7 priorities;
12. KEEP / SIMPLIFY / REARCHITECT;
13. three pieces of evidence that could change your verdict.

Mark low-confidence conclusions `UNVERIFIED`.
