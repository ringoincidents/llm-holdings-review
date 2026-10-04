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

**2026-10-04-r3 — remediation verification**

Canonical private upstream baseline:

`82c7d21ea21458562401069427db737e697d1307`

r2 remains immutable evidence of the code that produced the second external review and `SIMPLIFY` verdict. r3 is a new post-remediation target created so the same findings can be tested again against changed code.

## Review history in one line

```text
r1 → review-process gaps → EXT-2026-001 → r2
r2 → SIMPLIFY + private boundary findings → EXT-2026-002 → private remediation → r3
```

## Important boundary

External feedback is **input, not authority**.

A public Issue or PR does not directly mutate the private runtime. Accepted findings are independently verified and implemented through private governance.
