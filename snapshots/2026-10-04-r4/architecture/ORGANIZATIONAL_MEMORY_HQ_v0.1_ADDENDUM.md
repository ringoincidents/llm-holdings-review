# Organizational Memory & HQ Coordination Addendum v0.1

Authority: LLMH-013  
Status: CANDIDATE  
Date: 2026-09-27

## Runtime objects

- `OrganizationalMemory`: employee / lab / holdings scoped retained memory.
- `FounderNote`: immutable raw Founder input plus separately evolving interpretation state.
- `LabProposal`: a Lab finding requesting HQ consideration.
- `InterLabRequest`: durable routed request between Labs.
- `HoldingsInitiative`: HQ-approved coordinated body of work.
- `HoldingsWorkLedgerEntry`: global sequence, priority, dependency and owner record.

## Scope rule

```text
employee memory → visible to that Seat
lab memory      → visible to that Lab
holdings memory → visible to all Labs
```

Promotion upward is explicit. Local model output is not silently made global truth.

## Coordination rule

```text
Lab
→ LAB_HANDOFF action=propose
→ HQ Proposal
→ Initiative
→ ordered Lab Missions
→ Global Work Ledger
```

The Founder does not manually shuttle context between Labs.

## Concurrency / order rule

A new cross-Lab request receives a ledger sequence and explicit dependency references.
Existing running Work is not overwritten. A dependent Work remains blocked until predecessor entries complete.

## Founder interface rule

Original Artifact content is preserved. The default human surface renders a separate concise Founder brief first.
AI work instructions require Korean-first human-facing output and a compact brief before detailed internal material.

## Raw idea rule

Raw Founder text is preserved independently from interpretation. State advancement is explicit and reversible only where the transition table permits it.

## MVP boundary

This addendum establishes coordination and persistent state, not autonomous policy adoption.
Holdings-wide memory promotion and high-impact global change remain Founder-authorized.
