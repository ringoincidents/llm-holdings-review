# LLM Holdings — System Overview

Review round: `2026-10-04-r2`  
Canonical private upstream baseline: `468e544926de5786d448ad4779c0b858ddd5d59d`

LLM Holdings is a persistent, governed Runtime for specialist AI Labs that execute durable Missions, retain scoped organizational knowledge, collaborate through explicit handoffs, and separate reasoning from evidence, decision, execution, and approval.

## Frozen invariants

- Agent != Model
- Model != Provider
- Provider != Account
- Harness != Model
- Decision != Reasoning
- Reasoning != Evidence
- Decision != Execution
- Execution != Approval

## Intelligence layers

```text
D0  deterministic code / rules / validators / math
D1  bounded Decision Intelligence
D2  reasoning models behind Model Gateway
Governance  approvals / audit / kill switches
```

## Organizational layer

```text
Founder / HQ
    ↓ authority
Lab
    ↓
Mission
    ↓
Work
    ↓
Runtime execution
    ↓
Artifact / Evidence / Proposal / Decision
    ↓
Approval / Audit / Organizational Knowledge
```

## Knowledge model

```text
Source
→ KnowledgeConcept
→ KnowledgeClaim
→ KnowledgeRelation
→ Canonical Projection
→ KnowledgeActionBinding
```

The memory design attempts to preserve sources while calculating current claims, contradictions, supersession, scope, and implementation state.

## Authority model

```text
Founder A4
HQ A3
Lab A2
Mission Owner A1
Agent / Seat A0
```

> Authority flows vertically. Knowledge flows horizontally. Memory remains distributed. Responsibility remains singular.

> Decision should occur at the lowest competent level.

## QuanTrade

QuanTrade is the first real client and is being shaped as one Private Investment Office rather than an AI stock picker.

A central review question is whether this generic Holdings Runtime measurably accelerates QuanTrade or becomes a competing architecture project.

## Main architectural bet

The main bet is not “more agents.” It is that a durable AI organization can be built from replaceable models plus deterministic runtime state, scoped knowledge, explicit authority, provenance, auditability, and specialized workspaces.
