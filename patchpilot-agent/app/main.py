"""MewCode browser-safe showcase API."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .engine import create_run, decide_run
from .fixtures import get_scenario, list_scenarios
from .models import AgentRun, Dashboard, DecisionRequest, RunCreate, RunStatus, Scenario
from .store import RunStore


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
store = RunStore(max_runs=int(os.getenv("MEWCODE_MAX_RUNS", "200")))
RATE_LIMIT = int(os.getenv("MEWCODE_RATE_LIMIT_PER_MINUTE", "12"))
request_windows: dict[str, deque[float]] = defaultdict(deque)

app = FastAPI(
    title="MewCode Showcase API",
    version="1.0.0",
    description="Browser-safe projection of MewCode's bounded Agent Loop.",
)


@app.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    if request.method == "POST" and request.url.path.startswith("/api/"):
        now = time.monotonic()
        client = request.client.host if request.client else "unknown"
        window = request_windows[client]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= RATE_LIMIT:
            return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后重试。"})
        window.append(now)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@app.get("/api/health")
def health() -> dict[str, str | int]:
    return {"status": "ok", "version": "1.0.0", "execution_mode": "versioned-fixture", "run_count": store.count()}


@app.get("/api/dashboard", response_model=Dashboard)
def dashboard() -> Dashboard:
    return Dashboard(
        scenario_count=len(list_scenarios()),
        run_count=store.count(),
        completed_count=store.count(RunStatus.COMPLETED),
        tool_count=6,
        execution_mode="versioned-fixture",
    )


@app.get("/api/scenarios", response_model=list[Scenario])
def scenarios() -> list[Scenario]:
    return list_scenarios()


@app.post("/api/runs", response_model=AgentRun, status_code=status.HTTP_201_CREATED)
def start_run(payload: RunCreate) -> AgentRun:
    if get_scenario(payload.scenario_key) is None:
        raise HTTPException(status_code=404, detail="未找到该演示任务")
    return create_run(store, payload.scenario_key)


@app.get("/api/runs/{run_id}", response_model=AgentRun)
def get_run(run_id: str) -> AgentRun:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="未找到运行记录")
    return run


@app.post("/api/runs/{run_id}/decision", response_model=AgentRun)
def decision(run_id: str, payload: DecisionRequest) -> AgentRun:
    run = store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="未找到运行记录")
    try:
        return decide_run(store, run, payload.decision)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


if not FRONTEND_DIR.is_dir():
    raise RuntimeError(f"Frontend directory not found: {FRONTEND_DIR}")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
