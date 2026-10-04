from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from .events import emit
from .lab_seats import AISeatNotFound, require_seat
from .labs import LabNotFound, require_lab
from .models import (
    Artifact,
    Decision,
    Evidence,
    LabContextDelivery,
    LabContextRef,
    LabContextSnapshot,
    LabObjectLink,
)

RUNTIME_CONTEXT_MODELS = {
    "decision": Decision,
    "evidence": Evidence,
    "artifact": Artifact,
}
EXTERNAL_CONTEXT_TYPES = {"file", "repository_state"}
ALL_CONTEXT_TYPES = frozenset(RUNTIME_CONTEXT_MODELS) | EXTERNAL_CONTEXT_TYPES


class LabContextInvalid(ValueError):
    pass


class LabContextRefNotFound(LookupError):
    pass


class LabContextSnapshotNotFound(LookupError):
    pass


def _require_identifiable_source(value: str | None) -> str:
    source = (value or "").strip()
    if ":" not in source:
        raise LabContextInvalid(
            "External Lab context requires an independently identifiable source URI"
        )
    return source


def add_context_ref(
    db: Session,
    *,
    lab_id: str,
    context_type: str,
    ref: str,
    label: str,
    source_uri: str | None = None,
    priority: int = 0,
    metadata: dict | None = None,
    created_by: str = "founder",
) -> LabContextRef:
    require_lab(db, lab_id)
    if context_type not in ALL_CONTEXT_TYPES:
        raise LabContextInvalid(f"Unsupported context type: {context_type}")

    normalized_ref = ref.strip()
    if not normalized_ref:
        raise LabContextInvalid("Context ref cannot be empty")

    if context_type in RUNTIME_CONTEXT_MODELS:
        model = RUNTIME_CONTEXT_MODELS[context_type]
        obj = db.get(model, normalized_ref)
        if obj is None:
            raise LabContextInvalid(f"Runtime context object not found: {context_type}:{normalized_ref}")
        linked = db.scalar(
            select(LabObjectLink).where(
                LabObjectLink.lab_id == lab_id,
                LabObjectLink.object_type == context_type,
                LabObjectLink.object_id == normalized_ref,
            )
        )
        if linked is None:
            raise LabContextInvalid(
                "Runtime context object must belong to the Lab before it can enter Shared Context"
            )
    else:
        source_uri = _require_identifiable_source(source_uri)

    existing = db.scalar(
        select(LabContextRef).where(
            LabContextRef.lab_id == lab_id,
            LabContextRef.context_type == context_type,
            LabContextRef.ref == normalized_ref,
        )
    )
    if existing:
        return existing

    item = LabContextRef(
        lab_id=lab_id,
        context_type=context_type,
        ref=normalized_ref,
        label=label.strip(),
        source_uri=source_uri,
        priority=priority,
        metadata_json=json.dumps(metadata or {}, sort_keys=True, ensure_ascii=False),
        created_by=created_by,
    )
    db.add(item)
    db.flush()
    emit(
        db,
        "LAB_CONTEXT_REF_ADDED",
        lab_id=lab_id,
        context_ref_id=item.id,
        context_type=item.context_type,
        ref=item.ref,
        priority=item.priority,
    )
    db.commit()
    db.refresh(item)
    return item


def list_context_refs(db: Session, lab_id: str) -> list[LabContextRef]:
    require_lab(db, lab_id)
    return list(
        db.scalars(
            select(LabContextRef)
            .where(LabContextRef.lab_id == lab_id)
            .order_by(
                LabContextRef.priority.desc(),
                LabContextRef.context_type,
                LabContextRef.ref,
                LabContextRef.id,
            )
        ).all()
    )


def _runtime_payload(db: Session, item: LabContextRef) -> dict:
    if item.context_type == "decision":
        obj = db.get(Decision, item.ref)
        return {
            "id": obj.id,
            "question": obj.question,
            "prediction": obj.prediction,
            "confidence": obj.confidence,
            "provider": obj.provider,
        }
    if item.context_type == "evidence":
        obj = db.get(Evidence, item.ref)
        return {
            "id": obj.id,
            "source": obj.source,
            "content": obj.content,
            "supports": obj.supports,
        }
    if item.context_type == "artifact":
        obj = db.get(Artifact, item.ref)
        return {
            "id": obj.id,
            "kind": obj.kind,
            "content": obj.content,
            "producer_type": obj.producer_type,
            "producer_id": obj.producer_id,
        }
    raise LabContextInvalid(f"Not a runtime context ref: {item.context_type}")


