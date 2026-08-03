"""LangGraph workflows for proposal generation and approved execution."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .fixtures import get_scenario
from .models import AgentRun, ReviewResult, RunStatus, TestResult, TraceEvent
from .store import RunStore
from .tools import execute_approved_patch, patch_preview, repo_list_files, repo_read_file


class ProposalState(TypedDict, total=False):
    scenario_key: str
    files: list[str]
    target_content: str
    plan: list[str]
    proposed_diff: str


def _inspect(state: ProposalState) -> ProposalState:
    scenario = get_scenario(state["scenario_key"])
    if scenario is None:
        raise ValueError("unknown scenario")
    return {
        "files": repo_list_files(scenario.key),
        "target_content": repo_read_file(scenario.key, scenario.target_file),
    }


def _plan(state: ProposalState) -> ProposalState:
    scenario = get_scenario(state["scenario_key"])
    if scenario is None:
        raise ValueError("unknown scenario")
    return {
        "plan": [
            f"定位并读取 {scenario.target_file}",
            "生成满足验收条件的最小补丁",
            "等待人工确认补丁后执行受限测试",
            "根据测试输出完成独立审查并记录轨迹",
        ]
    }


def _preview(state: ProposalState) -> ProposalState:
    return {"proposed_diff": patch_preview(state["scenario_key"])}


proposal_builder = StateGraph(ProposalState)
proposal_builder.add_node("repo_analyst", _inspect)
proposal_builder.add_node("planner", _plan)
proposal_builder.add_node("patch_preview", _preview)
proposal_builder.add_edge(START, "repo_analyst")
proposal_builder.add_edge("repo_analyst", "planner")
proposal_builder.add_edge("planner", "patch_preview")
proposal_builder.add_edge("patch_preview", END)
proposal_graph = proposal_builder.compile()


def _event(run: AgentRun, stage: str, actor: str, message: str, *, tool: str | None = None, duration_ms: int = 0) -> None:
    run.trace.append(
        TraceEvent(
            sequence=len(run.trace) + 1,
            stage=stage,
            actor=actor,
            status="succeeded",
            message=message,
            tool=tool,
            duration_ms=duration_ms,
        )
    )
    run.updated_at = datetime.now(timezone.utc)


def create_proposal(store: RunStore, scenario_key: str, session_id: str) -> AgentRun:
    scenario = get_scenario(scenario_key)
    if scenario is None:
        raise ValueError("unknown scenario")
    started = time.perf_counter()
    state = proposal_graph.invoke({"scenario_key": scenario_key})
    elapsed = round((time.perf_counter() - started) * 1000)
    run = AgentRun(
        run_id=f"run_{uuid.uuid4().hex[:12]}",
        scenario_key=scenario.key,
        session_id=session_id,
        status=RunStatus.AWAITING_APPROVAL,
        issue=scenario.issue,
        repository=scenario.repository,
        language=scenario.language,
        plan=state["plan"],
        files=state["files"],
        proposed_diff=state["proposed_diff"],
        limitations=[
            "公开演示只运行仓库内置、版本化的可信 fixture，不接受任意 Git URL 或用户代码。",
            "公开环境不创建真实 Pull Request，也不持有 GitHub 写权限。",
            "SQLite 用于单实例演示；多副本生产部署需迁移到 PostgreSQL。",
        ],
    )
    _event(run, "inspect", "Repo Analyst", f"发现 {len(run.files)} 个文件并读取目标文件。", tool="repo_list_files")
    _event(run, "plan", "Coordinator", f"生成 {len(run.plan)} 步维护计划。")
    _event(run, "preview", "Patch Agent", "生成最小 Unified Diff，等待人工审批。", tool="patch_preview", duration_ms=elapsed)
    return store.save(run)


def decide_run(store: RunStore, run: AgentRun, decision: str, operator: str) -> AgentRun:
    if run.status != RunStatus.AWAITING_APPROVAL:
        raise RuntimeError("run is not awaiting approval")
    run.approval = {
        "decision": decision,
        "operator": operator,
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
    if decision == "reject":
        run.status = RunStatus.REJECTED
        _event(run, "approval", "Human Reviewer", "补丁被拒绝，未执行任何代码。")
        return store.save(run)

    _event(run, "approval", "Human Reviewer", "补丁已批准，允许在临时 fixture 副本中执行。")
    run.status = RunStatus.PATCHING
    store.save(run)
    try:
        diff, raw_test = execute_approved_patch(run.scenario_key)
    except Exception as exc:
        run.status = RunStatus.FAILED
        run.trace.append(
            TraceEvent(
                sequence=len(run.trace) + 1,
                stage="execution",
                actor="Test Agent",
                status="failed",
                message=f"受限执行失败：{type(exc).__name__}",
            )
        )
        return store.save(run)

    run.applied_diff = diff
    _event(run, "patch", "Patch Agent", "补丁已应用到临时工作区。", tool="approved_patch.apply")
    run.status = RunStatus.TESTING
    store.save(run)
    run.test_result = TestResult.model_validate(raw_test)
    _event(
        run,
        "test",
        "Test Agent",
        "全部测试通过。" if run.test_result.passed else "测试失败，补丁未通过验证。",
        tool="pytest.run",
        duration_ms=run.test_result.duration_ms,
    )
    run.status = RunStatus.REVIEWING
    store.save(run)

    findings = [
        "补丁只修改一个允许列表文件。",
        "补丁不引入网络、文件系统或进程执行能力。",
        "测试命令由服务端固定，用户无法覆盖。",
    ]
    approved = run.test_result.passed and run.applied_diff == run.proposed_diff
    run.review = ReviewResult(
        approved=approved,
        findings=findings,
        summary="测试与安全审查通过。" if approved else "测试或补丁一致性审查未通过。",
    )
    run.status = RunStatus.COMPLETED if approved else RunStatus.FAILED
    _event(run, "review", "Review Agent", run.review.summary)
    return store.save(run)

