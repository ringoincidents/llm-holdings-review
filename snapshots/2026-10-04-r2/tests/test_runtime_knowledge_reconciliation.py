import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from runtime.db import Base
from runtime.delivery import ensure_delivery
from runtime.knowledge_lifecycle import (
    concept_projection,
    create_claim,
    ensure_concept,
)
from runtime.models import LabMission, SharedOSChangeBinding
from runtime.organization import ensure_organization, organization_labs
from runtime.shared_os_change import (
    approve_shared_os_change,
    reconcile_all_shared_os_knowledge_actions,
    reconcile_shared_os_knowledge_action,
    shared_os_change_state,
    submit_shared_os_change,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()


def claim_backed_change(db):
    ensure_organization(db)
    labs = organization_labs(db)
    ensure_concept(
        db,
        key="founder-interface-runtime-state",
        title="Founder Interface Runtime State",
        scope_type="lab",
        scope_id=labs["design"].id,
        created_by="founder",
    )
    claim = create_claim(
        db,
        concept_key="founder-interface-runtime-state",
        content="Shared Founder interface state should be projected from canonical Runtime truth.",
        initial_status="current",
        disposition="implement",
        source_type="decision",
        source_id="DEC-FOUNDER-UI-001",
        created_by="founder",
        scope_type="lab",
        scope_id=labs["design"].id,
    )
    db.commit()
    binding = submit_shared_os_change(
        db,
        source_lab_id=labs["design"].id,
        title="Implement canonical Founder state projection",
        summary="Runtime Engineering must implement the accepted Claim.",
        source_type="claim",
        source_id=claim.id,
        impact="cross_lab",
        created_by="seat:design-reviewer",
    )
    return labs, claim, binding


def test_claim_link_starts_planned_then_hq_approval_queues_real_runtime_mission(db):
    labs, claim, binding = claim_backed_change(db)

    submitted = shared_os_change_state(db, proposal_id=binding.proposal_id)
    assert submitted["knowledge_action"]["claim_id"] == claim.id
    assert submitted["knowledge_action"]["status"] == "planned"
    projection = concept_projection(
        db,
        key="founder-interface-runtime-state",
        scope_type="lab",
        scope_id=labs["design"].id,
    )
    assert projection["action_state"] == "planned"

    approved = approve_shared_os_change(
        db,
        proposal_id=binding.proposal_id,
        reviewed_by="hq",
        priority="high",
    )
    assert approved["implementation_lab_id"] == labs["runtime"].id
    assert approved["knowledge_action"]["status"] == "queued"
    assert approved["knowledge_action"]["detail"]["implementation_mission_id"]


def test_runtime_delivery_drives_claim_projection_without_document_edit(db, monkeypatch):
    labs, claim, binding = claim_backed_change(db)
    approved = approve_shared_os_change(
        db,
        proposal_id=binding.proposal_id,
        reviewed_by="hq",
        priority="high",
    )
    mission = db.get(LabMission, approved["implementation_mission_id"])
    assert mission is not None

    mission.status = "running"
    db.commit()
    running = reconcile_shared_os_knowledge_action(
        db, proposal_id=binding.proposal_id
    )
    assert running["knowledge_action"]["status"] == "in_progress"

    delivery = ensure_delivery(db, mission)
    delivery.stage = "local_verified"
    delivery.status = "waiting_publication"
    delivery.branch = "holdings/runtime-change"
    db.commit()
    verified = reconcile_shared_os_knowledge_action(
        db, proposal_id=binding.proposal_id
    )
    assert verified["knowledge_action"]["status"] == "verified"
    assert verified["knowledge_action"]["detail"]["delivery_stage"] == "local_verified"
    assert verified["knowledge_action"]["detail"]["branch"] == "holdings/runtime-change"

    delivery.stage = "merged"
    delivery.status = "waiting_deploy"
    delivery.merged_sha = "merge-123"
    mission.status = "waiting_for_delivery"
    db.commit()
    still_verified = reconcile_shared_os_knowledge_action(
        db, proposal_id=binding.proposal_id
    )
    assert still_verified["knowledge_action"]["status"] == "verified"
    assert still_verified["knowledge_action"]["detail"]["merged_sha"] == "merge-123"

    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "merge-123")
    deployed = reconcile_shared_os_knowledge_action(
        db, proposal_id=binding.proposal_id
    )
    assert deployed["knowledge_action"]["status"] == "deployed"
    assert deployed["knowledge_action"]["detail"]["deployed_sha"] == "merge-123"

    projection = concept_projection(
        db,
        key="founder-interface-runtime-state",
        scope_type="lab",
        scope_id=labs["design"].id,
    )
    assert projection["action_state"] == "deployed"
    assert projection["already_addressed"] is True

    # The immutable Claim text itself is unchanged; implementation state is a projection.
    assert claim.content == (
        "Shared Founder interface state should be projected from canonical Runtime truth."
    )


def test_startup_style_reconciliation_is_idempotent(db):
    _labs, claim, binding = claim_backed_change(db)
    approve_shared_os_change(
        db,
        proposal_id=binding.proposal_id,
        reviewed_by="hq",
    )
    first = reconcile_all_shared_os_knowledge_actions(db)
    second = reconcile_all_shared_os_knowledge_actions(db)
    assert first == second == 1

    state = shared_os_change_state(db, proposal_id=binding.proposal_id)
    assert state["knowledge_action"]["claim_id"] == claim.id
    assert state["knowledge_action"]["status"] == "queued"
    assert db.query(SharedOSChangeBinding).count() == 1


def test_non_claim_runtime_change_does_not_fabricate_knowledge_binding(db):
    ensure_organization(db)
    labs = organization_labs(db)
    from runtime.lab_missions import create_mission

    source = create_mission(
        db,
        lab_id=labs["quantrade"].id,
        objective="Report a shared API defect",
        mode="research",
    )
    binding = submit_shared_os_change(
        db,
        source_lab_id=labs["quantrade"].id,
        title="Shared API defect",
        summary="Mission provenance exists, but no KnowledgeClaim is linked.",
        source_type="mission",
        source_id=source.id,
    )
    state = reconcile_shared_os_knowledge_action(
        db, proposal_id=binding.proposal_id
    )
    assert state["knowledge_action"] is None
