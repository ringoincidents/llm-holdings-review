# Copy/Paste Prompt — r3 Remediation Verification

Act as an independent senior software/security architect reviewing LLM Holdings.

Target snapshot: `2026-10-04-r3`.

This round follows an earlier r2 review that concluded `SIMPLIFY` with partial code evidence.

Your task is **not** to praise the remediation. Try to falsify it.

1. Read `REMEDIATION_VERIFICATION.md`.
2. Use `DIRECT_BLOB_LINKS.md`; do not rely on tree navigation.
3. For V1–V9, return VERIFIED / PARTIAL / FAILED / UNVERIFIED with file/function evidence.
4. Look for bypasses and regressions, but do not publish sensitive exploit instructions.
5. Distinguish authentication from authorization/principal binding.
6. Verify that memory trust fails closed without preventing legitimate low-trust candidate observation.
7. Verify that cross-Lab references do not become cross-Lab containment.
8. Verify that app startup is decoupled from the explicit production smoke.
9. Review negative tests for behavioral value rather than test count.

Then update the architectural verdict:

- KEEP
- SIMPLIFY
- REARCHITECT

Also state which original r2 findings are CLOSED, PARTIAL, or STILL OPEN.

Do not infer live production deployment from source/CI evidence alone.
