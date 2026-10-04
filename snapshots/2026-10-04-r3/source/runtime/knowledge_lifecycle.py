"""Living organizational knowledge lifecycle.

LLMH-027 / TASK-042 moves the Holdings from document-centric memory to a
source-preserving knowledge graph. Raw source records remain durable; current
organizational knowledge is a deterministic projection over concepts, claims,
typed relations and action bindings.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base
from .memory_trust import (
    AUTHORITY_FOR_TRUST,
    TRUST_RANK,
    ensure_memory_trust,
    infer_trust_class,
    trust_for_memory,
    validate_memory_write,
)
from .models import OrganizationalMemory, now_utc, uid


RELATION_TYPES = {
    "supports",
    "contradicts",
    "supersedes",
    "derived_from",
    "tested_by",
    "adopted_as",
    "rejected_by",
    "relates_to",
    "extends",
    "narrows",
    "implements",
}
CLAIM_STATUSES = {"candidate", "current", "rejected", "historical"}
DISPOSITIONS = {
    "reference_only",
    "watch",
    "experiment",
    "implement",
    "propose_policy",
    "supersede",
    "duplicate",
    "archive",
}
ACTION_STATUSES = {
    "planned",
    "queued",
    "in_progress",
    "implemented",
    "verified",
    "deployed",
    "rolled_back",
}
ACTION_STATUS_RANK = {
    "rolled_back": -1,
    "planned": 0,
    "queued": 1,
    "in_progress": 2,
    "implemented": 3,
    "verified": 4,
    "deployed": 5,
}
AUTHORITY_RANK = {"A0": 0, "A1": 1, "A2": 2, "A3": 3, "A4": 4}
CLAIM_RESOLUTION_ACTIONS = {"adopt", "supersede", "reject", "archive"}


class KnowledgeLifecycleError(ValueError):
    pass


class KnowledgeNotFound(LookupError):
    pass


class KnowledgeConcept(Base):
    """Stable topic address independent from any single source document."""

    __tablename__ = "knowledge_concepts"
    __table_args__ = (
        UniqueConstraint(
            "scope_type",
            "scope_id",
            "canonical_key",
            name="uq_knowledge_concept_scope_key",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: uid("KCON")
    )
    canonical_key: Mapped[str] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(240))
    description: Mapped[str] = mapped_column(Text, default="")
    scope_type: Mapped[str] = mapped_column(String(32), index=True)
    scope_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class KnowledgeClaim(Base):
    """Immutable source-derived statement attached to a stable concept."""

    __tablename__ = "knowledge_claims"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: uid("KCLM")
    )
    concept_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_concepts.id"), index=True
    )
    memory_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizational_memory.id"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text)
    initial_status: Mapped[str] = mapped_column(
        String(32), default="candidate", index=True
    )
    disposition: Mapped[str] = mapped_column(
        String(32), default="reference_only", index=True
    )
    source_type: Mapped[str] = mapped_column(String(64), default="internal")
    source_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    trust_class: Mapped[str] = mapped_column(String(32), index=True)
    authority_level: Mapped[str] = mapped_column(String(2), index=True)
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class KnowledgeRelation(Base):
    """Append-only typed relationship between two claims."""

    __tablename__ = "knowledge_relations"
    __table_args__ = (
        UniqueConstraint(
            "source_claim_id",
            "target_claim_id",
            "relation_type",
            name="uq_knowledge_claim_relation",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: uid("KREL")
    )
    source_claim_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_claims.id"), index=True
    )
    target_claim_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_claims.id"), index=True
    )
    relation_type: Mapped[str] = mapped_column(String(32), index=True)
    rationale: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class KnowledgeClaimResolution(Base):
    """Append-only governance decision over an immutable candidate Claim."""

    __tablename__ = "knowledge_claim_resolutions"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: uid("KRES")
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_claims.id"), index=True
    )
    action: Mapped[str] = mapped_column(String(24), index=True)
    target_claim_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_claims.id"), nullable=True, index=True
    )
    disposition_override: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    rationale: Mapped[str] = mapped_column(Text, default="")
    resolved_by: Mapped[str] = mapped_column(String(128), default="founder")
    authority_level: Mapped[str] = mapped_column(String(2), default="A4")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )


class KnowledgeActionBinding(Base):
    """Tracks what organizational action has already been taken for a claim."""

    __tablename__ = "knowledge_action_bindings"
    __table_args__ = (
        UniqueConstraint(
            "claim_id",
            "action_type",
            "action_id",
            name="uq_knowledge_claim_action",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: uid("KACT")
    )
    claim_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_claims.id"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(48), index=True)
    action_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


LLMH_027_PRINCIPLES = (
    (
        "knowledge_is_not_document",
        "Knowledge Is Not a Document: 문서는 immutable source로 보존하고, 현재 조직 지식은 stable Concept에 연결된 Claim과 관계의 projection으로 계산한다.",
    ),
    (
        "source_preserved_projection_current",
        "Preserve Source, Recompute Current Truth: 과거 문서와 판단을 삭제하지 않으며 supersession/contradiction을 관계로 보존하고 현재 유효 지식은 projection으로 제공한다.",
    ),
    (
        "knowledge_and_action_state_separate",
        "Knowledge State != Action State: 지식의 유효성(current/superseded/contested)과 실행 상태(planned/implemented/verified/deployed)는 분리 추적한다.",
    ),
    (
        "reconcile_before_new_work",
        "Reconcile Before New Work: 새 Work를 만들기 전에 관련 현재 지식과 기존 Action Binding을 확인해 이미 구현·검증·배포된 사항의 중복 개발을 방지한다.",
    ),
)


def _canonical_key(value: str) -> str:
    normalized = re.sub(r"[^\w-]+", "-", (value or "").strip().lower(), flags=re.UNICODE)
    normalized = re.sub(r"-+", "-", normalized).strip("-")
    if not normalized:
        raise KnowledgeLifecycleError("Concept key cannot be empty")
    return normalized[:160]


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _claim_payload(claim: KnowledgeClaim, effective_status: str) -> dict[str, Any]:
    return {
        "id": claim.id,
        "concept_id": claim.concept_id,
        "memory_id": claim.memory_id,
        "content": claim.content,
        "initial_status": claim.initial_status,
        "effective_status": effective_status,
        "disposition": claim.disposition,
        "source_type": claim.source_type,
        "source_id": claim.source_id,
        "trust_class": claim.trust_class,
        "authority_level": claim.authority_level,
        "created_by": claim.created_by,
        "created_at": _iso(claim.created_at),
    }


NON_IMPLEMENTATION_ACTION_PURPOSES = {
    "verification",
    "experiment",
    "research",
    "capability_reference",
}


def _resolution_payload(resolution: KnowledgeClaimResolution) -> dict[str, Any]:
    return {
        "id": resolution.id,
        "claim_id": resolution.claim_id,
        "action": resolution.action,
        "target_claim_id": resolution.target_claim_id,
        "disposition_override": resolution.disposition_override,
        "rationale": resolution.rationale,
        "resolved_by": resolution.resolved_by,
        "authority_level": resolution.authority_level,
        "created_at": _iso(resolution.created_at),
    }


def _action_detail(binding: KnowledgeActionBinding) -> dict[str, Any]:
    try:
        value = json.loads(binding.detail_json or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _binding_counts_as_implementation(binding: KnowledgeActionBinding) -> bool:
    purpose = str(_action_detail(binding).get("purpose") or "implementation")
    return purpose not in NON_IMPLEMENTATION_ACTION_PURPOSES


def _action_payload(binding: KnowledgeActionBinding) -> dict[str, Any]:
    detail = _action_detail(binding)
    return {
        "id": binding.id,
        "claim_id": binding.claim_id,
        "action_type": binding.action_type,
        "action_id": binding.action_id,
        "status": binding.status,
        "detail": detail,
        "created_by": binding.created_by,
        "created_at": _iso(binding.created_at),
        "updated_at": _iso(binding.updated_at),
    }


def ensure_concept(
    db: Session,
    *,
    key: str,
    title: str,
    scope_type: str,
    scope_id: str,
    description: str = "",
    created_by: str = "system",
) -> KnowledgeConcept:
    if scope_type not in {"employee", "lab", "holdings"}:
        raise KnowledgeLifecycleError("Unsupported concept scope")
    canonical_key = _canonical_key(key)
    existing = db.scalar(
        select(KnowledgeConcept).where(
            KnowledgeConcept.scope_type == scope_type,
            KnowledgeConcept.scope_id == scope_id,
            KnowledgeConcept.canonical_key == canonical_key,
        )
    )
    if existing is not None:
        return existing
    concept = KnowledgeConcept(
        canonical_key=canonical_key,
        title=title.strip() or canonical_key,
        description=description.strip(),
        scope_type=scope_type,
        scope_id=scope_id,
        created_by=created_by,
    )
    db.add(concept)
    db.flush()
    return concept


def require_concept(
    db: Session,
    *,
    key: str,
    scope_type: str = "holdings",
    scope_id: str = "holdings",
) -> KnowledgeConcept:
    concept = db.scalar(
        select(KnowledgeConcept).where(
            KnowledgeConcept.scope_type == scope_type,
            KnowledgeConcept.scope_id == scope_id,
            KnowledgeConcept.canonical_key == _canonical_key(key),
        )
    )
    if concept is None:
        raise KnowledgeNotFound("Knowledge concept not found")
    return concept


def require_claim(db: Session, claim_id: str) -> KnowledgeClaim:
    claim = db.get(KnowledgeClaim, claim_id)
    if claim is None:
        raise KnowledgeNotFound("Knowledge claim not found")
    return claim


def _resolve_claim_authority(
    db: Session,
    *,
    concept: KnowledgeConcept,
    memory_id: str | None,
    created_by: str,
    source_type: str | None,
) -> tuple[OrganizationalMemory | None, str, str, str]:
    if memory_id:
        memory = db.get(OrganizationalMemory, memory_id)
        if memory is None:
            raise KnowledgeNotFound("Source organizational memory not found")
        if (
            memory.scope_type != concept.scope_type
            or memory.scope_id != concept.scope_id
        ):
            raise KnowledgeLifecycleError(
                "A claim cannot widen or change its source memory scope"
            )
        trust = trust_for_memory(db, memory)
        return (
            memory,
            trust.trust_class,
            trust.authority_level,
            source_type or memory.source_type or "organizational_memory",
        )

    resolved_source = source_type or "internal"
    trust_class = infer_trust_class(
        created_by=created_by,
        source_type=resolved_source,
    )
    authority_level = AUTHORITY_FOR_TRUST[trust_class]
    return None, trust_class, authority_level, resolved_source


def add_relation(
    db: Session,
    *,
    source_claim_id: str,
    target_claim_id: str,
    relation_type: str,
    rationale: str = "",
    created_by: str = "system",
) -> KnowledgeRelation:
    if relation_type not in RELATION_TYPES:
        raise KnowledgeLifecycleError("Unsupported knowledge relation type")
    if source_claim_id == target_claim_id:
        raise KnowledgeLifecycleError("A claim cannot relate to itself")

    source = require_claim(db, source_claim_id)
    target = require_claim(db, target_claim_id)
    source_concept = db.get(KnowledgeConcept, source.concept_id)
    target_concept = db.get(KnowledgeConcept, target.concept_id)
    if source_concept is None or target_concept is None:
        raise KnowledgeNotFound("Knowledge concept not found")
    if (
        source_concept.scope_type != target_concept.scope_type
        or source_concept.scope_id != target_concept.scope_id
    ):
        raise KnowledgeLifecycleError(
            "Knowledge relations cannot widen private memory scope"
        )

    existing = db.scalar(
        select(KnowledgeRelation).where(
            KnowledgeRelation.source_claim_id == source_claim_id,
            KnowledgeRelation.target_claim_id == target_claim_id,
            KnowledgeRelation.relation_type == relation_type,
        )
    )
    if existing is not None:
        return existing

    if relation_type == "supersedes":
        if source.concept_id != target.concept_id:
            raise KnowledgeLifecycleError(
                "Supersession must occur within the same stable concept"
            )
        if TRUST_RANK[source.trust_class] < TRUST_RANK[target.trust_class]:
            raise KnowledgeLifecycleError(
                "Lower-trust claim cannot supersede higher-trust claim"
            )
        if AUTHORITY_RANK[source.authority_level] < AUTHORITY_RANK[target.authority_level]:
            raise KnowledgeLifecycleError(
                "Lower-authority claim cannot supersede higher-authority claim"
            )

    relation = KnowledgeRelation(
        source_claim_id=source_claim_id,
        target_claim_id=target_claim_id,
        relation_type=relation_type,
        rationale=rationale.strip(),
        created_by=created_by,
    )
    db.add(relation)
    db.flush()
    return relation


def create_claim(
    db: Session,
    *,
    concept_key: str,
    content: str,
    memory_id: str | None = None,
    initial_status: str = "current",
    disposition: str = "reference_only",
    source_type: str | None = None,
    source_id: str | None = None,
    created_by: str = "system",
    supersedes_claim_id: str | None = None,
    scope_type: str = "holdings",
    scope_id: str = "holdings",
) -> KnowledgeClaim:
    if initial_status not in CLAIM_STATUSES:
        raise KnowledgeLifecycleError("Unsupported claim status")
    if disposition not in DISPOSITIONS:
        raise KnowledgeLifecycleError("Unsupported knowledge disposition")
    concept = require_concept(
        db,
        key=concept_key,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    memory, trust_class, authority_level, resolved_source = _resolve_claim_authority(
        db,
        concept=concept,
        memory_id=memory_id,
        created_by=created_by,
        source_type=source_type,
    )
    if (
        concept.scope_type == "holdings"
        and trust_class in {"external_untrusted", "external_verified", "inferred_internal"}
        and initial_status != "candidate"
    ):
        raise KnowledgeLifecycleError(
            "Low-trust content may enter Holdings only as a candidate claim"
        )

    resolved_content = (content or (memory.content if memory else "")).strip()
    if not resolved_content:
        raise KnowledgeLifecycleError("Knowledge claim content cannot be empty")
    resolved_source_id = source_id or (memory.id if memory else None)

    duplicate = db.scalar(
        select(KnowledgeClaim).where(
            KnowledgeClaim.concept_id == concept.id,
            KnowledgeClaim.source_type == resolved_source,
            KnowledgeClaim.source_id == resolved_source_id,
            KnowledgeClaim.content == resolved_content,
        )
    )
    if duplicate is not None:
        return duplicate

    claim = KnowledgeClaim(
        concept_id=concept.id,
        memory_id=memory.id if memory else None,
        content=resolved_content,
        initial_status=initial_status,
        disposition=disposition,
        source_type=resolved_source,
        source_id=resolved_source_id,
        trust_class=trust_class,
        authority_level=authority_level,
        created_by=created_by,
    )
    db.add(claim)
    db.flush()

    if supersedes_claim_id:
        target = require_claim(db, supersedes_claim_id)
        if target.concept_id != concept.id:
            raise KnowledgeLifecycleError(
                "A superseding claim must belong to the same concept"
            )
        add_relation(
            db,
            source_claim_id=claim.id,
            target_claim_id=target.id,
            relation_type="supersedes",
            rationale="Explicit lifecycle supersession",
            created_by=created_by,
        )
    return claim


def resolve_candidate_claim(
    db: Session,
    *,
    claim_id: str,
    action: str,
    target_claim_id: str | None = None,
    disposition: str | None = None,
    rationale: str = "",
    resolved_by: str = "founder",
    authority_level: str = "A4",
) -> KnowledgeClaimResolution:
    """Govern a candidate Claim without mutating the immutable Claim row."""

    if action not in CLAIM_RESOLUTION_ACTIONS:
        raise KnowledgeLifecycleError("Unsupported claim resolution action")
    if authority_level not in AUTHORITY_RANK:
        raise KnowledgeLifecycleError("Unsupported resolution authority level")
    if disposition is not None and disposition not in DISPOSITIONS:
        raise KnowledgeLifecycleError("Unsupported resolution disposition")

    claim = require_claim(db, claim_id)
    concept = db.get(KnowledgeConcept, claim.concept_id)
    if concept is None:
        raise KnowledgeNotFound("Knowledge concept not found")
    if claim.initial_status != "candidate":
        raise KnowledgeLifecycleError("Only candidate Claims require governance resolution")

    existing = db.scalar(
        select(KnowledgeClaimResolution)
        .where(KnowledgeClaimResolution.claim_id == claim.id)
        .order_by(
            KnowledgeClaimResolution.created_at.desc(),
            KnowledgeClaimResolution.id.desc(),
        )
        .limit(1)
    )
    if existing is not None:
        if (
            existing.action == action
            and existing.target_claim_id == target_claim_id
            and existing.disposition_override == disposition
        ):
            return existing
        raise KnowledgeLifecycleError("Candidate Claim already has a governance resolution")

    if concept.scope_type == "holdings" and authority_level != "A4":
        raise KnowledgeLifecycleError(
            "Holdings canonical Claim resolution requires Founder authority"
        )

    target = None
    if action == "supersede":
        if not target_claim_id:
            raise KnowledgeLifecycleError("Supersession requires target_claim_id")
        target = require_claim(db, target_claim_id)
        if target.concept_id != claim.concept_id:
            raise KnowledgeLifecycleError(
                "Supersession target must belong to the same stable Concept"
            )
        if TRUST_RANK[claim.trust_class] < TRUST_RANK[target.trust_class]:
            raise KnowledgeLifecycleError(
                "Lower-trust candidate cannot supersede higher-trust Claim"
            )
        if AUTHORITY_RANK[authority_level] < AUTHORITY_RANK[target.authority_level]:
            raise KnowledgeLifecycleError(
                "Resolution authority is below the target Claim authority"
            )
    elif target_claim_id:
        raise KnowledgeLifecycleError(
            "target_claim_id is only valid for supersede resolution"
        )

    resolution = KnowledgeClaimResolution(
        claim_id=claim.id,
        action=action,
        target_claim_id=target.id if target is not None else None,
        disposition_override=disposition,
        rationale=rationale.strip()[:4000],
        resolved_by=resolved_by.strip() or "founder",
        authority_level=authority_level,
    )
    db.add(resolution)
    db.flush()

    if action == "supersede" and target is not None:
        add_relation(
            db,
            source_claim_id=claim.id,
            target_claim_id=target.id,
            relation_type="supersedes",
            rationale=rationale.strip() or "Governed candidate supersession",
            created_by=resolved_by,
        )
    return resolution


def bind_action(
    db: Session,
    *,
    claim_id: str,
    action_type: str,
    action_id: str,
    status: str,
    detail: dict[str, Any] | None = None,
    created_by: str = "system",
) -> KnowledgeActionBinding:
    if status not in ACTION_STATUSES:
        raise KnowledgeLifecycleError("Unsupported action status")
    require_claim(db, claim_id)
    existing = db.scalar(
        select(KnowledgeActionBinding).where(
            KnowledgeActionBinding.claim_id == claim_id,
            KnowledgeActionBinding.action_type == action_type,
            KnowledgeActionBinding.action_id == action_id,
        )
    )
    if existing is None:
        existing = KnowledgeActionBinding(
            claim_id=claim_id,
            action_type=action_type.strip()[:48],
            action_id=action_id.strip()[:128],
            status=status,
            detail_json=json.dumps(detail or {}, ensure_ascii=False, sort_keys=True),
            created_by=created_by,
        )
        db.add(existing)
    else:
        existing.status = status
        existing.detail_json = json.dumps(
            detail or {}, ensure_ascii=False, sort_keys=True
        )
    db.flush()
    return existing


def concept_projection(
    db: Session,
    *,
    key: str,
    scope_type: str = "holdings",
    scope_id: str = "holdings",
) -> dict[str, Any]:
    concept = require_concept(
        db,
        key=key,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    claims = list(
        db.scalars(
            select(KnowledgeClaim)
            .where(KnowledgeClaim.concept_id == concept.id)
            .order_by(KnowledgeClaim.created_at.asc(), KnowledgeClaim.id.asc())
        )
    )
    claim_ids = [claim.id for claim in claims]
    relations = (
        list(
            db.scalars(
                select(KnowledgeRelation).where(
                    KnowledgeRelation.source_claim_id.in_(claim_ids)
                    | KnowledgeRelation.target_claim_id.in_(claim_ids)
                )
            )
        )
        if claim_ids
        else []
    )
    bindings = (
        list(
            db.scalars(
                select(KnowledgeActionBinding).where(
                    KnowledgeActionBinding.claim_id.in_(claim_ids)
                )
            )
        )
        if claim_ids
        else []
    )
    resolutions = (
        list(
            db.scalars(
                select(KnowledgeClaimResolution)
                .where(KnowledgeClaimResolution.claim_id.in_(claim_ids))
                .order_by(
                    KnowledgeClaimResolution.created_at.asc(),
                    KnowledgeClaimResolution.id.asc(),
                )
            )
        )
        if claim_ids
        else []
    )
    latest_resolution: dict[str, KnowledgeClaimResolution] = {}
    for resolution in resolutions:
        latest_resolution[resolution.claim_id] = resolution

    superseded = {
        relation.target_claim_id
        for relation in relations
        if relation.relation_type == "supersedes"
    }
    effective: dict[str, str] = {}
    effective_disposition: dict[str, str] = {}
    for claim in claims:
        status = "superseded" if claim.id in superseded else claim.initial_status
        disposition = claim.disposition
        resolution = latest_resolution.get(claim.id)
        if resolution is not None and claim.id not in superseded:
            if resolution.action in {"adopt", "supersede"}:
                status = "current"
            elif resolution.action == "reject":
                status = "rejected"
            elif resolution.action == "archive":
                status = "historical"
            if resolution.disposition_override:
                disposition = resolution.disposition_override
        effective[claim.id] = status
        effective_disposition[claim.id] = disposition
    current_claims = [
        claim
        for claim in claims
        if effective[claim.id] == "current"
    ]
    current_ids = {claim.id for claim in current_claims}
    contradictions = [
        relation
        for relation in relations
        if relation.relation_type == "contradicts"
        and relation.source_claim_id in current_ids
        and relation.target_claim_id in current_ids
    ]
    projection_status = (
        "empty"
        if not current_claims
        else "contested"
        if contradictions
        else "current"
    )

    actions_by_claim: dict[str, list[KnowledgeActionBinding]] = {}
    for binding in bindings:
        actions_by_claim.setdefault(binding.claim_id, []).append(binding)

    current_actions = [
        binding
        for claim in current_claims
        for binding in actions_by_claim.get(claim.id, [])
        if _binding_counts_as_implementation(binding)
    ]
    already_addressed = any(
        ACTION_STATUS_RANK[binding.status]
        >= ACTION_STATUS_RANK["implemented"]
        for binding in current_actions
    )
    strongest_action = max(
        (ACTION_STATUS_RANK[binding.status] for binding in current_actions),
        default=-99,
    )
    if strongest_action >= ACTION_STATUS_RANK["deployed"]:
        action_state = "deployed"
    elif strongest_action >= ACTION_STATUS_RANK["verified"]:
        action_state = "verified"
    elif strongest_action >= ACTION_STATUS_RANK["implemented"]:
        action_state = "implemented"
    elif strongest_action >= ACTION_STATUS_RANK["in_progress"]:
        action_state = "in_progress"
    elif strongest_action >= ACTION_STATUS_RANK["planned"]:
        action_state = "planned"
    else:
        action_state = "no_action"

    return {
        "concept": {
            "id": concept.id,
            "key": concept.canonical_key,
            "title": concept.title,
            "description": concept.description,
            "scope_type": concept.scope_type,
            "scope_id": concept.scope_id,
            "status": concept.status,
            "created_by": concept.created_by,
            "created_at": _iso(concept.created_at),
            "updated_at": _iso(concept.updated_at),
        },
        "projection_status": projection_status,
        "current_claims": [
            {
                **_claim_payload(claim, effective[claim.id]),
                "effective_disposition": effective_disposition[claim.id],
            }
            for claim in current_claims
        ],
        "history": [
            {
                **_claim_payload(claim, effective[claim.id]),
                "effective_disposition": effective_disposition[claim.id],
            }
            for claim in claims
        ],
        "resolutions": [_resolution_payload(item) for item in resolutions],
        "relations": [
            {
                "id": relation.id,
                "source_claim_id": relation.source_claim_id,
                "target_claim_id": relation.target_claim_id,
                "relation_type": relation.relation_type,
                "rationale": relation.rationale,
                "created_by": relation.created_by,
                "created_at": _iso(relation.created_at),
            }
            for relation in relations
        ],
        "actions": [_action_payload(binding) for binding in bindings],
        "action_state": action_state,
        "already_addressed": already_addressed,
        "duplicate_guard": {
            "block_duplicate_work": already_addressed,
            "recommended_action": (
                "reuse_existing_capability"
                if already_addressed
                else "evaluate_new_work"
            ),
        },
    }


def seed_knowledge_lifecycle_principles(db: Session) -> None:
    concept = ensure_concept(
        db,
        key="organizational-knowledge-lifecycle",
        title="조직 지식 수명주기",
        description=(
            "문서를 source로 보존하면서 현재 지식, 변경 관계, 실행 상태를 "
            "자동으로 연결·투영하는 Holdings 지식 운영체계."
        ),
        scope_type="holdings",
        scope_id="holdings",
        created_by="founder",
    )
    for key, content in LLMH_027_PRINCIPLES:
        source_id = f"LLMH-027:{key}"
        memory = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
            )
        )
        if memory is None:
            trust_class, authority_level = validate_memory_write(
                db,
                scope_type="holdings",
                scope_id="holdings",
                memory_type="principle",
                created_by="founder",
                source_type="operating_principle",
            )
            memory = OrganizationalMemory(
                scope_type="holdings",
                scope_id="holdings",
                memory_type="principle",
                content=content,
                status="retained",
                source_type="operating_principle",
                source_id=source_id,
                created_by="founder",
            )
            db.add(memory)
            db.flush()
            ensure_memory_trust(
                db,
                memory,
                origin_actor="founder",
                source_type="operating_principle",
                trust_class=trust_class,
                authority_level=authority_level,
                provenance={"decision": "LLMH-027", "principle": key},
            )

        existing_claim = db.scalar(
            select(KnowledgeClaim).where(
                KnowledgeClaim.concept_id == concept.id,
                KnowledgeClaim.memory_id == memory.id,
            )
        )
        if existing_claim is None:
            create_claim(
                db,
                concept_key=concept.canonical_key,
                content=memory.content,
                memory_id=memory.id,
                initial_status="current",
                disposition="reference_only",
                source_type="operating_principle",
                source_id=memory.id,
                created_by="founder",
            )
