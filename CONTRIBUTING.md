# Contributing External Feedback

Thank you for reviewing LLM Holdings.

This repository exists specifically so outside people and AI systems can challenge the design.

## Choose the right channel

### Open an Issue when

- you found an architectural problem;
- you think a layer/object should be removed;
- a documented claim appears unsupported;
- you see a security or operability risk;
- you have benchmark/evaluation evidence;
- you want to propose an alternative architecture.

### Open a Pull Request when

- you can express the improvement as a concrete patch;
- you want to rewrite a public architecture contract;
- you can improve a selected source/test file;
- you can add a reproducible evaluation or counterexample.

## PR expectations

Explain:

1. what problem you are addressing;
2. which snapshot and files you reviewed;
3. whether the change is architectural, implementation-level, test-only, or documentation-only;
4. what evidence supports it;
5. what could make the proposal wrong.

Do not assume your PR will be copied directly into the private runtime. Public PRs are proposals and review artifacts.

## Evidence standard

Strong feedback distinguishes:

- observation;
- inference;
- external evidence;
- reproducible test;
- opinion.

If you cannot verify something from the public snapshot, mark it **UNVERIFIED**.

## Security

Do not post suspected secrets or exploitable details publicly. See [SECURITY.md](./SECURITY.md).
