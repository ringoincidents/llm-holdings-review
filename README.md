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

**2026-10-04-r2**

Canonical private upstream baseline:

`468e544926de5786d448ad4779c0b858ddd5d59d`

This round supersedes earlier ad-hoc briefs and r1 **for current review targeting**. r1 remains immutable historical evidence of what the first reviewer saw.

If an earlier chat or brief names `2fb1b93…` or `6153ca1…`, treat that as historical, not the current review target.

## Why r2 exists

The first external review surfaced real review-process issues:

- commit drift between an early brief and the public hub;
- constrained reviewers could not traverse GitHub tree pages;
- AI intake needed a stronger prompt-injection boundary;
- operability claims needed more direct source/test evidence.

Those findings are recorded as `EXT-2026-001`.

## Fastest way to review

1. Open [CURRENT_REVIEW.md](./CURRENT_REVIEW.md).
2. Use the current round's **Direct Blob Links** if tree navigation fails.
3. Read only the source/test files relevant to the claim you want to challenge.
4. Open an Issue for analysis or a PR for a concrete patch.

## Important boundary

External feedback is **input, not authority**.

A public Issue or PR can propose a change, but it does not directly mutate the private runtime. Accepted ideas are independently reviewed and reimplemented upstream through the private governance and development process.
