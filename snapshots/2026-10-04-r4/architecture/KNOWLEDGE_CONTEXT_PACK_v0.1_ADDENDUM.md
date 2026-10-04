# Knowledge-Aware Context Pack v0.1

Authority: LLMH-035  
Status: IMPLEMENTING  
Date: 2026-10-03

## Purpose

Prevent organizational amnesia at the moment work begins.

The Runtime already preserves durable memory, KnowledgeConcepts, Claims, relations, Actions and Lab Context snapshots. This addendum connects those layers so stored knowledge is actually delivered to workers.

## Read path

```text
Work.title + Work.instructions
        ↓
bounded topic query
        ↓
┌──────────────────────┬──────────────────────┐
│ Lab-private concepts │ Holdings shared      │
│ exact lab scope      │ exact holdings scope │
└──────────────────────┴──────────────────────┘
        ↓
deduplicate stable Concept IDs
        ↓
Canonical Projection
        ↓
current Claims
contradictions
Action Bindings
bounded history
provenance
        +
manual LabContextRef entries
        ↓
LabContextSnapshot v2
        ↓
AI Seat delivery
```

## Context priority

The pack is ordered for execution usefulness:

1. current truth;
2. unresolved conflict;
3. implementation/action state;
4. provenance and source IDs;
5. bounded history;
6. manual context references.

The model should not need to read every old document merely to determine what is current.

## Token discipline

The pack is bounded.

- top relevant Concepts per scope are limited;
- historical Claims are truncated and capped;
- current Claims remain intact within reasonable field limits;
- all IDs are retained so deeper expansion can be requested;
- irrelevant global history is omitted.

## Scope rule

Automatic retrieval for Lab L:

```text
ALLOW: scope=lab:L
ALLOW: scope=holdings:holdings
DENY:  scope=lab:other
DENY:  scope=employee:any
```

No semantic retriever may bypass this rule.

## Snapshot semantics

A Context Pack is immutable once hashed into LabContextSnapshot.

If organizational knowledge changes later, a later Work receives a new snapshot. Historical Work keeps the old snapshot, allowing audit of what was known at execution time.

## Fallback

If no relevant KnowledgeConcept is found, the pack still contains:

- Lab identity;
- manual Shared Context;
- the query;
- an explicit `knowledge_match_count=0`.

Absence of a match must not be fabricated into prior organizational knowledge.
