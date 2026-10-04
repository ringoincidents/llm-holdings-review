"""Automatic source ingestion into governed candidate knowledge (TASK-047 C/D).

This compiler converts durable organizational source objects into *candidate*
KnowledgeClaims when an existing stable Concept can be narrowed safely. It does
not make the candidate current, does not auto-supersede, and records unresolved
or governance-blocked inputs instead of guessing.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base
from .knowledge_lifecycle import (
    KnowledgeLifecycleError,
    add_relation,
    create_claim,
    now_utc,
    uid,
)
from .knowledge_retrieval import reconciliation_preview
from .memory_trust import infer_trust_class, trust_for_memory
from .events import emit
from .models import Artifact, Decision, FounderNote, OrganizationalMemory


SUPPORTED_SOURCE_TYPES = {
    "founder_note",
    "organizational_memory",
    "decision",
    "artifact",
}


class KnowledgeReconciliationError(ValueError):
    pass


class KnowledgeReconciliationRecord(Base):
    """Idempotent audit record for one durable source reconciliation."""

    __tablename__ = "knowledge_reconciliation_records"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "scope_type",
            "scope_id",
            name="uq_knowledge_reconciliation_source_scope",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: uid("KREC")
    )
    source_type: Mapped[str] = mapped_column(String(48), index=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    source_hash: Mapped[str] = mapped_column(String(64), index=True)
    scope_type: Mapped[str] = mapped_column(String(32), index=True)
    scope_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    concept_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_concepts.id"), nullable=True, index=True
    )
    claim_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_claims.id"), nullable=True, index=True
    )
    target_claim_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_claims.id"), nullable=True, index=True
    )
    relationship_preview: Mapped[str | None] = mapped_column(
        String(48), nullable=True
    )
    preview_json: Mapped[str] = mapped_column(Text, default="{}")
    message: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(
        String(128), default="system:knowledge_reconciliation"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


@dataclass(frozen=True)
class ReconciliationSource:
    source_type: str
    source_id: str
    text: str
    created_by: str
    memory_id: str | None = None


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_from_founder_note(
    db: Session,
    *,
    source_id: str,
    scope_type: str,
    scope_id: str,
) -> ReconciliationSource:
    note = db.get(FounderNote, source_id)
    if note is None:
        raise KnowledgeReconciliationError("FounderNote not found")
    if note.proposed_lab_id:
        if scope_type != "lab" or scope_id != note.proposed_lab_id:
            raise KnowledgeReconciliationError(
                "FounderNote proposed for a Lab cannot be widened to another scope"
            )
    elif scope_type != "holdings" or scope_id != "holdings":
        raise KnowledgeReconciliationError(
            "Unscoped FounderNote defaults to Holdings scope"
        )
    return ReconciliationSource(
        source_type="founder_note",
        source_id=note.id,
        text=note.raw_text.strip(),
        created_by=note.created_by or "founder",
    )


def _source_from_memory(
    db: Session,
    *,
    source_id: str,
    scope_type: str,
    scope_id: str,
) -> ReconciliationSource:
    memory = db.get(OrganizationalMemory, source_id)
    if memory is None:
        raise KnowledgeReconciliationError("OrganizationalMemory not found")
    if memory.scope_type != scope_type or memory.scope_id != scope_id:
        raise KnowledgeReconciliationError(
            "OrganizationalMemory reconciliation must preserve exact source scope"
        )
    return ReconciliationSource(
        source_type="organizational_memory",
        source_id=memory.id,
        text=memory.content.strip(),
        created_by=memory.created_by or "system",
        memory_id=memory.id,
    )


def _source_from_decision(
    db: Session,
    *,
    source_id: str,
) -> ReconciliationSource:
    decision = db.get(Decision, source_id)
    if decision is None:
        raise KnowledgeReconciliationError("Decision not found")
    if decision.accepted is not True:
        raise KnowledgeReconciliationError(
            "Only accepted Decisions are eligible for automatic knowledge ingestion"
        )
    resolution = (decision.human_decision or decision.prediction or "").strip()
    text = "\n".join(
        part for part in [decision.question.strip(), resolution] if part
    )
    if not text:
        raise KnowledgeReconciliationError("Accepted Decision has no usable content")
    actor = (
        "founder"
        if decision.provider == "founder" or decision.human_decision
        else "hq"
    )
    return ReconciliationSource(
        source_type="decision",
        source_id=decision.id,
        text=text,
        created_by=actor,
    )


def _source_from_artifact(
    db: Session,
    *,
    source_id: str,
) -> ReconciliationSource:
    artifact = db.get(Artifact, source_id)
    if artifact is None:
        raise KnowledgeReconciliationError("Artifact not found")
    text = (artifact.content or "").strip()
    if not text:
        raise KnowledgeReconciliationError("Artifact has no usable content")
    producer = artifact.producer_id or artifact.producer_type or "agent"
    return ReconciliationSource(
        source_type="artifact",
        source_id=artifact.id,
        text=text,
        created_by=f"agent:{producer}",
    )


def resolve_source(
    db: Session,
    *,
    source_type: str,
    source_id: str,
    scope_type: str,
    scope_id: str,
) -> ReconciliationSource:
    if source_type not in SUPPORTED_SOURCE_TYPES:
        raise KnowledgeReconciliationError("Unsupported reconciliation source type")
    if scope_type not in {"employee", "lab", "holdings"}:
        raise KnowledgeReconciliationError("Unsupported reconciliation scope")

    if source_type == "founder_note":
        return _source_from_founder_note(
            db,
            source_id=source_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )
    if source_type == "organizational_memory":
        return _source_from_memory(
            db,
            source_id=source_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )
    if source_type == "decision":
        return _source_from_decision(db, source_id=source_id)
    return _source_from_artifact(db, source_id=source_id)


def _record_payload(record: KnowledgeReconciliationRecord) -> dict[str, Any]:
    try:
        preview = json.loads(record.preview_json or "{}")
    except json.JSONDecodeError:
        preview = {}
    return {
        "id": record.id,
        "source_type": record.source_type,
        "source_id": record.source_id,
        "source_hash": record.source_hash,
        "scope_type": record.scope_type,
        "scope_id": record.scope_id,
        "status": record.status,
        "concept_id": record.concept_id,
        "claim_id": record.claim_id,
        "target_claim_id": record.target_claim_id,
        "relationship_preview": record.relationship_preview,
        "preview": preview,
        "message": record.message,
        "created_by": record.created_by,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def get_reconciliation_record(
    db: Session,
    *,
    record_id: str,
) -> dict[str, Any]:
    record = db.get(KnowledgeReconciliationRecord, record_id)
    if record is None:
        raise KnowledgeReconciliationError("Knowledge reconciliation record not found")
    return _record_payload(record)


def _best_relationship(preview: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return the strongest relation across all retrieved Concept candidates."""
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for candidate in preview.get("candidates") or []:
        for relationship in candidate.get("relationship_previews") or []:
            pairs.append((candidate, relationship))
    if not pairs:
        candidates = preview.get("candidates") or []
        return (candidates[0], None) if candidates else (None, None)

    relation_priority = {
        "duplicate": 5,
        "possible_conflict_or_supersession": 4,
        "possible_extends": 3,
        "possible_narrows": 3,
        "related": 2,
        "unrelated": 0,
    }
    pairs.sort(
        key=lambda pair: (
            -float(pair[1].get("confidence") or 0.0),
            -relation_priority.get(str(pair[1].get("relationship") or ""), 1),
            -float(pair[0].get("score") or 0.0),
            str(pair[0].get("concept_key") or ""),
            str(pair[1].get("target_claim_id") or ""),
        )
    )
    return pairs[0]


