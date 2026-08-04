"""Typed contracts for the browser-safe MewCode demonstration."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    COMPLETED = "completed"
    AWAITING_APPROVAL = "awaiting-approval"
    REJECTED = "rejected"


class Scenario(BaseModel):
    key: str
    title: str
    mode: Literal["read-only", "write"]
    prompt: str
    fixture: str
    goal: str
    expected_tools: list[str]


class RunCreate(BaseModel):
    scenario_key: str = Field(min_length=1, max_length=80)


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]


class TraceEvent(BaseModel):
    sequence: int
    kind: Literal["model", "tool", "gate", "system"]
    name: str
    status: Literal["succeeded", "pending", "rejected"]
    summary: str
    input: dict[str, Any] | None = None
    output: str | None = None
    duration_ms: int = 0


class AgentRun(BaseModel):
    run_id: str
    scenario_key: str
    status: RunStatus
    prompt: str
    trace: list[TraceEvent]
    final_answer: str | None = None
    context_tokens: int = 0
    tool_calls: int = 0
    permission_mode: str = "default"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Dashboard(BaseModel):
    scenario_count: int
    run_count: int
    completed_count: int
    tool_count: int
    execution_mode: str
