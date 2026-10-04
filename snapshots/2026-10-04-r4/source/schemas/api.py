from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AISeatCreate(BaseModel):
    seat_key: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    role: str = Field(min_length=1, max_length=120)
    capabilities: list[str] = Field(default_factory=list)
    model_policy: str = Field(min_length=1, max_length=96)
    status: Literal["ready", "working", "paused", "offline"] = "ready"


class AISeatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    seat_key: str
    name: str
    role: str
    capabilities: list[str]
    model_policy: str
    status: str
    created_at: datetime
    updated_at: datetime


class LabWorkAssignmentCreate(BaseModel):
    object_type: Literal["case", "task", "work"]
    object_id: str = Field(min_length=1)
    seat_id: str = Field(min_length=1)
    assigned_by: str = "founder"


class LabWorkAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    seat_id: str
    object_type: str
    object_id: str
    assigned_by: str
    assigned_at: datetime


class LabContextRefCreate(BaseModel):
    context_type: Literal["file", "decision", "evidence", "artifact", "repository_state"]
    ref: str = Field(min_length=1, max_length=320)
    label: str = Field(min_length=1, max_length=200)
    source_uri: str | None = Field(default=None, max_length=500)
    priority: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str = "founder"


class LabContextRefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    context_type: str
    ref: str
    label: str
    source_uri: str | None
    priority: int
    metadata_json: str
    created_by: str
    created_at: datetime


class LabContextSnapshotCreate(BaseModel):
    created_by: str = "founder"


class LabContextSnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    content_hash: str
    context_json: str
    created_by: str
    created_at: datetime


class LabContextDeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    snapshot_id: str
    seat_id: str
    delivered_at: datetime


class LabWorkCreate(BaseModel):
    work_type: Literal["task", "case", "review", "question", "experiment"]
    title: str = Field(min_length=1, max_length=240)
    instructions: str = ""
    context_snapshot_id: str | None = None
    created_by: str = "founder"


class LabWorkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    work_type: str
    title: str
    instructions: str
    status: str
    context_snapshot_id: str | None
    runtime_object_type: str | None
    runtime_object_id: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class LabWorkDelegate(BaseModel):
    seat_id: str = Field(min_length=1)
    assigned_by: str = "founder"


class LabWorkResultCreate(BaseModel):
    result_type: Literal["artifact", "review", "evidence", "decision"]
    result_id: str = Field(min_length=1)


class LabWorkResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    work_id: str
    result_type: str
    result_id: str
    created_at: datetime


class LabDecisionPromote(BaseModel):
    statement: str = Field(min_length=1, max_length=160)
    question: str | None = Field(default=None, max_length=500)


class LabCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=1)
    status: Literal["active", "paused", "archived"] = "active"
    created_by: str = "founder"


class LabOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    objective: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


LabObjectType = Literal[
    "case",
    "task",
    "decision",
    "execution_run",
    "artifact",
    "evidence",
    "approval",
]


class LabObjectLinkCreate(BaseModel):
    object_type: LabObjectType
    object_id: str = Field(min_length=1)
    relationship: str = Field(default="contains", min_length=1, max_length=64)


class LabObjectLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    object_type: str
    object_id: str
    relationship: str
    created_at: datetime


class CaseCreate(BaseModel):
    company: str = "quantrade"
    title: str = Field(min_length=3, max_length=240)
    priority: Literal["low", "normal", "high", "critical"] = "normal"
    risk_level: Literal["low", "medium", "high", "critical"] = "low"


class CaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    company: str
    title: str
    status: str
    priority: str
    risk_level: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class LabDetail(LabOut):
    objects: list[LabObjectLinkOut]
    cases: list[CaseOut]
    seats: list[AISeatOut]
    assignments: list[LabWorkAssignmentOut]
    context_refs: list[LabContextRefOut]
    work: list[LabWorkOut]
    work_results: list[LabWorkResultOut]
    history: list[dict[str, Any]]


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    type: str
    owner_agent: str
    status: str
    result: str | None
    created_at: datetime
    completed_at: datetime | None


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    decision_type: str
    question: str
    prediction: str
    confidence: float
    provider: str
    human_decision: str | None
    accepted: bool | None
    supersedes_id: str | None
    created_at: datetime


class ExecutionRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    task_id: str | None
    decision_id: str | None
    status: str
    provider: str | None
    model: str | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    cost_usd: float
    tools_used_json: str
    error: str | None
    retries: int
    human_override: bool | None
    outcome: str | None
    started_at: datetime
    finished_at: datetime | None


class ArtifactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    task_id: str | None
    kind: str
    content: str
    content_hash: str
    producer_type: str
    producer_id: str
    provider: str | None
    model: str | None
    created_at: datetime


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    source: str
    content: str
    content_hash: str
    supports: str
    retrieved_at: datetime


class ApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    reason: str
    risk_level: str
    status: str
    created_at: datetime
    resolved_at: datetime | None


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    case_id: str | None
    type: str
    payload_json: str
    created_at: datetime


class S1ChoiceResult(BaseModel):
    choice: str
    confidence: float
    distribution: dict[str, float]
    provider: str


class S1BooleanResult(BaseModel):
    value: bool
    probability: float
    provider: str


class S1ScoreResult(BaseModel):
    score: str
    confidence: float
    distribution: dict[str, float]
    provider: str


class S1RouteInput(BaseModel):
    company: str
    title: str = Field(min_length=1)
    risk_level: Literal["low", "medium", "high", "critical"] = "low"


class S1RouteResult(BaseModel):
    company: str
    department: Literal["research", "review", "developer", "human"]
    task_type: str
    human_review: bool
    confidence: float
    provider: str


class CaseDetail(CaseOut):
    tasks: list[TaskOut]
    decisions: list[DecisionOut]
    runs: list[ExecutionRunOut]
    artifacts: list[ArtifactOut]
    evidence: list[EvidenceOut]
    approvals: list[ApprovalOut]
    events: list[EventOut]


class KillSwitchStatus(BaseModel):
    global_stopped: bool
    company_stopped: bool
    case_stopped: bool
    effective_stopped: bool
    blocked_by: str | None


class DashboardStats(BaseModel):
    active_cases: int
    waiting_approval: int
    agents_running: int
    today_cost_usd: float = 0.0
    stopped: bool
    companies: dict[str, int]


class AgentView(BaseModel):
    agent_id: str
    role: str
    capabilities: list[str]
    model_policy: str
    status: str
    case_id: str | None = None


class RunResult(BaseModel):
    case: CaseOut
    route: S1RouteResult
    task: TaskOut
    execution: ExecutionRunOut
    approval: ApprovalOut | None = None
    metadata: dict[str, Any] = {}



class LabWorkRunOut(BaseModel):
    work: LabWorkOut
    seat: AISeatOut
    case: CaseOut
    task: TaskOut
    decision: DecisionOut
    execution: ExecutionRunOut
    artifact: ArtifactOut
    context_snapshot: LabContextSnapshotOut


class LabMissionCreate(BaseModel):
    owner: str | None = Field(default=None, min_length=1, max_length=128)
    authority_level: Literal["A0", "A1", "A2"] = "A1"
    objective: str = Field(min_length=1)
    constraints: str = ""
    success_criteria: str = ""
    mode: Literal["auto", "research", "build"] = "auto"
    max_steps: int = Field(default=4, ge=1, le=8)
    created_by: str = "founder"
    delivery_target: Literal["local_verified", "pr_published", "merged", "deployed"] | None = None
    max_cost_usd: float | None = Field(default=None, gt=0, le=5.0)
    data_classification: Literal["public", "internal", "confidential"] = "internal"


class LabMissionOut(BaseModel):
    owner: str
    authority_level: str
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    objective: str
    constraints: str
    success_criteria: str
    mode: str
    status: str
    max_steps: int
    step_count: int
    final_artifact_id: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class MissionExecutionJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    mission_id: str
    status: str
    baseline_step_count: int
    attempt_count: int
    max_attempts: int
    lease_owner: str | None
    lease_expires_at: datetime | None
    last_error: str | None
    created_by: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


class LabMissionWorkLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    mission_id: str
    work_id: str
    sequence: int
    created_at: datetime


class LabAgentRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    lab_id: str
    mission_id: str
    from_seat_id: str | None
    to_seat_id: str | None
    target_key: str
    request_type: str
    message: str
    rationale: str
    origin: str
    source_work_id: str | None
    target_work_id: str | None
    status: str
    created_at: datetime
    resolved_at: datetime | None


class FounderMissionAction(BaseModel):
    action: Literal["approve", "revise", "defer", "cancel"]
    message: str = ""
    extra_steps: int = Field(default=2, ge=1, le=8)


class LabMissionRunOut(BaseModel):
    governance: dict[str, Any] = Field(default_factory=dict)
    authority_resolutions: list[dict[str, Any]] = Field(default_factory=list)
    discovery: list[dict[str, Any]] = Field(default_factory=list)
    mission: LabMissionOut
    work_links: list[LabMissionWorkLinkOut]
    requests: list[LabAgentRequestOut]
    final_artifact: ArtifactOut | None = None
    founder_brief: dict[str, Any] | None = None
    founder_actions: list[dict[str, Any]] = Field(default_factory=list)
    founder_report: dict[str, Any] = Field(default_factory=dict)
    completion_integrity: dict[str, Any] = Field(default_factory=dict)
    delivery: dict[str, Any] = Field(default_factory=dict)
    budget: dict[str, Any] = Field(default_factory=dict)
    execution_evidence: list[dict[str, Any]] = Field(default_factory=list)
    execution_job: MissionExecutionJobOut | None = None



