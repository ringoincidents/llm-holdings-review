from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .events import emit
from .lab_context import LabContextSnapshotNotFound, require_snapshot
from .lab_seats import assign_work
from .labs import LabNotFound, require_lab
from .models import (
    Artifact,
    Decision,
    Evidence,
    LabWork,
    LabWorkResult,
)

WORK_TYPES = {"task", "case", "review", "question", "experiment"}
RESULT_TYPES = {"artifact", "review", "evidence", "decision"}
WORK_ACTION_PURPOSE = {
    "task": "implementation",
    "case": "implementation",
    "review": "verification",
    "question": "research",
    "experiment": "experiment",
}


class LabWorkNotFound(LookupError):
    pass


class LabWorkInvalid(ValueError):
    pass


class LabWorkResultInvalid(ValueError):
    pass


def create_work(
    db: Session,
    *,
    lab_id: str,
    work_type: str,
    title: str,
    instructions: str = "",
    context_snapshot_id: str | None = None,
    created_by: str = "founder",
) -> LabWork:
    require_lab(db, lab_id)
    if work_type not in WORK_TYPES:
        raise LabWorkInvalid(f"Unsupported Work type: {work_type}")
    if context_snapshot_id:
        require_snapshot(db, lab_id=lab_id, snapshot_id=context_snapshot_id)

    from .action_reconciliation import (
        DuplicateActionPrevented,
        bind_planned_action,
        preflight_action,
        record_preflight,
    )
    action_query = " ".join(
        part for part in [title.strip(), instructions.strip()] if part
    )
    action_purpose = WORK_ACTION_PURPOSE[work_type]
    action_preflight = preflight_action(
        db,
        lab_id=lab_id,
        action_type="work",
        query=action_query,
        purpose=action_purpose,
        created_by=created_by,
    )
    if action_preflight.get("block"):
        record_preflight(
            db,
            lab_id=lab_id,
            action_type="work",
            query=action_query,
            result=action_preflight,
            created_by=created_by,
        )
        db.commit()
        raise LabWorkInvalid(str(DuplicateActionPrevented(action_preflight)))

    work = LabWork(
        lab_id=lab_id,
        work_type=work_type,
        title=title.strip(),
        instructions=instructions.strip(),
        context_snapshot_id=context_snapshot_id,
        created_by=created_by,
    )
    db.add(work)
    db.flush()
    record_preflight(
        db,
        lab_id=lab_id,
        action_type="work",
        query=action_query,
        result=action_preflight,
        action_id=work.id,
        created_by=created_by,
    )
    bind_planned_action(
        db,
        result=action_preflight,
        action_type="work",
        action_id=work.id,
        purpose=action_purpose,
        created_by=created_by,
    )
    if work_type == "experiment":
        from .action_reconciliation import bind_action_alias
        bind_action_alias(
            db,
            source_action_type="work",
            source_action_id=work.id,
            action_type="experiment",
            action_id=work.id,
            status="planned",
            purpose="experiment",
            created_by=created_by,
        )
    if not created_by.startswith("mission:") and work.title:
        from .capabilities import discover_work
        discover_work(db, lab_id=lab_id, query=work.title[:4000], work=work)
    emit(
        db,
        "LAB_WORK_CREATED",
        lab_id=lab_id,
        work_id=work.id,
        work_type=work.work_type,
        title=work.title,
        context_snapshot_id=work.context_snapshot_id,
    )
    db.commit()
    db.refresh(work)
    return work


def require_work(db: Session, *, lab_id: str, work_id: str) -> LabWork:
    require_lab(db, lab_id)
    work = db.get(LabWork, work_id)
    if work is None or work.lab_id != lab_id:
        raise LabWorkNotFound(work_id)
    return work


def list_work(db: Session, lab_id: str) -> list[LabWork]:
    require_lab(db, lab_id)
    return list(
        db.scalars(
            select(LabWork)
            .where(LabWork.lab_id == lab_id)
            .order_by(LabWork.created_at, LabWork.id)
        ).all()
    )


def delegate_work(
    db: Session,
    *,
    lab_id: str,
    work_id: str,
    seat_id: str,
    assigned_by: str = "founder",
):
    work = require_work(db, lab_id=lab_id, work_id=work_id)
    assignment = assign_work(
        db,
        lab_id=lab_id,
        object_type="work",
        object_id=work.id,
        seat_id=seat_id,
        assigned_by=assigned_by,
    )
    work.status = "assigned"
    from .action_reconciliation import update_bound_action_status
    update_bound_action_status(
        db,
        action_type="work",
        action_id=work.id,
        status="in_progress",
        detail={"seat_id": seat_id, "assigned_by": assigned_by},
        created_by=assigned_by,
    )
    db.commit()
    db.refresh(work)
    return assignment


