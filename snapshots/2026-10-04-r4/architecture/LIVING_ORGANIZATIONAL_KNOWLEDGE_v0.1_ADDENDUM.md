# Living Organizational Knowledge Lifecycle Addendum v0.1

Authority: LLMH-027  
Status: IMPLEMENTING  
Date: 2026-10-03

## Problem

A document-centric memory store degrades as the organization evolves.

If multiple direction documents exist for the same topic, future agents must rediscover which document is current, whether an older instruction was superseded, whether an implementation already happened, and whether a new proposal would duplicate existing work.

LLM Holdings therefore separates **source preservation** from **current knowledge projection**.

## Core objects

### Source

Existing durable objects remain the historical record:

- FounderNote
- OrganizationalMemory
- Decision
- Artifact
- Mission / Work
- Evidence
- ExternalSignal / TechnologyCandidate
- repository files / PR / deployment records

Sources are not replaced merely to keep a human folder tidy.

### KnowledgeConcept

A stable topic address.

Examples:

- `decision-authority-model`
- `organizational-memory-architecture`
- `external-intelligence`
- `development-philosophy`

A Concept survives individual document versions.

### KnowledgeClaim

A source-derived statement attached to a Concept.

It preserves:

- content
- source reference
- trust class
- authority level
- initial knowledge status
- disposition
- creation provenance

### KnowledgeRelation

Append-only typed relationship between Claims.

Initial relation vocabulary:

- supports
- contradicts
- supersedes
- derived_from
- tested_by
- adopted_as
- rejected_by
- relates_to
- extends
- narrows
- implements

The relation is history; the older source is not deleted.

### KnowledgeActionBinding

Connects a Claim to concrete organizational action.

Examples:

- TASK-035 / completed
- PR #57 / merged
- production commit / deployed
- Experiment / verified
- Capability / active

Action state is separate from claim validity.

## Canonical projection

For a Concept, the Runtime derives:

- current Claims
- superseded/history Claims
- contradictions
- related Claims
- current action state
- whether the current direction is already materially implemented
- duplicate-work guard recommendation

The projection is computed from durable source and relationship state. It is not a manually maintained replacement document.

## Supersession rule

A new Claim may supersede an older Claim only when:

1. both are in the same allowed knowledge scope;
2. the new Claim has at least the required trust level;
3. the new Claim has at least the required authority level;
4. a durable `supersedes` relationship is created.

The old Claim remains retrievable as history.

## Conflict rule

`contradicts` does not automatically choose a winner.

If conflicting Claims are simultaneously current, the Concept projection is `contested`. Existing authority/governance decides whether a supersession or other resolution is appropriate.

## Knowledge lifecycle state

Knowledge validity and action execution are orthogonal.

```text
Knowledge
candidate | current | contested | superseded | rejected | historical

Action
no_action | planned | queued | in_progress | implemented | verified | deployed | rolled_back
```

## Disposition

A Claim may carry a post-processing disposition:

- REFERENCE_ONLY
- WATCH
- EXPERIMENT
- IMPLEMENT
- PROPOSE_POLICY
- SUPERSEDE
- DUPLICATE
- ARCHIVE

This answers the operational question: “What should happen to this knowledge?”

## Retrieval rule

Future Mission context should prefer:

1. current Concept projection;
2. relevant unresolved contradictions;
3. current Action Bindings;
4. only the historical sources needed for rationale.

This should reduce stale-context pollution and repeated reading of obsolete documents.

## UI / Obsidian rule

Human visualization is a projection layer.

A Founder Knowledge Observatory may provide:

- topic pages
- current view
- timeline
- graph
- contradictions
- implementation state
- provenance / “why do we believe this?”

An Obsidian/Markdown vault may be generated from the same Runtime state, but must not become an uncontrolled second source of truth.

## v0.1 implementation boundary

TASK-042 implements the durable schema, explicit APIs and deterministic projection first.

Automatic semantic extraction/linking from every new document is deliberately deferred to TASK-047 so the system does not grant model-generated relationships authority before the storage and trust invariants are tested.
