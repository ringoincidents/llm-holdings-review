# LLM Holdings Runtime v0.1 — Architecture Freeze

Status: **FROZEN**

## Core principle

- Agent != Model
- Model != Provider
- Provider != Account
- Harness != Model
- Decision != Reasoning
- Reasoning != Evidence
- Decision != Execution
- Execution != Approval

## Intelligence layers

- D0: deterministic code / rules / math / validators
- D1: decision intelligence / S1
- D2: reasoning intelligence / frontier or local LLMs
- Governance: human approval, policies, immutable audit

## v0.1 vertical slice

1. Founder creates a Case from mobile.
2. D1 routes the Case to Researcher, Reviewer, Developer, or Human.
3. Runtime creates a Task.
4. Agent runs through Model Gateway.
5. Evidence and Decision are persisted.
6. Governance decides whether Founder approval is required.
7. Founder approves or rejects from mobile.
8. Events preserve the complete audit trail.

## First client

QuanTrade.

## First S1 problem

Routing only:

- research
- review
- developer
- human

## Out of scope

Foundation-model training, autonomous trading, dozens of agents, complex debates, Kubernetes, agent marketplace, always-on iPhone execution, full offline mode.
