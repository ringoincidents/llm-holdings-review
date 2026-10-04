from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from runtime.background_execution import (
    MissionExecutionQueueError,
    enqueue_mission_execution,
    latest_mission_job,
)
from runtime.db import get_db
from runtime.lab_execution import (
    LabWorkExecutionError,
    LabWorkNotAssigned,
    promote_work_decision,
    run_delegated_work,
)
from runtime.lab_context import (
    LabContextInvalid,
    LabContextSnapshotNotFound,
    add_context_ref,
    assemble_context,
    deliver_context,
    list_context_refs,
    list_deliveries,
    require_snapshot,
)
from runtime.lab_seats import (
    AISeatAlreadyExists,
    AISeatNotFound,
    LabWorkNotLinked,
    assign_work,
    list_assignments,
    list_seats,
    register_seat,
)
from runtime.lab_work import (
    LabWorkInvalid,
    LabWorkNotFound as DurableLabWorkNotFound,
    LabWorkResultInvalid,
    add_work_result,
    create_work,
    delegate_work,
    list_work,
    list_work_results,
    require_work,
)
from runtime.labs import (
    LabNotFound,
    LabObjectAlreadyLinked,
    LabObjectNotFound,
    create_lab,
    linked_cases,
    link_object,
    list_lab_history,
    list_labs,
    list_links,
    require_lab,
)
from runtime.minimum_lab import ensure_minimum_lab
from runtime.lab_missions import (
    LabMissionInvalid,
    LabMissionNotFound,
    create_mission,
    list_agent_requests,
    list_missions,
    mission_state,
    run_mission,
    apply_founder_action,
)
from runtime.organization import (
    OrganizationInvalid,
    OrganizationNotFound,
    advance_founder_note,
    approve_proposal,
    capture_founder_note,
    dispatch_founder_command,
    ensure_organization,
    list_memory,
    organization_state,
    promote_memory_to_holdings,
    retain_memory,
    run_initiative,
    submit_proposal,
    triage_founder_note,
)
from schemas.api import (
    AISeatCreate,
    AISeatOut,
    ArtifactOut,
    CaseOut,
    DecisionOut,
    ExecutionRunOut,
    LabContextDeliveryOut,
    LabContextRefCreate,
    LabContextRefOut,
    LabContextSnapshotCreate,
    LabContextSnapshotOut,
    LabCreate,
    LabDecisionPromote,
    LabDetail,
    LabObjectLinkCreate,
    LabObjectLinkOut,
    LabOut,
    LabWorkAssignmentCreate,
    LabWorkAssignmentOut,
    LabWorkCreate,
    LabWorkDelegate,
    LabWorkOut,
    LabWorkResultCreate,
    LabWorkResultOut,
    LabWorkRunOut,
    LabMissionCreate,
    LabMissionOut,
    LabMissionRunOut,
    MissionExecutionJobOut,
    FounderMissionAction,
    FounderCommandCreate,
    FounderCommandDispatchOut,
    LabAgentRequestOut,
    FounderNoteAdvance,
    FounderNoteCreate,
    FounderNoteOut,
    HoldingsInitiativeOut,
    LabProposalCreate,
    LabProposalOut,
    MemoryPromote,
    OrganizationStateOut,
    OrganizationalMemoryCreate,
    OrganizationalMemoryOut,
    ProposalApprove,
    TaskOut,
)

router = APIRouter(prefix="/labs", tags=["labs"])


@router.post("", response_model=LabOut, status_code=201)
def create(payload: LabCreate, db: Session = Depends(get_db)):
    return create_lab(db, **payload.model_dump())


@router.get("", response_model=list[LabOut])
def list_all(db: Session = Depends(get_db)):
    return list_labs(db)


@router.post("/bootstrap", response_model=LabOut)
def bootstrap_minimum_lab(db: Session = Depends(get_db)):
    return ensure_minimum_lab(db)


@router.post("/bootstrap-organization", response_model=OrganizationStateOut)
def bootstrap_organization(db: Session = Depends(get_db)):
    return ensure_organization(db)


