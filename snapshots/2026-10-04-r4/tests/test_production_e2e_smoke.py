from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tools.production_e2e_smoke import (
    ProductionE2ESmokeError,
    _knowledge_view,
    _normalized_run_id,
    main,
    run_startup_smoke_if_enabled,
)


def test_smoke_run_id_is_bounded_and_safe():
    assert _normalized_run_id("  prod smoke / 2026-10-03  ") == "prod-smoke-2026-10-03"
    assert len(_normalized_run_id("x" * 200)) == 72


def test_smoke_is_disabled_without_explicit_run_id(monkeypatch, capsys):
    monkeypatch.delenv("LLM_HOLDINGS_E2E_SMOKE_RUN_ID", raising=False)

    assert main() == 0

    line = capsys.readouterr().out.strip()
    assert line.startswith("PRODUCTION_E2E_SMOKE ")
    payload = json.loads(line.split(" ", 1)[1])
    assert payload["status"] == "disabled"


def test_knowledge_view_requires_v2_pack_and_finds_target_concept():
    snapshot = SimpleNamespace(
        context_json=json.dumps(
            {
                "schema_version": "lab-context-v2-knowledge-pack",
                "knowledge": {
                    "concepts": [
                        {
                            "concept": {"key": "e2e-memory-smoke-run-1"},
                            "current_claims": [{"content": "SMOKE_V2"}],
                            "bounded_history": [
                                {
                                    "content": "SMOKE_V1",
                                    "effective_status": "superseded",
                                }
                            ],
                        }
                    ]
                },
            }
        )
    )

    view = _knowledge_view(snapshot, "e2e-memory-smoke-run-1")

    assert view["current_claims"][0]["content"] == "SMOKE_V2"
    assert view["bounded_history"][0]["effective_status"] == "superseded"


def test_knowledge_view_fails_closed_on_old_schema():
    snapshot = SimpleNamespace(
        context_json=json.dumps(
            {
                "schema_version": "lab-context-v1",
                "knowledge": {"concepts": []},
            }
        )
    )

    with pytest.raises(ProductionE2ESmokeError, match="Unexpected context schema"):
        _knowledge_view(snapshot, "missing")



def test_current_claim_may_reference_historical_marker_without_being_stale():
    snapshot = SimpleNamespace(
        context_json=json.dumps(
            {
                "schema_version": "lab-context-v2-knowledge-pack",
                "knowledge": {
                    "concepts": [
                        {
                            "concept": {"key": "e2e-memory-smoke-run-2"},
                            "current_claims": [
                                {
                                    "id": "V2",
                                    "content": "SMOKE_V2 is current; SMOKE_V1 is superseded history.",
                                    "effective_status": "current",
                                }
                            ],
                            "bounded_history": [
                                {
                                    "id": "V1",
                                    "content": "SMOKE_V1",
                                    "effective_status": "superseded",
                                }
                            ],
                        }
                    ]
                },
            }
        )
    )

    view = _knowledge_view(snapshot, "e2e-memory-smoke-run-2")
    current_ids = {str(item.get("id") or "") for item in view["current_claims"]}
    history_ids = {str(item.get("id") or "") for item in view["bounded_history"]}

    assert current_ids == {"V2"}
    assert history_ids == {"V1"}
    assert "SMOKE_V1" in view["current_claims"][0]["content"]



def test_startup_smoke_hook_is_inert_without_run_id(monkeypatch):
    monkeypatch.delenv("LLM_HOLDINGS_E2E_SMOKE_RUN_ID", raising=False)

    assert run_startup_smoke_if_enabled() is None


def test_startup_smoke_hook_runs_and_returns_result(monkeypatch):
    monkeypatch.setenv("LLM_HOLDINGS_E2E_SMOKE_RUN_ID", "hook-run")

    class FakeSession:
        def close(self):
            pass

        def rollback(self):
            pass

    monkeypatch.setattr(
        "tools.production_e2e_smoke.SessionLocal",
        lambda: FakeSession(),
    )
    monkeypatch.setattr(
        "tools.production_e2e_smoke.run_production_e2e_smoke",
        lambda db, run_id: {"status": "passed", "run_id": run_id},
    )

    assert run_startup_smoke_if_enabled() == {
        "status": "passed",
        "run_id": "hook-run",
    }


def test_startup_smoke_hook_fails_closed(monkeypatch):
    monkeypatch.setenv("LLM_HOLDINGS_E2E_SMOKE_RUN_ID", "hook-fail")

    class FakeSession:
        def close(self):
            pass

        def rollback(self):
            pass

    def fail(db, run_id):
        raise ProductionE2ESmokeError("expected smoke failure")

    monkeypatch.setattr(
        "tools.production_e2e_smoke.SessionLocal",
        lambda: FakeSession(),
    )
    monkeypatch.setattr(
        "tools.production_e2e_smoke.run_production_e2e_smoke",
        fail,
    )

    with pytest.raises(ProductionE2ESmokeError, match="expected smoke failure"):
        run_startup_smoke_if_enabled()
