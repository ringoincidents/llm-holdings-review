# r4 Expanded Verification Questions

## A. Authority

Inspect `runtime/authority.py`, `schemas/api.py`, `runtime/organization.py`, and the federated tests.

- Do A0–A4 have distinct enforceable semantics?
- Who can settle A2 and A3 pending resolutions?
- Is the reviewer still justified in recommending three states?
- Mark the answer VERIFIED / PARTIAL / FAILED / UNVERIFIED.

## B. Lab scope

Inspect:

- `runtime/labs.py`
- `runtime/lab_work.py`
- `runtime/lab_seats.py`
- `runtime/lab_context.py`
- `backend/app/routers/labs.py`
- security/federated tests.

Verify whether the r2 cross-Lab object/history leak is closed and look for equivalent leaks in Work, Seat, Context, Memory and Mission paths.

## C. Operability

Inspect:

- `runtime/background_execution.py`
- `runtime/telemetry.py`
- `runtime/runtime_ops.py`
- `backend/app/routers/system.py`
- `tests/test_runtime_ops.py`
- `tests/test_lab_history.py`.

Distinguish:
- retry support;
- durable queued/running Jobs;
- leases and heartbeat recovery;
- stalled/expired lease visibility;
- provider/run telemetry;
- deployment/CI alignment;
- what remains unmeasured.

Do not treat `process_reachable` as service health.

## D. Production E2E

Inspect `tools/production_e2e_smoke.py`, `backend/app/main.py`, and relevant tests.

Determine:
- whether startup is now decoupled from production smoke;
- whether the smoke itself is a real environment E2E when explicitly executed;
- what CI/staging evidence is still missing.

## E. Memory / Knowledge / Record Writer

Inspect:

- `runtime/record_writer.py`
- `runtime/knowledge_lifecycle.py`
- `runtime/knowledge_reconciliation.py`
- `runtime/shared_os_change.py`
- `runtime/action_reconciliation.py`
- associated tests.

Check:
- model output vs Evidence boundary;
- candidate vs current truth;
- supersession/history preservation;
- whether PR merge and deployment are distinct states;
- whether Projection/Action Binding are unnecessarily durable;
- taint propagation / freshness / `last_verified` gaps.

## F. D1 / Clef

Inspect `s1/providers/clef.py`.

Decide whether D1 is:
- a useful interchangeable fixed-choice decision layer;
- an abstraction without present value;
- or actively harmful complexity.

Do not judge from the name alone; judge interface, fallback, tests/evidence, and whether deterministic D0 would suffice.

## G. Product / UI

Inspect representative mobile surfaces:

- Founder Control Plane
- Founder Knowledge Observatory
- Lab Workspace
- Runtime Dev Console
- QuanTrade Private Office

Judge whether the organizational model produces a usable control plane for one mobile-first Founder, or merely exposes backend abstractions.

## H. Multi-agent ROI

The default remains one strong model + deterministic tools unless measured evidence says otherwise.

If no comparative experiment is included, keep this OPEN rather than assuming either architecture wins.

## I. Final verdict

Return:
- CLOSED r2 findings
- PARTIAL r2 findings
- STILL OPEN findings
- NEW findings
- revised KEEP / SIMPLIFY / REARCHITECT verdict
- top five changes with expected user value, not just architectural elegance.
