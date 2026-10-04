from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .events import emit
from .lab_seats import list_seats, register_seat
from .labs import create_lab, require_lab
from .minimum_lab import ensure_minimum_lab
from .operational_learning import list_operational_incidents, operational_health
from .models import (
    FounderNote,
    HoldingsInitiative,
    HoldingsWorkLedgerEntry,
    InterLabRequest,
    Lab,
    LabMission,
    LabProposal,
    OperationalIncident,
    OrganizationalMemory,
    RuntimeState,
)


LAB_SPECS = {
    "hq": {
        "title": "Holdings HQ / 비서실",
        "objective": "Coordinate Labs, resolve priorities and dependencies, and present only decision-ready work to the Founder.",
    },
    "design": {
        "title": "Design Lab",
        "objective": "Accumulate design knowledge and turn product, interface, architecture and visual findings into reusable design decisions.",
    },
    "quantrade": {
        "title": "QuanTrade",
        "objective": "Operate the investment decision-support organization while keeping research, risk, decisions and performance auditable.",
    },
    "runtime": {
        "title": "Runtime Engineering Lab",
        "objective": "Own, maintain, verify and deliver the shared LLM Holdings OS while preserving architecture, authority, provenance and operational reliability.",
    },
}

COMMON_SEATS = (
    {
        "seat_key": "researcher",
        "name": "Researcher",
        "role": "Investigate the Lab domain and build evidence-aware knowledge.",
        "capabilities": ["research", "evidence_analysis"],
        "model_policy": "research-standard",
    },
    {
        "seat_key": "reviewer",
        "name": "Reviewer",
        "role": "Challenge claims, detect conflicts and verify work before escalation.",
        "capabilities": ["review", "verification"],
        "model_policy": "review-standard",
    },
    {
        "seat_key": "developer",
        "name": "Builder",
        "role": "Turn approved Lab direction into concrete implementation or operating artifacts.",
        "capabilities": ["development", "implementation"],
        "model_policy": "coding-standard",
    },
) 

LAB_EXTRA_SEATS = {
    "quantrade": (
        {
            "seat_key": "client_intelligence",
            "name": "Client Intelligence Officer",
            "role": "Maintain private Client facts, identify information gaps, prepare question reports, and represent Client context in QuanTrade internal meetings.",
            "capabilities": ["client_intelligence", "client_questioning", "capital_context", "meeting_support"],
            "model_policy": "research-standard",
        },
    ),
    "runtime": (
        {
            "seat_key": "maintainer",
            "name": "Runtime Maintainer",
            "role": "Own shared OS maintenance, repository integrity and bounded implementation.",
            "capabilities": ["runtime_maintenance", "platform_engineering", "debugging"],
            "model_policy": "coding-standard",
        },
        {
            "seat_key": "release_engineer",
            "name": "Release Engineer",
            "role": "Verify CI, delivery, deployment and rollback evidence for shared Runtime changes.",
            "capabilities": ["release_engineering", "delivery_verification", "recovery"],
            "model_policy": "review-standard",
        },
    ),
}

NOTE_STATES = ("raw", "interpreted", "hypothesis", "proposal", "approved_work", "decision")
NOTE_TRANSITIONS = {
    "raw": {"interpreted"},
    "interpreted": {"hypothesis", "raw"},
    "hypothesis": {"proposal", "interpreted"},
    "proposal": {"approved_work", "hypothesis"},
    "approved_work": {"decision", "proposal"},
    "decision": set(),
}


HOLDINGS_OPERATING_PRINCIPLES = (
    (
        "closed_loop_engineering",
        "Closed-Loop Engineering: 어떤 기능도 Trigger → Action → State transition → Response → Recovery → Completion의 실행 가능한 경로가 검증되기 전에는 완료로 간주하지 않는다.",
    ),
    (
        "no_dead_end_approval",
        "No Dead-End Approval: Founder 판단을 요구하는 상태는 반드시 같은 화면/API에서 실행 가능한 승인·수정·중단 action과 후속 상태 전이를 제공해야 한다.",
    ),
    (
        "reasoning_only_for_uncertainty",
        "Reasoning Only for Uncertainty: 확실한 규칙은 schema/state machine/validator/test로 처리하고, LLM은 불확실성·영향도·새로움이 실제로 높은 문제에만 사용한다.",
    ),
    (
        "compile_organizational_learning",
        "Compile Organizational Learning: 반복해서 발견된 교훈은 Incident → Principle → Policy → deterministic invariant/test로 내려보내 이후 같은 문제에 대한 LLM 호출을 줄인다.",
    ),
    (
        "adaptive_work_routing",
        "Adaptive Work Routing: 모든 Work가 Researcher → Reviewer → Developer를 고정적으로 통과하지 않는다. 작업의 불확실성·영향도·새로움에 따라 필요한 최소 역할만 호출한다.",
    ),
    (
        "implementation_requires_execution",
        "No Implementation Without Execution Evidence: 실제 변경, 최신 변경 이후의 검증 통과, non-empty diff 같은 실행 증거가 없으면 구현 완료로 간주하지 않는다.",
    ),
    (
        "authority_before_global_effect",
        "Authority Before Global Effect: Lab 지식의 전사 승격, 외부 행동, 비용·배포·조직 변경은 필요한 권한이 확인되기 전에는 적용하지 않는다.",
    ),
    (
        "no_silent_overwrite",
        "No Silent Overwrite: 기존 Decision, Work, Memory, Artifact를 조용히 덮어쓰지 않고 supersede/provenance/history를 보존한다.",
    ),
    (
        "no_cold_start_organizational_work",
        "No Cold-Start Organizational Work: 관련 Work를 시작할 때 사람이 과거 채팅을 다시 설명하게 하지 않는다. 같은 Lab의 private knowledge와 Holdings shared knowledge에서 현재 Claim, 결정 근거, 구현 상태와 필요한 bounded history를 자동 Context Pack으로 제공하되 scope와 authority를 보존한다.",
    ),
)


HOLDINGS_EXECUTION_PRINCIPLES = (
    (
        "tool_affordance_matches_work",
        "Tool Affordance Must Match Work: AI 실행 도구는 실제 작업 단위와 맞아야 한다. 큰 기존 파일의 작은 수정에 전체 파일 재작성만 요구하는 식의 도구 계약은 허용하지 않는다.",
    ),
    (
        "measure_real_resource",
        "Measure Real Resource: 실행 예산은 이름이 아니라 실제 소비 단위와 일치해야 한다. model turn, tool call, protocol error, completion rejection을 분리 측정한다.",
    ),
    (
        "converge_before_escalation",
        "Converge Before Escalation: 내부 실행 실패를 Founder에게 넘기기 전에 검색·부분읽기·부분수정·검증 같은 최소 실행 수단이 충분히 제공되어 있는지 먼저 확인한다.",
    ),
)