@router.get("/organization", response_model=OrganizationStateOut)
def holdings_organization(db: Session = Depends(get_db)):
    return organization_state(db)


@router.post(
    "/organization/commands",
    response_model=FounderCommandDispatchOut,
    status_code=202,
)
def dispatch_command(
    payload: FounderCommandCreate,
    db: Session = Depends(get_db),
):
    try:
        return dispatch_founder_command(db, **payload.model_dump())
    except (OrganizationInvalid, LabMissionInvalid, MissionExecutionQueueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/organization/notes", response_model=FounderNoteOut, status_code=201)
def create_founder_note(payload: FounderNoteCreate, db: Session = Depends(get_db)):
    try:
        return capture_founder_note(db, **payload.model_dump())
    except OrganizationInvalid as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/organization/notes/{note_id}/triage",
    response_model=OrganizationStateOut,
)
def triage_note(
    note_id: str,
    db: Session = Depends(get_db),
):
    try:
        return triage_founder_note(db, note_id=note_id)
    except OrganizationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OrganizationInvalid, LabMissionInvalid) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.patch("/organization/notes/{note_id}", response_model=FounderNoteOut)
def update_founder_note(
    note_id: str,
    payload: FounderNoteAdvance,
    db: Session = Depends(get_db),
):
    try:
        return advance_founder_note(db, note_id=note_id, **payload.model_dump())
    except OrganizationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OrganizationInvalid as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/organization/memory",
    response_model=list[OrganizationalMemoryOut],
)
def holdings_memory(db: Session = Depends(get_db)):
    return list_memory(db, scope_type="holdings", scope_id="holdings")


@router.post(
    "/organization/memory/{memory_id}/promote",
    response_model=OrganizationalMemoryOut,
    status_code=201,
)
def promote_organization_memory(
    memory_id: str,
    payload: MemoryPromote,
    db: Session = Depends(get_db),
):
    try:
        return promote_memory_to_holdings(
            db,
            memory_id=memory_id,
            approved_by=payload.approved_by,
        )
    except OrganizationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OrganizationInvalid as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/organization/proposals/{proposal_id}/approve",
    response_model=HoldingsInitiativeOut,
    status_code=201,
)
def approve_organization_proposal(
    proposal_id: str,
    payload: ProposalApprove,
    db: Session = Depends(get_db),
):
    try:
        return approve_proposal(db, proposal_id=proposal_id, **payload.model_dump())
    except OrganizationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OrganizationInvalid as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/organization/initiatives/{initiative_id}/run",
    response_model=OrganizationStateOut,
)
def run_organization_initiative(
    initiative_id: str,
    db: Session = Depends(get_db),
):
    try:
        return run_initiative(db, initiative_id=initiative_id)
    except OrganizationNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (OrganizationInvalid, LabMissionInvalid) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{lab_id}", response_model=LabDetail)
def detail(lab_id: str, db: Session = Depends(get_db)):
    try:
        lab = require_lab(db, lab_id)
        objects = list_links(db, lab_id)
        cases = linked_cases(db, lab_id)
        seats = list_seats(db, lab_id)
        assignments = list_assignments(db, lab_id)
        context_refs = list_context_refs(db, lab_id)
        work = list_work(db, lab_id)
        work_results = list_work_results(db, lab_id=lab_id)
        history = list_lab_history(db, lab_id)
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc

    return LabDetail(
        **LabOut.model_validate(lab).model_dump(),
        objects=[LabObjectLinkOut.model_validate(item) for item in objects],
        cases=[CaseOut.model_validate(case) for case in cases],
        seats=[AISeatOut.model_validate(seat) for seat in seats],
        assignments=[
            LabWorkAssignmentOut.model_validate(item) for item in assignments
        ],
        context_refs=[
            LabContextRefOut.model_validate(item) for item in context_refs
        ],
        work=[LabWorkOut.model_validate(item) for item in work],
        work_results=[
            LabWorkResultOut.model_validate(item) for item in work_results
        ],
        history=[
            {
                "id": event.id,
                "case_id": event.case_id,
                "type": event.type,
                "payload_json": event.payload_json,
                "created_at": event.created_at,
            }
            for event in history
        ],
    )


