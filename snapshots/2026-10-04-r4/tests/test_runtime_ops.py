from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from runtime.db import Base
from runtime.models import ExecutionRun, MissionExecutionJob
from runtime.runtime_ops import runtime_ops_snapshot


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


def _github_handler(main_sha="abc123", *, pending=False):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": main_sha})
        if request.url.path.endswith(f"/commits/{main_sha}/check-runs"):
            return httpx.Response(
                200,
                json={
                    "check_runs": [
                        {
                            "name": "backend",
                            "status": "in_progress" if pending else "completed",
                            "conclusion": None if pending else "success",
                        },
                        {
                            "name": "mobile",
                            "status": "completed",
                            "conclusion": "success",
                        },
                    ]
                },
            )
        return httpx.Response(404)

    return handler


def test_runtime_ops_projects_deployed_main_ci_and_measured_execution_health(
    monkeypatch,
    db,
):
    monkeypatch.setenv("LLM_HOLDINGS_DEV_REPO", "ringoincidents/llm-holdings-runtime")
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc123")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    monkeypatch.setenv("RAILWAY_SERVICE_NAME", "llm-holdings-runtime")
    monkeypatch.setenv("RAILWAY_PROJECT_NAME", "capable-charm")
    monkeypatch.setenv("RAILWAY_DEPLOYMENT_ID", "dep-1")

    db.add(
        MissionExecutionJob(
            lab_id="LAB-OPS",
            mission_id="MIS-OPS",
            status="queued",
            created_by="founder",
        )
    )
    db.commit()

    with httpx.Client(
        transport=httpx.MockTransport(_github_handler())
    ) as client:
        snapshot = runtime_ops_snapshot(db=db, client=client)

    assert snapshot["schema"] == "runtime_ops_v0.2"
    assert snapshot["runtime"]["ok"] is True
    assert snapshot["runtime"]["status"] == "operational"
    assert snapshot["runtime"]["process_reachable"] is True
    assert snapshot["runtime"]["execution"]["queued_jobs"] == 1
    assert snapshot["runtime"]["execution"]["expired_running_leases"] == 0
    assert snapshot["runtime"]["environment"] == "production"
    assert snapshot["runtime"]["service"] == "llm-holdings-runtime"
    assert snapshot["runtime"]["deployed_sha"] == "abc123"
    assert snapshot["repository"]["main_sha"] == "abc123"
    assert snapshot["repository"]["deployment_matches_main"] is True
    assert snapshot["repository"]["ci"]["status"] == "success"
    assert snapshot["repository"]["ci"]["check_count"] == 2
    assert snapshot["repository"]["error"] is None


def test_runtime_ops_marks_expired_execution_lease_degraded(monkeypatch, db):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc123")
    db.add(
        MissionExecutionJob(
            lab_id="LAB-STALE",
            mission_id="MIS-STALE",
            status="running",
            lease_owner="worker:test",
            lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            created_by="founder",
        )
    )
    db.add(
        ExecutionRun(
            case_id="CASE-FAILED",
            status="failed",
            error="provider timeout",
        )
    )
    db.commit()

    with httpx.Client(
        transport=httpx.MockTransport(_github_handler())
    ) as client:
        snapshot = runtime_ops_snapshot(db=db, client=client)

    assert snapshot["runtime"]["ok"] is False
    assert snapshot["runtime"]["status"] == "degraded"
    assert snapshot["runtime"]["execution"]["running_jobs"] == 1
    assert snapshot["runtime"]["execution"]["expired_running_leases"] == 1
    assert snapshot["runtime"]["execution"]["failed_runs_total"] == 1


def test_runtime_ops_marks_pending_ci_and_commit_drift(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "deployed")

    with httpx.Client(
        transport=httpx.MockTransport(
            _github_handler(main_sha="main-new", pending=True)
        )
    ) as client:
        snapshot = runtime_ops_snapshot(client=client)

    assert snapshot["runtime"]["status"] == "unknown"
    assert snapshot["runtime"]["ok"] is None
    assert snapshot["repository"]["deployment_matches_main"] is False
    assert snapshot["repository"]["ci"]["status"] == "pending"


def test_runtime_ops_github_failure_does_not_claim_execution_health(monkeypatch):
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = runtime_ops_snapshot(client=client)

    assert snapshot["runtime"]["process_reachable"] is True
    assert snapshot["runtime"]["status"] == "unknown"
    assert snapshot["runtime"]["ok"] is None
    assert snapshot["repository"]["github_status"] == "unavailable"
    assert snapshot["repository"]["main_sha"] is None
    assert snapshot["repository"]["ci"]["status"] == "unavailable"
    assert snapshot["repository"]["deployment_matches_main"] is None
    assert snapshot["repository"]["error"]