HOLDINGS_COMPLETION_PRINCIPLES = (
    (
        "completion_requires_proof",
        "Completion Requires Proof: 완료 상태는 AI의 선언이 아니라 해당 Mission 유형이 요구하는 검증 증거로 결정한다. build Mission은 verified Developer execution evidence 없이 completed가 될 수 없다.",
    ),
    (
        "status_must_match_outcome",
        "Status Must Match Outcome: 하위 Work가 incomplete 또는 blocked이면 상위 Request/Mission이 이를 completed로 표현해서는 안 된다.",
    ),
    (
        "recover_invalid_completion",
        "Recover Invalid Completion: 과거 completed 상태라도 필수 증거가 없으면 invalid completion으로 탐지하고 같은 Mission을 복구·재개할 수 있어야 한다.",
    ),
)


HOLDINGS_DELIVERY_PRINCIPLES = (
    (
        "completion_matches_delivery_target",
        "Completion Matches Delivery Target: 완료는 로컬 구현 여부가 아니라 Mission이 명시한 delivery target(local_verified, pr_published, merged, deployed)에 도달했는지로 판정한다.",
    ),
    (
        "local_verified_is_not_shipped",
        "Local Verified Is Not Shipped: 실제 코드 변경·테스트·diff가 있어도 원격 저장소와 production에 반영되지 않았다면 제품 변경 완료로 표현하지 않는다.",
    ),
    (
        "delivery_progress_is_durable",
        "Delivery Progress Is Durable: PR 번호·branch·merge SHA·deployed SHA와 blocker를 Mission별 영속 상태로 기록해 세션이나 Runtime 재기동 뒤에도 배송 단계를 복구한다.",
    ),
    (
        "deployment_requires_commit_reconciliation",
        "Deployment Requires Commit Reconciliation: production 배포 완료는 LLM 주장이나 merge 사실만으로 인정하지 않고 실제 Runtime commit이 merged SHA와 일치할 때 확정한다.",
    ),
)


HOLDINGS_CONCURRENCY_PRINCIPLES = (
    (
        "query_must_be_side_effect_free",
        "Query Must Be Side-Effect Free: 조회·polling·상태 표시 경로는 durable state를 생성·수정·flush하지 않는다. 상태 변경은 명시적 command, event, startup reconciliation에서만 수행한다.",
    ),
    (
        "polling_must_not_compete_with_execution",
        "Polling Must Not Compete With Execution: 진행 상태 polling은 장기 실행 Work와 DB write lock을 경쟁하지 않아야 하며, read path 실패가 실행 중복·복구 오판을 만들면 안 된다.",
    ),
    (
        "reconciliation_is_explicit",
        "Reconciliation Is Explicit: 과거 상태 보정이나 배포 상태 승격은 GET의 부수효과가 아니라 명시적 reconciliation 단계에서 수행하고 감사 가능한 이벤트를 남긴다.",
    ),
    (
        "core_policy_is_non_evictable",
        "Core Policy Is Non-Evictable: 전사 운영 원칙과 현재 source-of-truth 인덱스는 일반 기억의 recency/길이 제한에 밀려 Mission context에서 사라지면 안 된다.",
    ),
)


HOLDINGS_ACTIONABILITY_PRINCIPLES = (
    (
        "blocker_must_be_actionable",
        "Blocker Must Be Actionable: blocker를 노출할 때는 코드명만 보여주지 않고 원인, 해결 주체, 실행 가능한 다음 행동, 앱 내부 해결 가능 여부를 함께 제공한다.",
    ),
    (
        "external_setup_is_not_founder_decision",
        "External Setup Is Not a Founder Decision: 자격증명·외부 서비스 설정처럼 앱 안에서 실행할 수 없는 조건은 가짜 승인 요청으로 만들지 않고 명시적 setup blocker로 표현한다.",
    ),
)


HOLDINGS_SELF_IMPROVEMENT_PRINCIPLES = (
    (
        "observe_friction_before_founder",
        "Observe Friction Before Founder: 반복 실행 실패, 상태 무결성 복구, 완료 거부 같은 운영 마찰을 Founder 지적을 기다리지 않고 Runtime Event에서 자동 Incident로 축적한다.",
    ),
    (
        "repeat_before_improvement_proposal",
        "Repeat Before Improvement Proposal: 일반 운영 실패는 동일 fingerprint가 반복될 때만 개선 Proposal로 승격하고, 단일 우발 실패마다 조직 전체 Work를 생성하지 않는다.",
    ),
    (
        "propose_improvement_do_not_auto_apply",
        "Propose Improvement, Do Not Auto-Apply: Runtime은 반복 Incident를 HQ 개선 Proposal로 올릴 수 있지만 전사 변경을 자동 적용하지 않는다.",
    ),
    (
        "measure_founder_intervention",
        "Measure Founder Intervention: Founder action과 revision이 발생한 Mission 비율을 운영 지표로 측정해 수동 개입 의존도가 실제로 감소하는지 추적한다.",
    ),
)


HOLDINGS_MODEL_ECONOMY_PRINCIPLES = (
    (
        "cheap_first_execution",
        "Cheap-First Execution: 동일 성공 기준을 만족할 수 있다면 deterministic code → free/cheap model → premium model 순서로 실행하고, 고가 모델을 기본 노동력으로 사용하지 않는다.",
    ),
    (
        "data_policy_before_price",
        "Data Policy Before Price: 무료·저가 Provider 사용 여부는 가격보다 데이터 등급(public/internal/confidential) 정책을 먼저 만족해야 한다. 민감 정보는 허용되지 않은 외부 tier로 보내지 않는다.",
    ),
    (
        "mission_cost_is_bounded",
        "Mission Cost Is Bounded: Mission마다 영속 비용 예산을 두고 실제 provider usage를 누적한다. 예산 소진 후 Founder 승인 없이 자동으로 한도를 늘리거나 유료 호출을 계속하지 않는다.",
    ),
    (
        "premium_requires_escalation_reason",
        "Premium Requires Escalation Reason: premium model 사용은 작업 난이도·위험·불확실성 또는 저가 경로 실패 같은 명시적 사유가 있을 때만 허용한다.",
    ),
)


HOLDINGS_ESCALATION_PRINCIPLES = (
    (
        "fallback_before_founder",
        "Fallback Before Founder: Provider quota·rate limit·일시 장애처럼 Runtime이 다른 허용 Provider로 해결할 수 있는 실패는 Founder에게 에스컬레이션하기 전에 자동 fallback한다.",
    ),
    (
        "premium_escalation_requires_evidence",
        "Premium Escalation Requires Evidence: 상위 비용 모델 승격은 저가 경로의 Provider 실패 또는 deterministic quality gate 거부 같은 실행 증거를 남겨야 한다.",
    ),
    (
        "fallback_cannot_bypass_policy",
        "Fallback Cannot Bypass Policy: fallback과 품질 승격은 Mission 비용 한도·데이터 등급·위험/복잡도 정책을 우회할 수 없다.",
    ),
    (
        "model_route_is_auditable",
        "Model Route Is Auditable: 실제 선택된 모델뿐 아니라 실패·품질 거부·cooldown·최종 수락 경로를 trace로 기록해 비용과 품질 승격 이유를 검증할 수 있어야 한다.",
    ),
)


