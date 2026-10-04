from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .events import emit
from .labs import LabNotFound, require_lab
from .models import AISeat, LabObjectLink, LabWork, LabWorkAssignment


class AISeatNotFound(LookupError):
    pass


class AISeatAlreadyExists(ValueError):
    pass


class LabWorkNotLinked(LookupError):
    pass


def register_seat(
    db: Session,
    *,
    lab_id: str,
    seat_key: str,
    name: str,
    role: str,
    capabilities: list[str],
    model_policy: str,
    status: str = "ready",
) -> AISeat:
    require_lab(db, lab_id)

    existing = db.scalar(
        select(AISeat).where(
            AISeat.lab_id == lab_id,
            AISeat.seat_key == seat_key,
        )
    )
    if existing:
        raise AISeatAlreadyExists(seat_key)

    seat = AISeat(
        lab_id=lab_id,
        seat_key=seat_key,
        name=name,
        role=role,
        capabilities_json=json.dumps(capabilities, ensure_ascii=False),
        model_policy=model_policy,
        status=status,
    )
    db.add(seat)
    db.flush()
    emit(
        db,
        "LAB_SEAT_REGISTERED",
        lab_id=lab_id,
        seat_id=seat.id,
        seat_key=seat.seat_key,
        role=seat.role,
        model_policy=seat.model_policy,
    )
    db.commit()
    db.refresh(seat)
    return seat


def list_seats(db: Session, lab_id: str) -> list[AISeat]:
    require_lab(db, lab_id)
    return list(
        db.scalars(
            select(AISeat)
            .where(AISeat.lab_id == lab_id)
            .order_by(AISeat.created_at)
        ).all()
    )


def require_seat(db: Session, lab_id: str, seat_id: str) -> AISeat:
    require_lab(db, lab_id)
    seat = db.get(AISeat, seat_id)
    if seat is None or seat.lab_id != lab_id:
        raise AISeatNotFound(seat_id)
    return seat


def assign_work(
    db: Session,
    *,
    lab_id: str,
    object_type: str,
    object_id: str,
    seat_id: str,
    assigned_by: str = "founder",
) -> LabWorkAssignment:
    seat = require_seat(db, lab_id, seat_id)

    if object_type == "work":
        work = db.get(LabWork, object_id)
        if work is None or work.lab_id != lab_id:
            raise LabWorkNotLinked(f"work:{object_id}")
    else:
        link = db.scalar(
            select(LabObjectLink).where(
                LabObjectLink.lab_id == lab_id,
                LabObjectLink.object_type == object_type,
                LabObjectLink.object_id == object_id,
            )
        )
        if link is None:
            raise LabWorkNotLinked(f"{object_type}:{object_id}")

    assignment = db.scalar(
        select(LabWorkAssignment).where(
            LabWorkAssignment.lab_id == lab_id,
            LabWorkAssignment.object_type == object_type,
            LabWorkAssignment.object_id == object_id,
        )
    )
    if assignment is None:
        assignment = LabWorkAssignment(
            lab_id=lab_id,
            seat_id=seat.id,
            object_type=object_type,
            object_id=object_id,
            assigned_by=assigned_by,
        )
        db.add(assignment)
    else:
        assignment.seat_id = seat.id
        assignment.assigned_by = assigned_by

    db.flush()
    emit(
        db,
        "LAB_WORK_ASSIGNED",
        lab_id=lab_id,
        assignment_id=assignment.id,
        seat_id=seat.id,
        object_type=object_type,
        object_id=object_id,
        assigned_by=assigned_by,
    )
    db.commit()
    db.refresh(assignment)
    return assignment


def list_assignments(db: Session, lab_id: str) -> list[LabWorkAssignment]:
    require_lab(db, lab_id)
    return list(
        db.scalars(
            select(LabWorkAssignment)
            .where(LabWorkAssignment.lab_id == lab_id)
            .order_by(LabWorkAssignment.assigned_at)
        ).all()
    )
