"""Typed contracts for PatchPilot's approval-gated maintenance workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field, StringConstraints


NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class RunStatus(str, Enum):
    ANALYZING = "analyzing"
    AWAITING_APPROVAL = "awaiting-approval"
    PATCHING = "patching"
    TESTING = "testing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class Scenario(BaseModel):
    key: str
    title: str
    repository: str
    language: str
    issue: str
    risk: str
    target_file: str
    before: str
    after: str
    test_command: list[str]
    acceptance: list[str]


class RunCreate(BaseModel):
    scenario_key: NonEmpty
    session_id: str = Field(default="public-demo", min_length=1, max_length=120)


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    operator: str = Field(default="public-reviewer", min_length=2, max_length=120)


class TraceEvent(BaseModel):
    sequence: int = Field(ge=1)
    stage: str
    actor: str
    status: str
    message: str
    duration_ms: int = Field(default=0, ge=0)
    tool: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TestResult(BaseModel):
    passed: bool
    command: list[str]
    exit_code: int
    duration_ms: int
    output: str


class ReviewResult(BaseModel):
    approved: bool
    findings: list[str]
    summary: str


class AgentRun(BaseModel):
    run_id: str
    scenario_key: str
    session_id: str
    status: RunStatus
    issue: str
    repository: str
    language: str
    plan: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)
    proposed_diff: str | None = None
    applied_diff: str | None = None
    trace: list[TraceEvent] = Field(default_factory=list)
    test_result: TestResult | None = None
    review: ReviewResult | None = None
    approval: dict[str, Any] | None = None
    execution_mode: str = "fixture-sandbox"
    limitations: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Dashboard(BaseModel):
    scenario_count: int
    run_count: int
    completed_count: int
    awaiting_approval_count: int
    mcp_endpoint: str
    execution_mode: str