HOLDINGS_RUNTIME_OWNERSHIP_PRINCIPLES = (
    (
        "shared_os_single_writer",
        "Shared OS Single Writer: 모든 Lab은 Runtime 개선을 제안할 수 있지만 canonical shared OS repository의 직접 구현 책임은 Runtime Engineering Lab 하나에 둔다.",
    ),
    (
        "requirements_flow_to_runtime",
        "Requirements Flow to Runtime: Domain Lab은 문제·Evidence·Claim·Proposal을 올리고, HQ 권한 검토를 거쳐 Runtime Engineering이 구현한다. 제안 권한과 shared OS write ownership은 분리한다.",
    ),
    (
        "implementation_state_from_delivery",
        "Implementation State From Delivery: 문서의 개발완료 표시는 AI 선언이 아니라 Mission/PR/CI/deployment 및 KnowledgeActionBinding 증거에서 projection한다.",
    ),
)


HOLDINGS_BACKGROUND_EXECUTION_PRINCIPLES = (
    (
        "control_plane_is_not_execution_lifetime",
        "Control Plane Is Not Execution Lifetime: Founder의 모바일 HTTP 연결 수명과 Mission 실행 수명을 분리한다. 실행 요청은 durable Job으로 저장하고 Cloud worker가 독립적으로 수행한다.",
    ),
    (
        "background_work_is_leased_and_recoverable",
        "Background Work Is Leased and Recoverable: background Job은 worker lease와 heartbeat를 사용하며, 프로세스 종료 후 lease가 만료되면 다른 worker가 같은 durable Job을 회수할 수 있어야 한다.",
    ),
    (
        "background_execution_is_idempotent_at_boundary",
        "Background Execution Is Idempotent at Boundary: 동일 Mission의 queued/running Job을 중복 생성하지 않고, sync 실행과 background 실행이 동시에 같은 Mission을 소유하지 못하게 한다.",
    ),
    (
        "checkpoint_before_disconnect",
        "Checkpoint Before Disconnect: Mission/Work/Artifact/Request 상태는 각 단계에서 durable DB에 기록되어 Founder가 앱을 닫거나 네트워크를 잃어도 완료·중단·복구 판단이 가능해야 한다.",
    ),
)

class OrganizationInvalid(ValueError):
    pass


