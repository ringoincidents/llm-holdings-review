# Governed Record Writer Addendum v0.1

Authority: LLMH-037  
Status: IMPLEMENTING  
Date: 2026-10-04

## Purpose

Make organizational records resilient to short-lived model calls, changing conversations, and long-running development.

The objective is not to make every API model remember like a long-running conversational assistant.

The objective is to make **the organization remember**, so any sufficiently capable model can produce consistent records from governed context.

## Core principle

> Model quality helps writing quality. Record quality comes from context, schema, provenance, reconciliation, and authority.

A strong model with weak context can write a polished wrong history.

A cheaper model with the correct current Claims, source diff, and constrained schema can often produce a safer organizational record.

## Record pipeline

```text
Raw source
  ↓
Source preservation
  ↓
Relevant Concept retrieval
  ↓
Current canonical projection + bounded history
  ↓
Structured record draft
  ↓
Deterministic validation
  ↓
Conflict / supersession reconciliation
  ↓
Authority check
  ↓
Canonical promotion or non-canonical disposition
  ↓
Human-readable projection
```

## Structured draft

A Record Writer should return fields equivalent to:

```text
record_type
summary
candidate_claims[]
affected_concepts[]
relation_to_existing[]
  EXTENDS | NARROWS | SUPERSEDES | EXPERIMENT | REJECTS | REFERENCE_ONLY
decisions[]
open_questions[]
implementation_implications[]
confidence
source_refs[]
requires_human_review
```

The exact schema may evolve, but free-form prose must not be the only machine-readable output.

## When one-shot models are enough

A cheap/stateless model is usually sufficient when:

- the source is bounded;
- the relevant canonical context is supplied;
- the output schema is strict;
- no high-authority conflict exists;
- the task is summarization or extraction;
- deterministic checks can validate required fields and provenance.

## When stronger reasoning is warranted

Escalate when:

- the new source conflicts with current canonical direction;
- multiple historical decisions appear inconsistent;
- the source implicitly changes authority or scope;
- the change would affect many Labs;
- the model cannot determine EXTENDS vs SUPERSEDES;
- the record would trigger capital, deployment, policy, or safety consequences.

## Verification

For material records, the Runtime should compare the draft against:

- source text;
- existing current Claims;
- cited provenance;
- relationship validity;
- authority rules;
- implementation bindings.

A second model may review semantic faithfulness, but deterministic checks should enforce IDs, source presence, allowed relations, required fields, and scope.

## Anti-drift safeguards

1. No “latest note wins.”
2. No silent overwrite.
3. No promotion without provenance.
4. No inference that code deployment equals strategic approval.
5. No experiment promoted into product identity without explicit decision.
6. No human-readable projection allowed to become an uncontrolled second source of truth.
7. Retrieval should prefer current Claims and only bounded history needed for rationale.

## Founder experience

The Founder should not manually curate every knowledge object.

The expected interaction is:

```text
Conversation / decision / result
        ↓
Runtime drafts record
        ↓
Routine records file automatically within delegated authority
        ↓
Material change appears as concise Founder review
        ↓
Approve / revise / defer / reject
```

This preserves low-friction conversation while keeping long-term organizational continuity.
