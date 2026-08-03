"""PatchPilot FastAPI application and mounted MCP Streamable HTTP server."""

from __future__ import annotations

import contextlib
import os
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.applications import Starlette
from starlette.routing import Mount

from .engine import create_proposal, decide_run
from .fixtures import get_scenario, list_scenarios
from .models import AgentRun, Dashboard, DecisionRequest, RunCreate, RunStatus, Scenario
from .store import RunStore
from .tools import mcp_server


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_VALUE = (
    os.getenv("PATCHPILOT_DATA_DIR", "").strip()
    or os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    or str(BASE_DIR / "data")
)
DATA_DIR = Path(DATA_VALUE)
if not DATA_DIR.is_absolute():
    DATA_DIR = BASE_DIR / DATA_DIR

store = RunStore(DATA_DIR, max_runs=int(os.getenv("PATCHPILOT_MAX_RUNS", "200")))
RATE_LIMIT = int(os.getenv("PATCHPILOT_RATE_LIMIT_PER_MINUTE", "8"))
DAILY_LIMIT = int(os.getenv("PATCHPILOT_DAILY_LIMIT", "50"))
request_windows: dict[str, deque[float]] = defaultdict(deque)
daily_usage: dict[str, tuple[str, int]] = {}

api = FastAPI(
    title="PatchPilot Agent API",
    version="0.1.0",
    description="Approval-gated software-maintenance agent over versioned fixture repositories.",
)
api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"https://[a-zA-Z0-9-]+\.github\.io",
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@api.middleware("http")
async def security_and_rate_limit(request: Request, call_next):
    if request.method == "POST" and request.url.path.startswith("/api/"):
        now = time.monotonic()
        client = request.client.host if request.client else "unknown"
        window = request_windows[client]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= RATE_LIMIT:
            return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后重试。"})
        from datetime import datetime, timezone

        current_day = datetime.now(timezone.utc).date().isoformat()
        stored_day, count = daily_usage.get(client, (current_day, 0))
        if stored_day != current_day:
            count = 0
        if count >= DAILY_LIMIT:
            return JSONResponse(status_code=429, content={"detail": "今日公开演示额度已用完。"})
        window.append(now)
        daily_usage[client] = (current_day, count + 1)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


@api.get("/api/health")
def health() -> dict[str, str | int | bool]:
    return {
        "status": "ok",
        "version": "0.1.0",
        "langgraph": True,
        "mcp_transport": "streamable-http",
        "execution_mode": "fixture-sandbox",
        "store": "sqlite",
        "run_count": store.count(),
    }


@api.get("/api/dashboard", response_model=Dashboard)
def dashboard() -> Dashboard:
    return Dashboard(
        scenario_count=len(list_scenarios()),
        run_count=store.count(),
        completed_count=store.count(RunStatus.COMPLETED),
        awaiting_approval_count=store.count(RunStatus.AWAITING_APPROVAL),
        mcp_endpoint="/mcp/",
        execution_mode="fixture-sandbox",
    )


@api.get("/api/scenarios", response_model=list[Scenario])
def scenarios() -> list[Scenario]:
    return list_scenarios()


@api.get("/api/scenarios/{scenario_key}", response_model=Scenario)
def scenario(scenario_key: str) -> Scenario:
    item = get_scenario(scenario_key)
    if item is None:
        raise HTTPException(status_code=404, detail="未找到该任务")
    return item


@api.post("/api/runs", response_model=AgentRun, status_code=status.HTTP_201_CREATED)
def create_run(payload: RunCreate) -> AgentRun:
    if get_scenario(payload.scenario_key) is None:
        raise HTTPException(status_code=404, detail="未找到该任务")
    try:
        return create_proposal(store, payload.scenario_key, payload.session_id)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@api.get("/api/runs", response_model=list[AgentRun])
def runs(session_id: str | None = None) -> list[AgentRun]:
    return store.list(session_id=session_id)


@api.get("/api/runs/{run_id}", response_model=AgentRun)
def run(run_id: str) -> AgentRun:
    item = store.get(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="未找到运行记录")
    return item


@api.post("/api/runs/{run_id}/decision", response_model=AgentRun)
def decision(run_id: str, payload: DecisionRequest) -> AgentRun:
    item = store.get(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="未找到运行记录")
    try:
        return decide_run(store, item, payload.decision, payload.operator)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


if not FRONTEND_DIR.is_dir():
    raise RuntimeError(f"Frontend directory not found: {FRONTEND_DIR}")
api.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@contextlib.asynccontextmanager
async def lifespan(_app: Starlette):
    async with mcp_server.session_manager.run():
        yield


# MCP is mounted before the main application so /mcp is not captured by the
# static-site fallback. The server is stateless and suitable for one Railway
# service instance; the task store remains SQLite for this public demo.
app = Starlette(
    routes=[
        Mount("/mcp", app=mcp_server.streamable_http_app()),
        Mount("/", app=api),
    ],
    lifespan=lifespan,
)
