# LLM Holdings v0.1 — Lab Layer Addendum

Status: ACTIVE ADDENDUM  
Authority: LLMH-011  
Date: 2026-09-26

## Purpose

The original Runtime freeze remains valid as the execution engine. This addendum defines the product layer immediately above it.

## Layering

```text
Founder
  ↓
Lab / Workspace          ← persistent human + AI working environment
  ↓
Work Objects             ← Task / Case / Review / Question / Experiment
  ↓
LLM Holdings Runtime     ← routing / agents / models / tools / governance
  ↓
Providers / Tools / Client systems
```

## Lab

A Lab is the continuity boundary for work across sessions and AI providers.

Minimum Lab state:

- `lab_id`
- `title`
- `objective`
- `status`
- AI Seats
- Work objects
- Shared Context
- Decisions
- Experiments
- Evidence
- Artifacts
- History / Events

## Relationship to Case

`Case` is not removed or demoted as a Runtime execution primitive.

A Case is one type of durable work that may belong to a Lab. The Runtime may continue to execute Cases exactly as designed.

## Interaction principle

The primary near-term interface answers:

> What are we working on together, what context do the AIs share, who is doing what, what has been learned or decided, and what should happen next?

It does not primarily answer:

> How are all companies performing?

The latter becomes an aggregation/dashboard surface later.

## First vertical slice

The first Lab is `LLM Holdings Lab` and is used to develop LLM Holdings itself.

Minimum vertical slice:

```text
Open LLM Holdings Lab
→ see Objective
→ see AI Seats
→ see current Work
→ delegate one Work object
→ AI receives Shared Context
→ result becomes Artifact / Evidence / Review
→ important conclusion becomes Decision
→ close app/session
→ reopen Lab
→ continue from durable state
```

## Design constraint

Dashboard components may exist where useful, but the Lab interaction model must not default to KPI-card / company-dashboard composition.
