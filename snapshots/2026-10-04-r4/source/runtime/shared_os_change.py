"""Governed shared-OS change handoff (LLMH-028 / TASK-052).

This module reuses LabProposal → HQ approval → HoldingsInitiative → Mission.
SharedOSChangeBinding adds provenance and keeps Runtime Engineering as the sole
implementation owner without creating a parallel workflow.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .events import emit
from .knowledge_lifecycle import (
    KnowledgeActionBinding,
    KnowledgeClaim,
    KnowledgeConcept,
    bind_action,
)
from .models import (
    HoldingsInitiative,
    HoldingsWorkLedgerEntry,
    LabMission,
    LabProposal,
    OperationalIncident,
    SharedOSChangeBinding,
    TechnologyCandidate,
)
from .organization import (
    OrganizationInvalid,
    OrganizationNotFound,
    approve_proposal,
    organization_labs,
    submit_proposal,
)


SOURCE_TYPES = {"mission", "incident", "claim", "technology_candidate"}


class SharedOSChangeError(ValueError):
    pass


def _validate_source(
    db: Session,
    *,
    source_lab_id: str,
    source_type: str,
    source_id: str,
) -> None:
    if source_type not in SOURCE_TYPES:
        raise SharedOSChangeError("Unsupported shared OS change source type")

    if source_type == "mission":
        row = db.get(LabMission, source_id)
        if row is None or row.lab_id != source_lab_id:
            raise SharedOSChangeError("Source Mission is missing or out of Lab scope")
        return

    if source_type == "incident":
        row = db.get(OperationalIncident, source_id)
        if row is None:
            raise SharedOSChangeError("Source OperationalIncident not found")
        if row.lab_id is not None and row.lab_id != source_lab_id:
            raise SharedOSChangeError("Source OperationalIncident is out of Lab scope")
        return

    if source_type == "technology_candidate":
        row = db.get(TechnologyCandidate, source_id)
        if row is None:
            raise SharedOSChangeError("Source TechnologyCandidate not found")
        if row.matched_lab_id is not None and row.matched_lab_id != source_lab_id:
            raise SharedOSChangeError("Source TechnologyCandidate is out of Lab scope")
        return

    claim = db.get(KnowledgeClaim, source_id)
    if claim is None:
        raise SharedOSChangeError("Source KnowledgeClaim not found")
    concept = db.get(KnowledgeConcept, claim.concept_id)
    if concept is None:
        raise SharedOSChangeError("Source KnowledgeConcept not found")
    if concept.scope_type == "lab" and concept.scope_id != source_lab_id:
        raise SharedOSChangeError("Source KnowledgeClaim is out of Lab scope")
    if concept.scope_type not in {"lab", "holdings"}:
        raise SharedOSChangeError(
            "Employee-scoped claims must be promoted before requesting shared OS change"
        )


def submit_shared_os_change(
    db: Session,
    *,
    source_lab_id: str,
    title: str,
    summary: str,
    source_type: str,
    source_id: str,
    impact: str = "cross_lab",
    created_by: str = "agent",
) -> SharedOSChangeBinding:
    if impact not in {"cross_lab", "holdings"}:
        raise SharedOSChangeError("Shared OS change impact must be cross_lab or holdings")
    _validate_source(
        db,
        source_lab_id=source_lab_id,
        source_type=source_type,
        source_id=source_id,
    )

    source_mission_id = source_id if source_type == "mission" else None
    try:
        proposal = submit_proposal(
            db,
            source_lab_id=source_lab_id,
            title=title,
            summary=summary,
            source_mission_id=source_mission_id,
            impact=impact,
            required_labs=["runtime"],
            created_by=created_by,
        )
    except (OrganizationInvalid, OrganizationNotFound) as exc:
        raise SharedOSChangeError(str(exc)) from exc

    binding = SharedOSChangeBinding(
        proposal_id=proposal.id,
        source_lab_id=source_lab_id,
        source_type=source_type,
        source_id=source_id,
        required_authority="A4" if impact == "holdings" else "A3",
        status="submitted",
        created_by=created_by,
    )
    db.add(binding)
    db.flush()
    emit(
        db,
        "SHARED_OS_CHANGE_SUBMITTED",
        proposal_id=proposal.id,
        source_lab_id=source_lab_id,
        source_type=source_type,
        source_id=source_id,
        required_authority=binding.required_authority,
    )
    if source_type == "claim":
        bind_action(
            db,
            claim_id=source_id,
            action_type="shared_os_change",
            action_id=proposal.id,
            status="planned",
            detail={
                "proposal_id": proposal.id,
                "source_lab_id": source_lab_id,
                "implementation_mission_id": None,
            },
            created_by="system:runtime_change_reconciliation",
        )
    db.commit()
    db.refresh(binding)
    return binding


def _runtime_entry(
    db: Session,
    initiative: HoldingsInitiative,
) -> HoldingsWorkLedgerEntry:
    runtime_lab = organization_labs(db)["runtime"]
    entry = db.scalar(
        select(HoldingsWorkLedgerEntry).where(
            HoldingsWorkLedgerEntry.initiative_id == initiative.id,
            HoldingsWorkLedgerEntry.lab_id == runtime_lab.id,
        )
    )
    if entry is None or entry.mission_id is None:
        raise SharedOSChangeError("Approved shared OS change did not create Runtime Mission")
    return entry


def approve_shared_os_change(
    db: Session,
    *,
    proposal_id: str,
    reviewed_by: str,
    priority: str = "normal",
) -> dict[str, Any]:
    binding = db.get(SharedOSChangeBinding, proposal_id)
    proposal = db.get(LabProposal, proposal_id)
    if binding is None or proposal is None:
        raise SharedOSChangeError("Shared OS change not found")

    reviewer = reviewed_by.strip().lower()
    if binding.required_authority == "A4" and reviewer != "founder":
        raise SharedOSChangeError("A4 shared OS change requires Founder approval")
    if binding.required_authority == "A3" and reviewer not in {"hq", "founder"}:
        raise SharedOSChangeError("A3 shared OS change requires HQ or Founder approval")

    try:
        initiative = approve_proposal(
            db,
            proposal_id=proposal_id,
            reviewed_by=reviewer,
            priority=priority,
        )
    except (OrganizationInvalid, OrganizationNotFound) as exc:
        raise SharedOSChangeError(str(exc)) from exc

    entry = _runtime_entry(db, initiative)
    binding.implementation_mission_id = entry.mission_id
    binding.status = "queued"
    emit(
        db,
        "SHARED_OS_CHANGE_APPROVED",
        proposal_id=proposal_id,
        initiative_id=initiative.id,
        implementation_mission_id=entry.mission_id,
        reviewed_by=reviewer,
        required_authority=binding.required_authority,
    )
    if binding.source_type == "claim":
        reconcile_shared_os_knowledge_action(db, proposal_id=proposal_id)
    db.commit()
    return shared_os_change_state(db, proposal_id=proposal_id)


def _project_action_status(db: Session, binding: SharedOSChangeBinding) -> tuple[str, dict[str, Any]]:
    """Purely derive Claim action state from real Mission/delivery state."""
    proposal = db.get(LabProposal, binding.proposal_id)
    mission = (
        db.get(LabMission, binding.implementation_mission_id)
        if binding.implementation_mission_id
        else None
    )
    detail: dict[str, Any] = {
        "proposal_id": binding.proposal_id,
        "source_lab_id": binding.source_lab_id,
        "implementation_mission_id": binding.implementation_mission_id,
    }
    if mission is None:
        return "planned", detail

    from .delivery import delivery_state

    delivery = delivery_state(db, mission)
    detail.update(
        {
            "mission_status": mission.status,
            "delivery_target": delivery.get("target"),
            "delivery_stage": delivery.get("stage"),
            "repository": delivery.get("repository"),
            "branch": delivery.get("branch"),
            "pr_number": delivery.get("pr_number"),
            "pr_url": delivery.get("pr_url"),
            "pr_head_sha": delivery.get("pr_head_sha"),
            "merged_sha": delivery.get("merged_sha"),
            "deployed_sha": delivery.get("deployed_sha"),
            "reviewed_by": proposal.reviewed_by if proposal else None,
        }
    )
    stage = str(delivery.get("stage") or "pending")
    if stage == "deployed":
        return "deployed", detail
    if stage in {"local_verified", "pr_published", "merged"}:
        return "verified", detail
    if mission.status == "running":
        return "in_progress", detail
    if mission.status == "completed":
        return "implemented", detail
    return "queued", detail


def _knowledge_action_payload(
    db: Session,
    binding: SharedOSChangeBinding,
) -> dict[str, Any] | None:
    if binding.source_type != "claim":
        return None
    row = db.scalar(
        select(KnowledgeActionBinding).where(
            KnowledgeActionBinding.claim_id == binding.source_id,
            KnowledgeActionBinding.action_type == "shared_os_change",
            KnowledgeActionBinding.action_id == binding.proposal_id,
        )
    )
    if row is None:
        return None
    try:
        detail = json.loads(row.detail_json or "{}")
    except json.JSONDecodeError:
        detail = {}
    return {
        "id": row.id,
        "claim_id": row.claim_id,
        "action_type": row.action_type,
        "action_id": row.action_id,
        "status": row.status,
        "detail": detail,
        "updated_at": row.updated_at,
    }


def reconcile_shared_os_knowledge_action(
    db: Session,
    *,
    proposal_id: str,
) -> dict[str, Any]:
    binding = db.get(SharedOSChangeBinding, proposal_id)
    if binding is None:
        raise SharedOSChangeError("Shared OS change not found")
    if binding.source_type != "claim":
        return shared_os_change_state(db, proposal_id=proposal_id)

    status, detail = _project_action_status(db, binding)
    bind_action(
        db,
        claim_id=binding.source_id,
        action_type="shared_os_change",
        action_id=binding.proposal_id,
        status=status,
        detail=detail,
        created_by="system:runtime_change_reconciliation",
    )
    binding.status = status
    emit(
        db,
        "SHARED_OS_KNOWLEDGE_ACTION_RECONCILED",
        proposal_id=proposal_id,
        claim_id=binding.source_id,
        implementation_mission_id=binding.implementation_mission_id,
        action_status=status,
        delivery_stage=detail.get("delivery_stage"),
    )
    db.commit()
    return shared_os_change_state(db, proposal_id=proposal_id)


def reconcile_all_shared_os_knowledge_actions(db: Session) -> int:
    rows = db.scalars(
        select(SharedOSChangeBinding).where(
            SharedOSChangeBinding.source_type == "claim"
        )
    ).all()
    count = 0
    for row in rows:
        status, detail = _project_action_status(db, row)
        bind_action(
            db,
            claim_id=row.source_id,
            action_type="shared_os_change",
            action_id=row.proposal_id,
            status=status,
            detail=detail,
            created_by="system:runtime_change_reconciliation",
        )
        row.status = status
        count += 1
    db.commit()
    return count


def shared_os_change_state(
    db: Session,
    *,
    proposal_id: str,
) -> dict[str, Any]:
    binding = db.get(SharedOSChangeBinding, proposal_id)
    proposal = db.get(LabProposal, proposal_id)
    if binding is None or proposal is None:
        raise SharedOSChangeError("Shared OS change not found")
    mission = (
        db.get(LabMission, binding.implementation_mission_id)
        if binding.implementation_mission_id
        else None
    )
    initiative = db.scalar(
        select(HoldingsInitiative).where(
            HoldingsInitiative.proposal_id == proposal_id
        )
    )
    return {
        "proposal_id": proposal.id,
        "proposal_status": proposal.status,
        "title": proposal.title,
        "summary": proposal.summary,
        "impact": proposal.impact,
        "source_lab_id": binding.source_lab_id,
        "source_type": binding.source_type,
        "source_id": binding.source_id,
        "required_authority": binding.required_authority,
        "status": binding.status,
        "reviewed_by": proposal.reviewed_by,
        "initiative_id": initiative.id if initiative else None,
        "implementation_mission_id": binding.implementation_mission_id,
        "implementation_mission_status": mission.status if mission else None,
        "implementation_lab_id": mission.lab_id if mission else None,
        "knowledge_action": _knowledge_action_payload(db, binding),
    }


def list_shared_os_changes(
    db: Session,
    *,
    source_lab_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    query = select(SharedOSChangeBinding)
    if source_lab_id:
        query = query.where(SharedOSChangeBinding.source_lab_id == source_lab_id)
    rows = db.scalars(
        query.order_by(
            SharedOSChangeBinding.created_at.desc(),
            SharedOSChangeBinding.proposal_id.desc(),
        ).limit(max(1, min(limit, 500)))
    ).all()
    return [
        shared_os_change_state(db, proposal_id=row.proposal_id)
        for row in rows
    ]
