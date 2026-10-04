# Direct Blob Links — Review Round 2026-10-04-r2

Some automated reviewers cannot traverse GitHub `tree` pages reliably. Use these explicit blob URLs.

## Highest-priority implementation review

1. [memory_trust.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/source/runtime/memory_trust.py)
2. [runtime/labs.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/source/runtime/labs.py)
3. [backend/app/routers/labs.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/source/backend/app/routers/labs.py)
4. [test_production_e2e_smoke.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/tests/test_production_e2e_smoke.py)
5. [test_federated_coordination.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/tests/test_federated_coordination.py)

## Operability / runtime controls

- [runtime_ops.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/source/runtime/runtime_ops.py)
- [telemetry.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/source/runtime/telemetry.py)
- [test_runtime_ops.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/tests/test_runtime_ops.py)

## Knowledge / record correctness

- [record_writer.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/source/runtime/record_writer.py)
- [test_record_writer.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/tests/test_record_writer.py)
- [test_runtime_knowledge_reconciliation.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/tests/test_runtime_knowledge_reconciliation.py)

## Decision layer

- [clef.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/source/s1/providers/clef.py)

## Architecture contracts

- [FROZEN_SPEC_v0.1.md](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/architecture/FROZEN_SPEC_v0.1.md)
- [MODULE_BOUNDARIES_v0.1.md](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/architecture/MODULE_BOUNDARIES_v0.1.md)
- [FEDERATED_AUTHORITY_v0.1_ADDENDUM.md](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/architecture/FEDERATED_AUTHORITY_v0.1_ADDENDUM.md)
- [LIVING_ORGANIZATIONAL_KNOWLEDGE_v0.1_ADDENDUM.md](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/architecture/LIVING_ORGANIZATIONAL_KNOWLEDGE_v0.1_ADDENDUM.md)
- [GOVERNED_RECORD_WRITER_v0.1_ADDENDUM.md](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/architecture/GOVERNED_RECORD_WRITER_v0.1_ADDENDUM.md)

## Product surface

- [QuanTradePrivateOfficeSurface.tsx](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r2/ui/QuanTradePrivateOfficeSurface.tsx)

These URLs are intentionally explicit so a reviewer can open individual files without directory traversal.
