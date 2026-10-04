from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Register model-owning companion modules before Base.metadata.create_all().
# TASK-048 keeps KnowledgeActionReconciliation outside runtime.models, so a
# fresh/legacy production database otherwise misses this table until too late.
from runtime import action_reconciliation as _action_reconciliation_models  # noqa: F401

from runtime.background_execution import (
    ensure_background_worker_started,
    reconcile_schema_bootstrap_failures,
    stop_background_worker,
)
from runtime.db import Base, SessionLocal, engine
from runtime.lab_missions import reconcile_build_missions_on_startup
from runtime.organization import ensure_holdings_operating_principles, ensure_organization
from runtime.quantrade_ceo_sync import (
    ensure_quantrade_ceo_sync_started,
    quantrade_ceo_sync_status,
    stop_quantrade_ceo_sync,
)
from tools.developer_workspace import developer_runtime_capabilities
from .auth import RuntimeBearerAuthMiddleware, auth_enabled, validate_auth_configuration
from .routers import approvals, cases, clients, coordination, datasets, events, external_intelligence, knowledge, labs, system

validate_auth_configuration()
Base.metadata.create_all(bind=engine)


def _run_startup_reconciliation() -> None:
    db = SessionLocal()
    try:
        ensure_holdings_operating_principles(db)
        ensure_organization(db)
        reconcile_schema_bootstrap_failures(db)
        reconcile_build_missions_on_startup(db)
        from runtime.authority import backfill_ownership
        from runtime.capabilities import seed_capabilities
        from runtime.client_intelligence import seed_client_intelligence
        from runtime.external_intelligence import seed_external_sources
        from runtime.memory_trust import backfill_memory_trust
        from runtime.knowledge_lifecycle import seed_knowledge_lifecycle_principles
        from runtime.record_writer import seed_quantrade_canonical_vision
        from runtime.shared_os_change import reconcile_all_shared_os_knowledge_actions
        backfill_ownership(db)
        seed_capabilities(db)
        seed_client_intelligence(db)
        seed_external_sources(db)
        backfill_memory_trust(db)
        seed_knowledge_lifecycle_principles(db)
        seed_quantrade_canonical_vision(db)
        reconcile_all_shared_os_knowledge_actions(db)
        db.commit()
    finally:
        db.close()


_run_startup_reconciliation()

_EXECUTABLE_DEVELOPER_CAPABILITIES = developer_runtime_capabilities()
print(
    "EXECUTABLE_DEVELOPER_CAPABILITIES "
    + json.dumps(_EXECUTABLE_DEVELOPER_CAPABILITIES, sort_keys=True)
)

app = FastAPI(title="LLM Holdings Runtime", version="0.1.0")
app.add_middleware(RuntimeBearerAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cases.router)
app.include_router(clients.router)
app.include_router(datasets.router)
app.include_router(events.router)
app.include_router(external_intelligence.router)
app.include_router(knowledge.router)
app.include_router(coordination.router)
app.include_router(labs.router)
app.include_router(approvals.router)
app.include_router(system.router)


@app.on_event("startup")
def _start_runtime_workers() -> None:
    ensure_background_worker_started()
    ensure_quantrade_ceo_sync_started()


@app.on_event("shutdown")
def _stop_runtime_workers() -> None:
    stop_quantrade_ceo_sync()
    stop_background_worker()


@app.get("/health")
def health():
    return {
        "ok": True,
        "runtime": "llm-holdings",
        "version": "0.1.0",
        "auth_enabled": auth_enabled(),
        "executable_developer": _EXECUTABLE_DEVELOPER_CAPABILITIES,
        "quantrade_ceo_sync": quantrade_ceo_sync_status(),
    }
