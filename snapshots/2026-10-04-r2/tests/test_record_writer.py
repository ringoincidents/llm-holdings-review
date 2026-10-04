from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

import pytest

from runtime.db import Base
from runtime.knowledge_lifecycle import (
    KnowledgeClaim,
    KnowledgeClaimResolution,
    concept_projection,
    create_claim,
    ensure_concept,
    resolve_candidate_claim,
)
from runtime.knowledge_reconciliation import KnowledgeReconciliationRecord
from runtime.organization import ensure_organization, organization_labs
from runtime.record_writer import (
    record_writer_queue,
    resolve_record_writer_item,
    seed_quantrade_canonical_vision,
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


def _claim(
    db: Session,
    *,
    key: str,
    content: str,
    status: str,
    source_id: str,
):
    return create_claim(
        db,
        concept_key=key,
        content=content,
        initial_status=status,
        disposition="reference_only",
        source_type="founder_direction",
        source_id=source_id,
        created_by="founder",
        scope_type="holdings",
        scope_id="holdings",
    )


def test_candidate_resolution_supersedes_without_rewriting_history(db):
    ensure_concept(
        db,
        key="record-writer-direction",
        title="Record Writer Direction",
        scope_type="holdings",
        scope_id="holdings",
        created_by="founder",
    )
    old = _claim(
        db,
        key="record-writer-direction",
        content="기존 방향을 유지한다.",
        status="current",
        source_id="old",
    )
    candidate = _claim(
        db,
        key="record-writer-direction",
        content="새 방향으로 전환한다.",
        status="candidate",
        source_id="candidate",
    )

    resolution = resolve_candidate_claim(
        db,
        claim_id=candidate.id,
        action="supersede",
        target_claim_id=old.id,
        rationale="Founder가 새 방향을 승인함",
        resolved_by="founder",
        authority_level="A4",
    )
    db.commit()

    projection = concept_projection(
        db,
        key="record-writer-direction",
        scope_type="holdings",
        scope_id="holdings",
    )
    assert resolution.action == "supersede"
    assert [item["id"] for item in projection["current_claims"]] == [candidate.id]
    history = {item["id"]: item for item in projection["history"]}
    assert history[old.id]["effective_status"] == "superseded"
    assert history[candidate.id]["effective_status"] == "current"
    assert db.get(KnowledgeClaim, old.id) is not None
    assert db.get(KnowledgeClaim, candidate.id) is not None


def test_experiment_resolution_stays_out_of_current_truth(db):
    ensure_concept(
        db,
        key="bounded-experiment",
        title="Bounded Experiment",
        scope_type="holdings",
        scope_id="holdings",
        created_by="founder",
    )
    candidate = _claim(
        db,
        key="bounded-experiment",
        content="이 아이디어는 실험으로만 검증한다.",
        status="candidate",
        source_id="experiment",
    )
    resolve_candidate_claim(
        db,
        claim_id=candidate.id,
        action="archive",
        disposition="experiment",
        rationale="제품 정체성이 아니라 제한된 실험으로 보존",
        resolved_by="founder",
        authority_level="A4",
    )
    db.commit()

    projection = concept_projection(
        db,
        key="bounded-experiment",
        scope_type="holdings",
        scope_id="holdings",
    )
    assert projection["current_claims"] == []
    item = next(row for row in projection["history"] if row["id"] == candidate.id)
    assert item["effective_status"] == "historical"
    assert item["effective_disposition"] == "experiment"


def test_record_writer_queue_hides_routine_artifact_candidate(db):
    ensure_concept(
        db,
        key="queue-signal",
        title="Queue Signal",
        scope_type="holdings",
        scope_id="holdings",
        created_by="founder",
    )
    artifact_claim = _claim(
        db,
        key="queue-signal",
        content="routine artifact note",
        status="candidate",
        source_id="artifact-candidate",
    )
    founder_claim = _claim(
        db,
        key="queue-signal",
        content="Founder direction note",
        status="candidate",
        source_id="founder-candidate",
    )
    db.add_all(
        [
            KnowledgeReconciliationRecord(
                source_type="artifact",
                source_id="ART-ROUTINE",
                source_hash="a" * 64,
                scope_type="holdings",
                scope_id="holdings",
                status="candidate_created",
                concept_id=artifact_claim.concept_id,
                claim_id=artifact_claim.id,
                relationship_preview="related",
            ),
            KnowledgeReconciliationRecord(
                source_type="founder_note",
                source_id="NOTE-DIRECTION",
                source_hash="b" * 64,
                scope_type="holdings",
                scope_id="holdings",
                status="candidate_created",
                concept_id=founder_claim.concept_id,
                claim_id=founder_claim.id,
                relationship_preview="possible_extends",
            ),
        ]
    )
    db.commit()

    queue = record_writer_queue(db)
    assert queue["count"] == 1
    assert queue["records"][0]["source_type"] == "founder_note"
    assert queue["policy"]["model_is_drafter_not_authority"] is True


def test_record_writer_queue_surfaces_unresolved_source_for_explicit_semantic_review(db):
    record = KnowledgeReconciliationRecord(
        source_type="founder_note",
        source_id="NOTE-NEEDS-SEMANTIC",
        source_hash="d" * 64,
        scope_type="holdings",
        scope_id="holdings",
        status="needs_semantic_resolution",
        message="No deterministic Concept match.",
    )
    db.add(record)
    db.commit()

    queue = record_writer_queue(db)
    item = next(row for row in queue["records"] if row["id"] == record.id)

    assert item["requires_founder"] is True
    assert item["classification"] == "unresolved"
    assert "semantic_review" in item["founder_actions"]
    assert "archive" in item["founder_actions"]
    assert "reject" in item["founder_actions"]
    assert item["candidate_claim"] is None


def test_record_writer_resolution_is_append_only_and_idempotent(db):
    ensure_concept(
        db,
        key="record-resolution",
        title="Record Resolution",
        scope_type="holdings",
        scope_id="holdings",
        created_by="founder",
    )
    candidate = _claim(
        db,
        key="record-resolution",
        content="Founder 승인 후 현재 지식이 된다.",
        status="candidate",
        source_id="resolution-candidate",
    )
    record = KnowledgeReconciliationRecord(
        source_type="founder_note",
        source_id="NOTE-RESOLVE",
        source_hash="c" * 64,
        scope_type="holdings",
        scope_id="holdings",
        status="candidate_created",
        concept_id=candidate.concept_id,
        claim_id=candidate.id,
        relationship_preview="possible_extends",
    )
    db.add(record)
    db.commit()

    first = resolve_record_writer_item(
        db,
        record_id=record.id,
        action="adopt",
        rationale="현재 방향으로 승인",
    )
    db.commit()
    second = resolve_record_writer_item(
        db,
        record_id=record.id,
        action="adopt",
        rationale="중복 호출",
    )
    db.commit()

    assert first["status"] == "governed_current"
    assert second["status"] == "governed_current"
    resolutions = list(
        db.scalars(
            select(KnowledgeClaimResolution).where(
                KnowledgeClaimResolution.claim_id == candidate.id
            )
        )
    )
    assert len(resolutions) == 1


def test_quantrade_canonical_vision_seed_is_idempotent_and_current(db):
    ensure_organization(db)
    seed_quantrade_canonical_vision(db)
    seed_quantrade_canonical_vision(db)
    db.commit()

    quantrade = organization_labs(db)["quantrade"]
    projection = concept_projection(
        db,
        key="quantrade-private-investment-office-vision",
        scope_type="lab",
        scope_id=quantrade.id,
    )
    assert projection["projection_status"] == "current"
    assert len(projection["current_claims"]) == 1
    content = projection["current_claims"][0]["content"]
    assert "Private Investment Office" in content
    assert "Client Intelligence" in content
    assert "Performance & Learning" in content
    assert "암호화폐 자동매매 봇이 아니라" in content
