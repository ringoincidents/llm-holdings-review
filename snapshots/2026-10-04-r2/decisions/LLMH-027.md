# LLMH-027 — Living Organizational Knowledge Lifecycle

Status: **ADOPTED / IMPLEMENTING**  
Date: 2026-10-03

## Founder direction

LLM Holdings must not behave like a folder of periodically rewritten documents.

When a new Founder direction, report, experiment, Decision, Artifact, code change, or external finding appears, the Runtime should preserve the original source while determining how it relates to existing organizational knowledge, what is currently valid, what has been superseded or contested, and what action has already been taken.

The Founder should not need to manually find last week's direction document, delete it, create a new one, and tell future agents which file is now authoritative.

## Decision

Adopt a **Living Organizational Knowledge Lifecycle** above raw memory/documents.

The primary human and machine retrieval unit becomes a stable **Concept**, not a dated document.

```text
Immutable Sources
    ↓
Knowledge Claims
    ↓
Typed Relations
    ↓
Canonical Projection
    ↓
Disposition / Action Binding
    ↓
Task / Experiment / PR / Deployment
    ↓
Verified outcome returns to knowledge
```

## Principles

1. **Knowledge is not a document.**
   - Documents, notes, Artifacts and Decisions are source records.
   - Stable Concepts provide durable topic addresses across time.

2. **Preserve source; recompute current truth.**
   - Old source material is not deleted merely because direction changed.
   - `supersedes`, `contradicts`, `extends`, `supports` and other typed relations preserve evolution.
   - Current organizational knowledge is projected from the graph.

3. **Do not silently resolve ambiguity.**
   - An explicit higher/equal-authority supersession can retire an older claim from the current projection.
   - Conflicting current claims remain `contested` until governance resolves them.

4. **Knowledge state and action state are separate.**
   - A statement can be current while implementation is planned, in progress, implemented, verified, deployed, or rolled back.
   - Reading a knowledge topic must reveal both.

5. **Reconcile before creating new Work.**
   - Current knowledge and prior Action Bindings are checked before creating materially overlapping Work.
   - Already implemented/verified/deployed work should route toward reuse, verification, or intentional revision rather than duplicate development.

6. **Authority and trust still govern updates.**
   - LLMH-041 trust gates remain authoritative.
   - Lower-trust or lower-authority claims cannot silently supersede higher-trust/higher-authority claims.
   - External content cannot become Holdings canonical truth merely because it is semantically related.

7. **Projection is not source-of-truth mutation.**
   - Founder UI, graph views, timelines and Obsidian exports are projections over canonical Runtime state.
   - Editing a projection does not silently rewrite organizational truth.

8. **The lifecycle should become increasingly automatic.**
   - Near term: explicit Concept/Claim/Relation/Action APIs and deterministic projection.
   - Next: automatic source extraction, semantic linking, stale/conflict detection, disposition, action reconciliation and duplicate-work prevention.

## Initial implementation

TASK-042 is expanded from a typed memory graph into the first executable lifecycle core:

- `KnowledgeConcept`
- `KnowledgeClaim`
- `KnowledgeRelation`
- `KnowledgeActionBinding`
- deterministic canonical projection
- explicit supersession without deleting history
- current-vs-history separation
- knowledge-vs-action state separation
- duplicate-work guard signal

Follow-up program:

- TASK-047 — Automatic Knowledge Reconciliation Compiler
- TASK-048 — Action Reconciliation and Duplicate-Work Enforcement
- TASK-049 — Founder Knowledge Observatory
- TASK-050 — Obsidian/Markdown Projection

## Relationship to prior decisions

- Extends LLMH-013 scoped organizational memory.
- Depends on LLMH-025 Capability Registry / Knowledge Router and distributed-memory principles.
- Builds on LLMH-026 / TASK-041 provenance and trust gates.
- Preserves the frozen `Mission → Work → Artifact → Proposal → Decision` execution flow.
- Does not authorize agents to rewrite Founder/Constitution/policy memory without existing governance.
