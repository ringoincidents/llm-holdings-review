# Review Round 2026-10-04-r2

This round **supersedes 2026-10-04-r1 as the canonical external review target**.

Private upstream baseline:
`468e544926de5786d448ad4779c0b858ddd5d59d`

## Why r2 exists

The first external reviewer found four process gaps:

1. an older ad-hoc brief referenced a different commit;
2. some reviewers can open explicit blob URLs but cannot traverse GitHub tree pages;
3. AI intake of public Issues/PRs needs a stronger prompt-injection boundary;
4. operability claims needed more direct source/test evidence.

This round addresses those gaps without mutating the already-published r1 snapshot.

## Read first

1. [SYSTEM_OVERVIEW.md](./SYSTEM_OVERVIEW.md)
2. [REVIEW_GUIDE.md](./REVIEW_GUIDE.md)
3. [DIRECT_BLOB_LINKS.md](./DIRECT_BLOB_LINKS.md)
4. [EVIDENCE_LIMITS.md](./EVIDENCE_LIMITS.md)
5. [MANIFEST.md](./MANIFEST.md)
6. [REVIEW_PROMPT.md](./REVIEW_PROMPT.md)

## Canonical rule

If any earlier brief, chat, or review packet names a different upstream commit, treat it as historical.  
For this review round, the only canonical upstream baseline is:

`468e544926de5786d448ad4779c0b858ddd5d59d`
