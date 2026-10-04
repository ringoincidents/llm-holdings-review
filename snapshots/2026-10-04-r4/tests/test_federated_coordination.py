import json
from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from runtime.db import Base
from runtime.models import (AISeat, AuthorityResolution, Case, Event, HoldingsWorkLedgerEntry,
    InterLabRequest, LabMission, LabMissionBudget, LabMissionWorkLink, LabWork,
    MissionAuthority, OrganizationalMemory)
from runtime.authority import (AuthorityError, authority_state, backfill_ownership,
    exception_inbox, resolve_authority, routine_handoff, seed_authority, set_ownership)
from runtime.capabilities import (CapabilityError, discover_work, registry_state,
    route_knowledge, upsert_capability)
from runtime.governance import set_kill_switch
from runtime.labs import create_lab
from runtime.lab_missions import create_mission, mission_state, _mission_memory
from runtime.lab_work import create_work


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def setup(db, objective="Analyze routing latency", level="A1"):
    lab = create_lab(db, title="Test Lab", objective="Testing")
    mission = create_mission(db, lab_id=lab.id, objective=objective, mode="research",
        owner="accountable-owner", authority_level=level)
    return lab, mission


def test_singular_durable_owner_is_distinct_from_execution(db):
    lab, mission = setup(db)
    seat = AISeat(lab_id=lab.id, seat_key="researcher", name="Worker", role="Research", model_policy="research-standard")
    db.add(seat); db.commit()
    create_work(db, lab_id=lab.id, work_type="question", title="Analyze latency")
    assert mission.owner == "accountable-owner"
    set_ownership(db, mission, owner=f"seat:{seat.id}"); db.commit(); db.expire_all()
    assert db.get(LabMission, mission.id).owner == f"seat:{seat.id}"
    assert db.query(MissionAuthority).filter_by(mission_id=mission.id).count() == 1
    with pytest.raises(AuthorityError):
        set_ownership(db, mission, owner="founder", authority_level="A4")
    mission.status = "running"
    with pytest.raises(AuthorityError):
        set_ownership(db, mission, owner="replacement")


def test_legacy_backfill_is_explicit_and_reads_do_not_write(db):
    lab = create_lab(db, title="Legacy", objective="Legacy")
    old = LabMission(lab_id=lab.id, objective="Analyze", mode="research", created_by="legacy-owner")
    db.add(old); db.commit()
    assert authority_state(db, old)["owner"] == "legacy-owner"
    mission_state(db, lab_id=lab.id, mission_id=old.id)
    assert db.get(MissionAuthority, old.id) is None
    backfill_ownership(db); backfill_ownership(db)
    assert db.query(MissionAuthority).filter_by(mission_id=old.id).count() == 1


@pytest.mark.parametrize("action,level,status", [
    ("search", "A0", "resolved"), ("continue_review", "A1", "resolved"),
    ("cross_lab_request", "A2", "pending"), ("resolve_conflict", "A3", "pending"),
    ("merge_delivery", "A4", "pending"), ("increase_budget", "A4", "pending"),
    ("promote_memory", "A4", "pending")])
def test_lowest_competent_resolution_never_grants_founder_approval(db, action, level, status):
    _, mission = setup(db)
    row = resolve_authority(db, mission, action=action, action_key=action); db.commit()
    assert (row.authority_level, row.status) == (level, status)
    assert resolve_authority(db, mission, action=action, action_key=action).id == row.id
    with pytest.raises(AuthorityError):
        resolve_authority(db, mission, action=action, action_key=action, requested_level="A4")
    if level == "A4": assert row.approver == "founder"


def test_kill_budget_data_delivery_and_stale_decisions_fail_closed(db):
    _, mission = setup(db)
    resolve_authority(db, mission, action="continue_review", action_key="prior"); db.commit()
    set_kill_switch(db, scope="global", stopped=True)
    assert resolve_authority(db, mission, action="search", action_key="stopped").status == "blocked"
    with pytest.raises(AuthorityError):
        resolve_authority(db, mission, action="continue_review", action_key="prior")
    set_kill_switch(db, scope="global", stopped=False)
    budget = db.get(LabMissionBudget, mission.id)
    budget.spent_usd = budget.hard_limit_usd; db.commit()
    assert resolve_authority(db, mission, action="search", action_key="budget").status == "blocked"
    budget.spent_usd = 0; db.commit()
    assert resolve_authority(db, mission, action="search", action_key="data", data_allowed=False).status == "blocked"
    assert resolve_authority(db, mission, action="search", action_key="delivery", delivery_allowed=False).status == "blocked"


