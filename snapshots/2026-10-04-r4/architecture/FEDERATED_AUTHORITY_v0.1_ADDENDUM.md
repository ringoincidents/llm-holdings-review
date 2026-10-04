# Federated Authority & Organizational Meta-Knowledge Addendum v0.1

Authority: LLMH-025  
Status: ADOPTED / PLANNED  
Date: 2026-10-01

## Purpose

Extend the existing Lab/HQ architecture with explicit delegation, singular ownership, and organizational meta-knowledge while preserving v0.1 governance and scoped memory.

## Core structure

```text
Founder (A4)
   ↑ exceptions only
HQ (A3)
   ↑ Holdings-wide conflicts / policy / shared resources
Lab (A2)
   ↑ Lab-scoped decisions
Mission Owner (A1)
   ↑ Mission-scoped decisions
Agent / Seat (A0)
```

Knowledge and collaboration may move laterally between Labs through governed references and requests.

## Authority policy

Every governed action has:

- requested authority level;
- current owner;
- required approver when escalation is necessary;
- escalation policy;
- audit trail.

The Runtime chooses the lowest level that is both competent and authorized.

An escalation is valid only when the lower level cannot safely or legally resolve the action under existing policy.

## Ownership rule

Every Mission has exactly one accountable `Mission Owner`.

Execution may be delegated to many Seats. Accountability is not.

The owner is responsible for:
- Mission state;
- bounded resource use;
- local acceptance/rejection decisions within authority;
- escalation when policy requires it.

## Founder Exception Inbox

Founder-facing decision surfaces should prioritize:
- A4 decisions;
- unresolved cross-authority conflicts;
- explicit policy exceptions;
- decisions whose risk/irreversibility exceeds delegated authority.

Routine operational confirmations should be removed from the Founder path when a lower authority level can resolve them deterministically.

## Capability Registry

Each Lab exposes metadata such as:

```yaml
lab: LLM Lab
capabilities:
  - model_evaluation
  - agent_architecture
knowledge_domains:
  - llm
  - inference
active_missions:
  - mission_id
```

The registry is organizational meta-knowledge, not a substitute for scoped retained memory.

## Knowledge Router

A query may resolve to:
- relevant Lab;
- relevant Mission;
- relevant Artifact/Decision/Evidence reference;
- reusable capability;
- suggested InterLabRequest.

Routing must preserve scope and authorization.

## Duplicate-work prevention

Before creating substantial new Work, the Runtime may deterministically check:
- matching capabilities;
- semantically/tag-related existing Missions;
- retained knowledge references;
- reusable shared infrastructure.

Detection initially produces a suggestion or governed handoff, not silent cancellation or replacement of Work.

## Compatibility

This addendum extends:
- `LAB_LAYER_v0.1_ADDENDUM.md`;
- `MISSION_ORCHESTRATION_v0.1_ADDENDUM.md`;
- `ORGANIZATIONAL_MEMORY_HQ_v0.1_ADDENDUM.md`.

It does not supersede the frozen v0.1 core or existing Human Governance.
