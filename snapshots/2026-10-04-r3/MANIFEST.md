# Snapshot Manifest — 2026-10-04-r3

- review_round: `2026-10-04-r3`
- created_at: `2026-10-04`
- canonical_private_upstream_commit: `82c7d21ea21458562401069427db737e697d1307`
- predecessor_review_target: `2026-10-04-r2`
- triggering_review: `EXT-2026-002`
- purpose: post-remediation verification
- policy: selected sanitized snapshot; not a full private repository mirror

## Included evidence classes

- auth / app startup boundary
- Lab API routing
- memory trust
- Lab object scope
- federated authority
- knowledge lifecycle / reconciliation
- dedicated negative security-boundary tests
- existing federated coordination tests
- selected architecture contracts

## Explicit exclusions

No credentials, secrets, private client data, raw organizational memory, production deployment config, full task backlog, or complete private source tree.
