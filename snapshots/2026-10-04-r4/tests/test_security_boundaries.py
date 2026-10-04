import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.auth import validate_auth_configuration
from backend.app.main import app
from runtime.authority import exception_inbox, resolve_authority
from runtime.db import Base
from runtime.lab_missions import create_mission
from runtime.labs import (
    LabObjectScopeViolation,
    create_lab,
    link_object,
    linked_cases,
)
from runtime.memory_trust import (
    MemoryTrustError,
    ensure_memory_trust,
    infer_trust_class,
    trust_for_memory,
)
from runtime.models import Case, OrganizationalMemory, OrganizationalMemoryTrust


client = TestClient(app)


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


def test_managed_cloud_requires_runtime_auth_token(monkeypatch):
    monkeypatch.delenv("LLM_HOLDINGS_API_TOKEN", raising=False)
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "test-project")
    with pytest.raises(RuntimeError, match="LLM_HOLDINGS_API_TOKEN"):
        validate_auth_configuration()


def test_authenticated_api_ignores_payload_actor_identity(monkeypatch):
    monkeypatch.setenv("LLM_HOLDINGS_API_TOKEN", "security-test-token")
    headers = {"Authorization": "Bearer security-test-token"}

    lab = client.post(
        "/labs",
        json={
            "title": "Actor Boundary Lab",
            "objective": "Verify server-owned actor identity",
            "created_by": "system:e2e-smoke:spoofed",
        },
        headers=headers,
    )
    assert lab.status_code == 201
    lab_body = lab.json()
    assert lab_body["created_by"] == "founder"

    mission = client.post(
        f"/labs/{lab_body['id']}/missions",
        json={
            "objective": "Production E2E smoke attacker-controlled-objective",
            "mode": "research",
            "created_by": "system:e2e-smoke:spoofed",
        },
        headers=headers,
    )
    assert mission.status_code == 201
    assert mission.json()["created_by"] == "founder"

    memory = client.post(
        f"/labs/{lab_body['id']}/memory",
        json={
            "scope_type": "lab",
            "scope_id": lab_body["id"],
            "memory_type": "knowledge",
            "content": "Actor identity must come from authenticated server context.",
            "source_type": "internal",
            "created_by": "hq:spoofed",
        },
        headers=headers,
    )
    assert memory.status_code == 201
    assert memory.json()["created_by"] == "founder"


def test_unknown_memory_actor_is_not_governed_by_default():
    assert (
        infer_trust_class(created_by="mystery-actor", source_type="internal")
        == "inferred_internal"
    )


def test_memory_trust_rejects_authority_mismatch(db):
    memory = OrganizationalMemory(
        scope_type="lab",
        scope_id="lab-test",
        memory_type="knowledge",
        content="Untrusted inferred memory",
        source_type="internal",
        created_by="agent:test",
    )
    db.add(memory)
    db.flush()

    with pytest.raises(MemoryTrustError, match="must match"):
        ensure_memory_trust(
            db,
            memory,
            trust_class="inferred_internal",
            authority_level="A4",
        )


def test_memory_trust_read_path_does_not_persist_backfill(db):
    memory = OrganizationalMemory(
        scope_type="lab",
        scope_id="lab-test",
        memory_type="knowledge",
        content="Legacy memory without companion trust row",
        source_type="internal",
        created_by="legacy-actor",
    )
    db.add(memory)
    db.commit()

    assert db.get(OrganizationalMemoryTrust, memory.id) is None
    projected = trust_for_memory(db, memory)
    assert projected.trust_class == "inferred_internal"
    assert db.get(OrganizationalMemoryTrust, memory.id) is None


def test_cross_lab_contains_is_blocked_but_reference_does_not_expose_case(db):
    first = create_lab(db, title="First Lab", objective="Own case")
    second = create_lab(db, title="Second Lab", objective="Reference only")
    case = Case(company="test", title="Scoped case", risk_level="low")
    db.add(case)
    db.commit()

    link_object(
        db,
        lab_id=first.id,
        object_type="case",
        object_id=case.id,
        relationship="contains",
    )

    with pytest.raises(LabObjectScopeViolation):
        link_object(
            db,
            lab_id=second.id,
            object_type="case",
            object_id=case.id,
            relationship="contains",
        )

    link_object(
        db,
        lab_id=second.id,
        object_type="case",
        object_id=case.id,
        relationship="reference",
    )
    assert linked_cases(db, second.id) == []


def test_objective_text_cannot_hide_founder_exception(db):
    lab = create_lab(db, title="Review Lab", objective="Verify exception visibility")
    mission = create_mission(
        db,
        lab_id=lab.id,
        objective="Production E2E smoke user-controlled-text",
        mode="research",
        created_by="founder",
        owner="researcher",
        authority_level="A1",
    )
    row = resolve_authority(
        db,
        mission,
        action="exception",
        action_key="objective-spoof",
    )
    db.commit()

    assert row.status == "pending"
    inbox = exception_inbox(db)
    assert any(item["mission_id"] == mission.id for item in inbox)


def test_app_startup_no_longer_runs_production_smoke(monkeypatch):
    import backend.app.main as main_module
    import tools.production_e2e_smoke as smoke_module

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("production smoke must not run inside app startup")

    monkeypatch.setattr(smoke_module, "run_startup_smoke_if_enabled", fail_if_called)
    monkeypatch.setattr(main_module, "ensure_background_worker_started", lambda: None)
    monkeypatch.setattr(main_module, "ensure_quantrade_ceo_sync_started", lambda: None)

    main_module._start_runtime_workers()
