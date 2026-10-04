from __future__ import annotations

import json
import os
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import inspect, or_, select, update
from sqlalchemy.orm import Session

from .db import SessionLocal
from .events import emit
from .lab_execution import LabWorkExecutionError
from .lab_missions import LabMissionInvalid, run_mission
from .models import LabMission, MissionExecutionJob


JOB_ACTIVE_STATUSES = {"queued", "running"}
MISSION_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "superseded"}
MISSION_HUMAN_BLOCKED_STATUSES = {"awaiting_founder", "budget_blocked"}
SCHEMA_BOOTSTRAP_RECOVERY_ACTOR = "runtime:schema-bootstrap-recovery"
SCHEMA_BOOTSTRAP_RECOVERY_SIGNATURES = (
    "no such table: knowledge_action_reconciliations",
)
SCHEMA_BOOTSTRAP_RECOVERABLE_MISSION_STATUSES = {
    "created",
    "queued",
    "running",
    "failed",
}
JOB_LEASE_SECONDS = int(os.getenv("LLM_HOLDINGS_JOB_LEASE_SECONDS", "300"))
WORKER_POLL_SECONDS = 1.0
JOB_HEARTBEAT_SECONDS = max(15, min(60, JOB_LEASE_SECONDS // 4))

_worker_lock = threading.Lock()
_worker_stop = threading.Event()
_worker_thread: threading.Thread | None = None
_worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"


class MissionExecutionQueueError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def background_worker_enabled() -> bool:
    if "PYTEST_CURRENT_TEST" in os.environ and "LLM_HOLDINGS_BACKGROUND_WORKER" not in os.environ:
        return False
    return os.getenv("LLM_HOLDINGS_BACKGROUND_WORKER", "1").strip() not in {
        "0",
        "false",
        "False",
        "off",
    }


def enqueue_mission_execution(
    db: Session,
    *,
    lab_id: str,
    mission_id: str,
    initial_spec: dict | None = None,
    created_by: str = "founder",
    refresh_queued_active: bool = False,
) -> MissionExecutionJob:
    mission = db.get(LabMission, mission_id)
    if mission is None or mission.lab_id != lab_id:
        raise MissionExecutionQueueError("Lab Mission not found")
    if mission.status in MISSION_TERMINAL_STATUSES:
        raise MissionExecutionQueueError(
            f"Mission cannot be queued from terminal status: {mission.status}"
        )
    if mission.status in MISSION_HUMAN_BLOCKED_STATUSES:
        raise MissionExecutionQueueError(
            f"Mission requires Founder action before execution: {mission.status}"
        )

    active = db.scalar(
        select(MissionExecutionJob)
        .where(
            MissionExecutionJob.mission_id == mission.id,
            MissionExecutionJob.status.in_(tuple(JOB_ACTIVE_STATUSES)),
        )
        .order_by(MissionExecutionJob.created_at.desc())
    )
    if active is not None:
        if active.status == "queued" and refresh_queued_active:
            active.initial_spec_json = json.dumps(initial_spec or {}, ensure_ascii=False)
            active.baseline_step_count = mission.step_count
            active.created_by = created_by
            active.last_error = None
            active.updated_at = _now()
            mission.status = "queued"
            mission.updated_at = _now()
            from .organization import sync_mission_ledger_status
            sync_mission_ledger_status(db, mission)
            emit(
                db,
                "MISSION_EXECUTION_JOB_RECOVERY_REFRESHED",
                lab_id=lab_id,
                mission_id=mission.id,
                job_id=active.id,
                baseline_step_count=active.baseline_step_count,
                created_by=created_by,
            )
            db.commit()
            db.refresh(active)
        elif active.status == "queued" and mission.status != "queued":
            mission.status = "queued"
            mission.updated_at = _now()
            from .organization import sync_mission_ledger_status
            sync_mission_ledger_status(db, mission)
            db.commit()
        elif active.status == "running" and refresh_queued_active:
            active.initial_spec_json = json.dumps(initial_spec or {}, ensure_ascii=False)
            active.baseline_step_count = mission.step_count
            active.created_by = created_by
            active.updated_at = _now()
            mission.status = "running"
            mission.updated_at = _now()
            from .organization import sync_mission_ledger_status
            sync_mission_ledger_status(db, mission)
            emit(
                db,
                "MISSION_EXECUTION_JOB_RECOVERY_STAGED",
                lab_id=lab_id,
                mission_id=mission.id,
                job_id=active.id,
                baseline_step_count=active.baseline_step_count,
                created_by=created_by,
                lease_owner=active.lease_owner,
                lease_expires_at=(
                    active.lease_expires_at.isoformat()
                    if active.lease_expires_at is not None
                    else None
                ),
            )
            db.commit()
            db.refresh(active)
        elif active.status == "running" and mission.status != "running":
            mission.status = "running"
            mission.updated_at = _now()
            from .organization import sync_mission_ledger_status
            sync_mission_ledger_status(db, mission)
            db.commit()
        ensure_background_worker_started()
        return active

    job = MissionExecutionJob(
        lab_id=lab_id,
        mission_id=mission.id,
        status="queued",
        initial_spec_json=json.dumps(initial_spec or {}, ensure_ascii=False),
        baseline_step_count=mission.step_count,
        created_by=created_by,
    )
    db.add(job)
    db.flush()
    mission.status = "queued"
    mission.updated_at = _now()
    from .organization import sync_mission_ledger_status
    sync_mission_ledger_status(db, mission)
    emit(
        db,
        "MISSION_EXECUTION_JOB_QUEUED",
        lab_id=lab_id,
        mission_id=mission.id,
        job_id=job.id,
        baseline_step_count=job.baseline_step_count,
        created_by=created_by,
    )
    db.commit()
    db.refresh(job)
    ensure_background_worker_started()
    return job


def latest_mission_job(
    db: Session,
    *,
    lab_id: str,
    mission_id: str,
) -> MissionExecutionJob | None:
    return db.scalar(
        select(MissionExecutionJob)
        .where(
            MissionExecutionJob.lab_id == lab_id,
            MissionExecutionJob.mission_id == mission_id,
        )
        .order_by(
            MissionExecutionJob.created_at.desc(),
            MissionExecutionJob.id.desc(),
        )
    )


def _is_schema_bootstrap_failure(error: str | None) -> bool:
    value = str(error or "").casefold()
    return any(signature in value for signature in SCHEMA_BOOTSTRAP_RECOVERY_SIGNATURES)


def reconcile_schema_bootstrap_failures(db: Session) -> int:
    """Requeue one bounded job after a known, already-repaired schema bootstrap fault.

    The failed job remains immutable audit evidence. A new job is created only
    when the missing table now exists, the Mission is still resumable, and no
    prior schema-recovery job has been created for that Mission.
    """

    bind = db.get_bind()
    if bind is None or not inspect(bind).has_table("knowledge_action_reconciliations"):
        return 0

    failed_jobs = list(
        db.scalars(
            select(MissionExecutionJob)
            .where(
                MissionExecutionJob.status == "failed",
                MissionExecutionJob.last_error.is_not(None),
            )
            .order_by(
                MissionExecutionJob.created_at.asc(),
                MissionExecutionJob.id.asc(),
            )
        ).all()
    )
    recovered = 0

    for failed_job in failed_jobs:
        if failed_job.created_by == SCHEMA_BOOTSTRAP_RECOVERY_ACTOR:
            continue
        if not _is_schema_bootstrap_failure(failed_job.last_error):
            continue

        mission = db.get(LabMission, failed_job.mission_id)
        if (
            mission is None
            or mission.lab_id != failed_job.lab_id
            or mission.status not in SCHEMA_BOOTSTRAP_RECOVERABLE_MISSION_STATUSES
        ):
            continue

        prior_recovery = db.scalar(
            select(MissionExecutionJob)
            .where(
                MissionExecutionJob.mission_id == mission.id,
                MissionExecutionJob.created_by == SCHEMA_BOOTSTRAP_RECOVERY_ACTOR,
            )
            .order_by(MissionExecutionJob.created_at.desc())
            .limit(1)
        )
        if prior_recovery is not None:
            continue

        active = db.scalar(
            select(MissionExecutionJob)
            .where(
                MissionExecutionJob.mission_id == mission.id,
                MissionExecutionJob.status.in_(tuple(JOB_ACTIVE_STATUSES)),
            )
            .order_by(MissionExecutionJob.created_at.desc())
            .limit(1)
        )
        if active is not None:
            continue

        previous_status = mission.status
        recovery_job = MissionExecutionJob(
            lab_id=mission.lab_id,
            mission_id=mission.id,
            status="queued",
            initial_spec_json=failed_job.initial_spec_json or "{}",
            baseline_step_count=mission.step_count,
            created_by=SCHEMA_BOOTSTRAP_RECOVERY_ACTOR,
        )
        db.add(recovery_job)
        db.flush()

        mission.status = "queued"
        mission.updated_at = _now()
        from .organization import sync_mission_ledger_status
        sync_mission_ledger_status(db, mission)

        emit(
            db,
            "MISSION_EXECUTION_SCHEMA_RECOVERY_QUEUED",
            lab_id=mission.lab_id,
            mission_id=mission.id,
            failed_job_id=failed_job.id,
            recovery_job_id=recovery_job.id,
            previous_mission_status=previous_status,
            recovery_reason="knowledge_action_reconciliations schema is now available",
            created_by=SCHEMA_BOOTSTRAP_RECOVERY_ACTOR,
        )
        db.commit()
        recovered += 1

    return recovered


def _claim_next_job(
    db: Session,
    *,
    job_id: str | None = None,
) -> MissionExecutionJob | None:
    now = _now()
    eligible = or_(
        MissionExecutionJob.status == "queued",
        (
            (MissionExecutionJob.status == "running")
            & (MissionExecutionJob.lease_expires_at.is_not(None))
            & (MissionExecutionJob.lease_expires_at < now)
        ),
    )
    query = select(MissionExecutionJob).where(eligible)
    if job_id is not None:
        query = query.where(MissionExecutionJob.id == job_id)

    candidate = db.scalar(
        query
        .order_by(MissionExecutionJob.created_at.asc())
        .limit(1)
    )
    if candidate is None:
        return None

    previous_status = candidate.status
    claim_conditions = [MissionExecutionJob.id == candidate.id]
    if previous_status == "queued":
        claim_conditions.append(MissionExecutionJob.status == "queued")
    else:
        claim_conditions.extend(
            [
                MissionExecutionJob.status == "running",
                MissionExecutionJob.lease_expires_at.is_not(None),
                MissionExecutionJob.lease_expires_at < now,
            ]
        )

    values = {
        "status": "running",
        "lease_owner": _worker_id,
        "lease_expires_at": now + timedelta(seconds=JOB_LEASE_SECONDS),
        "attempt_count": int(candidate.attempt_count) + 1,
        "started_at": candidate.started_at or now,
        "updated_at": now,
    }
    claimed = db.execute(
        update(MissionExecutionJob)
        .where(*claim_conditions)
        .values(**values)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        db.rollback()
        return None

    db.flush()
    claimed_job = db.get(MissionExecutionJob, candidate.id)
    if claimed_job is None:
        db.rollback()
        return None
    emit(
        db,
        "MISSION_EXECUTION_JOB_CLAIMED",
        lab_id=claimed_job.lab_id,
        mission_id=claimed_job.mission_id,
        job_id=claimed_job.id,
        attempt_count=claimed_job.attempt_count,
        previous_status=previous_status,
        lease_owner=_worker_id,
    )
    db.commit()
    db.refresh(claimed_job)
    return claimed_job


def _job_initial_spec(job: MissionExecutionJob, mission: LabMission) -> dict | None:
    if mission.step_count > job.baseline_step_count:
        return None
    try:
        parsed = json.loads(job.initial_spec_json or "{}")
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) and parsed else None


def _finish_job_from_mission(
    db: Session,
    job: MissionExecutionJob,
    mission: LabMission,
) -> None:
    if mission.status == "completed":
        job.status = "completed"
    elif mission.status in {"awaiting_founder", "budget_blocked", "delivery_blocked", "waiting_for_delivery", "review_required"}:
        job.status = "paused"
    elif mission.status in {"cancelled", "superseded"}:
        job.status = "cancelled"
    elif mission.status == "failed":
        job.status = "failed"
    else:
        # run_mission is bounded and normally settles the Mission. Keeping the
        # Job queued is safer than pretending completion if another step is needed.
        job.status = "queued"
    job.lease_owner = None
    job.lease_expires_at = None
    job.updated_at = _now()
    if job.status in {"completed", "paused", "cancelled", "failed"}:
        job.finished_at = _now()
    emit(
        db,
        "MISSION_EXECUTION_JOB_SETTLED",
        lab_id=job.lab_id,
        mission_id=job.mission_id,
        job_id=job.id,
        job_status=job.status,
        mission_status=mission.status,
        step_count=mission.step_count,
    )
    db.commit()

    if mission.status == "completed":
        try:
            initial_spec = json.loads(job.initial_spec_json or "{}")
        except json.JSONDecodeError:
            initial_spec = {}
        experiment_id = (
            str(initial_spec.get("experiment_id") or "").strip()
            if initial_spec.get("technology_experiment") is True
            else ""
        )
        if experiment_id:
            from .technology_experiment import (
                TechnologyExperimentError,
                reconcile_experiment,
            )
            try:
                reconcile_experiment(db, experiment_id=experiment_id)
            except TechnologyExperimentError as exc:
                emit(
                    db,
                    "TECHNOLOGY_EXPERIMENT_AUTO_RECONCILE_FAILED",
                    lab_id=job.lab_id,
                    mission_id=job.mission_id,
                    job_id=job.id,
                    experiment_id=experiment_id,
                    reason=str(exc),
                )
                db.commit()

    if mission.status == "review_required":
        from .lab_missions import _resume_ready_developer_recovery_on_startup
        _resume_ready_developer_recovery_on_startup(db, mission)


def _heartbeat_job_lease(job_id: str, stop_event: threading.Event) -> None:
    while not stop_event.wait(JOB_HEARTBEAT_SECONDS):
        db = SessionLocal()
        try:
            now = _now()
            updated = db.execute(
                update(MissionExecutionJob)
                .where(
                    MissionExecutionJob.id == job_id,
                    MissionExecutionJob.status == "running",
                    MissionExecutionJob.lease_owner == _worker_id,
                )
                .values(
                    lease_expires_at=now + timedelta(seconds=JOB_LEASE_SECONDS),
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if updated.rowcount != 1:
                db.rollback()
                return
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()


def _run_claimed_job(job_id: str) -> None:
    db = SessionLocal()
    heartbeat_stop = threading.Event()
    heartbeat_thread: threading.Thread | None = None
    try:
        job = db.get(MissionExecutionJob, job_id)
        if job is None or job.status != "running" or job.lease_owner != _worker_id:
            return
        mission = db.get(LabMission, job.mission_id)
        if mission is None:
            job.status = "failed"
            job.last_error = "Mission no longer exists"
            job.finished_at = _now()
            job.lease_owner = None
            job.lease_expires_at = None
            db.commit()
            return

        heartbeat_thread = threading.Thread(
            target=_heartbeat_job_lease,
            args=(job.id, heartbeat_stop),
            name=f"mission-job-heartbeat-{job.id}",
            daemon=True,
        )
        heartbeat_thread.start()

        initial_spec = _job_initial_spec(job, mission)
        try:
            run_mission(
                db,
                lab_id=job.lab_id,
                mission_id=job.mission_id,
                initial_spec=initial_spec,
                allow_background_resume=True,
            )
        except (LabMissionInvalid, LabWorkExecutionError) as exc:
            db.rollback()
            job = db.get(MissionExecutionJob, job_id)
            mission = db.get(LabMission, job.mission_id) if job else None
            if job is None:
                return
            job.last_error = str(exc)
            if mission is not None and mission.status in {
                "completed",
                "failed",
                "cancelled",
                "superseded",
                "awaiting_founder",
                "budget_blocked",
                "delivery_blocked",
                "waiting_for_delivery",
                "review_required",
            }:
                _finish_job_from_mission(db, job, mission)
                return
            if job.attempt_count >= job.max_attempts:
                job.status = "failed"
                job.finished_at = _now()
            else:
                job.status = "queued"
            job.lease_owner = None
            job.lease_expires_at = None
            job.updated_at = _now()
            emit(
                db,
                "MISSION_EXECUTION_JOB_RETRY",
                lab_id=job.lab_id,
                mission_id=job.mission_id,
                job_id=job.id,
                attempt_count=job.attempt_count,
                job_status=job.status,
                reason=str(exc),
            )
            db.commit()
            return

        db.expire_all()
        job = db.get(MissionExecutionJob, job_id)
        mission = db.get(LabMission, job.mission_id) if job else None
        if job is None or mission is None:
            return
        job.last_error = None
        _finish_job_from_mission(db, job, mission)
    except Exception as exc:
        db.rollback()
        job = db.get(MissionExecutionJob, job_id)
        if job is not None:
            job.last_error = f"{type(exc).__name__}: {exc}"
            if job.attempt_count >= job.max_attempts:
                job.status = "failed"
                job.finished_at = _now()
            else:
                job.status = "queued"
            job.lease_owner = None
            job.lease_expires_at = None
            job.updated_at = _now()
            emit(
                db,
                "MISSION_EXECUTION_JOB_CRASHED",
                lab_id=job.lab_id,
                mission_id=job.mission_id,
                job_id=job.id,
                attempt_count=job.attempt_count,
                job_status=job.status,
                error=job.last_error,
            )
            db.commit()
    finally:
        heartbeat_stop.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=1.0)
        db.close()


def run_worker_once(job_id: str | None = None) -> bool:
    db = SessionLocal()
    try:
        job = _claim_next_job(db, job_id=job_id)
        if job is None:
            return False
        job_id = job.id
    finally:
        db.close()

    _run_claimed_job(job_id)
    return True


def _reconcile_ready_recoveries_once() -> None:
    db = SessionLocal()
    try:
        from .lab_missions import (
            _resume_paused_ownership_router_runtime_mission,
            _resume_ready_developer_recovery_on_startup,
        )
        missions = list(
            db.scalars(
                select(LabMission).where(
                    LabMission.mode == "build",
                    LabMission.status.in_(("review_required", "created", "queued")),
                )
            ).all()
        )
        for mission in missions:
            if _resume_paused_ownership_router_runtime_mission(db, mission):
                continue
            _resume_ready_developer_recovery_on_startup(db, mission)
    except Exception:
        db.rollback()
    finally:
        db.close()


def _run_idle_knowledge_once() -> bool:
    """Spend semantic-review budget only while Mission execution is idle."""
    try:
        from .knowledge_semantic import run_auto_semantic_review_once

        result = run_auto_semantic_review_once()
        return bool(result.get("worked"))
    except Exception:
        # Background knowledge maintenance must never crash the Mission worker.
        return False


def _worker_loop() -> None:
    while not _worker_stop.is_set():
        try:
            worked = run_worker_once()
            _reconcile_ready_recoveries_once()
            if not worked:
                worked = _run_idle_knowledge_once()
        except Exception:
            worked = False
        if not worked:
            _worker_stop.wait(WORKER_POLL_SECONDS)


def ensure_background_worker_started() -> None:
    global _worker_thread
    if not background_worker_enabled():
        return
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_stop.clear()
        _worker_thread = threading.Thread(
            target=_worker_loop,
            name="llm-holdings-mission-worker",
            daemon=True,
        )
        _worker_thread.start()


def stop_background_worker(timeout: float = 2.0) -> None:
    global _worker_thread
    with _worker_lock:
        thread = _worker_thread
        if thread is None:
            return
        _worker_stop.set()
        thread.join(timeout=timeout)
        _worker_thread = None
