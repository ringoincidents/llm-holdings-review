"""Governed Record Writer projection and Founder resolution workflow.

This module completes the source -> candidate -> semantic review pipeline by
exposing only governance-relevant records to the Founder and applying explicit
candidate resolutions without mutating immutable source/Claim rows.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .events import emit
from .knowledge_lifecycle import (
    KnowledgeClaim,
    KnowledgeLifecycleError,
    KnowledgeNotFound,
    concept_projection,
    create_claim,
    ensure_concept,
    resolve_candidate_claim,
)
from .knowledge_reconciliation import (
    KnowledgeReconciliationError,
    KnowledgeReconciliationRecord,
    get_reconciliation_record,
    resolve_source,
)
from .knowledge_semantic import get_semantic_review
from .memory_trust import ensure_memory_trust, validate_memory_write
from .models import OrganizationalMemory
from .organization import organization_labs


RECORD_WRITER_ACTIONABLE_STATUSES = {
    "needs_semantic_resolution",
    "candidate_created",
    "governance_required",
    "new_concept_proposed",
    "semantic_uncertain",
    "semantic_failed",
}
RECORD_WRITER_HIGH_SIGNAL_STATUSES = {
    "needs_semantic_resolution",
    "governance_required",
    "new_concept_proposed",
    "semantic_uncertain",
}
RECORD_WRITER_TERMINAL_STATUSES = {
    "duplicate",
    "semantic_unrelated",
    "governed_current",
    "governed_superseded",
    "governed_rejected",
    "governed_archived",
}
RECORD_WRITER_RESOLUTION_ACTIONS = {"adopt", "supersede", "reject", "archive"}

QUANTRADE_CANONICAL_SOURCE_ID = "quantrade-canonical-vision:2026-10-04"
QUANTRADE_CANONICAL_CONCEPT = "quantrade-private-investment-office-vision"
QUANTRADE_CANONICAL_CONTENT = (
    "QuanTrade는 한 명의 Client를 위한 AI-native Private Investment Office다. "
    "목표는 AI stock picker나 암호화폐 자동매매 봇이 아니라, "
    "Client Intelligence → Strategy/Investment Mandate → Research → Portfolio Management "
    "→ Risk & Compliance → Investment Committee → Decision Management → Execution "
    "→ Performance & Learning의 전문 투자조직 과정을 소프트웨어로 구현하는 것이다. "
    "Research는 Evidence를 만들고 포트폴리오 행동을 직접 결정하지 않는다. "
    "Portfolio Management는 고객 전체 자산 관점에서 allocation/position sizing을 판단하며, "
    "Risk는 독립적으로 제한하거나 veto할 수 있다. Portfolio Decision과 Execution Timing은 분리한다. "
    "결정과 실패는 append-only로 보존하고 deterministic calculation을 LLM reasoning보다 우선한다. "
    "시장 실험(BTC/paper 포함)은 QuanTrade의 정체성이 아니라 검증용 laboratory이며, "
    "Holdings Runtime은 Memory/Authority/Audit/Model Gateway/Cost/Execution infrastructure를 제공하되 "
    "QuanTrade의 제품 언어는 Client Mandate, Research Case, Evidence, Investment Thesis, "
    "Portfolio Proposal, Risk Opinion, Committee Decision, Decision Plan, Execution, Performance Review를 유지한다. "
    "상세 인간용 canonical projection은 ringoincidents/quantrade/QUANTRADE_CANONICAL_VISION.md에 있다."
)


class RecordWriterError(ValueError):
    pass


def _record_entry(db: Session, record: KnowledgeReconciliationRecord) -> dict[str, Any]:
    base = get_reconciliation_record(db, record_id=record.id)
    semantic = get_semantic_review(db, record_id=record.id)
    try:
        source = resolve_source(
            db,
            source_type=record.source_type,
            source_id=record.source_id,
            scope_type=record.scope_type,
            scope_id=record.scope_id,
        )
        source_preview = source.text[:900].rstrip()
        if len(source.text) > 900:
            source_preview += "…"
    except Exception:
        source_preview = ""

    claim = db.get(KnowledgeClaim, record.claim_id) if record.claim_id else None
    classification = (
        str((semantic or {}).get("classification") or "").strip()
        or str(record.relationship_preview or "").strip()
        or "unresolved"
    )
    proposal = (semantic or {}).get("proposal") or {}
    suggested_disposition = str(
        proposal.get("suggested_disposition") or "reference_only"
    )
    suggested_record_action = str(
        proposal.get("suggested_record_action") or "review"
    )
    actions: list[str] = []
    if record.status == "needs_semantic_resolution":
        actions.append("semantic_review")
    if record.claim_id:
        actions.extend(["adopt", "archive", "reject"])
        if record.target_claim_id:
            actions.append("supersede")
    elif record.status == "new_concept_proposed":
        actions.extend(["adopt", "archive", "reject"])
    else:
        actions.extend(["archive", "reject"])

    return {
        **base,
        "semantic_review": semantic,
        "classification": classification,
        "suggested_disposition": suggested_disposition,
        "suggested_record_action": suggested_record_action,
        "source_preview": source_preview,
        "candidate_claim": (
            {
                "id": claim.id,
                "content": claim.content,
                "trust_class": claim.trust_class,
                "authority_level": claim.authority_level,
                "disposition": claim.disposition,
            }
            if claim is not None
            else None
        ),
        "founder_actions": list(dict.fromkeys(actions)),
        "requires_founder": _requires_founder(record),
    }


def _requires_founder(record: KnowledgeReconciliationRecord) -> bool:
    if record.status in RECORD_WRITER_HIGH_SIGNAL_STATUSES:
        return True
    if record.status == "candidate_created":
        return record.source_type in {
            "founder_note",
            "organizational_memory",
            "decision",
        }
    return False


def record_writer_queue(
    db: Session,
    *,
    scope_type: str | None = None,
    scope_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    stmt = select(KnowledgeReconciliationRecord).where(
        KnowledgeReconciliationRecord.status.in_(
            tuple(RECORD_WRITER_ACTIONABLE_STATUSES)
        )
    )
    if scope_type:
        stmt = stmt.where(KnowledgeReconciliationRecord.scope_type == scope_type)
    if scope_id:
        stmt = stmt.where(KnowledgeReconciliationRecord.scope_id == scope_id)
    candidates = list(
        db.scalars(
            stmt.order_by(
                KnowledgeReconciliationRecord.updated_at.desc(),
                KnowledgeReconciliationRecord.id.desc(),
            ).limit(max(10, min(limit * 4, 200)))
        ).all()
    )
    records = [record for record in candidates if _requires_founder(record)][: max(1, min(limit, 100))]
    return {
        "schema": "governed-record-writer-queue-v1",
        "count": len(records),
        "records": [_record_entry(db, record) for record in records],
        "policy": {
            "model_is_drafter_not_authority": True,
            "latest_note_does_not_win": True,
            "sources_preserved": True,
            "canonical_change_requires_governance": True,
        },
    }


def _materialize_new_concept_candidate(
    db: Session,
    *,
    record: KnowledgeReconciliationRecord,
) -> KnowledgeClaim:
    semantic = get_semantic_review(db, record_id=record.id) or {}
    proposal = semantic.get("proposal") or {}
    key = str(proposal.get("new_concept_key") or "").strip()
    title = str(proposal.get("new_concept_title") or "").strip()
    if not key or not title:
        raise RecordWriterError("Semantic review did not provide a valid new Concept proposal")

    source = resolve_source(
        db,
        source_type=record.source_type,
        source_id=record.source_id,
        scope_type=record.scope_type,
        scope_id=record.scope_id,
    )
    concept = ensure_concept(
        db,
        key=key,
        title=title,
        description="Record Writer가 기존 canonical 지식과 분리된 새 주제로 제안한 Concept.",
        scope_type=record.scope_type,
        scope_id=record.scope_id,
        created_by="founder",
    )
    claim = create_claim(
        db,
        concept_key=concept.canonical_key,
        content=source.text,
        memory_id=source.memory_id,
        initial_status="candidate",
        disposition="reference_only",
        source_type=source.source_type,
        source_id=source.source_id,
        created_by=source.created_by,
        scope_type=record.scope_type,
        scope_id=record.scope_id,
    )
    record.concept_id = concept.id
    record.claim_id = claim.id
    return claim


def resolve_record_writer_item(
    db: Session,
    *,
    record_id: str,
    action: str,
    disposition: str | None = None,
    target_claim_id: str | None = None,
    rationale: str = "",
    resolved_by: str = "founder",
) -> dict[str, Any]:
    if action not in RECORD_WRITER_RESOLUTION_ACTIONS:
        raise RecordWriterError("Unsupported Record Writer resolution action")
    if resolved_by != "founder":
        raise RecordWriterError("Record Writer canonical resolution requires Founder authority")

    record = db.get(KnowledgeReconciliationRecord, record_id)
    if record is None:
        raise KnowledgeReconciliationError("Knowledge reconciliation record not found")
    if record.status in RECORD_WRITER_TERMINAL_STATUSES:
        return _record_entry(db, record)

    if action in {"archive", "reject"} and not record.claim_id:
        record.status = "governed_archived" if action == "archive" else "governed_rejected"
        record.message = (
            "Founder archived the source without canonical promotion."
            if action == "archive"
            else "Founder rejected the record draft; source remains durable."
        )
        emit(
            db,
            "KNOWLEDGE_RECORD_WRITER_RESOLVED",
            record_id=record.id,
            action=action,
            claim_id=None,
            resolved_by=resolved_by,
        )
        db.flush()
        return _record_entry(db, record)

    claim = db.get(KnowledgeClaim, record.claim_id) if record.claim_id else None
    if claim is None and record.status == "new_concept_proposed" and action == "adopt":
        claim = _materialize_new_concept_candidate(db, record=record)
    if claim is None:
        raise RecordWriterError(
            "This record has no candidate Claim yet; complete semantic reconciliation first"
        )

    resolved_target = target_claim_id or record.target_claim_id
    resolution = resolve_candidate_claim(
        db,
        claim_id=claim.id,
        action=action,
        target_claim_id=resolved_target if action == "supersede" else None,
        disposition=disposition,
        rationale=rationale,
        resolved_by=resolved_by,
        authority_level="A4",
    )
    record.status = {
        "adopt": "governed_current",
        "supersede": "governed_superseded",
        "reject": "governed_rejected",
        "archive": "governed_archived",
    }[action]
    record.message = f"Founder governance resolution applied: {action}"
    emit(
        db,
        "KNOWLEDGE_RECORD_WRITER_RESOLVED",
        record_id=record.id,
        action=action,
        claim_id=claim.id,
        target_claim_id=resolved_target,
        resolution_id=resolution.id,
        disposition=disposition,
        resolved_by=resolved_by,
    )
    db.flush()

    concept_key = None
    if record.concept_id:
        from .knowledge_lifecycle import KnowledgeConcept
        concept = db.get(KnowledgeConcept, record.concept_id)
        concept_key = concept.canonical_key if concept is not None else None
    return {
        **_record_entry(db, record),
        "canonical_projection": (
            concept_projection(
                db,
                key=concept_key,
                scope_type=record.scope_type,
                scope_id=record.scope_id,
            )
            if concept_key
            else None
        ),
    }


def seed_quantrade_canonical_vision(db: Session) -> None:
    """Put the human-approved QuanTrade North Star into Runtime canonical context."""

    labs = organization_labs(db)
    lab = labs.get("quantrade")
    if lab is None:
        return

    concept = ensure_concept(
        db,
        key=QUANTRADE_CANONICAL_CONCEPT,
        title="QuanTrade Private Investment Office 비전",
        description="QuanTrade의 현재 North Star와 anti-drift 경계.",
        scope_type="lab",
        scope_id=lab.id,
        created_by="founder",
    )

    memory = db.scalar(
        select(OrganizationalMemory).where(
            OrganizationalMemory.scope_type == "lab",
            OrganizationalMemory.scope_id == lab.id,
            OrganizationalMemory.source_type == "canonical_vision",
            OrganizationalMemory.source_id == QUANTRADE_CANONICAL_SOURCE_ID,
        )
    )
    if memory is None:
        trust_class, authority_level = validate_memory_write(
            db,
            scope_type="lab",
            scope_id=lab.id,
            memory_type="vision",
            created_by="founder",
            source_type="canonical_vision",
        )
        memory = OrganizationalMemory(
            scope_type="lab",
            scope_id=lab.id,
            memory_type="vision",
            content=QUANTRADE_CANONICAL_CONTENT,
            status="retained",
            source_type="canonical_vision",
            source_id=QUANTRADE_CANONICAL_SOURCE_ID,
            created_by="founder",
        )
        db.add(memory)
        db.flush()
        ensure_memory_trust(
            db,
            memory,
            origin_actor="founder",
            source_type="canonical_vision",
            trust_class=trust_class,
            authority_level=authority_level,
            provenance={
                "decision": "LLMH-037",
                "repository": "ringoincidents/quantrade",
                "path": "QUANTRADE_CANONICAL_VISION.md",
                "effective_date": "2026-10-04",
            },
        )

    existing = db.scalar(
        select(KnowledgeClaim).where(
            KnowledgeClaim.concept_id == concept.id,
            KnowledgeClaim.memory_id == memory.id,
        )
    )
    if existing is None:
        create_claim(
            db,
            concept_key=concept.canonical_key,
            content=memory.content,
            memory_id=memory.id,
            initial_status="current",
            disposition="reference_only",
            source_type="canonical_vision",
            source_id=memory.id,
            created_by="founder",
            scope_type="lab",
            scope_id=lab.id,
        )
