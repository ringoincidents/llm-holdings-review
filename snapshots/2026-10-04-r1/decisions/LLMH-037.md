# LLMH-037 — Domain Vision Canon and Governed Record Writing

Status: **ADOPTED / IMPLEMENTING**  
Date: 2026-10-04

## Decision

LLM Holdings will not rely on chat recency, a single model invocation, or the newest implementation artifact to define the current direction of a Lab or company.

Every material domain may maintain a **current canonical vision projection** backed by durable sources, Claims, Decisions, relations, and implementation evidence.

For QuanTrade, the current human-readable canonical projection is:

`ringoincidents/quantrade/QUANTRADE_CANONICAL_VISION.md`

Its North Star is:

> QuanTrade is an AI-native Private Investment Office for one Client. It implements the professional process of understanding the Client, defining mandate and strategy, researching markets, constructing the portfolio, independently controlling risk, reaching governed decisions, managing execution timing, executing within authority, and learning from outcomes.

## Why

QuanTrade repeatedly experienced direction drift:

1. a coherent vision was discussed;
2. implementation accelerated;
3. local experiments and technical issues became more salient than the product purpose;
4. later conversations had to reconstruct the original intent.

This is an organizational-memory failure, not merely a UX problem.

The organization must preserve both history and current truth without allowing “latest chat wins.”

## Canonical record rule

Material direction statements must be classified relative to existing canonical knowledge as one of:

- EXTENDS
- NARROWS
- SUPERSEDES
- EXPERIMENT
- REJECTS
- REFERENCE_ONLY

A new source does not become canonical merely because it is newer.

Canonical promotion must preserve:

- source/provenance;
- author/authority;
- affected Concept;
- relationship to prior Claims;
- rationale;
- implementation state separately from knowledge validity.

## One-shot model boundary

A one-shot API model is a **record drafter**, not an authority that may silently rewrite organizational truth.

Models may:

- summarize a meeting;
- extract candidate Claims;
- propose relations;
- draft a canonical update;
- identify conflicts or missing context.

Models may not, by themselves:

- delete prior sources;
- silently overwrite current Claims;
- infer that implementation equals policy;
- promote a low-trust observation into Founder-level direction;
- treat the newest statement as authoritative without reconciliation.

## Record Writer context contract

When a model is asked to write or update organizational records, the Runtime should provide a bounded Record Context Pack containing, when relevant:

1. the raw source being recorded;
2. current canonical Claims for the same Concepts;
3. unresolved contradictions;
4. relevant Founder/HQ Decisions;
5. bounded superseded history;
6. implementation/action bindings;
7. required record schema;
8. allowed relationship vocabulary;
9. authority/trust metadata;
10. explicit instruction to distinguish fact, interpretation, decision, proposal, experiment, and implementation.

The model should produce a structured draft before human-readable prose.

## Quality and cost principle

Routine notes should use deterministic extraction or cheap models when possible.

Material vision/policy changes receive stronger review:

`deterministic checks → cheap structured draft → reconciliation → higher-quality review only if ambiguity/conflict/impact warrants it`

The organization should spend reasoning cost where a wrong record would cause future work to drift, not on repeatedly rewriting routine prose.

## Human-readable projection

Markdown documents, Founder reports, Lab handbooks, and UI summaries are projections of governed knowledge.

They are useful and should be readable, but they are not independent truth stores.

A projection should state:

- current status;
- effective date;
- what it supersedes or extends;
- what remains historical;
- what is experimental;
- what is implemented vs merely intended.

## QuanTrade domain boundary

Holdings provides shared infrastructure such as Memory, Authority, Audit, Model Gateway, Cost Governance, execution machinery, and organizational learning.

QuanTrade retains domain-native semantics such as:

- Client Mandate;
- Research Case;
- Evidence;
- Investment Thesis;
- Portfolio Proposal;
- Risk Opinion;
- Committee Decision;
- Decision Plan;
- Order/Execution;
- Performance Review.

Generic Runtime objects are implementation substrate and must not silently replace the domain vision.

## Success criterion

A future Lab or API model should be able to enter QuanTrade without prior chat history and answer:

- What is QuanTrade for?
- What changed since the founding vision?
- Which ideas are experiments rather than identity?
- What is current vs superseded?
- Which parts are implemented vs still intended?
- What constraints must not be violated?

without reconstructing the answer from scattered conversations.
