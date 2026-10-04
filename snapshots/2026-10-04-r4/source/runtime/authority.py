"""Federated policy is additive; resolution never grants executor permission."""
import json
from sqlalchemy import select
from .models import (AISeat, AuthorityResolution, Case, LabMission, LabMissionWorkLink,
                     LabWork, MissionAuthority, OrganizationalMemory)
from .governance import blocking_kill_switch, requires_approval
from .events import emit

LEVELS = ("A0", "A1", "A2", "A3", "A4")
ACTION_LEVELS = {
    "search": "A0", "draft": "A0", "local_check": "A0",
    "continue_research": "A1", "continue_review": "A1",
    "cross_lab_request": "A2", "lab_priority": "A2", "resolve_conflict": "A3",
    "promote_memory": "A4", "merge_delivery": "A4", "increase_budget": "A4",
    "change_policy": "A4", "create_lab": "A4", "exception": "A4",
}
PRINCIPLES = (
    ("authority_vertical", "Authority Flows Vertically: A0–A4 권한은 기존 승인·예산·데이터·배포 정책을 우회하지 않는다."),
    ("knowledge_horizontal", "Knowledge Flows Horizontally: Lab 협력은 출처와 범위를 유지한 참조로 전달한다."),
    ("memory_distributed", "Memory Remains Distributed: 역량 발견은 비공개 기억의 전사 승격을 의미하지 않는다."),
    ("singular_responsibility", "Responsibility Remains Singular: Mission 책임자는 하나이며 실행 Seat와 구분된다."),
    ("lowest_competent", "Decide at the Lowest Competent Level: 명시적으로 허가된 최저 권한에서 결정하고 이관 이유를 기록한다."),
    ("founder_exceptions", "Founder Handles Exceptions, Not Routine Operations: A4와 해결되지 않은 예외를 Founder에게 전달한다."),
    ("know_who_knows", "Know Who Knows: 역량·지식 도메인·관련 작업 메타데이터로 관련 Lab을 찾는다."),
    ("reuse_before_duplicate", "Reuse Before Duplicate Work: 기존 역량을 확인하되 활성 Work를 덮어쓰거나 취소하지 않는다."),
)


class AuthorityError(ValueError):
    pass


def validate_owner(db, mission, owner, level):
    if level not in LEVELS[:3] or not owner.strip() or len(owner) > 128:
        raise AuthorityError("Mission owner/delegation is invalid")
    if owner.startswith("seat:"):
        seat = db.get(AISeat, owner[5:])
        if not seat or seat.lab_id != mission.lab_id:
            raise AuthorityError("Owner Seat must belong to Mission Lab")


def ensure_ownership(db, mission, *, owner=None, authority_level="A1"):
    existing = db.get(MissionAuthority, mission.id)
    if existing:
        return existing
    owner = (owner or mission.created_by or "founder").strip()
    validate_owner(db, mission, owner, authority_level)
    row = MissionAuthority(mission_id=mission.id, owner=owner,
        authority_level=authority_level, escalation_policy="lowest_competent")
    db.add(row); db.flush(); db.expire(mission, ["governance"])
    emit(db, "MISSION_OWNER_ASSIGNED", mission_id=mission.id, lab_id=mission.lab_id,
         owner=owner, authority_level=authority_level)
    return row


def set_ownership(db, mission, *, owner, authority_level="A1"):
    validate_owner(db, mission, owner, authority_level)
    if mission.status in {"queued", "running"}:
        raise AuthorityError("Cannot transfer ownership during active execution")
    row = ensure_ownership(db, mission)
    previous = {"owner": row.owner, "authority_level": row.authority_level}
    row.owner, row.authority_level = owner.strip(), authority_level
    db.flush(); db.expire(mission, ["governance"])
    emit(db, "MISSION_OWNER_CHANGED", mission_id=mission.id, previous=previous,
         owner=row.owner, authority_level=authority_level, authorized_by="founder")
    return row


def backfill_ownership(db):
    for mission in db.scalars(select(LabMission)).all():
        ensure_ownership(db, mission)
    db.commit()


