from fastapi.testclient import TestClient

import app.main as main_module
from app.store import RunStore


def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(main_module, "store", RunStore())
    return TestClient(main_module.app)


def test_health_and_scenarios(monkeypatch):
    test_client = client(monkeypatch)
    assert test_client.get("/api/health").json()["execution_mode"] == "versioned-fixture"
    scenarios = test_client.get("/api/scenarios").json()
    assert len(scenarios) == 2
    assert {item["mode"] for item in scenarios} == {"read-only", "write"}


def test_read_only_agent_loop_completes(monkeypatch):
    test_client = client(monkeypatch)
    response = test_client.post("/api/runs", json={"scenario_key": "trace-auth-flow"})
    assert response.status_code == 201
    run = response.json()
    assert run["status"] == "completed"
    assert run["tool_calls"] == 3
    assert "require_user" in run["final_answer"]


def test_write_task_requires_permission(monkeypatch):
    test_client = client(monkeypatch)
    run = test_client.post("/api/runs", json={"scenario_key": "fix-negative-quantity"}).json()
    assert run["status"] == "awaiting-approval"
    assert run["trace"][-1]["name"] == "Permission Gate"
    assert run["trace"][-1]["status"] == "pending"

    completed = test_client.post(
        f"/api/runs/{run['run_id']}/decision",
        json={"decision": "approve"},
    )
    assert completed.status_code == 200
    payload = completed.json()
    assert payload["status"] == "completed"
    assert payload["trace"][-2]["name"] == "Pytest"
    assert "回归测试通过" in payload["final_answer"]


def test_rejection_never_calls_edit_or_pytest(monkeypatch):
    test_client = client(monkeypatch)
    run = test_client.post("/api/runs", json={"scenario_key": "fix-negative-quantity"}).json()
    rejected = test_client.post(
        f"/api/runs/{run['run_id']}/decision",
        json={"decision": "reject"},
    ).json()
    assert rejected["status"] == "rejected"
    names = [event["name"] for event in rejected["trace"]]
    assert "EditFile" not in names
    assert "Pytest" not in names


def test_unknown_scenario_is_rejected(monkeypatch):
    response = client(monkeypatch).post("/api/runs", json={"scenario_key": "unknown"})
    assert response.status_code == 404