@router.post(
    "/{lab_id}/objects",
    response_model=LabObjectLinkOut,
    status_code=201,
)
def attach(
    lab_id: str,
    payload: LabObjectLinkCreate,
    db: Session = Depends(get_db),
):
    try:
        return link_object(
            db,
            lab_id=lab_id,
            object_type=payload.object_type,
            object_id=payload.object_id,
            relationship=payload.relationship,
        )
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc
    except LabObjectNotFound as exc:
        raise HTTPException(404, "Runtime object not found") from exc
    except LabObjectAlreadyLinked as exc:
        raise HTTPException(409, "Runtime object is already linked to this Lab") from exc



@router.post(
    "/{lab_id}/seats",
    response_model=AISeatOut,
    status_code=201,
)
def add_seat(
    lab_id: str,
    payload: AISeatCreate,
    db: Session = Depends(get_db),
):
    try:
        return register_seat(db, lab_id=lab_id, **payload.model_dump())
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc
    except AISeatAlreadyExists as exc:
        raise HTTPException(409, "Seat key already exists in this Lab") from exc


@router.get("/{lab_id}/seats", response_model=list[AISeatOut])
def seats(lab_id: str, db: Session = Depends(get_db)):
    try:
        return list_seats(db, lab_id)
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc


@router.post(
    "/{lab_id}/assignments",
    response_model=LabWorkAssignmentOut,
    status_code=201,
)
def assign(
    lab_id: str,
    payload: LabWorkAssignmentCreate,
    db: Session = Depends(get_db),
):
    try:
        return assign_work(db, lab_id=lab_id, **payload.model_dump())
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc
    except AISeatNotFound as exc:
        raise HTTPException(404, "AI Seat not found in this Lab") from exc
    except LabWorkNotLinked as exc:
        raise HTTPException(409, "Work object must be linked to the Lab before assignment") from exc


@router.get(
    "/{lab_id}/assignments",
    response_model=list[LabWorkAssignmentOut],
)
def assignments(lab_id: str, db: Session = Depends(get_db)):
    try:
        return list_assignments(db, lab_id)
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc



@router.post(
    "/{lab_id}/context/refs",
    response_model=LabContextRefOut,
    status_code=201,
)
def add_shared_context_ref(
    lab_id: str,
    payload: LabContextRefCreate,
    db: Session = Depends(get_db),
):
    try:
        values = payload.model_dump()
        metadata = values.pop("metadata")
        return add_context_ref(db, lab_id=lab_id, metadata=metadata, **values)
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc
    except LabContextInvalid as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get(
    "/{lab_id}/context/refs",
    response_model=list[LabContextRefOut],
)
def shared_context_refs(lab_id: str, db: Session = Depends(get_db)):
    try:
        return list_context_refs(db, lab_id)
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc


@router.post(
    "/{lab_id}/context/snapshots",
    response_model=LabContextSnapshotOut,
    status_code=201,
)
def create_context_snapshot(
    lab_id: str,
    payload: LabContextSnapshotCreate,
    db: Session = Depends(get_db),
):
    try:
        return assemble_context(db, lab_id=lab_id, created_by=payload.created_by)
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc


@router.get(
    "/{lab_id}/context/snapshots/{snapshot_id}",
    response_model=LabContextSnapshotOut,
)
def context_snapshot(
    lab_id: str,
    snapshot_id: str,
    db: Session = Depends(get_db),
):
    try:
        return require_snapshot(db, lab_id=lab_id, snapshot_id=snapshot_id)
    except (LabNotFound, LabContextSnapshotNotFound) as exc:
        raise HTTPException(404, "Context snapshot not found") from exc