def seed_authority(db):
    rows = []
    for key, content in PRINCIPLES:
        source = f"LLMH-025:{key}"
        row = db.scalar(select(OrganizationalMemory).where(
            OrganizationalMemory.scope_type == "holdings",
            OrganizationalMemory.scope_id == "holdings",
            OrganizationalMemory.source_type == "operating_principle",
            OrganizationalMemory.source_id == source,
            OrganizationalMemory.status == "retained"))
        if row is None:
            row = OrganizationalMemory(scope_type="holdings", scope_id="holdings",
                memory_type="principle", content=content, status="retained",
                source_type="operating_principle", source_id=source, created_by="founder")
            db.add(row); db.flush()
            emit(db, "HOLDINGS_OPERATING_PRINCIPLE_COMPILED", memory_id=row.id, source_id=source)
        rows.append(row)
    return rows


def authority_state(db, mission):
    row = db.get(MissionAuthority, mission.id)
    return {"owner": row.owner if row else (mission.created_by or "founder"),
            "authority_level": row.authority_level if row else "A1",
            "escalation_policy": row.escalation_policy if row else "lowest_competent",
            "levels": dict(zip(LEVELS, ("agent", "mission", "lab", "hq", "founder")))}


def guard_reasons(db, mission, action):
    from .cost_governor import budget_state
    cases = list(db.scalars(select(Case).join(LabWork, LabWork.runtime_object_id == Case.id)
        .join(LabMissionWorkLink, LabMissionWorkLink.work_id == LabWork.id)
        .where(LabMissionWorkLink.mission_id == mission.id)).all())
    reasons = []
    if blocking_kill_switch(db) or any(blocking_kill_switch(
            db, company=case.company, case_id=case.id) for case in cases):
        reasons.append("kill_switch")
    budget = budget_state(db, mission)
    if action != "increase_budget" and (
            budget["remaining_usd"] <= 0 or budget["status"] == "hard_stop"):
        reasons.append("budget_exhausted")
    if requires_approval(mission.objective, "low", False) or any(
            requires_approval(case.title, case.risk_level, False) for case in cases):
        reasons.append("mandatory_human_governance")
    return reasons


def resolution_payload(row):
    return {"id": row.id, "mission_id": row.mission_id, "action": row.action,
        "authority_level": row.authority_level, "approver": row.approver,
        "escalation_policy": row.escalation_policy, "status": row.status,
        "reasons": json.loads(row.reasons_json)}


def resolve_authority(db, mission, *, action, action_key, requested_level="A0",
                      data_allowed=True, delivery_allowed=True):
    if action not in ACTION_LEVELS or requested_level not in LEVELS:
        raise AuthorityError("Unknown governed action or level")
    if not action_key.strip() or len(action_key) > 160:
        raise AuthorityError("Invalid idempotency key")
    fingerprint = json.dumps([action, requested_level, data_allowed, delivery_allowed])
    existing = db.scalar(select(AuthorityResolution).where(
        AuthorityResolution.mission_id == mission.id, AuthorityResolution.action_key == action_key))
    guards = guard_reasons(db, mission, action)
    if existing:
        if existing.fingerprint != fingerprint:
            raise AuthorityError("Action key belongs to another request")
        if existing.status == "resolved" and guards:
            raise AuthorityError("Previously resolved action is now blocked")
        return existing
    policy = ensure_ownership(db, mission)
    floor = ACTION_LEVELS[action]
    level = LEVELS[max(LEVELS.index(floor), LEVELS.index(requested_level))]
    reasons = list(guards)
    if LEVELS.index(requested_level) < LEVELS.index(floor):
        reasons.append("action_requires_higher_competence")
    if not data_allowed:
        reasons.append("data_policy")
    if not delivery_allowed:
        reasons.append("delivery_policy")
    if "mandatory_human_governance" in reasons:
        level = "A4"
    status = "blocked" if any(reason in reasons for reason in
        ("kill_switch", "budget_exhausted", "data_policy", "delivery_policy")) else "resolved"
    approver = policy.owner
    if level == "A4":
        approver = "founder"
        if status != "blocked": status = "pending"
    elif LEVELS.index(level) > LEVELS.index(policy.authority_level):
        approver = f"lab:{mission.lab_id}" if level == "A2" else "hq"
        reasons.append("outside_mission_delegation")
        if status != "blocked": status = "pending"
    row = AuthorityResolution(mission_id=mission.id, action_key=action_key,
        action=action, authority_level=level, approver=approver,
        escalation_policy=policy.escalation_policy, status=status,
        reasons_json=json.dumps(reasons), fingerprint=fingerprint)
    db.add(row); db.flush()
    emit(db, "AUTHORITY_RESOLVED", **resolution_payload(row), lab_id=mission.lab_id)
    return row


