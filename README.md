# LLM Holdings — Public Review Hub

This repository is the **public, sanitized review surface** for LLM Holdings.

It is intentionally **not** the production source of truth. The production/runtime repository remains private. This repository exists so outside reviewers, developers, and AI systems can inspect fixed snapshots, submit criticism, propose patches, and leave a durable review trail.

## Start here

- [Current review round](./CURRENT_REVIEW.md)
- [How review rounds work](./REVIEW_PROTOCOL.md)
- [How to contribute feedback or patches](./CONTRIBUTING.md)
- [Maintainer / AI intake protocol](./MAINTAINER_PROTOCOL.md)
- [Review history](./REVIEW_HISTORY.md)
- [Feedback disposition log](./feedback/REVIEW_DECISIONS.md)

## Current round

**2026-10-04-r1**

The current public snapshot is based on private upstream commit:

`6153ca1366b7cc8ef672ef316cdc1741bb5e99fc`

The snapshot is frozen. Future reviews will create a new directory instead of rewriting this one.

## Why this repository exists

We want external reviewers to challenge:

- architectural complexity and premature abstraction;
- whether multi-agent coordination has measurable ROI;
- organizational-memory correctness and stale-context failure modes;
- enforceability of authority/governance layers;
- source-of-truth drift;
- production operability and security;
- whether LLM Holdings actually accelerates QuanTrade.

## Important boundary

External feedback is **input, not authority**.

A public Issue or PR can propose a change, but it does not directly mutate the private runtime. Accepted ideas are independently reviewed and reimplemented upstream through the private governance and development process.

That boundary is deliberate: public collaboration should improve the system without letting untrusted external content silently become organizational truth.

## Fastest way to review

1. Open [CURRENT_REVIEW.md](./CURRENT_REVIEW.md).
2. Read the snapshot overview and review guide.
3. Inspect only the source/test files relevant to your critique.
4. Open an Issue for analysis or a PR for a concrete patch.