@router.post(
    "/{lab_id}/context/snapshots/{snapshot_id}/deliver/{seat_id}",
    response_model=LabContextDeliveryOut,
    status_code=201,
)
def deliver_shared_context(
    lab_id: str,
    snapshot_id: str,
    seat_id: str,
    db: Session = Depends(get_db),
):
    try:
        return deliver_context(
            db,
            lab_id=lab_id,
            snapshot_id=snapshot_id,
            seat_id=seat_id,
        )
    except (LabNotFound, LabContextSnapshotNotFound, AISeatNotFound) as exc:
        raise HTTPException(404, "Lab, snapshot, or AI Seat not found") from exc


@router.get(
    "/{lab_id}/context/deliveries",
    response_model=list[LabContextDeliveryOut],
)
def context_deliveries(
    lab_id: str,
    snapshot_id: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        return list_deliveries(db, lab_id=lab_id, snapshot_id=snapshot_id)
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc



@router.post(
    "/{lab_id}/work",
    response_model=LabWorkOut,
    status_code=201,
)
def create_lab_work(
    lab_id: str,
    payload: LabWorkCreate,
    db: Session = Depends(get_db),
):
    try:
        return create_work(db, lab_id=lab_id, **payload.model_dump())
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc
    except (LabWorkInvalid, LabContextSnapshotNotFound) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get(
    "/{lab_id}/work",
    response_model=list[LabWorkOut],
)
def lab_work(lab_id: str, db: Session = Depends(get_db)):
    try:
        return list_work(db, lab_id)
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc


@router.get(
    "/{lab_id}/work/{work_id}",
    response_model=LabWorkOut,
)
def lab_work_detail(
    lab_id: str,
    work_id: str,
    db: Session = Depends(get_db),
):
    try:
        return require_work(db, lab_id=lab_id, work_id=work_id)
    except (LabNotFound, DurableLabWorkNotFound) as exc:
        raise HTTPException(404, "Lab Work not found") from exc


@router.post(
    "/{lab_id}/work/{work_id}/delegate",
    response_model=LabWorkAssignmentOut,
    status_code=201,
)
def delegate_lab_work(
    lab_id: str,
    work_id: str,
    payload: LabWorkDelegate,
    db: Session = Depends(get_db),
):
    try:
        return delegate_work(
            db,
            lab_id=lab_id,
            work_id=work_id,
            seat_id=payload.seat_id,
            assigned_by=payload.assigned_by,
        )
    except (LabNotFound, DurableLabWorkNotFound, AISeatNotFound) as exc:
        raise HTTPException(404, "Lab Work or AI Seat not found") from exc


@router.post(
    "/{lab_id}/work/{work_id}/results",
    response_model=LabWorkResultOut,
    status_code=201,
)
def link_lab_work_result(
    lab_id: str,
    work_id: str,
    payload: LabWorkResultCreate,
    db: Session = Depends(get_db),
):
    try:
        return add_work_result(
            db,
            lab_id=lab_id,
            work_id=work_id,
            **payload.model_dump(),
        )
    except (LabNotFound, DurableLabWorkNotFound) as exc:
        raise HTTPException(404, "Lab Work not found") from exc
    except LabWorkResultInvalid as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get(
    "/{lab_id}/work/{work_id}/results",
    response_model=list[LabWorkResultOut],
)
def lab_work_results(
    lab_id: str,
    work_id: str,
    db: Session = Depends(get_db),
):
    try:
        return list_work_results(db, lab_id=lab_id, work_id=work_id)
    except (LabNotFound, DurableLabWorkNotFound) as exc:
        raise HTTPException(404, "Lab Work not found") from exc



@router.post(
    "/{lab_id}/work/{work_id}/run",
    response_model=LabWorkRunOut,
)
def run_lab_work(
    lab_id: str,
    work_id: str,
    db: Session = Depends(get_db),
):
    try:
        result = run_delegated_work(db, lab_id=lab_id, work_id=work_id)
    except (LabNotFound, DurableLabWorkNotFound) as exc:
        raise HTTPException(404, "Lab Work not found") from exc
    except LabWorkNotAssigned as exc:
        raise HTTPException(409, "Lab Work must be delegated before execution") from exc
    except LabWorkExecutionError as exc:
        raise HTTPException(409, str(exc)) from exc

    return LabWorkRunOut(
        work=LabWorkOut.model_validate(result["work"]),
        seat=AISeatOut.model_validate(result["seat"]),
        case=CaseOut.model_validate(result["case"]),
        task=TaskOut.model_validate(result["task"]),
        decision=DecisionOut.model_validate(result["decision"]),
        execution=ExecutionRunOut.model_validate(result["execution"]),
        artifact=ArtifactOut.model_validate(result["artifact"]),
        context_snapshot=LabContextSnapshotOut.model_validate(
            result["context_snapshot"]
        ),
    )


@router.post(
    "/{lab_id}/work/{work_id}/promote-decision",
    response_model=DecisionOut,
    status_code=201,
)
def promote_lab_work_decision(
    lab_id: str,
    work_id: str,
    payload: LabDecisionPromote,
    db: Session = Depends(get_db),
):
    try:
        return promote_work_decision(
            db,
            lab_id=lab_id,
            work_id=work_id,
            statement=payload.statement,
            question=payload.question,
        )
    except (LabNotFound, DurableLabWorkNotFound) as exc:
        raise HTTPException(404, "Lab Work not found") from exc
    except LabWorkExecutionError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post(
    "/{lab_id}/missions",
    response_model=LabMissionOut,
    status_code=201,
)
def create_lab_mission(
    lab_id: str,
    payload: LabMissionCreate,
    db: Session = Depends(get_db),
):
    try:
        return create_mission(db, lab_id=lab_id, **payload.model_dump())
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc
    except LabMissionInvalid as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get(
    "/{lab_id}/missions",
    response_model=list[LabMissionOut],
)
def lab_missions(lab_id: str, db: Session = Depends(get_db)):
    try:
        return list_missions(db, lab_id)
    except LabNotFound as exc:
        raise HTTPException(404, "Lab not found") from exc


@router.get(
    "/{lab_id}/missions/{mission_id}",
    response_model=LabMissionRunOut,
)
def lab_mission_detail(
    lab_id: str,
    mission_id: str,
    db: Session = Depends(get_db),
):
    try:
        return mission_state(db, lab_id=lab_id, mission_id=mission_id)
    except (LabNotFound, LabMissionNotFound) as exc:
        raise HTTPException(404, "Lab Mission not found") from exc


@router.post(
    "/{lab_id}/missions/{mission_id}/enqueue",
    response_model=MissionExecutionJobOut,
    status_code=202,
)
def enqueue_lab_mission(
    lab_id: str,
    mission_id: str,
    db: Session = Depends(get_db),
):
    try:
        return enqueue_mission_execution(
            db,
            lab_id=lab_id,
            mission_id=mission_id,
            created_by="founder",
        )
    except MissionExecutionQueueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get(
    "/{lab_id}/missions/{mission_id}/execution-job",
    response_model=MissionExecutionJobOut | None,
)
def mission_execution_job(
    lab_id: str,
    mission_id: str,
    db: Session = Depends(get_db),
):
    return latest_mission_job(
        db,
        lab_id=lab_id,
        mission_id=mission_id,
    )


@router.post(
    "/{lab_id}/missions/{mission_id}/run",
    response_model=LabMissionRunOut,
)
def run_lab_mission(
    lab_id: str,
    mission_id: str,
    db: Session = Depends(get_db),
):
    try:
        return run_mission(db, lab_id=lab_id, mission_id=mission_id)
    except (LabNotFound, LabMissionNotFound) as exc:
        raise HTTPException(404, "Lab Mission not found") from exc
    except (LabMissionInvalid, LabWorkExecutionError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post(
    "/{lab_id}/missions/{mission_id}/founder-action-async",
    response_model=LabMissionRunOut,
)
def founder_action_on_mission_async(
    lab_id: str,
    mission_id: str,
    payload: FounderMissionAction,
    db: Session = Depends(get_db),
):
    try:
        return apply_founder_action(
            db,
            lab_id=lab_id,
            mission_id=mission_id,
            defer_execution=True,
            **payload.model_dump(),
        )
    except (LabNotFound, LabMissionNotFound) as exc:
        raise HTTPException(404, "Lab Mission not found") from exc
    except (LabMissionInvalid, LabWorkExecutionError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post(
    "/{lab_id}/missions/{mission_id}/founder-action",
    response_model=LabMissionRunOut,
)
def founder_action_on_mission(
    lab_id: str,
    mission_id: str,
    payload: FounderMissionAction,
    db: Session = Depends(get_db),
):
    try:
        return apply_founder_action(
            db,
            lab_id=lab_id,
            mission_id=mission_id,
            **payload.model_dump(),
        )
    except (LabNotFound, LabMissionNotFound) as exc:
        raise HTTPException(404, "Lab Mission not found") from exc
    except (LabMissionInvalid, LabWorkExecutionError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get(
    "/{lab_id}/agent-requests",
    response_model=list[LabAgentRequestOut],
)
def lab_agent_requests(
    lab_id: str,
    mission_id: str | None = None,
    db: Session = Depends(get_db),
):
    try:
        return list_agent_requests(db, lab_id=lab_id, mission_id=mission_id)
    except (LabNotFound, LabMissionNotFound) as exc:
        raise HTTPException(404, "Lab or Mission not found") from exc



@router.post(
    "/{lab_id}/memory",
    response_model=OrganizationalMemoryOut,
    status_code=201,
)
def retain_lab_memory(
    lab_id: str,
    payload: OrganizationalMemoryCreate,
    db: Session = Depends(get_db),
):
    if payload.scope_type != "lab" or payload.scope_id != lab_id:
        raise HTTPException(status_code=409, detail="Lab memory must use the current lab_id")
    try:
        return retain_memory(db, **payload.model_dump())
    except OrganizationInvalid as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/{lab_id}/memory",
    response_model=list[OrganizationalMemoryOut],
)
def lab_memory(lab_id: str, db: Session = Depends(get_db)):
    try:
        require_lab(db, lab_id)
        return list_memory(db, scope_type="lab", scope_id=lab_id)
    except LabNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{lab_id}/proposals",
    response_model=LabProposalOut,
    status_code=201,
)
def create_lab_proposal(
    lab_id: str,
    payload: LabProposalCreate,
    db: Session = Depends(get_db),
):
    try:
        return submit_proposal(
            db,
            source_lab_id=lab_id,
            **payload.model_dump(),
        )
    except (OrganizationInvalid, LabNotFound) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc



@router.post(
    "/{lab_id}/seats/{seat_id}/memory",
    response_model=OrganizationalMemoryOut,
    status_code=201,
)
def retain_employee_memory(
    lab_id: str,
    seat_id: str,
    payload: OrganizationalMemoryCreate,
    db: Session = Depends(get_db),
):
    seat_ids = {seat.id for seat in list_seats(db, lab_id)}
    if seat_id not in seat_ids:
        raise HTTPException(status_code=404, detail="AI Seat not found in this Lab")
    if payload.scope_type != "employee" or payload.scope_id != seat_id:
        raise HTTPException(status_code=409, detail="Employee memory must use the current seat_id")
    try:
        return retain_memory(db, **payload.model_dump())
    except OrganizationInvalid as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/{lab_id}/seats/{seat_id}/memory",
    response_model=list[OrganizationalMemoryOut],
)
def employee_memory(
    lab_id: str,
    seat_id: str,
    db: Session = Depends(get_db),
):
    seat_ids = {seat.id for seat in list_seats(db, lab_id)}
    if seat_id not in seat_ids:
        raise HTTPException(status_code=404, detail="AI Seat not found in this Lab")
    return list_memory(db, scope_type="employee", scope_id=seat_id)
