# Module Boundaries v0.1

This document operationalizes the frozen repository architecture. It does not amend it.

## Dependency direction

```text
apps/mobile ───────REST──────> backend/app
                                 │
                                 ▼
                              runtime
                            /    |    \
                         s1   gateway  schemas
                               │
                            providers
```

## Rules

### backend/app
Transport only: FastAPI application, HTTP routers and request/response wiring.

It MUST NOT own:
- agent definitions
- model providers
- S1 policy
- orchestration logic
- governance policy
- domain persistence models

### runtime
Owns Case/Task/Decision/Evidence/Artifact/Approval/Event state, agent registry, orchestration, governance and runtime persistence.

It may depend on stable S1 and Gateway surfaces. It must not know vendor account credentials.

### gateway
Owns model-provider adapters and deterministic model-policy resolution across task, risk, complexity and cost constraints.

Agents use model policies, not provider/model names. Gateway resolves the concrete provider/model target before invocation.

### s1
Owns D1 Decision Intelligence. TASK-003 formalizes the provider interface; TASK-012 makes S1-Bench-001 executable.

### tools
Owns registered tools, schemas, permissions, deterministic permission risk floors and executors. TASK-006 implements this boundary; runtime governance integrates it with kill switches, audit Events and ExecutionRun telemetry.

### knowledge
Owns structured Holdings knowledge access and read-only client-state adapters. v0.1 does not introduce a vector database. The first client adapter is QuanTrade and preserves source URLs for repository-backed state artifacts; it does not own trading execution.

### evals
Owns cross-runtime quality/cost/latency evaluation assets.

### schemas
Owns transport/data contracts and portable schema examples.

### tests
Repository-level verification. Architectural invariants belong here, not only in prose.

## Forbidden shortcuts

- No model output stored as Evidence.
- No provider name embedded in Agent identity.
- No live-provider logic inside FastAPI routers.
- No architecture change justified only by a chat message.
