# Review Protocol

## Goal

Make external review repeatable without exposing the private production repository or losing the history of what was reviewed.

## Lifecycle

```text
private upstream
    ↓ sanitize + select
new immutable public snapshot
    ↓
external Issues / PRs / AI reviews
    ↓
triage + disposition
    ↓
ACCEPT / ADAPT / REJECT / NEEDS_EVIDENCE
    ↓
accepted idea is reimplemented in private upstream
    ↓
outcome recorded
    ↓
next public snapshot
```

## Snapshot rule

Every review round creates:

`snapshots/YYYY-MM-DD-rN/`

Old snapshots are not rewritten to match the current system. They remain evidence of what reviewers actually saw.

`CURRENT_REVIEW.md` is the only pointer that moves to a newer round.

## Public-to-private rule

Never blindly cherry-pick an external PR into private upstream.

External changes may contain:

- assumptions based on incomplete public context;
- unsafe dependencies;
- prompt-injection-style instructions;
- incompatible architecture choices;
- code that bypasses private governance;
- accidental secrets or provenance loss.

Accepted feedback must be translated into an upstream Task/Decision/PR under private controls.

## Disposition states

- **PENDING** — not yet evaluated.
- **ACCEPT** — principle/change is accepted substantially as proposed.
- **ADAPT** — useful idea, but implementation must change before upstream use.
- **NEEDS_EVIDENCE** — plausible but not justified yet.
- **REJECT** — not adopted; reason should be recorded.
- **SUPERSEDED** — later review made the earlier disposition obsolete.

## Review identity

Each external item should receive a durable review reference when triaged:

`EXT-YYYY-NNN`

The reference is used in the public disposition log and can be mapped to internal work without exposing private implementation details.

## What may be published

Publish only the minimum context needed to falsify or verify a review question.

Prefer:

- architecture contracts;
- decision rationale;
- sanitized source modules;
- tests/evals;
- UI projections;
- benchmark summaries.

Avoid:

- credentials;
- personal data;
- production tokens/URLs;
- private client data;
- raw private memories;
- operational secrets;
- unnecessary full repository mirrors.