def test_case_risk_and_company_kill_switch_cannot_be_bypassed(db):
    lab, mission = setup(db, level="A2")
    case = Case(company="test-company", title="Check security", risk_level="critical")
    db.add(case); db.flush()
    work = LabWork(lab_id=lab.id, work_type="task", title="Task", runtime_object_type="case", runtime_object_id=case.id)
    db.add(work); db.flush()
    db.add(LabMissionWorkLink(lab_id=lab.id, mission_id=mission.id, work_id=work.id, sequence=1)); db.commit()
    row = resolve_authority(db, mission, action="cross_lab_request", action_key="risky")
    assert row.authority_level == "A4" and row.status == "pending"
    assert "mandatory_human_governance" in json.loads(row.reasons_json)
    set_kill_switch(db, scope="company", target=case.company, stopped=True)
    assert resolve_authority(db, mission, action="search", action_key="stopped").status == "blocked"


def test_principles_are_idempotent_and_survive_memory_growth(db):
    _, mission = setup(db)
    first = seed_authority(db); db.commit()
    assert [row.id for row in first] == [row.id for row in seed_authority(db)]
    assert len(first) == 8
    for n in range(40):
        db.add(OrganizationalMemory(scope_type="holdings", scope_id="holdings", memory_type="knowledge",
            content="Later memory " * 200, source_id=str(n)))
    db.commit()
    memory = _mission_memory(db, mission)
    assert all(row.source_id in memory for row in first)


def test_routine_and_exception_inbox_preserve_executable_actions(db):
    _, mission = setup(db)
    routine = routine_handoff(db, mission, {"governed_action": "continue_review"}, action_key="routine")
    db.commit()
    assert routine["to"] == "reviewer" and exception_inbox(db) == []
    assert routine_handoff(db, mission, {"governed_action": "merge_delivery"}, action_key="unsafe") is None
    db.commit()
    inbox = exception_inbox(db)
    assert len(inbox) == 1
    assert {item["action"] for item in inbox[0]["actions"]} == {"approve", "revise", "defer", "cancel"}
    mission.step_count = mission.max_steps
    assert routine_handoff(db, mission, {"governed_action": "continue_review"}, action_key="bounded") is None


def test_internal_verification_mission_never_enters_founder_exception_inbox(db):
    lab = create_lab(db, title="Smoke Lab", objective="Verification")
    mission = create_mission(
        db,
        lab_id=lab.id,
        objective="Production E2E smoke prod-test-hidden",
        mode="research",
        created_by="system:e2e-smoke:prod-test-hidden",
        owner="researcher",
        authority_level="A1",
    )
    row = resolve_authority(
        db,
        mission,
        action="exception",
        action_key="smoke-a4",
    )
    db.commit()

    assert row.authority_level == "A4"
    assert row.status == "pending"
    assert exception_inbox(db) == []


def test_founder_exception_inbox_clips_long_objective_but_keeps_action(db):
    lab, mission = setup(db, objective="Long exception " + ("context " * 100))
    row = resolve_authority(
        db,
        mission,
        action="exception",
        action_key="long-a4",
    )
    db.commit()

    assert row.status == "pending"
    inbox = exception_inbox(db)
    assert len(inbox) == 1
    assert inbox[0]["mission_id"] == mission.id
    assert len(inbox[0]["objective"]) <= 220
    assert inbox[0]["objective"].endswith("…")
    assert {item["action"] for item in inbox[0]["actions"]} == {
        "approve",
        "revise",
        "defer",
        "cancel",
    }


def test_registry_routes_metadata_without_disclosing_or_promoting_private_memory(db):
    lab, _ = setup(db)
    other = create_lab(db, title="Other", objective="Other")
    private = OrganizationalMemory(scope_type="lab", scope_id=lab.id, status="retained", content="PRIVATE CONTENT")
    db.add(private); db.commit()
    cap = upsert_capability(db, lab_id=lab.id, capability_key="model_evaluation",
        domains=["model", "evaluation"], source_refs=[{"type": "memory", "id": private.id}]); db.commit()
    with pytest.raises(CapabilityError):
        upsert_capability(db, lab_id=other.id, capability_key="copied", domains=["model"],
            source_refs=[{"type": "memory", "id": private.id}])
    routed = route_knowledge(db, query="model evaluation")
    assert routed == route_knowledge(db, query="model evaluation")
    assert routed[0]["source_refs"] == [{"type": "memory", "id": private.id}]
    assert routed[0]["scope_id"] == lab.id and "PRIVATE CONTENT" not in json.dumps(registry_state(db))
    assert private.scope_type == "lab"
    cap.updated_at = datetime.now(timezone.utc) - timedelta(days=91); db.commit()
    assert route_knowledge(db, query="model evaluation") == []
    cap.updated_at = datetime.now(timezone.utc); db.commit()
    db.delete(private); db.commit()
    assert registry_state(db)[0]["missing_refs"] and route_knowledge(db, query="model evaluation") == []


