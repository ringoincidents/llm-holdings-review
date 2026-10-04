from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .delivery import runtime_git_commit
from .governance import runtime_stopped
from .models import ExecutionRun, MissionExecutionJob
from .operational_learning import operational_health


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_name() -> str:
    return os.getenv(
        "LLM_HOLDINGS_DEV_REPO",
        "ringoincidents/llm-holdings-runtime",
    ).strip()


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "llm-holdings-runtime-ops",
    }
    token = os.getenv("LLM_HOLDINGS_GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _ci_summary(checks: list[dict[str, Any]]) -> dict[str, Any]:
    normalized = [
        {
            "name": str(item.get("name") or "unknown"),
            "status": str(item.get("status") or "unknown"),
            "conclusion": item.get("conclusion"),
        }
        for item in checks
    ]
    if not normalized:
        status = "unknown"
    elif any(item["status"] != "completed" for item in normalized):
        status = "pending"
    elif any(
        item["conclusion"] not in {"success", "neutral", "skipped"}
        for item in normalized
    ):
        status = "failed"
    else:
        status = "success"
    return {
        "status": status,
        "check_count": len(normalized),
        "checks": normalized[:12],
    }


def _execution_health(db: Session) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    queued_jobs = int(
        db.scalar(
            select(func.count(MissionExecutionJob.id)).where(
                MissionExecutionJob.status == "queued"
            )
        )
        or 0
    )
    running_jobs = int(
        db.scalar(
            select(func.count(MissionExecutionJob.id)).where(
                MissionExecutionJob.status == "running"
            )
        )
        or 0
    )
    expired_running_leases = int(
        db.scalar(
            select(func.count(MissionExecutionJob.id)).where(
                MissionExecutionJob.status == "running",
                MissionExecutionJob.lease_expires_at.is_not(None),
                MissionExecutionJob.lease_expires_at < now,
            )
        )
        or 0
    )
    failed_jobs = int(
        db.scalar(
            select(func.count(MissionExecutionJob.id)).where(
                MissionExecutionJob.status == "failed"
            )
        )
        or 0
    )
    failed_runs = int(
        db.scalar(
            select(func.count(ExecutionRun.id)).where(
                ExecutionRun.status == "failed"
            )
        )
        or 0
    )
    stopped = runtime_stopped(db)
    health = operational_health(db)

    if stopped:
        status = "stopped"
    elif expired_running_leases:
        status = "degraded"
    elif health["delivery_blocked"] or health["repeated_incidents"]:
        status = "degraded"
    else:
        status = "operational"

    return {
        "status": status,
        "ok": status == "operational",
        "runtime_stopped": stopped,
        "queued_jobs": queued_jobs,
        "running_jobs": running_jobs,
        "expired_running_leases": expired_running_leases,
        "failed_jobs_total": failed_jobs,
        "failed_runs_total": failed_runs,
        "operational": health,
    }


def runtime_ops_snapshot(
    *,
    db: Session | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Read-only operational projection for the Runtime Engineering console.

    Repository/CI data is best-effort. Runtime health is reported only when a
    database Session is supplied; callers must not interpret process reachability
    or a successful GitHub request as proof that execution is healthy.
    """

    repository = _repo_name()
    deployed_sha = runtime_git_commit() or None
    main_sha: str | None = None
    github_status = "unavailable"
    ci = {"status": "unavailable", "check_count": 0, "checks": []}
    github_error: str | None = None

    owns_client = client is None
    http = client or httpx.Client(timeout=4.0, headers=_github_headers())
    try:
        response = http.get(f"https://api.github.com/repos/{repository}/commits/main")
        response.raise_for_status()
        payload = response.json()
        main_sha = str(payload.get("sha") or "").strip() or None
        github_status = "available"

        if main_sha:
            checks_response = http.get(
                f"https://api.github.com/repos/{repository}/commits/{main_sha}/check-runs"
            )
            checks_response.raise_for_status()
            checks_payload = checks_response.json()
            ci = _ci_summary(list(checks_payload.get("check_runs") or []))
    except Exception as exc:  # best-effort observability must not break Runtime
        github_error = f"{type(exc).__name__}: {exc}"
    finally:
        if owns_client:
            http.close()

    if deployed_sha and main_sha:
        deployment_alignment: bool | None = deployed_sha == main_sha
    else:
        deployment_alignment = None

    execution = _execution_health(db) if db is not None else None

    return {
        "schema": "runtime_ops_v0.2",
        "checked_at": _now_iso(),
        "runtime": {
            "status": execution["status"] if execution else "unknown",
            "ok": execution["ok"] if execution else None,
            "process_reachable": True,
            "environment": os.getenv("RAILWAY_ENVIRONMENT_NAME") or None,
            "service": os.getenv("RAILWAY_SERVICE_NAME") or None,
            "project": os.getenv("RAILWAY_PROJECT_NAME") or None,
            "deployment_id": os.getenv("RAILWAY_DEPLOYMENT_ID") or None,
            "deployed_sha": deployed_sha,
            "execution": execution,
        },
        "repository": {
            "name": repository,
            "main_sha": main_sha,
            "github_status": github_status,
            "deployment_matches_main": deployment_alignment,
            "ci": ci,
            "error": github_error,
        },
    }
