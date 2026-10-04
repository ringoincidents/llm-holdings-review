import httpx

from runtime.runtime_ops import runtime_ops_snapshot


def test_runtime_ops_projects_deployed_main_and_ci(monkeypatch):
    monkeypatch.setenv("LLM_HOLDINGS_DEV_REPO", "ringoincidents/llm-holdings-runtime")
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc123")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")
    monkeypatch.setenv("RAILWAY_SERVICE_NAME", "llm-holdings-runtime")
    monkeypatch.setenv("RAILWAY_PROJECT_NAME", "capable-charm")
    monkeypatch.setenv("RAILWAY_DEPLOYMENT_ID", "dep-1")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "abc123"})
        if request.url.path.endswith("/commits/abc123/check-runs"):
            return httpx.Response(
                200,
                json={
                    "check_runs": [
                        {"name": "backend", "status": "completed", "conclusion": "success"},
                        {"name": "mobile", "status": "completed", "conclusion": "success"},
                    ]
                },
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = runtime_ops_snapshot(client=client)

    assert snapshot["schema"] == "runtime_ops_v0.1"
    assert snapshot["runtime"]["ok"] is True
    assert snapshot["runtime"]["environment"] == "production"
    assert snapshot["runtime"]["service"] == "llm-holdings-runtime"
    assert snapshot["runtime"]["deployed_sha"] == "abc123"
    assert snapshot["repository"]["main_sha"] == "abc123"
    assert snapshot["repository"]["deployment_matches_main"] is True
    assert snapshot["repository"]["ci"]["status"] == "success"
    assert snapshot["repository"]["ci"]["check_count"] == 2
    assert snapshot["repository"]["error"] is None


def test_runtime_ops_marks_pending_ci_and_commit_drift(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "deployed")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/commits/main"):
            return httpx.Response(200, json={"sha": "main-new"})
        if request.url.path.endswith("/commits/main-new/check-runs"):
            return httpx.Response(
                200,
                json={
                    "check_runs": [
                        {"name": "backend", "status": "completed", "conclusion": "success"},
                        {"name": "mobile", "status": "in_progress", "conclusion": None},
                    ]
                },
            )
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = runtime_ops_snapshot(client=client)

    assert snapshot["repository"]["deployment_matches_main"] is False
    assert snapshot["repository"]["ci"]["status"] == "pending"


def test_runtime_ops_fails_open_for_observability(monkeypatch):
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"message": "unavailable"})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        snapshot = runtime_ops_snapshot(client=client)

    assert snapshot["runtime"]["ok"] is True
    assert snapshot["repository"]["github_status"] == "unavailable"
    assert snapshot["repository"]["main_sha"] is None
    assert snapshot["repository"]["ci"]["status"] == "unavailable"
    assert snapshot["repository"]["deployment_matches_main"] is None
    assert snapshot["repository"]["error"]
