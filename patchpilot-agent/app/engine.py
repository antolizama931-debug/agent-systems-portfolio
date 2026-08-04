"""Deterministic, sandboxed Agent Loop used by the online showcase.

The production CLI can call model providers and local tools. The public demo
uses fixed model decisions and versioned in-memory files so visitors can inspect
the same model -> tool -> observation loop without receiving code-execution
authority on the Railway container.
"""

from __future__ import annotations

import uuid

from .fixtures import FILES, get_scenario
from .models import AgentRun, RunStatus, TraceEvent
from .store import RunStore


def _event(
    run: AgentRun,
    kind: str,
    name: str,
    summary: str,
    *,
    status: str = "succeeded",
    input: dict | None = None,
    output: str | None = None,
    duration_ms: int = 0,
) -> None:
    run.trace.append(
        TraceEvent(
            sequence=len(run.trace) + 1,
            kind=kind,
            name=name,
            status=status,
            summary=summary,
            input=input,
            output=output,
            duration_ms=duration_ms,
        )
    )


def create_run(store: RunStore, scenario_key: str) -> AgentRun:
    scenario = get_scenario(scenario_key)
    if scenario is None:
        raise ValueError("unknown scenario")

    run = AgentRun(
        run_id=f"run_{uuid.uuid4().hex[:10]}",
        scenario_key=scenario.key,
        status=RunStatus.COMPLETED,
        prompt=scenario.prompt,
        trace=[],
        context_tokens=318,
    )
    _event(run, "system", "Context", "载入系统提示、工具 Schema 与任务 Fixture。", output="318 tokens")
    _event(run, "model", "Agent", "先定位与任务相关的文件。", output="tool_call: Grep")

    files = FILES[scenario.fixture]
    if scenario.key == "trace-auth-flow":
        _event(run, "tool", "Grep", "搜索 profile 与鉴权符号。", input={"pattern": "profile|require_user"}, output="src/api.py:3, src/api.py:4, src/auth.py:1", duration_ms=3)
        _event(run, "model", "Agent", "读取接口入口和鉴权实现。", output="tool_call: ReadFile x2")
        _event(run, "tool", "ReadFile", "读取 src/api.py。", input={"path": "src/api.py"}, output=files["src/api.py"], duration_ms=1)
        _event(run, "tool", "ReadFile", "读取 src/auth.py。", input={"path": "src/auth.py"}, output=files["src/auth.py"], duration_ms=1)
        run.tool_calls = 3
        run.context_tokens = 612
        run.final_answer = "profile() 从 Authorization 请求头取值并调用 require_user()；请求头缺失时，require_user() 直接抛出 PermissionError，因此业务处理不会继续执行。"
        _event(run, "model", "Agent", "依据真实文件内容给出调用链结论。", output=run.final_answer)
    else:
        _event(run, "tool", "Grep", "定位 checkout 定义与失败测试。", input={"pattern": "checkout|negative"}, output="src/checkout.py:1, tests/test_checkout.py:3", duration_ms=2)
        _event(run, "tool", "ReadFile", "读取目标实现。", input={"path": "src/checkout.py"}, output=files["src/checkout.py"], duration_ms=1)
        _event(run, "model", "Agent", "生成最小修改，请求写权限。", output="tool_call: EditFile")
        _event(run, "gate", "Permission Gate", "EditFile 属于写操作，等待人工批准。", status="pending", input={"path": "src/checkout.py"})
        run.status = RunStatus.AWAITING_APPROVAL
        run.tool_calls = 2
        run.context_tokens = 544

    return store.save(run)


def decide_run(store: RunStore, run: AgentRun, decision: str) -> AgentRun:
    if run.status != RunStatus.AWAITING_APPROVAL:
        raise RuntimeError("run is not awaiting approval")

    gate = run.trace[-1]
    if decision == "reject":
        gate.status = "rejected"
        gate.summary = "用户拒绝写入；文件保持不变。"
        run.status = RunStatus.REJECTED
        run.final_answer = "写操作已取消，未修改 Fixture，也未执行测试。"
        _event(run, "model", "Agent", "遵循权限决定并停止。", output=run.final_answer)
        return store.save(run)

    gate.status = "succeeded"
    gate.summary = "用户批准仅修改 Fixture 中的 src/checkout.py。"
    patch = "@@\n def checkout(quantity: int, unit_price: float) -> float:\n+    if quantity < 0:\n+        raise ValueError(\"quantity must be non-negative\")\n     return quantity * unit_price"
    _event(run, "tool", "EditFile", "应用单文件最小修改。", input={"path": "src/checkout.py"}, output=patch, duration_ms=2)
    _event(run, "model", "Agent", "修改完成，运行固定测试。", output="tool_call: Pytest")
    _event(run, "tool", "Pytest", "在隔离 Fixture 中执行允许列表测试。", input={"target": "tests/test_checkout.py"}, output="1 passed in 0.04s", duration_ms=41)
    run.status = RunStatus.COMPLETED
    run.tool_calls = 4
    run.context_tokens = 781
    run.final_answer = "已在 checkout() 入口拒绝负数数量；固定回归测试通过。公开演示未执行用户命令或访问外部仓库。"
    _event(run, "model", "Agent", "根据补丁与测试结果结束循环。", output=run.final_answer)
    return store.save(run)
