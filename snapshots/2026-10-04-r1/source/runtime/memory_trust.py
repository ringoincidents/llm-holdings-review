"""Trust/provenance gates for organizational memory.

TASK-041 deliberately uses a companion table so production SQLite rows are not
ALTERed in place. Existing memory can be backfilled explicitly at startup.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import OrganizationalMemory, OrganizationalMemoryTrust


TRUST_RANK = {
    "external_untrusted": 0,
    "external_verified": 1,
    "inferred_internal": 2,
    "governed_internal": 3,
    "authoritative_founder": 4,
}

AUTHORITY_FOR_TRUST = {
    "external_untrusted": "A0",
    "external_verified": "A1",
    "inferred_internal": "A0",
    "governed_internal": "A3",
    "authoritative_founder": "A4",
}

EXTERNAL_SOURCE_TYPES = {
    "external",
    "external_signal",
    "github",
    "repository",
    "web",
    "paper",
    "tool_output",
    "retrieved_document",
}

PROTECTED_MEMORY_TYPES = {
    "constitution",
    "principle",
    "policy",
    "preference",
    "founder_preference",
    "authority",
}


class MemoryTrustError(ValueError):
    pass


def infer_trust_class(*, created_by: str, source_type: str | None) -> str:
    source = (source_type or "").strip().lower()
    actor = (created_by or "system").strip().lower()
    if source in EXTERNAL_SOURCE_TYPES or source.startswith("external"):
        return "external_untrusted"
    if actor == "founder":
        return "authoritative_founder"
    if actor == "hq" or actor.startswith("hq:") or source in {
        "operating_principle",
        "decision",
        "governed_promotion",
    }:
        return "governed_internal"
    if actor.startswith("agent") or actor.startswith("model"):
        return "inferred_internal"
    return "governed_internal"


def _validate_trust_class(trust_class: str) -> None:
    if trust_class not in TRUST_RANK:
        raise MemoryTrustError(f"Unsupported memory trust class: {trust_class}")


def ensure_memory_trust(
    db: Session,
    memory: OrganizationalMemory,
    *,
    origin_actor: str | None = None,
    source_type: str | None = None,
    trust_class: str | None = None,
    authority_level: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> OrganizationalMemoryTrust:
    existing = db.get(OrganizationalMemoryTrust, memory.id)
    if existing is not None:
        return existing

    resolved_source = (source_type or memory.source_type or "internal").strip()
    resolved_trust = trust_class or infer_trust_class(
        created_by=memory.created_by,
        source_type=resolved_source,
    )
    _validate_trust_class(resolved_trust)
    resolved_authority = authority_level or AUTHORITY_FOR_TRUST[resolved_trust]
    if resolved_authority not in {"A0", "A1", "A2", "A3", "A4"}:
        raise MemoryTrustError("Invalid memory authority level")

    row = OrganizationalMemoryTrust(
        memory_id=memory.id,
        origin_actor=(origin_actor or memory.created_by or "system").strip()[:128],
        source_type=resolved_source[:64],
        trust_class=resolved_trust,
        target_scope=f"{memory.scope_type}:{memory.scope_id}"[:128],
        authority_level=resolved_authority,
        provenance_json=json.dumps(provenance or {}, ensure_ascii=False, sort_keys=True),
    )
    db.add(row)
    db.flush()
    return row


def trust_for_memory(
    db: Session,
    memory: OrganizationalMemory,
) -> OrganizationalMemoryTrust:
    row = db.get(OrganizationalMemoryTrust, memory.id)
    if row is not None:
        return row
    return ensure_memory_trust(db, memory)


def validate_memory_write(
    db: Session,
    *,
    scope_type: str,
    scope_id: str,
    memory_type: str,
    created_by: str,
    source_type: str | None,
    trust_class: str | None = None,
    supersedes_id: str | None = None,
    governed_promotion: bool = False,
) -> tuple[str, str]:
    resolved_trust = trust_class or infer_trust_class(
        created_by=created_by,
        source_type=source_type,
    )
    _validate_trust_class(resolved_trust)

    if (
        scope_type == "holdings"
        and resolved_trust in {"external_untrusted", "external_verified", "inferred_internal"}
        and not governed_promotion
    ):
        raise MemoryTrustError(
            "Low-trust or external content cannot directly enter Holdings shared memory"
        )

    if memory_type in PROTECTED_MEMORY_TYPES and resolved_trust not in {
        "governed_internal",
        "authoritative_founder",
    }:
        raise MemoryTrustError(
            "Protected organizational memory requires governed internal authority"
        )

    if supersedes_id:
        target = db.get(OrganizationalMemory, supersedes_id)
        if target is None:
            raise MemoryTrustError("Superseded memory does not exist")
        if target.scope_type != scope_type or target.scope_id != scope_id:
            raise MemoryTrustError("Memory cannot supersede across scopes")
        target_trust = trust_for_memory(db, target).trust_class
        if TRUST_RANK[resolved_trust] < TRUST_RANK[target_trust]:
            raise MemoryTrustError(
                "Lower-trust memory cannot supersede higher-trust memory"
            )

    return resolved_trust, AUTHORITY_FOR_TRUST[resolved_trust]


def backfill_memory_trust(db: Session) -> int:
    created = 0
    rows = db.scalars(select(OrganizationalMemory)).all()
    for memory in rows:
        if db.get(OrganizationalMemoryTrust, memory.id) is None:
            ensure_memory_trust(db, memory)
            created += 1
    return created


def memory_allowed_in_context(db: Session, memory: OrganizationalMemory) -> bool:
    """Fail closed for raw external content; governed promotion creates a new memory."""
    return trust_for_memory(db, memory).trust_class != "external_untrusted"


def memory_trust_payload(db: Session, memory: OrganizationalMemory) -> dict[str, Any]:
    trust = trust_for_memory(db, memory)
    try:
        provenance = json.loads(trust.provenance_json or "{}")
    except json.JSONDecodeError:
        provenance = {}
    return {
        "origin_actor": trust.origin_actor,
        "source_type": trust.source_type,
        "trust_class": trust.trust_class,
        "target_scope": trust.target_scope,
        "authority_level": trust.authority_level,
        "provenance": provenance,
    }
