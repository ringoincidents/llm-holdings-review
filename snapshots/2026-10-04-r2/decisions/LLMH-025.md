# LLMH-025 — Federated Authority, Distributed Memory, and Organizational Meta-Knowledge

Status: ADOPTED / PLANNED
Date: 2026-10-01

## Problem

LLM Holdings already has persistent Labs, scoped memory, HQ routing, durable Missions, Founder actions, and background execution.

As the number of Labs, Missions, and AI workers grows, a new bottleneck appears if every meaningful decision ultimately converges on the Founder or HQ:

- Founder decision load grows with organizational scale;
- responsibility becomes ambiguous when no single owner is attached to a Mission;
- Labs can become information silos despite separate memory scopes;
- duplicated work increases when the Runtime does not know which Lab already has relevant knowledge or capability;
- a large organization cannot rely on one person knowing where every piece of knowledge lives.

The Runtime therefore needs explicit authority delegation and organizational meta-knowledge without destroying Lab autonomy or the v0.1 governance boundary.

## Decision

LLM Holdings adopts a federated hierarchy:

> Authority flows vertically.  
> Knowledge flows horizontally.  
> Memory remains distributed.  
> Responsibility remains singular.

A second operating rule is adopted:

> Decision should occur at the lowest competent level.

### Authority levels

The Runtime will represent five authority levels:

- **A0 — Agent Authority**: reversible, low-risk execution decisions such as search, drafting, bounded analysis, local test execution, and other already-permitted tool work.
- **A1 — Mission Authority**: decisions owned by the Mission within its approved objective, constraints, budget, and risk boundary.
- **A2 — Lab Authority**: Lab-level priority, bounded Mission creation, internal resource allocation, and cross-Lab requests within policy.
- **A3 — HQ Authority**: Holdings-wide knowledge promotion, cross-Lab conflicts, shared infrastructure/policy changes, and material resource decisions within delegated policy.
- **A4 — Founder Authority**: Vision, Constitution, material capital allocation, new organizational units, irreversible/high-impact actions, and explicit exceptions outside delegated authority.

Existing high-risk Human Governance remains mandatory. This decision narrows Founder involvement where safe; it does not bypass existing approval gates.

### Mission ownership

Every Mission must have one accountable owner.

Ownership and execution are distinct: multiple Seats may work on a Mission, but responsibility for its state and escalation remains singular.

### Founder interface

The long-term Founder Inbox becomes an **Exception Inbox**.

Routine A0–A3 work should be resolved or routed at its competent level. The Founder should receive A4 decisions and unresolved exceptions, not routine operational questions.

### Organizational meta-knowledge

LLM Holdings will maintain a Capability Registry / Knowledge Router that answers:

> Who knows what, who can do what, and where relevant work already exists?

This registry stores metadata about capabilities, knowledge domains, active Missions, and relevant retained knowledge references. It does not silently promote Lab-private knowledge to Holdings-wide truth.

### Cross-Lab discovery

Cross-Lab coordination evolves from manual handoff alone toward automatic discovery:

- suggest relevant existing capabilities;
- detect likely duplicate work;
- surface related Lab knowledge;
- propose an InterLabRequest or reuse path.

Automatic discovery may propose/reroute work within delegated authority, but may not silently change Holdings-wide policy or promote knowledge beyond its scope.

## Architectural compatibility

This decision does not replace the frozen v0.1 object model.

The existing flow remains authoritative:

`Mission → Work → Artifact → Proposal → Decision`

Authority is added as metadata/policy around existing objects rather than by replacing them.

Expected additive concepts include:

- `owner`
- `authority_level`
- `approver`
- `escalation_policy`
- Capability Registry / Knowledge Router projections

## Organizational principles

- Authority Flows Vertically
- Knowledge Flows Horizontally
- Memory Remains Distributed
- Responsibility Remains Singular
- Decide at the Lowest Competent Level
- Founder Handles Exceptions, Not Routine Operations
- Know Who Knows
- Reuse Before Duplicate Work

These principles must become Holdings-scope organizational memory and remain available to every Lab Mission.

## Non-goals

This decision does not authorize:

- automatic Lab creation;
- unrestricted autonomous spending;
- automatic production deployment outside existing gates;
- automatic Holdings-wide memory promotion;
- removal of kill switches;
- removal of Founder authority over A4 decisions.
