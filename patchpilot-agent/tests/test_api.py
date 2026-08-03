from pathlib import Path

from fastapi.testclient import TestClient

import app.main as main_module
from app.store import RunStore


def client(tmp_path: Path, monkeypatch) -> TestClient:
    temporary_store = RunStore(tmp_path)
    monkeypatch.setattr(main_module, "store", temporary_store)
    # API behavior is tested independently from the process-scoped MCP session
    # manager, whose official SDK lifecycle can only be entered once.
    return TestClient(main_module.api)


def test_health_and_scenarios(tmp_path, monkeypatch):
    test_client = client(tmp_path, monkeypatch)
    health = test_client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["mcp_transport"] == "streamable-http"
    scenarios = test_client.get("/api/scenarios")
    assert scenarios.status_code == 200
    assert len(scenarios.json()) == 2


def test_approval_gated_execution(tmp_path, monkeypatch):
    test_client = client(tmp_path, monkeypatch)
    created = test_client.post(
        "/api/runs",
        json={"scenario_key": "python-slug-separators", "session_id": "test"},
    )
    assert created.status_code == 201
    run = created.json()
    assert run["status"] == "awaiting-approval"
    assert run["test_result"] is None
    assert "slug.py" in run["proposed_diff"]

    completed = test_client.post(
        f"/api/runs/{run['run_id']}/decision",
        json={"decision": "approve", "operator": "pytest-reviewer"},
    )
    assert completed.status_code == 200
    payload = completed.json()
    assert payload["status"] == "completed"
    assert payload["test_result"]["passed"] is True
    assert payload["review"]["approved"] is True


def test_rejection_never_executes_tests(tmp_path, monkeypatch):
    test_client = client(tmp_path, monkeypatch)
    created = test_client.post("/api/runs", json={"scenario_key": "python-average-empty"}).json()
    rejected = test_client.post(
        f"/api/runs/{created['run_id']}/decision",
        json={"decision": "reject", "operator": "pytest-reviewer"},
    )
    assert rejected.status_code == 200
    payload = rejected.json()
    assert payload["status"] == "rejected"
    assert payload["test_result"] is None


def test_duplicate_decision_is_rejected(tmp_path, monkeypatch):
    test_client = client(tmp_path, monkeypatch)
    created = test_client.post("/api/runs", json={"scenario_key": "python-average-empty"}).json()
    test_client.post(
        f"/api/runs/{created['run_id']}/decision",
        json={"decision": "reject", "operator": "pytest-reviewer"},
    )
    duplicate = test_client.post(
        f"/api/runs/{created['run_id']}/decision",
        json={"decision": "approve", "operator": "pytest-reviewer"},
    )
    assert duplicate.status_code == 409
