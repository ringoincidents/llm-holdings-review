# LLMH-035 — No Cold-Start Organizational Work

Status: **ADOPTED / IMPLEMENTING**  
Date: 2026-10-03

## Founder direction

A Lab meeting, Mission, or Work item must not restart from zero merely because the prior discussion happened in another ChatGPT session, another AI Seat, or an earlier week.

If the organization has already discussed, decided, implemented, verified, deployed, rejected, superseded, or experimented on a topic, the next relevant work must receive that organizational state automatically.

The Founder must not be responsible for remembering which old chat or document contains the prior context.

## Decision

Adopt **No Cold-Start Organizational Work** as a Holdings operating invariant.

Before substantive AI Work executes, the Runtime should assemble a bounded, scope-safe **Knowledge Context Pack** for the Work topic.

The pack should prefer:

1. current canonical KnowledgeConcept projections;
2. current Claims and unresolved contradictions;
3. Decision / provenance references supporting those Claims;
4. KnowledgeActionBinding implementation state;
5. implemented / verified / deployed evidence references;
6. a bounded superseded/history trail needed to understand how the current state evolved;
7. existing manually retained Lab Shared Context;
8. same-Lab relevant work history when useful.

## Example

A future LEANN meeting must not begin with “what is LEANN?” if Holdings already has relevant records.

The Context Pack should be able to surface, when present in canonical state:

- the LEANN external technology candidate;
- the Holdings-owned KnowledgeRetriever decision boundary;
- HOLDINGS-LEANN-001 experiment results;
- the current WATCH / CONTINUE EXPERIMENT disposition;
- relevant TASK / PR / CI / deployment state;
- unresolved next evidence such as production-scale, scope-isolation, stale-index and resource-cost tests.

The system should present the **current state first** and use old material as history, not as competing truth.

## Scope and privacy

A Lab Context Pack may automatically read:

- that Lab's private knowledge scope; and
- Holdings shared knowledge.

It may not silently read another Lab's private memory or employee-private memory.

Cross-Lab private knowledge still requires the existing Knowledge Router / governed handoff path.

## Authority

Retrieval does not create authority.

A Context Pack is a read projection. It cannot:

- make a candidate Claim current;
- supersede a Claim;
- promote Lab knowledge to Holdings;
- mark implementation complete;
- convert model output into Evidence.

## Persistence

The exact Context Pack delivered to an AI Seat must be durable and auditable through the existing LabContextSnapshot / LabContextDelivery mechanism.

This allows later review of what the worker actually knew when it made a recommendation or implementation.

## Relationship to prior decisions

- Extends LLMH-013 persistent Lab memory.
- Operationalizes LLMH-025: knowledge flows horizontally while memory remains distributed.
- Consumes LLMH-027 Living Organizational Knowledge Lifecycle projections.
- Uses TASK-047 retrieval/reconciliation without granting retrieval authority.
- Uses TASK-048 Action Binding state to prevent repeated implementation.
- Complements TASK-049 Founder Knowledge Observatory: Observatory is for the Founder; Context Pack is for organizational execution.

## Initial implementation

TASK-067 adds the first knowledge-aware context pack:

```text
Work topic
  ↓
same-Lab KnowledgeConcept retrieval
  +
Holdings Shared KnowledgeConcept retrieval
  +
manual Lab Shared Context
  ↓
current projection + action state + bounded history
  ↓
immutable LabContextSnapshot
  ↓
LabContextDelivery to executing Seat
```

Explicitly supplied snapshots remain supported. Otherwise the Runtime should generate a knowledge-aware snapshot before Work execution.
