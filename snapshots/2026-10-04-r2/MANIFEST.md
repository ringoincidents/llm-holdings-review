# Snapshot Manifest

- review_round: `2026-10-04-r2`
- created_at: `2026-10-04`
- canonical_private_upstream_commit: `468e544926de5786d448ad4779c0b858ddd5d59d`
- supersedes_for_review: `2026-10-04-r1`
- policy: selected sanitized snapshot; not a full repository mirror

## Added because of EXT-2026-001

- explicit blob URL index;
- runtime/labs.py;
- backend/app/routers/labs.py;
- tests/test_production_e2e_smoke.py;
- runtime/runtime_ops.py;
- tests/test_runtime_ops.py;
- runtime/telemetry.py;
- explicit prompt-injection intake hardening;
- explicit evidence-limit document.

## Exclusions remain

No credentials, private client data, raw private memory, production secrets, full deployment configuration, full task backlog, or full private repository mirror.