class OrganizationNotFound(LookupError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_lab_state(db: Session, key: str, spec: dict[str, str]) -> Lab:
    state_key = f"organization_lab:{key}"
    state = db.get(RuntimeState, state_key)
    lab = db.get(Lab, state.value) if state else None
    if lab is None:
        lab = create_lab(
            db,
            title=spec["title"],
            objective=spec["objective"],
            status="active",
            created_by="system",
        )
        if state is None:
            state = RuntimeState(key=state_key, value=lab.id)
            db.add(state)
        else:
            state.value = lab.id
        db.commit()

    existing = {seat.seat_key for seat in list_seats(db, lab.id)}
    seats = (*COMMON_SEATS, *LAB_EXTRA_SEATS.get(key, ()))
    for seat in seats:
        if seat["seat_key"] not in existing:
            register_seat(db, lab_id=lab.id, **seat)
    return lab


def ensure_holdings_operating_principles(db: Session) -> list[OrganizationalMemory]:
    retained: list[OrganizationalMemory] = []
    for key, content in HOLDINGS_OPERATING_PRINCIPLES:
        source_id = f"LLMH-015:{key}"
        existing = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
                OrganizationalMemory.status == "retained",
            )
        )
        if existing is not None:
            retained.append(existing)
            continue
        item = OrganizationalMemory(
            scope_type="holdings",
            scope_id="holdings",
            memory_type="principle",
            content=content,
            status="retained",
            source_type="operating_principle",
            source_id=source_id,
            created_by="founder",
        )
        db.add(item)
        db.flush()
        emit(
            db,
            "HOLDINGS_OPERATING_PRINCIPLE_COMPILED",
            scope_type="holdings",
            scope_id="holdings",
            memory_id=item.id,
            principle_key=key,
            source_id=source_id,
        )
        retained.append(item)
    for key, content in HOLDINGS_EXECUTION_PRINCIPLES:
        source_id = f"LLMH-016:{key}"
        existing = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
                OrganizationalMemory.status == "retained",
            )
        )
        if existing is not None:
            retained.append(existing)
            continue
        item = OrganizationalMemory(
            scope_type="holdings",
            scope_id="holdings",
            memory_type="principle",
            content=content,
            status="retained",
            source_type="operating_principle",
            source_id=source_id,
            created_by="founder",
        )
        db.add(item)
        db.flush()
        emit(
            db,
            "HOLDINGS_OPERATING_PRINCIPLE_COMPILED",
            scope_type="holdings",
            scope_id="holdings",
            memory_id=item.id,
            principle_key=key,
            source_id=source_id,
        )
        retained.append(item)
    for key, content in HOLDINGS_COMPLETION_PRINCIPLES:
        source_id = f"LLMH-017:{key}"
        existing = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
                OrganizationalMemory.status == "retained",
            )
        )
        if existing is not None:
            retained.append(existing)
            continue
        item = OrganizationalMemory(
            scope_type="holdings",
            scope_id="holdings",
            memory_type="principle",
            content=content,
            status="retained",
            source_type="operating_principle",
            source_id=source_id,
            created_by="founder",
        )
        db.add(item)
        db.flush()
        emit(
            db,
            "HOLDINGS_OPERATING_PRINCIPLE_COMPILED",
            scope_type="holdings",
            scope_id="holdings",
            memory_id=item.id,
            principle_key=key,
            source_id=source_id,
        )
        retained.append(item)
    for key, content in HOLDINGS_DELIVERY_PRINCIPLES:
        source_id = f"LLMH-018:{key}"
        existing = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
                OrganizationalMemory.status == "retained",
            )
        )
        if existing is not None:
            retained.append(existing)
            continue
        item = OrganizationalMemory(
            scope_type="holdings",
            scope_id="holdings",
            memory_type="principle",
            content=content,
            status="retained",
            source_type="operating_principle",
            source_id=source_id,
            created_by="founder",
        )
        db.add(item)
        db.flush()
        emit(
            db,
            "HOLDINGS_OPERATING_PRINCIPLE_COMPILED",
            scope_type="holdings",
            scope_id="holdings",
            memory_id=item.id,
            principle_key=key,
            source_id=source_id,
        )
        retained.append(item)
    for key, content in HOLDINGS_CONCURRENCY_PRINCIPLES:
        source_id = f"LLMH-019:{key}"
        existing = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
                OrganizationalMemory.status == "retained",
            )
        )
        if existing is not None:
            retained.append(existing)
            continue
        item = OrganizationalMemory(
            scope_type="holdings",
            scope_id="holdings",
            memory_type="principle",
            content=content,
            status="retained",
            source_type="operating_principle",
            source_id=source_id,
            created_by="founder",
        )
        db.add(item)
        db.flush()
        emit(
            db,
            "HOLDINGS_OPERATING_PRINCIPLE_COMPILED",
            scope_type="holdings",
            scope_id="holdings",
            memory_id=item.id,
            principle_key=key,
            source_id=source_id,
        )
        retained.append(item)
    for key, content in HOLDINGS_ACTIONABILITY_PRINCIPLES:
        source_id = f"LLMH-020:{key}"
        existing = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
                OrganizationalMemory.status == "retained",
            )
        )
        if existing is not None:
            retained.append(existing)
            continue
        item = OrganizationalMemory(
            scope_type="holdings",
            scope_id="holdings",
            memory_type="principle",
            content=content,
            status="retained",
            source_type="operating_principle",
            source_id=source_id,
            created_by="founder",
        )
        db.add(item)
        db.flush()
        emit(
            db,
            "HOLDINGS_OPERATING_PRINCIPLE_COMPILED",
            scope_type="holdings",
            scope_id="holdings",
            memory_id=item.id,
            principle_key=key,
            source_id=source_id,
        )
        retained.append(item)
    for key, content in HOLDINGS_SELF_IMPROVEMENT_PRINCIPLES:
        source_id = f"LLMH-021:{key}"
        existing = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
                OrganizationalMemory.status == "retained",
            )
        )
        if existing is not None:
            retained.append(existing)
            continue
        item = OrganizationalMemory(
            scope_type="holdings",
            scope_id="holdings",
            memory_type="principle",
            content=content,
            status="retained",
            source_type="operating_principle",
            source_id=source_id,
            created_by="founder",
        )
        db.add(item)
        db.flush()
        emit(
            db,
            "HOLDINGS_OPERATING_PRINCIPLE_COMPILED",
            scope_type="holdings",
            scope_id="holdings",
            memory_id=item.id,
            principle_key=key,
            source_id=source_id,
        )
        retained.append(item)
    for key, content in HOLDINGS_MODEL_ECONOMY_PRINCIPLES:
        source_id = f"LLMH-022:{key}"
        existing = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
                OrganizationalMemory.status == "retained",
            )
        )
        if existing is not None:
            retained.append(existing)
            continue
        item = OrganizationalMemory(
            scope_type="holdings",
            scope_id="holdings",
            memory_type="principle",
            content=content,
            status="retained",
            source_type="operating_principle",
            source_id=source_id,
            created_by="founder",
        )
        db.add(item)
        db.flush()
        emit(
            db,
            "HOLDINGS_OPERATING_PRINCIPLE_COMPILED",
            scope_type="holdings",
            scope_id="holdings",
            memory_id=item.id,
            principle_key=key,
            source_id=source_id,
        )
        retained.append(item)
    for key, content in HOLDINGS_ESCALATION_PRINCIPLES:
        source_id = f"LLMH-023:{key}"
        existing = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
                OrganizationalMemory.status == "retained",
            )
        )
        if existing is not None:
            retained.append(existing)
            continue
        item = OrganizationalMemory(
            scope_type="holdings",
            scope_id="holdings",
            memory_type="principle",
            content=content,
            status="retained",
            source_type="operating_principle",
            source_id=source_id,
            created_by="founder",
        )
        db.add(item)
        db.flush()
        emit(
            db,
            "HOLDINGS_OPERATING_PRINCIPLE_COMPILED",
            scope_type="holdings",
            scope_id="holdings",
            memory_id=item.id,
            principle_key=key,
            source_id=source_id,
        )
        retained.append(item)
    for key, content in HOLDINGS_BACKGROUND_EXECUTION_PRINCIPLES:
        source_id = f"LLMH-024:{key}"
        existing = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
                OrganizationalMemory.status == "retained",
            )
        )
        if existing is not None:
            retained.append(existing)
            continue
        item = OrganizationalMemory(
            scope_type="holdings",
            scope_id="holdings",
            memory_type="principle",
            content=content,
            status="retained",
            source_type="operating_principle",
            source_id=source_id,
            created_by="founder",
        )
        db.add(item)
        db.flush()
        emit(
            db,
            "HOLDINGS_OPERATING_PRINCIPLE_COMPILED",
            scope_type="holdings",
            scope_id="holdings",
            memory_id=item.id,
            principle_key=key,
            source_id=source_id,
        )
        retained.append(item)
    for key, content in HOLDINGS_RUNTIME_OWNERSHIP_PRINCIPLES:
        source_id = f"LLMH-028:{key}"
        existing = db.scalar(
            select(OrganizationalMemory).where(
                OrganizationalMemory.scope_type == "holdings",
                OrganizationalMemory.scope_id == "holdings",
                OrganizationalMemory.source_type == "operating_principle",
                OrganizationalMemory.source_id == source_id,
                OrganizationalMemory.status == "retained",
            )
        )
        if existing is not None:
            retained.append(existing)
            continue
        item = OrganizationalMemory(
            scope_type="holdings",
            scope_id="holdings",
            memory_type="principle",
            content=content,
            status="retained",
            source_type="operating_principle",
            source_id=source_id,
            created_by="founder",
        )
        db.add(item)
        db.flush()
        emit(
            db,
            "HOLDINGS_OPERATING_PRINCIPLE_COMPILED",
            scope_type="holdings",
            scope_id="holdings",
            memory_id=item.id,
            principle_key=key,
            source_id=source_id,
        )
        retained.append(item)
    from .authority import seed_authority
    retained.extend(seed_authority(db))
    db.commit()
    return retained


def ensure_organization(db: Session) -> dict:
    llm = ensure_minimum_lab(db)
    llm_state = db.get(RuntimeState, "organization_lab:llm")
    if llm_state is None:
        db.add(RuntimeState(key="organization_lab:llm", value=llm.id))
        db.commit()
    elif llm_state.value != llm.id:
        llm_state.value = llm.id
        db.commit()

    labs = {"llm": llm}
    for key, spec in LAB_SPECS.items():
        labs[key] = _ensure_lab_state(db, key, spec)
    ensure_holdings_operating_principles(db)
    from .capabilities import seed_capabilities
    seed_capabilities(db)
    db.commit()
    return organization_state(db)


def organization_labs(db: Session) -> dict[str, Lab]:
    result: dict[str, Lab] = {}
    for key in ("hq", "llm", "design", "quantrade", "runtime"):
        state = db.get(RuntimeState, f"organization_lab:{key}")
        if state:
            lab = db.get(Lab, state.value)
            if lab:
                result[key] = lab
    if len(result) < 5:
        ensure_organization(db)
        return organization_labs(db)
    return result


