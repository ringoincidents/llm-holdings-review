from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from gateway.service import gateway
from s1 import s1_provider
from schemas.api import S1RouteInput

from .agents import AGENTS
from .events import emit
from .governance import blocking_kill_switch, create_approval, requires_approval
from .models import Approval, Artifact, Case, Decision, Task
from .telemetry import (
    fail_run,
    finish_run,
    mark_waiting_approval,
    record_model_result,
    start_run,
)


def run_case(db: Session, case: Case):
    blocker = blocking_kill_switch(
        db,
        company=case.company,
        case_id=case.id,
    )
    if blocker:
        emit(
            db,
            "EXECUTION_BLOCKED",
            case.id,
            reason="kill_switch",
            blocked_by=blocker,
        )
        db.commit()
        raise RuntimeError(f"Kill switch engaged: {blocker}")

    if case.status in {"completed", "rejected"}:
        raise RuntimeError(f"Case is already {case.status}")

    emit(db, "CASE_RUN_REQUESTED", case.id)
    route = s1_provider.route(
        S1RouteInput(
            company=case.company,
            title=case.title,
            risk_level=case.risk_level,
        )
    )

    decision = Decision(
        case_id=case.id,
        decision_type="route",
        question="Which department should handle this case?",
        prediction=route.department,
        confidence=route.confidence,
        distribution_json=json.dumps({route.department: route.confidence}),
        provider=route.provider,
    )
    db.add(decision)
    db.flush()
    emit(
        db,
        "DECISION_MADE",
        case.id,
        decision_id=decision.id,
        prediction=route.department,
        confidence=route.confidence,
        provider=route.provider,
    )

    if route.department == "human":
        task = Task(
            case_id=case.id,
            type=route.task_type,
            owner_agent="human",
            status="waiting_approval",
        )
        db.add(task)
        db.flush()

        execution = start_run(
            db,
            case_id=case.id,
            task_id=task.id,
            decision_id=decision.id,
        )
        mark_waiting_approval(db, execution)

        emit(
            db,
            "TASK_CREATED",
            case.id,
            task_id=task.id,
            owner="human",
            type=task.type,
        )
        emit(db, "HUMAN_ROUTED", case.id, task_id=task.id)

        approval = create_approval(
            db,
            case.id,
            "S1 routed this case directly to Human Governance",
            case.risk_level,
        )
        case.status = "waiting_approval"
        db.commit()
        db.refresh(case)
        db.refresh(task)
        db.refresh(approval)
        db.refresh(execution)
        return route, task, approval, None, execution

    agent = AGENTS[route.department]
    task = Task(
        case_id=case.id,
        type=route.task_type,
        owner_agent=agent["agent_id"],
        status="running",
    )
    db.add(task)
    db.flush()

    execution = start_run(
        db,
        case_id=case.id,
        task_id=task.id,
        decision_id=decision.id,
    )

    case.status = "running"
    emit(
        db,
        "TASK_CREATED",
        case.id,
        task_id=task.id,
        owner=agent["agent_id"],
        type=task.type,
    )
    emit(db, "AGENT_STARTED", case.id, task_id=task.id, agent_id=agent["agent_id"])

    try:
        result = gateway.generate(
            policy=agent["model_policy"],
            prompt=case.title,
            task_type=route.task_type,
            risk_level=case.risk_level,
        )
    except Exception as exc:
        task.status = "failed"
        task.completed_at = datetime.now(timezone.utc)
        case.status = "failed"
        fail_run(db, execution, exc)
        emit(
            db,
            "AGENT_FAILED",
            case.id,
            task_id=task.id,
            agent_id=agent["agent_id"],
            error=f"{type(exc).__name__}: {exc}",
        )
        db.commit()
        raise RuntimeError("Model execution failed") from exc

    record_model_result(db, execution, result)
    emit(
        db,
        "MODEL_CALLED",
        case.id,
        task_id=task.id,
        run_id=execution.id,
        provider=result.provider,
        model=result.model,
        latency_ms=result.latency_ms,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        cost_usd=result.cost_usd,
    )

    digest = hashlib.sha256(result.text.encode("utf-8")).hexdigest()
    artifact = Artifact(
        case_id=case.id,
        task_id=task.id,
        kind="agent_result",
        content=result.text,
        content_hash=digest,
        producer_type="agent",
        producer_id=agent["agent_id"],
        provider=result.provider,
        model=result.model,
    )
    db.add(artifact)
    db.flush()
    emit(
        db,
        "ARTIFACT_CREATED",
        case.id,
        artifact_id=artifact.id,
        task_id=task.id,
        run_id=execution.id,
        kind=artifact.kind,
        producer_id=artifact.producer_id,
        provider=result.provider,
        model=result.model,
    )

    task.result = result.text
    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    emit(db, "AGENT_FINISHED", case.id, task_id=task.id, agent_id=agent["agent_id"])

    approval: Approval | None = None
    if requires_approval(case.title, case.risk_level, route.human_review):
        approval = create_approval(
            db,
            case.id,
            "Governance policy requires founder approval",
            case.risk_level,
        )
        mark_waiting_approval(db, execution)
        case.status = "waiting_approval"
    else:
        case.status = "completed"
        finish_run(db, execution, outcome="completed")
        emit(db, "CASE_CLOSED", case.id, outcome="completed")

    db.commit()
    db.refresh(case)
    db.refresh(task)
    db.refresh(execution)
    if approval:
        db.refresh(approval)
    return route, task, approval, result, execution