def test_duplicate_suggestions_never_cancel_work_or_reorder_dependencies(db):
    lab, original = setup(db, objective="Analyze model latency")
    second = create_mission(db, lab_id=lab.id, objective=original.objective, mode="research")
    work = create_work(db, lab_id=lab.id, work_type="task", title=original.objective)
    before = [(entry.id, entry.sequence, entry.depends_on_json) for entry in db.scalars(select(HoldingsWorkLedgerEntry)).all()]
    row = discover_work(db, lab_id=lab.id, mission=second, query=original.objective); db.commit()
    suggestions = json.loads(row.suggestions_json)
    assert any(item.get("mission_id") == original.id for item in suggestions)
    assert any(item.get("work_id") == work.id for item in suggestions)
    assert original.status == "created" and work.status == "created"
    assert before == [(entry.id, entry.sequence, entry.depends_on_json) for entry in db.scalars(select(HoldingsWorkLedgerEntry)).all()]


def test_cross_lab_request_is_scoped_idempotent_and_authority_bound(db):
    source, mission = setup(db, objective="Model evaluation", level="A2")
    target = create_lab(db, title="Target", objective="Model")
    upsert_capability(db, lab_id=target.id, capability_key="model_evaluation", domains=["model", "evaluation"]); db.commit()
    row = discover_work(db, lab_id=source.id, mission=mission, query="Model evaluation private-query", route_request=True); db.commit()
    assert row.request_id
    request = db.get(InterLabRequest, row.request_id)
    assert request.to_lab_id == target.id and "private-query" not in request.message
    assert discover_work(db, lab_id=source.id, mission=mission, query="Model evaluation private-query", route_request=True).request_id == row.request_id
    low = create_mission(db, lab_id=source.id, objective="Model evaluation", mode="research")
    blocked = discover_work(db, lab_id=source.id, mission=low, query="Model evaluation", route_request=True); db.commit()
    assert blocked.request_id is None
    assert db.get(AuthorityResolution, blocked.resolution_id).status == "pending"


def test_transport_rejects_approval_spoofing_and_reads_are_pure(db):
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from runtime.db import get_db
    saved = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        lab, mission = setup(db)
        base = f"/labs/{lab.id}/missions/{mission.id}"
        assert client.get(base).json()["governance"]["owner"] == "accountable-owner"
        assert client.post(base + "/authority", json={"action": "merge_delivery", "action_key": "m", "human_approved": True}).status_code == 422
        result = client.post(base + "/authority", json={"action": "merge_delivery", "action_key": "m"})
        assert result.json()["status"] == "pending" and result.json()["authority_level"] == "A4"
        assert client.put(base + "/owner", json={"owner": "owner", "authority_level": "A4"}).status_code == 422
        before = db.query(Event).count()
        assert client.get("/labs/organization/exceptions").status_code == 200
        assert client.get("/labs/organization/capabilities").status_code == 200
        assert db.query(Event).count() == before
    finally:
        app.dependency_overrides.clear(); app.dependency_overrides.update(saved)


def test_delegation_change_can_resolve_a_previously_routed_lab_request(db):
    source, mission = setup(db, objective="Model evaluation")
    target = create_lab(db, title="Target", objective="Models")
    upsert_capability(db, lab_id=target.id, capability_key="model_evaluation", domains=["model", "evaluation"])
    db.commit()
    row = discover_work(db, lab_id=source.id, mission=mission, query="Model evaluation", route_request=True); db.commit()
    assert row.request_id is None
    set_ownership(db, mission, owner=mission.owner, authority_level="A2"); db.commit()
    refreshed = discover_work(db, lab_id=source.id, mission=mission, query="Model evaluation", route_request=True); db.commit()
    assert refreshed.id == row.id and refreshed.request_id


def test_weak_metadata_match_does_not_route_cross_lab_work(db):
    source, mission = setup(db, level="A2")
    target = create_lab(db, title="Target", objective="Elsewhere")
    upsert_capability(db, lab_id=target.id, capability_key="market_research", domains=["market"])
    db.commit()
    row = discover_work(db, lab_id=source.id, mission=mission,
                        query="Explore market architecture interface latency", route_request=True)
    db.commit()
    assert row.request_id is None


def test_unique_discovery_scope_prevents_duplicate_records(db):
    from sqlalchemy.exc import IntegrityError
    from runtime.models import WorkDiscovery
    source, mission = setup(db)
    existing = discover_work(db, lab_id=source.id, mission=mission, query="Latency query"); db.commit()
    duplicate = WorkDiscovery(lab_id=source.id, mission_id=mission.id,
        scope_key=existing.scope_key, query_hash=existing.query_hash, suggestions_json="[]")
    db.add(duplicate)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