def dispatch_founder_command(
    db: Session,
    *,
    command: str,
    created_by: str = "founder",
) -> dict:
    """Translate one natural-language Founder command into a routed Mission.

    This is the Founder-facing abstraction boundary: the Founder supplies intent,
    while capability metadata selects the Lab and Runtime creates/enqueues the
    internal Mission. No additional LLM call is used for routing.
    """

    command = " ".join((command or "").split())
    if not command:
        raise OrganizationInvalid("Founder command cannot be empty")
    if len(command) > 4000:
        raise OrganizationInvalid("Founder command is too long")

    labs = organization_labs(db)
    from .capabilities import route_knowledge
    from .lab_missions import create_mission
    from .background_execution import enqueue_mission_execution

    matches = route_knowledge(db, query=command, limit=10)
    best_by_lab: dict[str, dict] = {}
    for item in matches:
        current = best_by_lab.get(item["lab_id"])
        if current is None or float(item["score"]) > float(current["score"]):
            best_by_lab[item["lab_id"]] = item

    ranked = sorted(
        best_by_lab.values(),
        key=lambda item: (-float(item["score"]), item["lab_id"]),
    )
    route_reason = "hq_fallback"
    selected_lab = labs["hq"]
    selected_key = "hq"
    selected_match = None

    if ranked:
        top = ranked[0]
        tied = [
            item for item in ranked
            if abs(float(item["score"]) - float(top["score"])) < 1e-9
        ]
        if len(tied) == 1:
            selected_lab = db.get(Lab, top["lab_id"]) or labs["hq"]
            selected_key = lab_key_for_id(db, selected_lab.id) or "hq"
            selected_match = top
            route_reason = "capability_match"

    command_note = FounderNote(
        raw_text=command,
        interpreted_text=(
            f"Founder Command → {selected_lab.title} / "
            f"{route_reason}"
        ),
        state="interpreted",
        proposed_lab_id=selected_lab.id,
        created_by=created_by,
    )
    db.add(command_note)
    db.flush()
    from .knowledge_reconciliation import auto_reconcile_source
    record_result = auto_reconcile_source(
        db,
        source_type="founder_note",
        source_id=command_note.id,
        scope_type="lab",
        scope_id=selected_lab.id,
        created_by="system:founder_command_record_hook",
    )

    mission = create_mission(
        db,
        lab_id=selected_lab.id,
        objective=command,
        constraints=(
            "Founder가 자연어로 내린 지시다. Founder에게 Mission/Work/Artifact 같은 내부 객체를 "
            "선택하게 하지 않는다. 기존 Context Pack과 조직 기억을 먼저 사용하고, A2 이하의 "
            "일상적 실행은 자율적으로 처리한다. 예산·배포·전사 권한 등 A4 판단이 실제로 필요할 "
            "때만 Founder 결재보고를 올린다. 사람용 결과는 한국어 우선으로 작성한다."
        ),
        success_criteria=(
            "지시의 실질적 목적을 달성하거나, 달성할 수 없는 경우 검증된 blocker를 남긴다. "
            "완료·검토·결재 상태는 Founder Action Report로 요약 가능해야 한다."
        ),
        mode="auto",
        max_steps=4,
        created_by=f"founder_command:{command_note.id}",
        authority_level="A2",
    )
    job = enqueue_mission_execution(
        db,
        lab_id=selected_lab.id,
        mission_id=mission.id,
        initial_spec={
            "_origin": "founder_command",
            "request_type": "task",
            "message": command,
            "reason": "Founder natural-language command",
        },
        created_by=created_by,
    )
    emit(
        db,
        "FOUNDER_COMMAND_DISPATCHED",
        command=command,
        lab_id=selected_lab.id,
        lab_key=selected_key,
        mission_id=mission.id,
        job_id=job.id,
        route_reason=route_reason,
        capability_key=(selected_match or {}).get("capability_key"),
        matched_terms=(selected_match or {}).get("matched_terms", []),
        source_note_id=command_note.id,
        reconciliation_id=record_result.get("id"),
        reconciliation_status=record_result.get("status"),
        created_by=created_by,
    )
    db.commit()
    return {
        "command": command,
        "routed_lab_key": selected_key,
        "routed_lab_id": selected_lab.id,
        "routed_lab_title": selected_lab.title,
        "route_reason": route_reason,
        "source_note_id": command_note.id,
        "record_writer": {
            "reconciliation_id": record_result.get("id"),
            "status": record_result.get("status"),
            "canonical_mutated": False,
        },
        "matched_capability": (
            {
                "capability_key": selected_match.get("capability_key"),
                "matched_terms": selected_match.get("matched_terms", []),
                "score": selected_match.get("score"),
            }
            if selected_match is not None
            else None
        ),
        "mission": mission,
        "execution_job": job,
    }


def lab_key_for_id(db: Session, lab_id: str) -> str | None:
    for key, lab in organization_labs(db).items():
        if lab.id == lab_id:
            return key
    return None


def organization_state(db: Session, *, labs: dict[str, Lab] | None = None) -> dict:
    labs = labs or organization_labs(db)
    memory_counts: dict[str, int] = {}
    for key, lab in labs.items():
        memory_counts[key] = int(
            db.scalar(
                select(func.count(OrganizationalMemory.id)).where(
                    OrganizationalMemory.scope_type == "lab",
                    OrganizationalMemory.scope_id == lab.id,
                    OrganizationalMemory.status == "retained",
                )
            )
            or 0
        )
    proposals = list(db.scalars(select(LabProposal).order_by(LabProposal.created_at.desc())).all())
    initiatives = list(db.scalars(select(HoldingsInitiative).order_by(HoldingsInitiative.created_at.desc())).all())
    ledger = list(db.scalars(select(HoldingsWorkLedgerEntry).order_by(HoldingsWorkLedgerEntry.sequence)).all())
    notes = list(db.scalars(select(FounderNote).order_by(FounderNote.created_at.desc()).limit(20)).all())
    inter_lab = list(db.scalars(select(InterLabRequest).order_by(InterLabRequest.created_at.desc()).limit(50)).all())
    from .authority import deferred_inbox, exception_inbox
    from .capabilities import registry_state
    incidents = list_operational_incidents(db, limit=30)
    return {
        "labs": [
            {"key": key, "lab": lab, "memory_count": memory_counts.get(key, 0)}
            for key, lab in labs.items()
        ],
        "proposals": proposals,
        "initiatives": initiatives,
        "ledger": ledger,
        "founder_notes": notes,
        "inter_lab_requests": inter_lab,
        "operational_health": operational_health(db),
        "incidents": incidents,
        "exception_inbox": exception_inbox(db),
        "deferred_inbox": deferred_inbox(db),
        "capability_registry": registry_state(db),
    }


