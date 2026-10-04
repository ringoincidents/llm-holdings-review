# LLM Holdings — Public Review Hub

This repository is the **public, sanitized review surface** for LLM Holdings.

It is intentionally **not** the production source of truth. The production/runtime repository remains private. Outside reviewers and AI systems can inspect fixed snapshots, submit criticism, propose patches, and leave a durable review trail.

## Start here

- [Current review round](./CURRENT_REVIEW.md)
- [Direct review links](./DIRECT_REVIEW_LINKS.md)
- [How review rounds work](./REVIEW_PROTOCOL.md)
- [How to contribute feedback or patches](./CONTRIBUTING.md)
- [Maintainer / AI intake protocol](./MAINTAINER_PROTOCOL.md)
- [Review history](./REVIEW_HISTORY.md)
- [Feedback disposition log](./feedback/REVIEW_DECISIONS.md)

## Current round

**2026-10-04-r4 — expanded implementation evidence**

Canonical private upstream baseline:

`3a23a806301669a727eee0b9613ede9c95415f4d`

r2 remains the historical target that produced the `SIMPLIFY` verdict. r3 captured the first remediation verification. r4 broadens the evidence surface to include authority, API schemas, Lab scope modules, background execution, telemetry, Runtime Ops, Record Writer, knowledge/action reconciliation, D1/Clef, and representative mobile UI.

## Review history in one line

```text
r1 → review-process gaps → EXT-2026-001 → r2
r2 → SIMPLIFY + boundary findings → EXT-2026-002 → remediation → r3
r2 supplement → operability/scope evidence → Runtime fixes → r4 expanded review
```

## Important boundary

External feedback is **input, not authority**.

A public Issue or PR does not directly mutate the private runtime. Accepted findings are independently verified and implemented through private governance.
