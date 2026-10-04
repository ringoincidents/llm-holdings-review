from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from gateway.providers.base import ModelResult

from .events import emit
from .models import ExecutionRun


def start_run(
    db: Session,
    *,
    case_id: str,
    task_id: str | None,
    decision_id: str | None,
    tools_used: Iterable[str] = (),
) -> ExecutionRun:
    run = ExecutionRun(
        case_id=case_id,
        task_id=task_id,
        decision_id=decision_id,
        status="running",
        tools_used_json=json.dumps(list(tools_used)),
    )
    db.add(run)
    db.flush()
    emit(
        db,
        "RUN_STARTED",
        case_id,
        run_id=run.id,
        task_id=task_id,
        decision_id=decision_id,
    )
    return run


def record_model_result(
    db: Session,
    run: ExecutionRun,
    result: ModelResult,
    *,
    retries: int = 0,
) -> None:
    run.provider = result.provider
    run.model = result.model
    run.latency_ms = result.latency_ms
    run.input_tokens = result.input_tokens
    run.output_tokens = result.output_tokens
    run.cost_usd = result.cost_usd
    run.retries = retries
    db.flush()
    if result.route_trace:
        emit(
            db,
            "MODEL_ROUTE_TRACE",
            run.case_id,
            run_id=run.id,
            provider=result.provider,
            model=result.model,
            cost_usd=result.cost_usd,
            attempts=list(result.route_trace),
        )


def mark_waiting_approval(db: Session, run: ExecutionRun) -> None:
    run.status = "waiting_approval"
    db.flush()


def finish_run(
    db: Session,
    run: ExecutionRun,
    *,
    outcome: str,
    human_override: bool | None = None,
) -> None:
    run.status = "completed" if outcome not in {"failed", "rejected"} else outcome
    run.outcome = outcome
    run.human_override = human_override
    run.finished_at = datetime.now(timezone.utc)
    emit(
        db,
        "RUN_FINISHED",
        run.case_id,
        run_id=run.id,
        outcome=outcome,
        human_override=human_override,
    )
    if run.decision_id:
        emit(
            db,
            "DECISION_DATASET_READY",
            run.case_id,
            run_id=run.id,
            decision_id=run.decision_id,
            outcome=outcome,
        )
    db.flush()


def fail_run(
    db: Session,
    run: ExecutionRun,
    error: Exception,
    *,
    retries: int = 0,
) -> None:
    run.status = "failed"
    run.error = f"{type(error).__name__}: {error}"
    run.retries = retries
    run.outcome = "failed"
    run.finished_at = datetime.now(timezone.utc)
    emit(
        db,
        "RUN_FAILED",
        run.case_id,
        run_id=run.id,
        error=run.error,
        retries=retries,
    )
    if run.decision_id:
        emit(
            db,
            "DECISION_DATASET_READY",
            run.case_id,
            run_id=run.id,
            decision_id=run.decision_id,
            outcome="failed",
        )
    db.flush()


def block_run(
    db: Session,
    run: ExecutionRun,
    *,
    outcome: str,
    reason: str,
) -> None:
    run.status = "blocked"
    run.error = reason
    run.outcome = outcome
    run.finished_at = datetime.now(timezone.utc)
    emit(
        db,
        "RUN_BLOCKED",
        run.case_id,
        run_id=run.id,
        outcome=outcome,
        reason=reason,
    )
    db.flush()
