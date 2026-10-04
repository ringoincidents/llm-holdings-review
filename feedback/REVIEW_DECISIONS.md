# External Review Disposition Log

Append-only public record of material external feedback.

## Entry template

```markdown
### EXT-YYYY-NNN — short title

- source: Issue # / PR # / external review reference
- target_snapshot: YYYY-MM-DD-rN
- status: PENDING | ACCEPT | ADAPT | NEEDS_EVIDENCE | REJECT | SUPERSEDED
- reviewed_at:
- claim:
- evidence:
- reasoning:
- upstream_action: none | private work created | already addressed | experiment required
- public_outcome:
```

### EXT-2026-001 — First public review process critique

- source: external AI review relayed by Founder
- target_snapshot: 2026-10-04-r1
- status: ADAPT
- reviewed_at: 2026-10-04
- claim:
  - earlier brief and hub used different baseline commits;
  - explicit blob URLs are needed for reviewers that cannot traverse GitHub tree pages;
  - AI intake of public Issue/PR content creates a prompt-injection risk unless external text is treated strictly as untrusted data;
  - operability claims exceed the evidence available in the public snapshot.
- evidence:
  - r1 public packet;
  - maintainer protocol before hardening;
  - reviewer access failure on tree navigation;
  - absence of production-operability source/test files in r1.
- reasoning:
  - all four findings are valid process or evidence-boundary concerns;
  - mutating r1 would violate the immutable-snapshot rule, so a new r2 round is required.
- upstream_action: public review process adapted; private runtime behavior unchanged
- public_outcome:
  - created 2026-10-04-r2;
  - declared one canonical current baseline;
  - added DIRECT_BLOB_LINKS.md;
  - added requested Lab/authority and operability source/tests;
  - added EVIDENCE_LIMITS.md;
  - strengthened AI intake prompt-injection rules.


### EXT-2026-002 — r2 architectural review: SIMPLIFY

- source: public Issue #3 / external AI review relayed by Founder
- target_snapshot: 2026-10-04-r2
- status: ADAPT
- reviewed_at: 2026-10-04
- claim:
  - retain the strong fail-closed invariants and memory-scope tests;
  - simplify only abstractions that lack distinct enforceable semantics or measured value;
  - production E2E evidence and review-snapshot consistency require stronger verification;
  - multi-agent execution needs a direct single-agent baseline;
  - security-sensitive identity/trust/scope concerns require private verification.
- evidence:
  - selected r2 runtime, router and test files reviewed by the external reviewer;
  - private maintainer verification against current Runtime source;
  - security details intentionally excluded from this public log.
- reasoning:
  - the overall SIMPLIFY verdict is useful, but immediate deletion of A0–A4 or organizational objects is not justified by one partial snapshot;
  - verified security boundaries should be remediated immediately;
  - structural simplification should follow measured semantics/ROI rather than reviewer preference alone.
- upstream_action: private remediation work created; evidence-gathering issues created
- public_outcome:
  - public architectural review preserved as Issue #3;
  - private security findings were independently verified and remediated through governed private work;
  - follow-up evaluation tracks authority-level semantics, direct-single-agent baseline, snapshot drift, provenance taint/revalidation, and explicit E2E verification.
