# Direct Blob Links — Review Round 2026-10-04-r3

Use these explicit blob URLs if GitHub tree navigation is unavailable.

## Verification packet

- [Remediation verification targets](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/REMEDIATION_VERIFICATION.md)
- [Evidence limits](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/EVIDENCE_LIMITS.md)
- [Review prompt](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/REVIEW_PROMPT.md)

## Identity / API boundary

- [backend/app/auth.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/source/backend/app/auth.py)
- [backend/app/main.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/source/backend/app/main.py)
- [backend/app/routers/labs.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/source/backend/app/routers/labs.py)

## Memory / scope / authority

- [runtime/memory_trust.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/source/runtime/memory_trust.py)
- [runtime/labs.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/source/runtime/labs.py)
- [runtime/authority.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/source/runtime/authority.py)

## Knowledge ingestion

- [runtime/knowledge_lifecycle.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/source/runtime/knowledge_lifecycle.py)
- [runtime/knowledge_reconciliation.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/source/runtime/knowledge_reconciliation.py)

## E2E boundary

- [tools/production_e2e_smoke.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/source/tools/production_e2e_smoke.py)

## Negative tests

- [tests/test_security_boundaries.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/tests/test_security_boundaries.py)
- [tests/test_federated_coordination.py](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/tests/test_federated_coordination.py)

## Architecture contracts

- [FROZEN_SPEC_v0.1.md](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/architecture/FROZEN_SPEC_v0.1.md)
- [FEDERATED_AUTHORITY_v0.1_ADDENDUM.md](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/architecture/FEDERATED_AUTHORITY_v0.1_ADDENDUM.md)
- [LIVING_ORGANIZATIONAL_KNOWLEDGE_v0.1_ADDENDUM.md](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/architecture/LIVING_ORGANIZATIONAL_KNOWLEDGE_v0.1_ADDENDUM.md)
- [GOVERNED_RECORD_WRITER_v0.1_ADDENDUM.md](https://github.com/ringoincidents/llm-holdings-review/blob/main/snapshots/2026-10-04-r3/architecture/GOVERNED_RECORD_WRITER_v0.1_ADDENDUM.md)