def routine_handoff(db, mission, handoff, *, action_key):
    action = handoff.get("governed_action", "exception")
    if action not in ("continue_research", "continue_review"):
        action = "exception"
    try:
        row = resolve_authority(db, mission, action=action, action_key=action_key)
    except AuthorityError:
        return None
    if row.status != "resolved" or mission.step_count >= mission.max_steps:
        return None
    emit(db, "ROUTINE_DECISION_RESOLVED", mission_id=mission.id,
         resolution_id=row.id, authority_level=row.authority_level)
    return {"to": "reviewer" if action == "continue_review" else "researcher",
        "request_type": "review" if action == "continue_review" else "question",
        "message": str(handoff.get("message", "Continue within Mission"))[:2000],
        "reason": "Policy-authorized routine decision", "_origin": "authority"}


def settle_authority(db, mission, action):
    resolvable_statuses = (
        ("pending",)
        if action == "defer"
        else ("pending", "deferred")
    )
    for row in db.scalars(select(AuthorityResolution).where(
        AuthorityResolution.mission_id == mission.id,
        AuthorityResolution.authority_level == "A4",
        AuthorityResolution.status.in_(resolvable_statuses))).all():
        row.status = {
            "approve": "approved",
            "revise": "revised",
            "defer": "deferred",
            "cancel": "cancelled",
        }[action]
        emit(db, "AUTHORITY_FOUNDER_ACTION", mission_id=mission.id, resolution_id=row.id,
             action=action, authorized_by="founder")


def _clip_founder_inbox_text(value: str, limit: int = 220) -> str:
    text = " ".join((value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _is_internal_verification_mission(mission: LabMission) -> bool:
    # Internal verification is identified only by a server-created actor namespace.
    # User-controlled objective text must never hide a Founder exception.
    created_by = str(mission.created_by or "")
    return created_by.startswith("system:e2e-smoke:")


def deferred_inbox(db):
    """Founder hold tray across all Labs; durable records remain in Mission history."""

    missions = db.scalars(
        select(LabMission)
        .where(LabMission.status == "deferred")
        .order_by(LabMission.updated_at.desc(), LabMission.id.desc())
        .limit(20)
    ).all()
    return [
        {
            "mission_id": mission.id,
            "lab_id": mission.lab_id,
            "objective": _clip_founder_inbox_text(mission.objective),
            "owner": mission.owner,
            "authority_level": "A4",
            "status": mission.status,
        }
        for mission in missions
        if not _is_internal_verification_mission(mission)
    ]


def exception_inbox(db):
    """Return only unresolved, executable Founder exceptions.

    Durable history can contain old Artifacts that once requested Founder input,
    but a Founder inbox is an operational queue rather than an audit log. Internal
    verification Missions and stale decision text from already completed Missions
    therefore stay in history without reappearing as current A4 work.
    """
    from .lab_missions import mission_state

    entries = []
    missions = db.scalars(
        select(LabMission)
        .where(LabMission.status.not_in(("cancelled", "superseded", "deferred")))
        .order_by(LabMission.created_at.desc(), LabMission.id.desc())
    ).all()
    for mission in missions:
        if _is_internal_verification_mission(mission):
            continue

        state = mission_state(db, lab_id=mission.lab_id, mission_id=mission.id)
        brief = state["founder_brief"]
        actions = list(state.get("founder_actions") or [])
        if not brief.get("founder_decision_required") or not actions:
            continue

        decision_source = str(brief.get("decision_source") or "")
        if (
            mission.status == "completed"
            and decision_source
            in {
                "artifact_brief",
                "legacy_artifact_brief",
                "structured_handoff",
            }
        ):
            # The durable Artifact remains inspectable, but a terminal Mission
            # must not keep resurfacing because of stale embedded decision text.
            continue

        entries.append(
            {
                "mission_id": mission.id,
                "lab_id": mission.lab_id,
                "objective": _clip_founder_inbox_text(mission.objective),
                "owner": mission.owner,
                "authority_level": "A4",
                "status": mission.status,
                "question": _clip_founder_inbox_text(
                    str(brief.get("decision_question") or ""),
                    180,
                ),
                "reason": decision_source,
                "actions": actions,
            }
        )
        if len(entries) >= 12:
            break
    return entries
