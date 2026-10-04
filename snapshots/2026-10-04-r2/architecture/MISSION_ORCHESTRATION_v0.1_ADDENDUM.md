# Mission Orchestration Addendum v0.1

Authority: LLMH-012  
Status: ACTIVE  
Date: 2026-09-27

## Purpose

Extend the persistent Lab from manual Seat dispatch into a bounded persistent AI organization.

## New durable objects

### Mission

Founder-level direction containing objective, constraints, success criteria, mode, status and a bounded step budget.

### Mission Work Link

Orders durable Work produced under a Mission without modifying the existing `LabWork` table.

### Agent Request

Records a request from a Seat or Runtime fallback to another Seat or Founder.

It stores:

- source Seat;
- destination Seat / Founder;
- request type;
- message and rationale;
- source Work;
- resulting target Work;
- origin (`agent` or `runtime_fallback`);
- status and timestamps.

## Execution rule

```text
Mission
→ create request
→ create Work
→ delegate to Seat
→ deliver Shared Context
→ execute through existing Runtime
→ Artifact
→ parse optional LAB_HANDOFF
→ next request or complete/escalate
```

The Runtime remains the execution engine. Mission orchestration does not bypass Case, Task, Decision, ExecutionRun, Artifact, kill switches or Model Gateway.

## Memory rule

Within one Mission, later Work receives prior Mission Artifacts as bounded Mission memory.

Across Missions, only Founder-retained Decisions automatically enter Shared Context. Generated model output is not silently promoted into organizational truth.

## Safety / cost rule

Default Mission autonomy is bounded to a small number of steps. Invalid handoffs do not expand authority. Exhausting the step budget stops for Founder review.