def retain_memory(
    db: Session,
    *,
    scope_type: str,
    scope_id: str,
    content: str,
    memory_type: str = "knowledge",
    source_type: str | None = None,
    source_id: str | None = None,
    created_by: str = "system",
    trust_class: str | None = None,
    origin_actor: str | None = None,
    authority_level: str | None = None,
    provenance: dict | None = None,
    supersedes_id: str | None = None,
    governed_promotion: bool = False,
) -> OrganizationalMemory:
    if scope_type not in {"employee", "lab", "holdings"}:
        raise OrganizationInvalid("Unsupported memory scope")
    if scope_type == "lab":
        require_lab(db, scope_id)
    content = content.strip()
    if not content:
        raise OrganizationInvalid("Memory content cannot be empty")

    from .memory_trust import (
        MemoryTrustError,
        ensure_memory_trust,
        validate_memory_write,
    )
    try:
        resolved_trust, resolved_authority = validate_memory_write(
            db,
            scope_type=scope_type,
            scope_id=scope_id,
            memory_type=memory_type,
            created_by=created_by,
            source_type=source_type,
            trust_class=trust_class,
            supersedes_id=supersedes_id,
            governed_promotion=governed_promotion,
        )
    except MemoryTrustError as exc:
        raise OrganizationInvalid(str(exc)) from exc

    item = OrganizationalMemory(
        scope_type=scope_type,
        scope_id=scope_id,
        memory_type=memory_type,
        content=content,
        source_type=source_type,
        source_id=source_id,
        supersedes_id=supersedes_id,
        created_by=created_by,
    )
    db.add(item)
    db.flush()
    ensure_memory_trust(
        db,
        item,
        origin_actor=origin_actor or created_by,
        source_type=source_type,
        trust_class=resolved_trust,
        authority_level=authority_level or resolved_authority,
        provenance=provenance,
    )
    emit(
        db,
        "ORGANIZATIONAL_MEMORY_RETAINED",
        scope_type=scope_type,
        scope_id=scope_id,
        memory_id=item.id,
        memory_type=memory_type,
        source_type=source_type,
        source_id=source_id,
        trust_class=resolved_trust,
        origin_actor=origin_actor or created_by,
    )
    from .knowledge_reconciliation import auto_reconcile_source
    auto_reconcile_source(
        db,
        source_type="organizational_memory",
        source_id=item.id,
        scope_type=scope_type,
        scope_id=scope_id,
        created_by="system:memory_hook",
    )
    db.commit()
    db.refresh(item)
    return item


def list_memory(db: Session, *, scope_type: str, scope_id: str) -> list[OrganizationalMemory]:
    return list(
        db.scalars(
            select(OrganizationalMemory)
            .where(
                OrganizationalMemory.scope_type == scope_type,
                OrganizationalMemory.scope_id == scope_id,
                OrganizationalMemory.status == "retained",
            )
            .order_by(OrganizationalMemory.created_at, OrganizationalMemory.id)
        ).all()
    )


def promote_memory_to_holdings(
    db: Session,
    *,
    memory_id: str,
    approved_by: str,
) -> OrganizationalMemory:
    if approved_by != "founder":
        raise OrganizationInvalid("Holdings-wide memory promotion requires Founder approval")
    source = db.get(OrganizationalMemory, memory_id)
    if source is None:
        raise OrganizationNotFound(memory_id)
    if source.scope_type == "holdings":
        return source
    from .memory_trust import memory_trust_payload
    source_trust = memory_trust_payload(db, source)
    return retain_memory(
        db,
        scope_type="holdings",
        scope_id="holdings",
        content=source.content,
        memory_type=source.memory_type,
        source_type="governed_promotion",
        source_id=source.id,
        created_by=approved_by,
        trust_class="authoritative_founder",
        origin_actor=approved_by,
        authority_level="A4",
        provenance={
            "promoted_from_memory_id": source.id,
            "source_trust": source_trust,
        },
        governed_promotion=True,
    )


def capture_founder_note(db: Session, *, raw_text: str, created_by: str = "founder") -> FounderNote:
    raw_text = raw_text.strip()
    if not raw_text:
        raise OrganizationInvalid("Founder note cannot be empty")
    note = FounderNote(raw_text=raw_text, created_by=created_by)
    db.add(note)
    db.flush()
    emit(db, "FOUNDER_NOTE_CAPTURED", note_id=note.id, state=note.state)
    from .knowledge_reconciliation import auto_reconcile_source
    auto_reconcile_source(
        db,
        source_type="founder_note",
        source_id=note.id,
        scope_type="holdings",
        scope_id="holdings",
        created_by="system:founder_note_hook",
    )
    db.commit()
    db.refresh(note)
    return note


def advance_founder_note(
    db: Session,
    *,
    note_id: str,
    state: str,
    interpreted_text: str = "",
    proposed_lab_id: str | None = None,
) -> FounderNote:
    note = db.get(FounderNote, note_id)
    if note is None:
        raise OrganizationNotFound(note_id)
    if state not in NOTE_STATES or state not in NOTE_TRANSITIONS.get(note.state, set()):
        raise OrganizationInvalid(f"Invalid note transition: {note.state} -> {state}")
    if proposed_lab_id:
        require_lab(db, proposed_lab_id)
    note.state = state
    if interpreted_text.strip():
        note.interpreted_text = interpreted_text.strip()
    if proposed_lab_id is not None:
        note.proposed_lab_id = proposed_lab_id
    emit(db, "FOUNDER_NOTE_ADVANCED", note_id=note.id, state=state, proposed_lab_id=proposed_lab_id)
    if proposed_lab_id is not None:
        from .knowledge_reconciliation import auto_reconcile_source
        auto_reconcile_source(
            db,
            source_type="founder_note",
            source_id=note.id,
            scope_type="lab",
            scope_id=proposed_lab_id,
            created_by="system:founder_note_scope_hook",
        )
    db.commit()
    db.refresh(note)
    return note


def triage_founder_note(db: Session, *, note_id: str) -> dict:
    note = db.get(FounderNote, note_id)
    if note is None:
        raise OrganizationNotFound(note_id)
    if note.state != "raw":
        raise OrganizationInvalid("Only raw Founder notes can enter HQ triage")

    labs = organization_labs(db)
    from .lab_missions import create_mission, run_mission

    mission = create_mission(
        db,
        lab_id=labs["hq"].id,
        objective=(
            "다음 Founder 원문 메모를 훼손하지 말고 구조화하라. "
            "핵심 의도, 가정, 질문, 관련 Lab, 검증해야 할 점과 다음 행동을 구분하라.\n\n"
            f"FOUNDER RAW NOTE:\n{note.raw_text}"
        ),
        constraints=(
            "원문에 없는 결론을 Founder 결정처럼 확정하지 않는다. "
            "단일 Lab에서 해결할 수 있으면 대상 Lab을 명시하고, 여러 Lab 또는 전사 변경이 필요하면 "
            "LAB_HANDOFF action=propose로 HQ Proposal을 생성한다."
        ),
        success_criteria=(
            "한국어 파운더 브리프와 구조화된 해석을 만들고, 필요한 경우 target Labs가 명시된 Proposal을 남긴다."
        ),
        mode="research",
        max_steps=3,
        created_by=f"founder_note:{note.id}",
    )
    state = run_mission(db, lab_id=labs["hq"].id, mission_id=mission.id)
    artifact = state.get("final_artifact")
    interpreted = ""
    if artifact is not None:
        interpreted = artifact.content.split("LAB_HANDOFF:", 1)[0].strip()[:6000]

    note.state = "interpreted"
    note.interpreted_text = interpreted
    emit(
        db,
        "FOUNDER_NOTE_TRIAGED",
        note_id=note.id,
        mission_id=mission.id,
        mission_status=state["mission"].status,
    )
    db.commit()
    db.refresh(note)
    return organization_state(db)