def ingest_source(
    db: Session,
    *,
    source_type: str,
    source_id: str,
    scope_type: str,
    scope_id: str,
    top_k: int = 8,
    created_by: str = "system:knowledge_reconciliation",
) -> dict[str, Any]:
    """Compile one durable source into a governed candidate Claim when safe.

    The function intentionally stops before current/superseded truth mutation.
    """
    source = resolve_source(
        db,
        source_type=source_type,
        source_id=source_id,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    if not source.text:
        raise KnowledgeReconciliationError("Reconciliation source is empty")
    source_hash = _hash_text(source.text)

    record = db.scalar(
        select(KnowledgeReconciliationRecord).where(
            KnowledgeReconciliationRecord.source_type == source_type,
            KnowledgeReconciliationRecord.source_id == source_id,
            KnowledgeReconciliationRecord.scope_type == scope_type,
            KnowledgeReconciliationRecord.scope_id == scope_id,
        )
    )
    if record is not None:
        if record.source_hash != source_hash:
            record.status = "source_changed"
            record.message = (
                "Durable source content changed under the same identity; "
                "automatic rewrite is refused."
            )
            db.flush()
            return _record_payload(record)
        if record.status in {
            "duplicate",
            "candidate_created",
            "needs_semantic_resolution",
            "governance_blocked",
        }:
            return _record_payload(record)
    else:
        record = KnowledgeReconciliationRecord(
            source_type=source_type,
            source_id=source_id,
            source_hash=source_hash,
            scope_type=scope_type,
            scope_id=scope_id,
            status="processing",
            created_by=created_by,
        )
        db.add(record)
        db.flush()

    preview = reconciliation_preview(
        db,
        text=source.text,
        scope_type=scope_type,
        scope_id=scope_id,
        top_k=top_k,
    )
    record.preview_json = json.dumps(preview, ensure_ascii=False, sort_keys=True)
    candidate, relationship = _best_relationship(preview)

    if candidate is None or relationship is None:
        record.status = "needs_semantic_resolution"
        record.message = "No sufficiently structured Concept relationship candidate found."
        db.flush()
        return _record_payload(record)

    confidence = float(relationship.get("confidence") or 0.0)
    if confidence < 0.45:
        record.status = "needs_semantic_resolution"
        record.concept_id = candidate.get("concept_id")
        record.target_claim_id = relationship.get("target_claim_id")
        record.relationship_preview = relationship.get("relationship")
        record.message = "Candidate exists but deterministic confidence is below safe ingestion threshold."
        db.flush()
        return _record_payload(record)

    record.concept_id = candidate.get("concept_id")
    record.target_claim_id = relationship.get("target_claim_id")
    record.relationship_preview = relationship.get("relationship")

    if relationship.get("relationship") == "duplicate" and confidence >= 0.999:
        record.status = "duplicate"
        record.message = "Exact current Claim already represents this source content."
        db.flush()
        return _record_payload(record)

    relation_type = {
        "possible_extends": "extends",
        "possible_narrows": "narrows",
        "related": "relates_to",
        # Conflict/supersession is deliberately not auto-materialized.
        "possible_conflict_or_supersession": "relates_to",
    }.get(str(relationship.get("relationship")), "relates_to")

    concept_key = str(candidate["concept_key"])

    # Automatic reconciliation is stricter than explicit candidate entry.
    # Low-trust sources may be reviewed as candidate observations, but the
    # compiler must not promote them into Holdings candidate state on its own.
    if source.memory_id:
        source_memory = db.get(OrganizationalMemory, source.memory_id)
        source_trust = (
            trust_for_memory(db, source_memory).trust_class
            if source_memory is not None
            else "external_untrusted"
        )
    else:
        source_trust = infer_trust_class(
            created_by=source.created_by,
            source_type=source.source_type,
        )
    if (
        scope_type == "holdings"
        and source_trust
        in {"external_untrusted", "external_verified", "inferred_internal"}
    ):
        record.status = "governance_blocked"
        record.message = (
            "Low-trust source cannot be automatically ingested into Holdings; "
            "explicit governed review may create a candidate observation."
        )
        db.flush()
        return _record_payload(record)

    try:
        claim = create_claim(
            db,
            concept_key=concept_key,
            content=source.text,
            memory_id=source.memory_id,
            initial_status="candidate",
            disposition="reference_only",
            source_type=source.source_type,
            source_id=source.source_id,
            created_by=source.created_by,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        if record.target_claim_id and claim.id != record.target_claim_id:
            add_relation(
                db,
                source_claim_id=claim.id,
                target_claim_id=record.target_claim_id,
                relation_type=relation_type,
                rationale=(
                    "Automatic candidate-only reconciliation. "
                    f"Preview={record.relationship_preview}; no current truth mutation."
                ),
                created_by=created_by,
            )
    except KnowledgeLifecycleError as exc:
        record.status = "governance_blocked"
        record.message = str(exc)
        db.flush()
        return _record_payload(record)

    record.claim_id = claim.id
    record.status = "candidate_created"
    record.message = (
        "Candidate Claim created. It remains non-current until governed reconciliation."
    )
    db.flush()
    return _record_payload(record)



def auto_reconcile_source(
    db: Session,
    *,
    source_type: str,
    source_id: str,
    scope_type: str,
    scope_id: str,
    created_by: str = "system:knowledge_reconciliation",
) -> dict[str, Any]:
    """Best-effort automatic hook that never makes the source write depend on reconciliation.

    Source durability has priority. Reconciliation failures are recorded as Events
    and leave canonical knowledge unchanged.
    """
    try:
        # Isolate reconciliation from the source-write transaction. A compiler
        # bug or provider-specific failure must not destroy the durable source.
        with db.begin_nested():
            result = ingest_source(
                db,
                source_type=source_type,
                source_id=source_id,
                scope_type=scope_type,
                scope_id=scope_id,
                created_by=created_by,
            )
    except Exception as exc:
        emit(
            db,
            "KNOWLEDGE_RECONCILIATION_AUTO_FAILED",
            source_type=source_type,
            source_id=source_id,
            scope_type=scope_type,
            scope_id=scope_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        return {
            "source_type": source_type,
            "source_id": source_id,
            "scope_type": scope_type,
            "scope_id": scope_id,
            "status": "hook_failed",
            "message": str(exc),
        }

    emit(
        db,
        "KNOWLEDGE_RECONCILIATION_AUTO_PROCESSED",
        source_type=source_type,
        source_id=source_id,
        scope_type=scope_type,
        scope_id=scope_id,
        reconciliation_id=result.get("id"),
        reconciliation_status=result.get("status"),
        concept_id=result.get("concept_id"),
        claim_id=result.get("claim_id"),
    )
    return result



def list_reconciliation_records(
    db: Session,
    *,
    status: str | None = None,
    scope_type: str | None = None,
    scope_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    stmt = select(KnowledgeReconciliationRecord)
    if status:
        stmt = stmt.where(KnowledgeReconciliationRecord.status == status)
    if scope_type:
        stmt = stmt.where(KnowledgeReconciliationRecord.scope_type == scope_type)
    if scope_id:
        stmt = stmt.where(KnowledgeReconciliationRecord.scope_id == scope_id)
    rows = list(
        db.scalars(
            stmt.order_by(
                KnowledgeReconciliationRecord.updated_at.desc(),
                KnowledgeReconciliationRecord.id.desc(),
            ).limit(max(1, min(limit, 500)))
        ).all()
    )
    return [_record_payload(row) for row in rows]
