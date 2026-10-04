# Current Review Round

## Round

`2026-10-04-r2`

## Canonical private upstream baseline

`468e544926de5786d448ad4779c0b858ddd5d59d`

If an older brief or chat references another commit, this file wins for the current external-review target.

## Review packet

- [README](./snapshots/2026-10-04-r2/README.md)
- [System Overview](./snapshots/2026-10-04-r2/SYSTEM_OVERVIEW.md)
- [Review Guide](./snapshots/2026-10-04-r2/REVIEW_GUIDE.md)
- [Direct Blob Links](./snapshots/2026-10-04-r2/DIRECT_BLOB_LINKS.md)
- [Evidence Limits](./snapshots/2026-10-04-r2/EVIDENCE_LIMITS.md)
- [Manifest](./snapshots/2026-10-04-r2/MANIFEST.md)
- [Copy/Paste Review Prompt](./snapshots/2026-10-04-r2/REVIEW_PROMPT.md)

## Priority code review order

1. `source/runtime/memory_trust.py`
2. `source/runtime/labs.py`
3. `source/backend/app/routers/labs.py`
4. `tests/test_production_e2e_smoke.py`
5. `tests/test_federated_coordination.py`

Use the absolute URLs in **Direct Blob Links** when automated navigation cannot open folder pages.

## How to respond

- Conceptual critique → open an Issue.
- Concrete code/document change → open a PR against this public repository.
- Security concern → follow `SECURITY.md`, not a public Issue.
