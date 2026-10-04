from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from runtime.db import SessionLocal
from runtime.knowledge_lifecycle import bind_action, create_claim, ensure_concept
from runtime.knowledge_observatory import topic_detail
from runtime.lab_missions import (
    create_mission,
    list_mission_work,
    mission_state,
    run_mission,
)
from runtime.models import LabContextSnapshot, LabMission, LabWork, RuntimeState
from runtime.organization import organization_labs


RUN_ID_ENV = "LLM_HOLDINGS_E2E_SMOKE_RUN_ID"
STATE_PREFIX = "e2e_smoke:"
CURRENT_MARKER = "SMOKE_V2"
HISTORICAL_MARKER = "SMOKE_V1"


class ProductionE2ESmokeError(RuntimeError):
    pass


def _normalized_run_id(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
    if not normalized:
        raise ProductionE2ESmokeError("Smoke run id is empty after normalization")
    return normalized[:72]


def _concept_key(run_id: str) -> str:
    return f"e2e-memory-smoke-{run_id}".lower()[:160]


def _state_key(run_id: str) -> str:
    return f"{STATE_PREFIX}{run_id}"[:160]


def _find_existing_mission(
    db: Session,
    *,
    lab_id: str,
    created_by: str,
) -> LabMission | None:
    return db.scalar(
        select(LabMission)
        .where(
            LabMission.lab_id == lab_id,
            LabMission.created_by == created_by,
        )
        .order_by(LabMission.created_at.desc(), LabMission.id.desc())
    )


def _knowledge_view(snapshot: LabContextSnapshot, concept_key: str) -> dict[str, Any]:
    payload = json.loads(snapshot.context_json)
    if payload.get("schema_version") != "lab-context-v2-knowledge-pack":
        raise ProductionE2ESmokeError(
            f"Unexpected context schema: {payload.get('schema_version')!r}"
        )
    for item in payload.get("knowledge", {}).get("concepts", []):
        concept = item.get("concept") or {}
        if concept.get("key") == concept_key:
            return item
    raise ProductionE2ESmokeError(
        f"Knowledge Context Pack did not retrieve concept {concept_key}"
    )


def run_production_e2e_smoke(
    db: Session,
    *,
    run_id: str,
) -> dict[str, Any]:
    run_id = _normalized_run_id(run_id)
    state_key = _state_key(run_id)
    previous = db.get(RuntimeState, state_key)
    if previous is not None and previous.value.startswith("passed:"):
        return {
            "status": "already_passed",
            "run_id": run_id,
            "mission_id": previous.value.removeprefix("passed:"),
        }

    labs = organization_labs(db)
    lab = labs["llm"]
    concept_key = _concept_key(run_id)
    created_by = f"system:e2e-smoke:{run_id}"[:128]

    ensure_concept(
        db,
        key=concept_key,
        title=f"Production E2E Memory Smoke {run_id}",
        description=(
            "Isolated Lab-private production smoke topic used to verify "
            "supersession, Context Pack delivery, Mission execution and Observatory projection."
        ),
        scope_type="lab",
        scope_id=lab.id,
        created_by="founder",
    )

    v1 = create_claim(
        db,
        concept_key=concept_key,
        content=(
            f"E2E_SMOKE {run_id}: CURRENT_MARKER={HISTORICAL_MARKER}. "
            "This seed claim must become bounded history after supersession."
        ),
        initial_status="current",
        disposition="experiment",
        source_type="decision",
        source_id=f"{run_id}:v1"[:64],
        created_by="founder",
        scope_type="lab",
        scope_id=lab.id,
    )
    db.commit()

    v2 = create_claim(
        db,
        concept_key=concept_key,
        content=(
            f"E2E_SMOKE {run_id}: CURRENT_MARKER={CURRENT_MARKER}. "
            f"Report {CURRENT_MARKER} as current; {HISTORICAL_MARKER} is superseded history."
        ),
        initial_status="current",
        disposition="experiment",
        source_type="decision",
        source_id=f"{run_id}:v2"[:64],
        created_by="founder",
        supersedes_claim_id=v1.id,
        scope_type="lab",
        scope_id=lab.id,
    )
    db.commit()

    mission = _find_existing_mission(
        db,
        lab_id=lab.id,
        created_by=created_by,
    )
    if mission is None or mission.status in {"failed", "cancelled"}:
        mission = create_mission(
            db,
            lab_id=lab.id,
            objective=(
                f"Production E2E smoke {run_id}: read the current knowledge for "
                f"{concept_key} and identify the currently valid marker."
            ),
            constraints=(
                "Read-only validation. Do not change repository code, external systems, "
                "organization policy, capital, deployment state, or other Lab data. "
                "Do not create a proposal. Use the delivered Context Pack."
            ),
            success_criteria=(
                f"The delivered Context Pack is lab-context-v2-knowledge-pack, "
                f"contains {CURRENT_MARKER} as current and {HISTORICAL_MARKER} only as "
                "superseded history, and the Researcher artifact identifies the current marker."
            ),
            mode="research",
            max_steps=1,
            created_by=created_by,
            max_cost_usd=0.03,
            data_classification="internal",
            owner="researcher",
            authority_level="A1",
        )

    if mission.status != "completed":
        result = run_mission(
            db,
            lab_id=lab.id,
            mission_id=mission.id,
            initial_spec={
                "_origin": "e2e_smoke",
                "to": "researcher",
                "request_type": "question",
                "message": (
                    f"Inspect the automatically delivered Context Pack for {concept_key}. "
                    f"State that the current marker is {CURRENT_MARKER}. "
                    f"Treat {HISTORICAL_MARKER} only as superseded history. "
                    "Do not perform external research and do not request another role. "
                    "Conclude the Mission now with LAB_HANDOFF action complete."
                ),
                "reason": "Bounded production memory/context smoke test",
            },
        )
    else:
        result = mission_state(db, lab_id=lab.id, mission_id=mission.id)

    mission = result["mission"]
    if mission.status != "completed":
        raise ProductionE2ESmokeError(
            f"Mission did not complete: status={mission.status}"
        )

    links = list_mission_work(db, lab_id=lab.id, mission_id=mission.id)
    if not links:
        raise ProductionE2ESmokeError("Mission completed without Work")
    work = db.get(LabWork, links[-1].work_id)
    if work is None or not work.context_snapshot_id:
        raise ProductionE2ESmokeError("Mission Work has no Context Pack snapshot")
    snapshot = db.get(LabContextSnapshot, work.context_snapshot_id)
    if snapshot is None:
        raise ProductionE2ESmokeError("Context Pack snapshot row is missing")

    view = _knowledge_view(snapshot, concept_key)
    current_claims = list(view.get("current_claims", []))
    history = list(view.get("bounded_history", []))

    current_ids = {str(item.get("id") or "") for item in current_claims}
    history_ids = {str(item.get("id") or "") for item in history}
    current_ok = (
        v2.id in current_ids
        and v1.id not in current_ids
        and any(
            CURRENT_MARKER in str(item.get("content") or "")
            for item in current_claims
            if str(item.get("id") or "") == v2.id
        )
    )
    history_ok = (
        v1.id in history_ids
        and any(
            str(item.get("id") or "") == v1.id
            and item.get("effective_status") == "superseded"
            for item in history
        )
    )
    if not current_ok or not history_ok:
        raise ProductionE2ESmokeError(
            "Context Pack current/history projection did not preserve supersession correctly"
        )

    artifact = result.get("final_artifact")
    if artifact is None:
        raise ProductionE2ESmokeError("Mission has no final Artifact")
    artifact_marker_ok = CURRENT_MARKER in (artifact.content or "")
    if not artifact_marker_ok:
        excerpt = " ".join((artifact.content or "").split())[:360]
        raise ProductionE2ESmokeError(
            "Researcher Artifact did not identify "
            f"{CURRENT_MARKER}; provider={artifact.provider}; model={artifact.model}; "
            f"artifact_excerpt={excerpt!r}"
        )

    bind_action(
        db,
        claim_id=v2.id,
        action_type="mission",
        action_id=mission.id,
        status="verified",
        detail={
            "purpose": "verification",
            "run_id": run_id,
            "context_snapshot_id": snapshot.id,
            "artifact_id": artifact.id,
            "assertions": {
                "context_schema_v2": True,
                "current_claim_v2": True,
                "superseded_v1_bounded_history": True,
                "researcher_read_current_marker": True,
            },
        },
        created_by="system:e2e-smoke",
    )
    db.commit()

    observatory = topic_detail(
        db,
        concept_key=concept_key,
        scope_type="lab",
        scope_id=lab.id,
    )
    matching_actions = [
        action
        for action in observatory.get("actions", [])
        if action.get("action_type") == "mission"
        and action.get("action_id") == mission.id
        and action.get("status") == "verified"
    ]
    if not matching_actions:
        raise ProductionE2ESmokeError(
            "Founder Knowledge Observatory did not project the verified Mission action"
        )
    if observatory.get("schema_version") != "founder-knowledge-observatory-v1":
        raise ProductionE2ESmokeError("Unexpected Knowledge Observatory schema")

    state = db.get(RuntimeState, state_key)
    if state is None:
        state = RuntimeState(key=state_key, value=f"passed:{mission.id}"[:240])
        db.add(state)
    else:
        state.value = f"passed:{mission.id}"[:240]
    db.commit()

    return {
        "status": "passed",
        "run_id": run_id,
        "lab_id": lab.id,
        "concept_key": concept_key,
        "v1_claim_id": v1.id,
        "v2_claim_id": v2.id,
        "mission_id": mission.id,
        "work_id": work.id,
        "context_snapshot_id": snapshot.id,
        "artifact_id": artifact.id,
        "context_schema": "lab-context-v2-knowledge-pack",
        "current_marker": CURRENT_MARKER,
        "historical_marker": HISTORICAL_MARKER,
        "observatory_schema": observatory["schema_version"],
        "observatory_action_recorded": True,
        "observatory_action_state": observatory.get("action_state"),
        "verification_action_is_non_implementation": True,
    }



def run_startup_smoke_if_enabled() -> dict[str, Any] | None:
    """Run the bounded production E2E smoke inside the Runtime process when explicitly enabled.

    The hook is inert unless LLM_HOLDINGS_E2E_SMOKE_RUN_ID is non-empty.
    When enabled, failures are raised so Railway healthcheck cannot report success
    for a deployment whose requested production smoke did not pass.
    """
    raw_run_id = os.getenv(RUN_ID_ENV, "").strip()
    if not raw_run_id:
        return None

    db = SessionLocal()
    try:
        result = run_production_e2e_smoke(db, run_id=raw_run_id)
        print(
            "PRODUCTION_E2E_SMOKE "
            + json.dumps(result, ensure_ascii=False, sort_keys=True),
            flush=True,
        )
        return result
    except Exception as exc:
        db.rollback()
        print(
            "PRODUCTION_E2E_SMOKE_FAILED "
            + json.dumps(
                {
                    "run_id": raw_run_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:800],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        )
        raise
    finally:
        db.close()

def main() -> int:
    raw_run_id = os.getenv(RUN_ID_ENV, "").strip()
    if not raw_run_id:
        print(
            "PRODUCTION_E2E_SMOKE "
            + json.dumps(
                {"status": "disabled", "reason": f"{RUN_ID_ENV} is not set"},
                sort_keys=True,
            )
        )
        return 0

    db = SessionLocal()
    try:
        result = run_production_e2e_smoke(db, run_id=raw_run_id)
        print(
            "PRODUCTION_E2E_SMOKE "
            + json.dumps(result, ensure_ascii=False, sort_keys=True)
        )
        return 0
    except Exception as exc:
        db.rollback()
        print(
            "PRODUCTION_E2E_SMOKE_FAILED "
            + json.dumps(
                {
                    "run_id": raw_run_id,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:800],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
