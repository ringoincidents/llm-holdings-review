# Copy/Paste Prompt — r4 Expanded Review

Act as an independent senior software architect reviewing LLM Holdings.

Target snapshot: `2026-10-04-r4`.

Earlier review r2 concluded `SIMPLIFY` with partial code evidence. r3 exposed the security remediation. r4 provides broader implementation evidence.

Your job is to **try to falsify both the project claims and the earlier review**.

1. Read `EXPANDED_VERIFICATION.md`.
2. Use `DIRECT_BLOB_LINKS.md`.
3. Do not infer behavior from docs when code/tests are available.
4. Mark uncertain statements UNVERIFIED.
5. Distinguish:
   - authentication vs authorization,
   - reasoning vs evidence,
   - candidate knowledge vs canonical truth,
   - merge vs deploy,
   - process reachability vs execution health,
   - organizational metaphor vs enforceable Runtime state.
6. Revisit every major r2 finding and label it CLOSED / PARTIAL / STILL OPEN.
7. Identify any new regression created by remediation.
8. Treat multi-agent ROI as OPEN unless there is comparative evidence.
9. Evaluate the representative UI as a real one-person mobile control plane.
10. End with KEEP / SIMPLIFY / REARCHITECT and the five highest-value next changes.

Security-sensitive exploit detail should not be placed in public Issues; follow SECURITY.md.