def bind_runtime_object(
    db: Session,
    *,
    lab_id: str,
    work_id: str,
    object_type: str,
    object_id: str,
) -> LabWork:
    work = require_work(db, lab_id=lab_id, work_id=work_id)
    work.runtime_object_type = object_type
    work.runtime_object_id = object_id
    db.flush()
    emit(
        db,
        "LAB_WORK_RUNTIME_BOUND",
        lab_id=lab_id,
        work_id=work.id,
        object_type=object_type,
        object_id=object_id,
    )
    db.commit()
    db.refresh(work)
    return work


def _validate_result_target(
    db: Session,
    *,
    lab_id: str,
    result_type: str,
    result_id: str,
) -> None:
    if result_type == "review":
        review = db.get(LabWork, result_id)
        if review is None or review.lab_id != lab_id or review.work_type != "review":
            raise LabWorkResultInvalid("Review result must reference Review Work in the same Lab")
        return

    model = {
        "artifact": Artifact,
        "evidence": Evidence,
        "decision": Decision,
    }.get(result_type)
    if model is None:
        raise LabWorkResultInvalid(f"Unsupported Work result type: {result_type}")

    obj = db.get(model, result_id)
    if obj is None:
        raise LabWorkResultInvalid(f"Result object not found: {result_type}:{result_id}")

    from .models import LabObjectLink

    linked = db.scalar(
        select(LabObjectLink).where(
            LabObjectLink.lab_id == lab_id,
            LabObjectLink.object_type == result_type,
            LabObjectLink.object_id == result_id,
        )
    )
    if linked is None:
        raise LabWorkResultInvalid("Result object must belong to the Lab before linkage")


def add_work_result(
    db: Session,
    *,
    lab_id: str,
    work_id: str,
    result_type: str,
    result_id: str,
) -> LabWorkResult:
    work = require_work(db, lab_id=lab_id, work_id=work_id)
    if result_type not in RESULT_TYPES:
        raise LabWorkResultInvalid(f"Unsupported Work result type: {result_type}")
    _validate_result_target(
        db,
        lab_id=lab_id,
        result_type=result_type,
        result_id=result_id,
    )

    existing = db.scalar(
        select(LabWorkResult).where(
            LabWorkResult.work_id == work.id,
            LabWorkResult.result_type == result_type,
            LabWorkResult.result_id == result_id,
        )
    )
    if existing:
        return existing

    result = LabWorkResult(
        lab_id=lab_id,
        work_id=work.id,
        result_type=result_type,
        result_id=result_id,
    )
    db.add(result)
    db.flush()
    emit(
        db,
        "LAB_WORK_RESULT_LINKED",
        lab_id=lab_id,
        work_id=work.id,
        work_result_id=result.id,
        result_type=result_type,
        result_id=result_id,
    )
    if result_type in {"artifact", "decision"}:
        from .knowledge_reconciliation import auto_reconcile_source
        auto_reconcile_source(
            db,
            source_type=result_type,
            source_id=result_id,
            scope_type="lab",
            scope_id=lab_id,
            created_by="system:lab_result_hook",
        )
    if result_type == "artifact":
        artifact = db.get(Artifact, result_id)
        if artifact is not None:
            from .developer_execution import dev_execution_verified, parse_dev_execution
            developer_verified = dev_execution_verified(
                parse_dev_execution(artifact.content)
            )
            from .action_reconciliation import (
                complete_work_bindings,
                update_bound_action_status,
            )
            complete_work_bindings(
                db,
                work_id=work.id,
                completed=work.status == "completed",
                developer_verified=developer_verified,
                artifact_id=artifact.id,
            )
            if work.work_type == "experiment" and work.status == "completed":
                update_bound_action_status(
                    db,
                    action_type="experiment",
                    action_id=work.id,
                    status="verified",
                    detail={
                        "artifact_id": artifact.id,
                        "purpose": "experiment",
                        "completion_basis": "experiment_work_completed",
                    },
                    created_by="system:experiment_reconciliation",
                )
    db.commit()
    db.refresh(result)
    return result


def list_work_results(
    db: Session,
    *,
    lab_id: str,
    work_id: str | None = None,
) -> list[LabWorkResult]:
    require_lab(db, lab_id)
    query = select(LabWorkResult).where(LabWorkResult.lab_id == lab_id)
    if work_id:
        require_work(db, lab_id=lab_id, work_id=work_id)
        query = query.where(LabWorkResult.work_id == work_id)
    return list(db.scalars(query.order_by(LabWorkResult.created_at, LabWorkResult.id)).all())
