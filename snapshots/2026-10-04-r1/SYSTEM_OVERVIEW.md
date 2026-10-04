# LLM Holdings — System Overview

Review round: `2026-10-04-r1`  
Private upstream baseline: `6153ca1366b7cc8ef672ef316cdc1741bb5e99fc`

## One-sentence definition

LLM Holdings is a persistent, governed Runtime for specialist AI Labs that execute durable Missions, retain scoped organizational knowledge, collaborate through explicit handoffs, and separate reasoning from evidence, decision, execution, and approval.

## Problem

Ordinary LLM workflows often lose continuity across sessions and providers. They also tend to blur generated reasoning, verified evidence, authority, execution, and memory.

LLM Holdings attempts to make the **organization** persistent even when individual model calls are replaceable and short-lived.

## Frozen Runtime invariants

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

## Product layer

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

### Lab

A durable specialist workspace with its own objectives, Seats, Work, context, decisions, experiments, evidence, artifacts, and history.

### Mission

A durable Founder direction with objective, constraints, success criteria, bounded autonomy, and one accountable owner.

### Cross-Lab coordination

Labs can raise proposals and requests that route through HQ rather than requiring the Founder to manually carry context between sessions.

## Authority model

```text
Founder A4
HQ A3
Lab A2
Mission Owner A1
Agent / Seat A0
```

Principles:

> Authority flows vertically. Knowledge flows horizontally. Memory remains distributed. Responsibility remains singular.

> Decision should occur at the lowest competent level.

## Living Organizational Knowledge

The current memory direction rejects “latest document wins.”

```text
Source
→ KnowledgeConcept
→ KnowledgeClaim
→ KnowledgeRelation
→ Canonical Projection
→ KnowledgeActionBinding
```

The system tries to preserve original sources while calculating the currently relevant projection, conflicts, supersession state, and whether a direction is already implemented.

## No Cold-Start Work

New substantive Work should receive a knowledge-aware Context Pack rather than depend on chat history.

The intended context prefers:

1. current canonical claims;
2. unresolved contradictions;
3. action/implementation bindings;
4. only bounded historical rationale.

Scope isolation matters: one Lab's private memory must not silently appear in another Lab's context.

## Governed Record Writer

The Record Writer is intended to turn raw Founder commands/results into durable structured records without giving a stateless model authority over organizational truth.

```text
raw source
→ preserve source
→ retrieve current concept/context
→ structured draft
→ deterministic validation
→ conflict/supersession reconciliation
→ authority check
→ canonical or non-canonical disposition
```

The snapshot baseline also keeps unresolved records visible and allows explicit bounded semantic review instead of uncontrolled background model spending.

## External intelligence

External repositories, models, papers, and patterns are treated as observations, not adoption authority.

The intended loop is problem-first:

```text
External Signal
→ map to Holdings capability gap
→ independent assessment
→ bounded experiment
→ ADOPT / ADAPT / WATCH / REJECT
→ measure outcome
```

## QuanTrade

QuanTrade is the first real client and is being shaped as one **Private Investment Office**, not an AI stock-picker.

The long-term flow is closer to:

```text
Client Intelligence
→ Research / Evidence
→ Portfolio Management
→ Risk / Compliance
→ Investment Decision
→ controlled execution
→ Performance / Learning
```

A central review question is whether the generic Holdings Runtime accelerates this client or becomes a competing architecture project.

## Main architectural bet

The main bet is not “more agents.”

It is that a durable AI organization can be built from replaceable models plus deterministic runtime state, scoped knowledge, explicit authority, provenance, auditability, and specialized workspaces.

External review should aggressively test whether that actually outperforms a much smaller baseline.
