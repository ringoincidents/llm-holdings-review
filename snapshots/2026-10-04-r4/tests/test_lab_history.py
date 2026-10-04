import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from runtime.db import Base
from runtime.labs import create_lab, link_object, list_lab_history
from runtime.models import Case, Event


def _db():
    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


def test_lab_history_is_bounded_and_excludes_unrelated_events():
    engine = _db()
    with Session(engine, expire_on_commit=False) as db:
        target = create_lab(db, title="Target", objective="Target history")
        other = create_lab(db, title="Other", objective="Other history")

        for index in range(250):
            db.add(
                Event(
                    type="NOISE",
                    payload_json=json.dumps(
                        {"lab_id": other.id, "index": index},
                        ensure_ascii=False,
                    ),
                )
            )
        for index in range(220):
            db.add(
                Event(
                    type="TARGET",
                    payload_json=json.dumps(
                        {"lab_id": target.id, "index": index},
                        ensure_ascii=False,
                    ),
                )
            )
        db.commit()

        history = list_lab_history(db, target.id)

        assert len(history) == 200
        assert all(json.loads(item.payload_json)["lab_id"] == target.id for item in history)
        assert json.loads(history[0].payload_json)["index"] == 20
        assert json.loads(history[-1].payload_json)["index"] == 219
    engine.dispose()


def test_lab_history_includes_owned_case_events_without_payload_lab_id():
    engine = _db()
    with Session(engine, expire_on_commit=False) as db:
        target = create_lab(db, title="Target", objective="Target history")
        case = Case(company="test", title="Scoped case", risk_level="low")
        db.add(case)
        db.commit()
        link_object(
            db,
            lab_id=target.id,
            object_type="case",
            object_id=case.id,
            relationship="contains",
        )
        event = Event(
            case_id=case.id,
            type="CASE_ONLY_EVENT",
            payload_json=json.dumps({"note": "no lab_id"}),
        )
        db.add(event)
        db.commit()

        history = list_lab_history(db, target.id)
        assert event.id in {item.id for item in history}
    engine.dispose()
