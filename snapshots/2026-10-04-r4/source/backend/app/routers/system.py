from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from runtime.agents import AGENTS
from runtime.db import get_db
from runtime.governance import (
    kill_switch_status,
    runtime_stopped,
    set_kill_switch,
    set_runtime_stopped,
)
from runtime.models import Approval, Case, ExecutionRun, Task
from runtime.runtime_ops import runtime_ops_snapshot
from schemas.api import AgentView, DashboardStats, KillSwitchStatus

router = APIRouter(tags=["system"])


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(db: Session = Depends(get_db)):
    active = (
        db.scalar(
            select(func.count())
            .select_from(Case)
            .where(Case.status.in_(["created", "running", "waiting_approval"]))
        )
        or 0
    )
    waiting = (
        db.scalar(
            select(func.count())
            .select_from(Approval)
            .where(Approval.status == "pending")
        )
        or 0
    )
    running = (
        db.scalar(select(func.count()).select_from(Task).where(Task.status == "running"))
        or 0
    )
    rows = db.execute(
        select(Case.company, func.count())
        .where(Case.status.in_(["created", "running", "waiting_approval"]))
        .group_by(Case.company)
    ).all()

    now = datetime.now(timezone.utc)
    day_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    today_cost = (
        db.scalar(
            select(func.sum(ExecutionRun.cost_usd)).where(
                ExecutionRun.started_at >= day_start
            )
        )
        or 0.0
    )

    return DashboardStats(
        active_cases=active,
        waiting_approval=waiting,
        agents_running=running,
        today_cost_usd=float(today_cost),
        stopped=runtime_stopped(db),
        companies={name: count for name, count in rows},
    )


@router.get("/runtime/ops")
def runtime_ops(db: Session = Depends(get_db)):
    return runtime_ops_snapshot(db=db)


@router.get("/agents", response_model=list[AgentView])
def agents(db: Session = Depends(get_db)):
    running_tasks = list(db.scalars(select(Task).where(Task.status == "running")).all())
    by_agent = {t.owner_agent: t.case_id for t in running_tasks}
    out = []

    for cfg in AGENTS.values():
        case_id = by_agent.get(cfg["agent_id"])
        out.append(
            AgentView(
                **cfg,
                status="running" if case_id else "idle",
                case_id=case_id,
            )
        )
    return out


@router.get("/kill-switch/status", response_model=KillSwitchStatus)
def stop_status(
    company: str | None = None,
    case_id: str | None = None,
    db: Session = Depends(get_db),
):
    return kill_switch_status(db, company=company, case_id=case_id)


@router.post("/kill-switch/global/stop")
def stop_global(db: Session = Depends(get_db)):
    set_kill_switch(db, scope="global", stopped=True)
    return {"scope": "global", "stopped": True}


@router.post("/kill-switch/global/start")
def start_global(db: Session = Depends(get_db)):
    set_kill_switch(db, scope="global", stopped=False)
    return {"scope": "global", "stopped": False}


@router.post("/kill-switch/company/{company}/stop")
def stop_company(company: str, db: Session = Depends(get_db)):
    set_kill_switch(db, scope="company", target=company, stopped=True)
    return {"scope": "company", "target": company.lower(), "stopped": True}


@router.post("/kill-switch/company/{company}/start")
def start_company(company: str, db: Session = Depends(get_db)):
    set_kill_switch(db, scope="company", target=company, stopped=False)
    return {"scope": "company", "target": company.lower(), "stopped": False}


def _require_case(db: Session, case_id: str) -> Case:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


@router.post("/kill-switch/case/{case_id}/stop")
def stop_case(case_id: str, db: Session = Depends(get_db)):
    _require_case(db, case_id)
    set_kill_switch(db, scope="case", target=case_id, stopped=True)
    return {"scope": "case", "target": case_id, "stopped": True}


@router.post("/kill-switch/case/{case_id}/start")
def start_case(case_id: str, db: Session = Depends(get_db)):
    _require_case(db, case_id)
    set_kill_switch(db, scope="case", target=case_id, stopped=False)
    return {"scope": "case", "target": case_id, "stopped": False}


# Backward-compatible global endpoints used by the current mobile scaffold.
@router.post("/kill-switch/stop")
def stop(db: Session = Depends(get_db)):
    set_runtime_stopped(db, True)
    return {"stopped": True}


@router.post("/kill-switch/start")
def start(db: Session = Depends(get_db)):
    set_runtime_stopped(db, False)
    return {"stopped": False}
