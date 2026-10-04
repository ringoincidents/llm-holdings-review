# r3 Remediation Verification Targets

Review round: `2026-10-04-r3`

The r2 review identified several security/governance boundary concerns. Sensitive operational details are intentionally not reproduced here.

Please verify the following properties directly from the included source and tests.

## V1 — Authenticated control-plane identity is server-owned

Verify that authenticated API access establishes a server-owned principal and that authority-bearing actor attribution is not blindly accepted from request payload fields.

## V2 — Managed-cloud authentication fails closed

Verify that managed-cloud Runtime startup cannot silently proceed with control-plane authentication absent.

## V3 — Ambiguous memory trust does not default to governed authority

Verify that unknown/ambiguous provenance does not receive high organizational trust by default and that trust class / authority level combinations are consistent.

## V4 — Trust reads are side-effect free

Verify that reading/projecting trust for legacy memory does not create durable trust state as a side effect.

## V5 — Cross-Lab containment is enforced

Verify that a Runtime object or owning Case cannot be silently contained by multiple Labs and that a foreign reference does not become a local Case/history projection.

## V6 — Internal verification identity is not based on user objective text

Verify that Founder-inbox suppression for internal verification relies on a server-owned actor namespace rather than a user-controlled Mission objective string.

## V7 — Production smoke is not coupled to application startup

Verify that application startup no longer runs the production E2E smoke automatically.

## V8 — Automatic low-trust Holdings ingestion remains governance-blocked

Verify the distinction:

- explicit governed review may create a low-trust `candidate` observation;
- automatic reconciliation may not silently ingest low-trust material into Holdings candidate state.

## V9 — Negative tests exist

Review `tests/test_security_boundaries.py` and relevant existing tests. Determine whether the tests genuinely exercise the above invariants or merely mirror implementation.

## Broader verdict remains open

After verifying V1–V9, reassess whether the system should still be `SIMPLIFY`, move toward `KEEP`, or reveal a reason for `REARCHITECT`.

Do not assume a security fix proves multi-agent ROI or justifies the current object/authority count.