class OrganizationalMemoryCreate(BaseModel):
    scope_type: Literal["employee", "lab", "holdings"]
    scope_id: str = Field(min_length=1, max_length=64)
    memory_type: str = Field(default="knowledge", min_length=1, max_length=48)
    content: str = Field(min_length=1)
    source_type: str | None = Field(default=None, max_length=48)
    source_id: str | None = Field(default=None, max_length=64)
    created_by: str = "system"


class OrganizationalMemoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    scope_type: str
    scope_id: str
    memory_type: str
    content: str
    status: str
    source_type: str | None
    source_id: str | None
    supersedes_id: str | None
    created_by: str
    created_at: datetime
    trust_class: str | None = None
    origin_actor: str | None = None
    authority_level: str | None = None
    provenance_json: str | None = None


class MemoryPromote(BaseModel):
    approved_by: str = "founder"


class FounderCommandCreate(BaseModel):
    command: str = Field(min_length=1, max_length=4000)
    created_by: str = "founder"


class FounderCommandDispatchOut(BaseModel):
    command: str
    routed_lab_key: str
    routed_lab_id: str
    routed_lab_title: str
    route_reason: str
    source_note_id: str
    record_writer: dict[str, Any] = Field(default_factory=dict)
    matched_capability: dict[str, Any] | None = None
    mission: LabMissionOut
    execution_job: MissionExecutionJobOut


class FounderNoteCreate(BaseModel):
    raw_text: str = Field(min_length=1)
    created_by: str = "founder"


class FounderNoteAdvance(BaseModel):
    state: Literal["interpreted", "hypothesis", "proposal", "approved_work", "decision", "raw"]
    interpreted_text: str = ""
    proposed_lab_id: str | None = None


class FounderNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    raw_text: str
    interpreted_text: str
    state: str
    proposed_lab_id: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime


class LabProposalCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    summary: str = Field(min_length=1)
    source_mission_id: str | None = None
    impact: Literal["lab", "cross_lab", "holdings"] = "cross_lab"
    required_labs: list[str] = Field(default_factory=list)
    created_by: str = "founder"


class LabProposalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source_lab_id: str
    source_mission_id: str | None
    title: str
    summary: str
    impact: str
    required_labs_json: str
    status: str
    created_by: str
    reviewed_by: str | None
    created_at: datetime
    reviewed_at: datetime | None


class ProposalApprove(BaseModel):
    reviewed_by: str = "founder"
    priority: Literal["low", "normal", "high", "critical"] = "normal"


class InterLabRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    proposal_id: str | None
    from_lab_id: str
    to_lab_id: str
    request_type: str
    message: str
    status: str
    created_by: str
    created_at: datetime
    resolved_at: datetime | None


class HoldingsInitiativeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    proposal_id: str | None
    title: str
    objective: str
    priority: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class HoldingsWorkLedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    initiative_id: str | None
    lab_id: str
    mission_id: str | None
    work_id: str | None
    title: str
    status: str
    priority: str
    sequence: int
    depends_on_json: str
    blocked_by_json: str
    source_type: str
    source_id: str | None
    created_at: datetime
    updated_at: datetime


class OperationalIncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    fingerprint: str
    category: str
    severity: str
    summary: str
    lab_id: str | None
    mission_id: str | None
    source_event_type: str
    occurrence_count: int
    status: str
    proposal_id: str | None
    first_event_id: int | None
    last_event_id: int | None
    created_at: datetime
    updated_at: datetime


class OrganizationLabSummary(BaseModel):
    key: str
    lab: LabOut
    memory_count: int


class OrganizationStateOut(BaseModel):
    exception_inbox: list[dict[str, Any]] = Field(default_factory=list)
    deferred_inbox: list[dict[str, Any]] = Field(default_factory=list)
    capability_registry: list[dict[str, Any]] = Field(default_factory=list)
    labs: list[OrganizationLabSummary]
    proposals: list[LabProposalOut]
    initiatives: list[HoldingsInitiativeOut]
    ledger: list[HoldingsWorkLedgerEntryOut]
    founder_notes: list[FounderNoteOut]
    inter_lab_requests: list[InterLabRequestOut]
    operational_health: dict[str, Any] = Field(default_factory=dict)
    incidents: list[OperationalIncidentOut] = Field(default_factory=list)
