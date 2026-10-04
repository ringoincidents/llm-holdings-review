"""Action reconciliation and duplicate-work prevention (TASK-048).

Before creating implementation Work/Missions, the Runtime compares the intent
against current knowledge only. Already-addressed current Claims can prevent
materially duplicate actions, while superseded historical implementation never
blocks required new work.

This layer is deterministic and conservative. It only auto-binds Claims whose
current disposition is 'implement'; model prose is never implementation proof.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base
from .events import emit
from .knowledge_lifecycle import (
    KnowledgeActionBinding,
    KnowledgeClaim,
    bind_action,
    concept_projection,
    now_utc,
    uid,
)
from .knowledge_retrieval import reconciliation_preview


ACTION_PURPOSES = {
    "implementation",
    "verification",
    "experiment",
    "research",
    "capability_reference",
}
STRONG_RELATIONS = {"duplicate", "possible_extends", "possible_narrows"}
RELATION_RANK = {
    "duplicate": 4,
    "possible_extends": 3,
    "possible_narrows": 3,
    "possible_conflict_or_supersession": 2,
    "related": 1,
    "unrelated": 0,
}


class ActionReconciliationError(ValueError):
    pass


class DuplicateActionPrevented(ActionReconciliationError):
    def __init__(self, result: dict[str, Any]):
        self.result = result
        concept = result.get("concept_key") or "unknown"
        state = result.get("action_state") or "unknown"
        super().__init__(
            f"Duplicate action prevented: current knowledge '{concept}' "
            f"is already addressed ({state}); reuse or verify existing capability"
        )


class KnowledgeActionReconciliation(Base):
    """Durable audit of knowledge-aware action creation decisions."""

    __tablename__ = "knowledge_action_reconciliations"

    id: Mapped[str] = mapped_column(
        String(40), primary_key=True, default=lambda: uid("KAR")
    )
    lab_id: Mapped[str] = mapped_column(String(40), index=True)
    action_type: Mapped[str] = mapped_column(String(48), index=True)
    action_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)
    query_text: Mapped[str] = mapped_column(Text)
    scope_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    scope_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    concept_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_concepts.id"), nullable=True, index=True
    )
    claim_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_claims.id"), nullable=True, index=True
    )
    decision: Mapped[str] = mapped_column(String(40), index=True)
    relationship: Mapped[str | None] = mapped_column(String(48), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    action_state: Mapped[str] = mapped_column(String(32), default="no_action")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_by: Mapped[str] = mapped_column(String(128), default="system:action_reconciliation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


def _query_hash(text: str) -> str:
    return hashlib.sha256(text.strip().casefold().encode("utf-8")).hexdigest()


def _scope_previews(db: Session, *, lab_id: str, query: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for priority, (scope_type, scope_id) in enumerate(
        (("lab", lab_id), ("holdings", "holdings"))
    ):
        preview = reconciliation_preview(
            db,
            text=query,
            scope_type=scope_type,
            scope_id=scope_id,
            top_k=8,
        )
        for candidate in preview.get("candidates") or []:
            candidate = dict(candidate)
            candidate["_scope_type"] = scope_type
            candidate["_scope_id"] = scope_id
            candidate["_scope_priority"] = priority
            results.append(candidate)
    return results


def _candidate_matches(
    db: Session,
    *,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for candidate in candidates:
        projection = concept_projection(
            db,
            key=str(candidate["concept_key"]),
            scope_type=str(candidate["_scope_type"]),
            scope_id=str(candidate["_scope_id"]),
        )
        implement_claims = {
            item["id"]: item
            for item in projection["current_claims"]
            if item.get("disposition") == "implement"
        }
        if not implement_claims:
            continue
        for relationship in candidate.get("relationship_previews") or []:
            claim_id = str(relationship.get("target_claim_id") or "")
            claim = implement_claims.get(claim_id)
            if claim is None:
                continue
            relation = str(relationship.get("relationship") or "unrelated")
            confidence = float(relationship.get("confidence") or 0.0)
            matches.append(
                {
                    "scope_type": candidate["_scope_type"],
                    "scope_id": candidate["_scope_id"],
                    "scope_priority": candidate["_scope_priority"],
                    "concept_id": candidate["concept_id"],
                    "concept_key": candidate["concept_key"],
                    "claim_id": claim_id,
                    "relationship": relation,
                    "confidence": confidence,
                    "action_state": projection["action_state"],
                    "already_addressed": bool(projection["already_addressed"]),
                    "duplicate_guard": projection["duplicate_guard"],
                }
            )
    matches.sort(
        key=lambda item: (
            -RELATION_RANK.get(item["relationship"], 0),
            -item["confidence"],
            item["scope_priority"],
            item["concept_key"],
            item["claim_id"],
        )
    )
    return matches


def preflight_action(
    db: Session,
    *,
    lab_id: str,
    action_type: str,
    query: str,
    purpose: str = "implementation",
    created_by: str = "system:action_reconciliation",
) -> dict[str, Any]:
    if purpose not in ACTION_PURPOSES:
        raise ActionReconciliationError(f"Unsupported action purpose: {purpose}")
    text = query.strip()
    if not text:
        return {
            "decision": "create_new",
            "block": False,
            "reason": "empty_intent",
            "query": "",
            "claim_id": None,
            "purpose": purpose,
        }

    matches = _candidate_matches(
        db,
        candidates=_scope_previews(db, lab_id=lab_id, query=text),
    )
    if not matches:
        return {
            "decision": "create_new",
            "block": False,
            "reason": "no_current_implementation_claim_match",
            "query": text,
            "claim_id": None,
            "purpose": purpose,
        }

    best = matches[0]
    relation = best["relationship"]
    confidence = best["confidence"]

    if purpose != "implementation":
        if relation in STRONG_RELATIONS and confidence >= 0.85:
            decision = "observe_existing"
            block = False
            reason = f"{purpose}_action_on_current_claim"
        else:
            decision = "create_new"
            block = False
            reason = "match_not_strong_enough_for_observational_binding"
    elif (
        best["already_addressed"]
        and relation == "duplicate"
        and confidence >= 0.999
    ):
        decision = "reuse_existing"
        block = True
        reason = "current_claim_already_implemented"
    elif relation in STRONG_RELATIONS and confidence >= 0.85:
        decision = "revise_existing" if best["already_addressed"] else "bind_planned"
        block = False
        reason = (
            "strong_match_to_addressed_current_claim"
            if best["already_addressed"]
            else "strong_match_to_unimplemented_current_claim"
        )
    else:
        decision = "create_new"
        block = False
        reason = "match_not_strong_enough_for_action_binding"

    return {
        **best,
        "decision": decision,
        "block": block,
        "reason": reason,
        "query": text,
        "action_type": action_type,
        "purpose": purpose,
    }


def record_preflight(
    db: Session,
    *,
    lab_id: str,
    action_type: str,
    query: str,
    result: dict[str, Any],
    action_id: str | None = None,
    created_by: str = "system:action_reconciliation",
) -> KnowledgeActionReconciliation:
    item = KnowledgeActionReconciliation(
        lab_id=lab_id,
        action_type=action_type,
        action_id=action_id,
        query_hash=_query_hash(query),
        query_text=query.strip(),
        scope_type=result.get("scope_type"),
        scope_id=result.get("scope_id"),
        concept_id=result.get("concept_id"),
        claim_id=result.get("claim_id"),
        decision=str(result.get("decision") or "create_new"),
        relationship=result.get("relationship"),
        confidence=round(float(result.get("confidence") or 0.0), 6),
        action_state=str(result.get("action_state") or "no_action"),
        detail_json=json.dumps(
            {
                "reason": result.get("reason"),
                "block": bool(result.get("block")),
                "concept_key": result.get("concept_key"),
                "duplicate_guard": result.get("duplicate_guard"),
                "purpose": result.get("purpose") or "implementation",
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        created_by=created_by,
    )
    db.add(item)
    db.flush()
    emit(
        db,
        "KNOWLEDGE_ACTION_PREFLIGHT",
        lab_id=lab_id,
        reconciliation_id=item.id,
        action_type=action_type,
        action_id=action_id,
        decision=item.decision,
        concept_id=item.concept_id,
        claim_id=item.claim_id,
        action_state=item.action_state,
    )
    return item


def bind_planned_action(
    db: Session,
    *,
    result: dict[str, Any],
    action_type: str,
    action_id: str,
    purpose: str | None = None,
    created_by: str = "system:action_reconciliation",
) -> KnowledgeActionBinding | None:
    claim_id = result.get("claim_id")
    if not claim_id or result.get("decision") not in {
        "bind_planned",
        "revise_existing",
        "observe_existing",
    }:
        return None
    resolved_purpose = purpose or str(result.get("purpose") or "implementation")
    if resolved_purpose not in ACTION_PURPOSES:
        raise ActionReconciliationError(f"Unsupported action purpose: {resolved_purpose}")
    return bind_action(
        db,
        claim_id=str(claim_id),
        action_type=action_type,
        action_id=action_id,
        status="planned",
        detail={
            "source": "knowledge_action_preflight",
            "decision": result.get("decision"),
            "relationship": result.get("relationship"),
            "confidence": result.get("confidence"),
            "concept_key": result.get("concept_key"),
            "purpose": resolved_purpose,
        },
        created_by=created_by,
    )


def _binding_detail(binding: KnowledgeActionBinding) -> dict[str, Any]:
    try:
        value = json.loads(binding.detail_json or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def inherit_action_bindings(
    db: Session,
    *,
    source_action_type: str,
    source_action_id: str,
    action_type: str,
    action_id: str,
    status: str = "in_progress",
    extra_detail: dict[str, Any] | None = None,
    created_by: str = "system:action_reconciliation",
) -> list[KnowledgeActionBinding]:
    """Carry Claim lineage from a parent organizational action to its child."""
    sources = list(
        db.scalars(
            select(KnowledgeActionBinding).where(
                KnowledgeActionBinding.action_type == source_action_type,
                KnowledgeActionBinding.action_id == source_action_id,
            )
        ).all()
    )
    created: list[KnowledgeActionBinding] = []
    for source in sources:
        detail = _binding_detail(source)
        created.append(
            bind_action(
                db,
                claim_id=source.claim_id,
                action_type=action_type,
                action_id=action_id,
                status=status,
                detail={
                    **detail,
                    "inherited_from": {
                        "action_type": source_action_type,
                        "action_id": source_action_id,
                    },
                    **(extra_detail or {}),
                },
                created_by=created_by,
            )
        )
    return created


def bind_action_alias(
    db: Session,
    *,
    source_action_type: str,
    source_action_id: str,
    action_type: str,
    action_id: str,
    status: str,
    purpose: str,
    created_by: str = "system:action_reconciliation",
) -> list[KnowledgeActionBinding]:
    if purpose not in ACTION_PURPOSES:
        raise ActionReconciliationError(f"Unsupported action purpose: {purpose}")
    return inherit_action_bindings(
        db,
        source_action_type=source_action_type,
        source_action_id=source_action_id,
        action_type=action_type,
        action_id=action_id,
        status=status,
        extra_detail={"purpose": purpose},
        created_by=created_by,
    )


def complete_work_bindings(
    db: Session,
    *,
    work_id: str,
    completed: bool,
    developer_verified: bool,
    artifact_id: str | None = None,
) -> list[KnowledgeActionBinding]:
    """Advance Work bindings while preserving implementation-vs-learning semantics."""
    rows = list(
        db.scalars(
            select(KnowledgeActionBinding).where(
                KnowledgeActionBinding.action_type == "work",
                KnowledgeActionBinding.action_id == work_id,
            )
        ).all()
    )
    updated: list[KnowledgeActionBinding] = []
    for row in rows:
        detail = _binding_detail(row)
        purpose = str(detail.get("purpose") or "implementation")
        if purpose == "implementation":
            if not developer_verified:
                continue
            basis = "dev_execution_verified"
        else:
            if not completed:
                continue
            basis = "nonimplementation_action_completed"
        updated.append(
            bind_action(
                db,
                claim_id=row.claim_id,
                action_type="work",
                action_id=work_id,
                status="verified",
                detail={
                    **detail,
                    "artifact_id": artifact_id,
                    "completion_basis": basis,
                    **(
                        {"verification": "dev_execution_verified"}
                        if purpose == "implementation"
                        else {}
                    ),
                },
                created_by="system:work_result_reconciliation",
            )
        )
    return updated


def complete_runtime_task_bindings(
    db: Session,
    *,
    task_id: str,
    task_type: str,
    completed: bool,
    developer_verified: bool,
    artifact_id: str | None = None,
) -> list[KnowledgeActionBinding]:
    """Advance Task bindings without turning model prose into implementation proof."""
    rows = list(
        db.scalars(
            select(KnowledgeActionBinding).where(
                KnowledgeActionBinding.action_type == "task",
                KnowledgeActionBinding.action_id == task_id,
            )
        ).all()
    )
    updated: list[KnowledgeActionBinding] = []
    for row in rows:
        detail = _binding_detail(row)
        purpose = str(detail.get("purpose") or "implementation")
        if purpose == "implementation":
            if task_type != "development" or not developer_verified:
                continue
            next_status = "verified"
        else:
            if not completed:
                continue
            next_status = "verified"
        updated.append(
            bind_action(
                db,
                claim_id=row.claim_id,
                action_type="task",
                action_id=task_id,
                status=next_status,
                detail={
                    **detail,
                    "artifact_id": artifact_id,
                    "task_type": task_type,
                    "completion_basis": (
                        "dev_execution_verified"
                        if purpose == "implementation"
                        else "nonimplementation_action_completed"
                    ),
                },
                created_by="system:runtime_task_reconciliation",
            )
        )
    return updated


def bind_capability_source_refs(
    db: Session,
    *,
    capability_id: str,
    lab_id: str,
    source_refs: list[dict[str, str]],
) -> list[KnowledgeActionBinding]:
    """Link capability metadata to current Claims without treating it as implementation proof."""
    created: list[KnowledgeActionBinding] = []
    for ref in source_refs:
        if ref.get("type") != "memory":
            continue
        memory_id = ref.get("id")
        if not memory_id:
            continue
        claims = list(
            db.scalars(
                select(KnowledgeClaim).where(KnowledgeClaim.memory_id == memory_id)
            ).all()
        )
        for claim in claims:
            from .knowledge_lifecycle import KnowledgeConcept
            concept = db.get(KnowledgeConcept, claim.concept_id)
            if concept is None:
                continue
            projection = concept_projection(
                db,
                key=concept.canonical_key,
                scope_type=concept.scope_type,
                scope_id=concept.scope_id,
            )
            if claim.id not in {item["id"] for item in projection["current_claims"]}:
                continue
            created.append(
                bind_action(
                    db,
                    claim_id=claim.id,
                    action_type="capability",
                    action_id=capability_id,
                    status="verified",
                    detail={
                        "purpose": "capability_reference",
                        "lab_id": lab_id,
                        "source_memory_id": memory_id,
                        "proof": "validated_capability_source_ref",
                    },
                    created_by="system:capability_reconciliation",
                )
            )
    return created


def update_bound_action_status(
    db: Session,
    *,
    action_type: str,
    action_id: str,
    status: str,
    detail: dict[str, Any] | None = None,
    created_by: str = "system:action_reconciliation",
) -> list[KnowledgeActionBinding]:
    rows = list(
        db.scalars(
            select(KnowledgeActionBinding).where(
                KnowledgeActionBinding.action_type == action_type,
                KnowledgeActionBinding.action_id == action_id,
            )
        ).all()
    )
    updated: list[KnowledgeActionBinding] = []
    for row in rows:
        updated.append(
            bind_action(
                db,
                claim_id=row.claim_id,
                action_type=action_type,
                action_id=action_id,
                status=status,
                detail={**json.loads(row.detail_json or "{}"), **(detail or {})},
                created_by=created_by,
            )
        )
    if updated:
        emit(
            db,
            "KNOWLEDGE_ACTION_STATUS_UPDATED",
            action_type=action_type,
            action_id=action_id,
            status=status,
            binding_count=len(updated),
        )
    return updated


def bind_delivery_evidence(
    db: Session,
    *,
    mission_id: str,
    repository: str,
    stage: str,
    pr_number: int | None = None,
    merged_sha: str | None = None,
    deployed_sha: str | None = None,
) -> list[KnowledgeActionBinding]:
    """Project verified delivery evidence from a bound Mission back to its Claim."""
    mission_bindings = list(
        db.scalars(
            select(KnowledgeActionBinding).where(
                KnowledgeActionBinding.action_type == "mission",
                KnowledgeActionBinding.action_id == mission_id,
            )
        ).all()
    )
    created: list[KnowledgeActionBinding] = []
    for source in mission_bindings:
        if pr_number:
            created.append(
                bind_action(
                    db,
                    claim_id=source.claim_id,
                    action_type="pull_request",
                    action_id=f"{repository}#{pr_number}",
                    status="verified" if merged_sha else "in_progress",
                    detail={"mission_id": mission_id, "merged_sha": merged_sha},
                    created_by="system:delivery_reconciliation",
                )
            )
        if deployed_sha:
            created.append(
                bind_action(
                    db,
                    claim_id=source.claim_id,
                    action_type="deployment",
                    action_id=deployed_sha,
                    status="deployed",
                    detail={"mission_id": mission_id, "repository": repository},
                    created_by="system:delivery_reconciliation",
                )
            )
            update_bound_action_status(
                db,
                action_type="mission",
                action_id=mission_id,
                status="deployed",
                detail={
                    "stage": stage,
                    "deployed_sha": deployed_sha,
                    "repository": repository,
                },
                created_by="system:delivery_reconciliation",
            )
        elif stage in {"local_verified", "pr_published", "merged"}:
            update_bound_action_status(
                db,
                action_type="mission",
                action_id=mission_id,
                status="verified",
                detail={
                    "stage": stage,
                    "merged_sha": merged_sha,
                    "repository": repository,
                },
                created_by="system:delivery_reconciliation",
            )
    return created