def _entry_payload(db: Session, item: LabContextRef) -> dict:
    payload = {
        "context_ref_id": item.id,
        "type": item.context_type,
        "ref": item.ref,
        "label": item.label,
        "source_uri": item.source_uri,
        "priority": item.priority,
        "metadata": json.loads(item.metadata_json or "{}"),
    }
    if item.context_type in RUNTIME_CONTEXT_MODELS:
        payload["value"] = _runtime_payload(db, item)
    return payload


def context_entries(db: Session, *, lab_id: str) -> list[dict]:
    """Read the Lab's manually retained Shared Context without creating a snapshot."""
    return [_entry_payload(db, item) for item in list_context_refs(db, lab_id)]


def assemble_context(
    db: Session,
    *,
    lab_id: str,
    created_by: str = "founder",
) -> LabContextSnapshot:
    lab = require_lab(db, lab_id)
    refs = list_context_refs(db, lab_id)
    context = {
        "schema_version": "lab-context-v1",
        "lab": {
            "id": lab.id,
            "title": lab.title,
            "objective": lab.objective,
            "status": lab.status,
        },
        "entries": context_entries(db, lab_id=lab_id),
    }
    canonical = json.dumps(
        context,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    existing = db.scalar(
        select(LabContextSnapshot).where(
            LabContextSnapshot.lab_id == lab_id,
            LabContextSnapshot.content_hash == digest,
        )
    )
    if existing:
        return existing

    snapshot = LabContextSnapshot(
        lab_id=lab_id,
        content_hash=digest,
        context_json=canonical,
        created_by=created_by,
    )
    db.add(snapshot)
    db.flush()
    emit(
        db,
        "LAB_CONTEXT_SNAPSHOT_CREATED",
        lab_id=lab_id,
        snapshot_id=snapshot.id,
        content_hash=digest,
        entry_count=len(refs),
    )
    db.commit()
    db.refresh(snapshot)
    return snapshot


def require_snapshot(
    db: Session,
    *,
    lab_id: str,
    snapshot_id: str,
) -> LabContextSnapshot:
    require_lab(db, lab_id)
    snapshot = db.get(LabContextSnapshot, snapshot_id)
    if snapshot is None or snapshot.lab_id != lab_id:
        raise LabContextSnapshotNotFound(snapshot_id)
    return snapshot


def deliver_context(
    db: Session,
    *,
    lab_id: str,
    snapshot_id: str,
    seat_id: str,
) -> LabContextDelivery:
    snapshot = require_snapshot(db, lab_id=lab_id, snapshot_id=snapshot_id)
    try:
        require_seat(db, lab_id, seat_id)
    except AISeatNotFound:
        raise

    existing = db.scalar(
        select(LabContextDelivery).where(
            LabContextDelivery.snapshot_id == snapshot.id,
            LabContextDelivery.seat_id == seat_id,
        )
    )
    if existing:
        return existing

    delivery = LabContextDelivery(
        lab_id=lab_id,
        snapshot_id=snapshot.id,
        seat_id=seat_id,
    )
    db.add(delivery)
    db.flush()
    emit(
        db,
        "LAB_CONTEXT_DELIVERED",
        lab_id=lab_id,
        snapshot_id=snapshot.id,
        seat_id=seat_id,
        delivery_id=delivery.id,
    )
    db.commit()
    db.refresh(delivery)
    return delivery


def list_deliveries(
    db: Session,
    *,
    lab_id: str,
    snapshot_id: str | None = None,
) -> list[LabContextDelivery]:
    require_lab(db, lab_id)
    query = select(LabContextDelivery).where(LabContextDelivery.lab_id == lab_id)
    if snapshot_id:
        query = query.where(LabContextDelivery.snapshot_id == snapshot_id)
    return list(db.scalars(query.order_by(LabContextDelivery.delivered_at)).all())