def submit_proposal(
    db: Session,
    *,
    source_lab_id: str,
    title: str,
    summary: str,
    source_mission_id: str | None = None,
    impact: str = "cross_lab",
    required_labs: list[str] | None = None,
    created_by: str = "agent",
) -> LabProposal:
    require_lab(db, source_lab_id)
    labs = organization_labs(db)
    if source_mission_id:
        mission = db.get(LabMission, source_mission_id)
        if mission is None or mission.lab_id != source_lab_id:
            raise OrganizationInvalid("Proposal mission does not belong to the source Lab")
    required = list(dict.fromkeys(required_labs or []))
    unknown = [key for key in required if key not in labs]
    if unknown:
        raise OrganizationInvalid(f"Unknown target Labs: {', '.join(unknown)}")
    proposal = LabProposal(
        source_lab_id=source_lab_id,
        source_mission_id=source_mission_id,
        title=title.strip(),
        summary=summary.strip(),
        impact=impact,
        required_labs_json=json.dumps(required, ensure_ascii=False),
        created_by=created_by,
    )
    db.add(proposal)
    db.flush()
    request = InterLabRequest(
        proposal_id=proposal.id,
        from_lab_id=source_lab_id,
        to_lab_id=labs["hq"].id,
        request_type="proposal_review",
        message=f"{proposal.title}\n\n{proposal.summary}",
        created_by=created_by,
    )
    db.add(request)
    emit(
        db,
        "LAB_PROPOSAL_SUBMITTED",
        lab_id=source_lab_id,
        proposal_id=proposal.id,
        hq_lab_id=labs["hq"].id,
        required_labs=required,
        impact=impact,
    )
    db.commit()
    db.refresh(proposal)
    return proposal


def route_shared_os_change_to_runtime(
    db: Session,
    *,
    source_mission: LabMission,
    reason: str,
    created_by: str = "runtime:ownership_router",
) -> dict:
    """Deterministically route a shared-OS write request to its single writer.

    This is an ownership handoff, not approval of the eventual code change or
    production delivery. Runtime Engineering still has to execute, verify and
    pass the normal delivery gates.
    """
    labs = organization_labs(db)
    runtime_lab = labs.get("runtime")
    if runtime_lab is None:
        raise OrganizationInvalid("Runtime Engineering Lab is not bootstrapped")
    if source_mission.lab_id == runtime_lab.id:
        return {
            "routed": False,
            "reason": "source mission already belongs to Runtime Engineering",
        }

    proposal = db.scalar(
        select(LabProposal)
        .where(
            LabProposal.source_mission_id == source_mission.id,
            LabProposal.created_by == created_by,
        )
        .order_by(LabProposal.created_at.desc(), LabProposal.id.desc())
    )
    if proposal is None:
        summary = (
            "Shared LLM Holdings OS repository write ownership requires Runtime Engineering.\n\n"
            f"Source Mission: {source_mission.id}\n"
            f"Objective: {source_mission.objective}\n"
            f"Constraints: {source_mission.constraints or 'none'}\n"
            f"Success criteria: {source_mission.success_criteria or 'none'}\n"
            f"Ownership guard: {reason}\n\n"
            "Treat this as a bounded implementation handoff. Preserve the source Mission evidence, "
            "implement only the requested shared-OS change, run verification, and keep normal PR/CI/"
            "delivery approval gates intact."
        )
        proposal = submit_proposal(
            db,
            source_lab_id=source_mission.lab_id,
            source_mission_id=source_mission.id,
            title=f"Runtime Engineering handoff · {source_mission.objective}"[:240],
            summary=summary,
            impact="cross_lab",
            required_labs=["runtime"],
            created_by=created_by,
        )

    initiative = db.scalar(
        select(HoldingsInitiative).where(HoldingsInitiative.proposal_id == proposal.id)
    )
    if initiative is None:
        if proposal.status not in {"submitted", "reviewing"}:
            raise OrganizationInvalid(
                f"Ownership handoff proposal cannot advance from {proposal.status}"
            )
        initiative = approve_proposal(
            db,
            proposal_id=proposal.id,
            reviewed_by="hq:ownership_router",
            priority="high",
        )

    entry = db.scalar(
        select(HoldingsWorkLedgerEntry).where(
            HoldingsWorkLedgerEntry.initiative_id == initiative.id,
            HoldingsWorkLedgerEntry.lab_id == runtime_lab.id,
        )
    )
    if entry is None or not entry.mission_id:
        raise OrganizationInvalid("Runtime Engineering handoff Mission was not created")
    runtime_mission = db.get(LabMission, entry.mission_id)
    if runtime_mission is None:
        raise OrganizationInvalid("Runtime Engineering handoff Mission is missing")

    from .cost_governor import ensure_mission_budget
    ensure_mission_budget(db, runtime_mission)
    db.commit()

    if runtime_mission.status not in {"completed", "cancelled", "superseded"}:
        from .background_execution import enqueue_mission_execution
        enqueue_mission_execution(
            db,
            lab_id=runtime_mission.lab_id,
            mission_id=runtime_mission.id,
            initial_spec={
                "to": "developer",
                "request_type": "task",
                "message": (
                    "This Mission is a deterministic shared-OS ownership handoff. "
                    "Do not repeat broad research. Read the source Mission context already "
                    "embedded in this Mission objective, inspect only the relevant repository "
                    "files, implement the bounded change, run post-edit verification, and "
                    "produce executable evidence. Preserve normal PR/CI/delivery gates."
                ),
                "reason": "HQ ownership router assigned the shared OS change to its canonical writer",
            },
            created_by="hq:ownership_router",
        )

    source_mission.status = "superseded"
    source_mission.updated_at = _now()
    sync_mission_ledger_status(db, source_mission)
    emit(
        db,
        "SHARED_OS_OWNERSHIP_HANDOFF_ROUTED",
        lab_id=source_mission.lab_id,
        mission_id=source_mission.id,
        proposal_id=proposal.id,
        initiative_id=initiative.id,
        runtime_lab_id=runtime_lab.id,
        runtime_mission_id=runtime_mission.id,
        reason=reason,
    )
    db.commit()
    return {
        "routed": True,
        "proposal_id": proposal.id,
        "initiative_id": initiative.id,
        "runtime_mission_id": runtime_mission.id,
        "runtime_lab_id": runtime_lab.id,
    }


