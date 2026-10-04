from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .events import emit
from .models import (
    Approval,
    Artifact,
    Case,
    Decision,
    Evidence,
    Event,
    ExecutionRun,
    Lab,
    LabObjectLink,
    Task,
)

OBJECT_MODELS = {
    "case": Case,
    "task": Task,
    "decision": Decision,
    "execution_run": ExecutionRun,
    "artifact": Artifact,
    "evidence": Evidence,
    "approval": Approval,
}


class LabNotFound(LookupError):
    pass


class LabObjectNotFound(LookupError):
    pass


class LabObjectAlreadyLinked(ValueError):
    pass


class LabObjectScopeViolation(ValueError):
    pass


def create_lab(
    db: Session,
    *,
    title: str,
    objective: str,
    status: str = "active",
    created_by: str = "founder",
) -> Lab:
    lab = Lab(
        title=title,
        objective=objective,
        status=status,
        created_by=created_by,
    )
    db.add(lab)
    db.flush()
    emit(
        db,
        "LAB_CREATED",
        lab_id=lab.id,
        title=lab.title,
        created_by=lab.created_by,
    )
    db.commit()
    db.refresh(lab)
    return lab


def list_labs(db: Session) -> list[Lab]:
    return list(db.scalars(select(Lab).order_by(Lab.created_at.desc())).all())


def require_lab(db: Session, lab_id: str) -> Lab:
    lab = db.get(Lab, lab_id)
    if not lab:
        raise LabNotFound(lab_id)
    return lab


def _require_runtime_object(db: Session, object_type: str, object_id: str):
    model = OBJECT_MODELS.get(object_type)
    if model is None:
        raise LabObjectNotFound(f"Unsupported Runtime object type: {object_type}")
    obj = db.get(model, object_id)
    if obj is None:
        raise LabObjectNotFound(f"{object_type}:{object_id}")
    return obj


def link_object(
    db: Session,
    *,
    lab_id: str,
    object_type: str,
    object_id: str,
    relationship: str = "contains",
) -> LabObjectLink:
    require_lab(db, lab_id)
    obj = _require_runtime_object(db, object_type, object_id)

    existing = db.scalar(
        select(LabObjectLink).where(
            LabObjectLink.lab_id == lab_id,
            LabObjectLink.object_type == object_type,
            LabObjectLink.object_id == object_id,
        )
    )
    if existing:
        raise LabObjectAlreadyLinked(f"{object_type}:{object_id}")

    if relationship == "contains":
        foreign_contains = db.scalar(
            select(LabObjectLink).where(
                LabObjectLink.object_type == object_type,
                LabObjectLink.object_id == object_id,
                LabObjectLink.relationship == "contains",
                LabObjectLink.lab_id != lab_id,
            )
        )
        if foreign_contains is not None:
            raise LabObjectScopeViolation(
                f"{object_type}:{object_id} is already contained by another Lab"
            )

        linked_case_id = obj.id if object_type == "case" else getattr(obj, "case_id", None)
        if linked_case_id:
            foreign_case = db.scalar(
                select(LabObjectLink).where(
                    LabObjectLink.object_type == "case",
                    LabObjectLink.object_id == linked_case_id,
                    LabObjectLink.relationship == "contains",
                    LabObjectLink.lab_id != lab_id,
                )
            )
            if foreign_case is not None:
                raise LabObjectScopeViolation(
                    f"{object_type}:{object_id} belongs to a Case contained by another Lab"
                )

    link = LabObjectLink(
        lab_id=lab_id,
        object_type=object_type,
        object_id=object_id,
        relationship=relationship,
    )
    db.add(link)
    db.flush()

    linked_case_id = obj.id if object_type == "case" else getattr(obj, "case_id", None)
    emit(
        db,
        "LAB_OBJECT_LINKED",
        linked_case_id,
        lab_id=lab_id,
        link_id=link.id,
        object_type=object_type,
        object_id=object_id,
        relationship=relationship,
    )
    db.commit()
    db.refresh(link)
    return link


def list_links(db: Session, lab_id: str) -> list[LabObjectLink]:
    require_lab(db, lab_id)
    return list(
        db.scalars(
            select(LabObjectLink)
            .where(LabObjectLink.lab_id == lab_id)
            .order_by(LabObjectLink.created_at)
        ).all()
    )


def linked_cases(db: Session, lab_id: str) -> list[Case]:
    require_lab(db, lab_id)
    links = list(
        db.scalars(
            select(LabObjectLink)
            .where(
                LabObjectLink.lab_id == lab_id,
                LabObjectLink.object_type == "case",
            )
            .order_by(LabObjectLink.created_at)
        ).all()
    )
    if not links:
        return []

    visible_links: list[LabObjectLink] = []
    for link in links:
        if link.relationship == "contains":
            visible_links.append(link)
            continue
        foreign_owner = db.scalar(
            select(LabObjectLink).where(
                LabObjectLink.object_type == "case",
                LabObjectLink.object_id == link.object_id,
                LabObjectLink.relationship == "contains",
                LabObjectLink.lab_id != lab_id,
            )
        )
        if foreign_owner is None:
            visible_links.append(link)

    if not visible_links:
        return []

    by_id = {
        case.id: case
        for case in db.scalars(
            select(Case).where(Case.id.in_([link.object_id for link in visible_links]))
        ).all()
    }
    return [
        by_id[link.object_id]
        for link in visible_links
        if link.object_id in by_id
    ]



def list_lab_history(db: Session, lab_id: str) -> list[Event]:
    require_lab(db, lab_id)
    case_ids = {case.id for case in linked_cases(db, lab_id)}

    history: list[Event] = []
    for event in db.scalars(select(Event).order_by(Event.id)).all():
        payload = {}
        try:
            payload = json.loads(event.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        if payload.get("lab_id") == lab_id or (
            event.case_id is not None and event.case_id in case_ids
        ):
            history.append(event)
    return history