def _next_ledger_sequence(db: Session) -> int:
    current = db.scalar(select(func.max(HoldingsWorkLedgerEntry.sequence)))
    return int(current or 0) + 1


def register_mission_in_ledger(
    db: Session,
    *,
    mission: LabMission,
    title: str | None = None,
    priority: str = "normal",
    initiative_id: str | None = None,
    source_type: str = "mission",
    source_id: str | None = None,
) -> HoldingsWorkLedgerEntry:
    existing = db.scalar(
        select(HoldingsWorkLedgerEntry).where(HoldingsWorkLedgerEntry.mission_id == mission.id)
    )
    if existing:
        return existing
    entry = HoldingsWorkLedgerEntry(
        initiative_id=initiative_id,
        lab_id=mission.lab_id,
        mission_id=mission.id,
        title=(title or mission.objective)[:240],
        status="queued" if mission.status == "created" else mission.status,
        priority=priority,
        sequence=_next_ledger_sequence(db),
        source_type=source_type,
        source_id=source_id or mission.id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def sync_mission_ledger_status(db: Session, mission: LabMission) -> None:
    entry = db.scalar(
        select(HoldingsWorkLedgerEntry).where(
            HoldingsWorkLedgerEntry.mission_id == mission.id
        )
    )
    if entry is not None:
        entry.status = mission.status
        entry.updated_at = _now()



def approve_proposal(
    db: Session,
    *,
    proposal_id: str,
    reviewed_by: str = "founder",
    priority: str = "normal",
) -> HoldingsInitiative:
    proposal = db.get(LabProposal, proposal_id)
    if proposal is None:
        raise OrganizationNotFound(proposal_id)
    if proposal.status not in {"submitted", "reviewing"}:
        raise OrganizationInvalid(f"Proposal cannot be approved from {proposal.status}")
    if proposal.impact == "holdings" and reviewed_by != "founder":
        raise OrganizationInvalid("Holdings-wide change requires Founder approval")

    labs = organization_labs(db)
    required_keys = json.loads(proposal.required_labs_json or "[]")
    if not required_keys:
        source_key = lab_key_for_id(db, proposal.source_lab_id)
        required_keys = [source_key] if source_key else []

    initiative = HoldingsInitiative(
        proposal_id=proposal.id,
        title=proposal.title,
        objective=proposal.summary,
        priority=priority,
        status="planned",
        created_by=reviewed_by,
    )
    db.add(initiative)
    db.flush()

    previous_entry_id: str | None = None
    for key in required_keys:
        lab = labs[key]
        mission = LabMission(
            lab_id=lab.id,
            objective=f"[{proposal.title}] {proposal.summary}",
            constraints=(
                "이 작업은 HQ가 승인한 교차 Lab Initiative의 일부다. "
                "다른 Lab의 권한이나 전사 정책을 임의로 변경하지 말고 결과를 Artifact/Proposal로 반환한다."
            ),
            success_criteria="구체적 결과, 영향, 미해결 위험, 다음 handoff를 한국어로 명확히 제시한다.",
            mode="build" if key == "runtime" else "research",
            status="created",
            max_steps=4,
            created_by=f"initiative:{initiative.id}",
        )
        db.add(mission)
        db.flush()
        from .authority import ensure_ownership
        ensure_ownership(db, mission)
        entry = HoldingsWorkLedgerEntry(
            initiative_id=initiative.id,
            lab_id=lab.id,
            mission_id=mission.id,
            title=f"{proposal.title} / {lab.title}",
            status="queued",
            priority=priority,
            sequence=_next_ledger_sequence(db),
            depends_on_json=json.dumps([previous_entry_id] if previous_entry_id else []),
            source_type="proposal",
            source_id=proposal.id,
        )
        db.add(entry)
        db.flush()
        previous_entry_id = entry.id

    proposal.status = "approved"
    proposal.reviewed_by = reviewed_by
    proposal.reviewed_at = _now()
    linked_incident = db.scalar(
        select(OperationalIncident).where(
            OperationalIncident.proposal_id == proposal.id
        )
    )
    if linked_incident is not None:
        linked_incident.status = "accepted"
        linked_incident.updated_at = _now()
    for request in db.scalars(
        select(InterLabRequest).where(
            InterLabRequest.proposal_id == proposal.id,
            InterLabRequest.status == "pending",
        )
    ).all():
        request.status = "resolved"
        request.resolved_at = _now()

    emit(
        db,
        "HOLDINGS_INITIATIVE_CREATED",
        proposal_id=proposal.id,
        initiative_id=initiative.id,
        priority=priority,
        target_labs=required_keys,
        reviewed_by=reviewed_by,
    )
    db.commit()
    db.refresh(initiative)
    return initiative


def run_initiative(db: Session, *, initiative_id: str) -> dict:
    initiative = db.get(HoldingsInitiative, initiative_id)
    if initiative is None:
        raise OrganizationNotFound(initiative_id)
    from .lab_missions import run_mission

    entries = list(
        db.scalars(
            select(HoldingsWorkLedgerEntry)
            .where(HoldingsWorkLedgerEntry.initiative_id == initiative.id)
            .order_by(HoldingsWorkLedgerEntry.sequence)
        ).all()
    )
    initiative.status = "running"
    db.commit()

    for entry in entries:
        if not entry.mission_id or entry.status in {"completed", "cancelled", "superseded"}:
            continue
        dependencies = json.loads(entry.depends_on_json or "[]")
        if dependencies:
            dep_entries = [db.get(HoldingsWorkLedgerEntry, dep_id) for dep_id in dependencies]
            if any(dep is None or dep.status != "completed" for dep in dep_entries):
                entry.status = "blocked"
                db.commit()
                break
        entry.status = "running"
        db.commit()
        state = run_mission(db, lab_id=entry.lab_id, mission_id=entry.mission_id)
        mission_status = state["mission"].status
        entry.status = "completed" if mission_status == "completed" else mission_status
        db.commit()
        if mission_status != "completed":
            initiative.status = "blocked" if mission_status in {"awaiting_founder", "review_required"} else mission_status
            db.commit()
            return organization_state(db)

    initiative.status = "completed"
    if initiative.proposal_id:
        linked_incident = db.scalar(
            select(OperationalIncident).where(
                OperationalIncident.proposal_id == initiative.proposal_id
            )
        )
        if linked_incident is not None:
            linked_incident.status = "resolved"
            linked_incident.updated_at = _now()
    db.commit()
    emit(db, "HOLDINGS_INITIATIVE_COMPLETED", initiative_id=initiative.id)
    db.commit()
    return organization_state(db)
