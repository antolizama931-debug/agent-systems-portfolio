"""Allowlisted repository tools, also exposed through an actual MCP endpoint."""

from __future__ import annotations

import difflib
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .fixtures import get_scenario, list_scenarios


BASE_DIR = Path(__file__).resolve().parent.parent
FIXTURE_DIR = BASE_DIR / "fixtures"

mcp_server = FastMCP(
    "PatchPilotTools",
    instructions=(
        "Read and validate only PatchPilot's versioned fixture repositories. "
        "No arbitrary paths, URLs, commands, or user-supplied code are accepted."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)


def _scenario_or_raise(scenario_key: str):
    scenario = get_scenario(scenario_key)
    if scenario is None:
        raise ValueError("unknown fixture scenario")
    return scenario


def _fixture_path(scenario_key: str) -> Path:
    scenario = _scenario_or_raise(scenario_key)
    path = (FIXTURE_DIR / scenario.repository.removeprefix("fixture/")).resolve()
    if FIXTURE_DIR.resolve() not in path.parents or not path.is_dir():
        raise ValueError("fixture repository is unavailable")
    return path


@mcp_server.resource("patchpilot://scenarios")
def scenario_catalog() -> str:
    """Return the public, non-executable task catalog."""
    return "\n".join(f"{item.key}: {item.issue}" for item in list_scenarios())


@mcp_server.tool()
def repo_list_files(scenario_key: str) -> list[str]:
    """List files in an allowlisted fixture repository."""
    root = _fixture_path(scenario_key)
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    )


@mcp_server.tool()
def repo_read_file(scenario_key: str, relative_path: str) -> str:
    """Read one text file from an allowlisted fixture repository."""
    root = _fixture_path(scenario_key)
    target = (root / relative_path).resolve()
    if root not in target.parents or not target.is_file():
        raise ValueError("file is outside the fixture repository")
    if target.stat().st_size > 50_000:
        raise ValueError("file exceeds the public demo limit")
    return target.read_text(encoding="utf-8")


@mcp_server.tool()
def patch_preview(scenario_key: str) -> str:
    """Generate the approved fixture's minimal unified diff without mutating files."""
    scenario = _scenario_or_raise(scenario_key)
    original = repo_read_file(scenario_key, scenario.target_file)
    if original.count(scenario.before) != 1:
        raise ValueError("patch precondition is not satisfied exactly once")
    updated = original.replace(scenario.before, scenario.after, 1)
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{scenario.target_file}",
            tofile=f"b/{scenario.target_file}",
        )
    )


def execute_approved_patch(scenario_key: str) -> tuple[str, dict[str, object]]:
    """Apply and test a fixed patch in an ephemeral copy of a trusted fixture.

    This function is intentionally not exposed as an MCP tool. The public HTTP
    API can call it only after recording a human approval decision.
    """
    scenario = _scenario_or_raise(scenario_key)
    source = _fixture_path(scenario_key)
    with tempfile.TemporaryDirectory(prefix="patchpilot-") as temporary:
        workspace = Path(temporary) / "repo"
        shutil.copytree(source, workspace)
        target = workspace / scenario.target_file
        original = target.read_text(encoding="utf-8")
        if original.count(scenario.before) != 1:
            raise RuntimeError("patch precondition failed")
        updated = original.replace(scenario.before, scenario.after, 1)
        target.write_text(updated, encoding="utf-8")
        diff = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=f"a/{scenario.target_file}",
                tofile=f"b/{scenario.target_file}",
            )
        )

        started = time.perf_counter()
        command = [sys.executable, "-m", "pytest", "-q"]
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
            # The fixture suites use only built-in pytest behavior. Disabling
            # third-party plugin autoload keeps the subprocess deterministic
            # and prevents unrelated host plugins from entering the sandbox.
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }
        try:
            completed = subprocess.run(
                command,
                cwd=workspace,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                env=environment,
                check=False,
            )
            output = (completed.stdout + "\n" + completed.stderr).strip()[-4000:]
            exit_code = completed.returncode
        except subprocess.TimeoutExpired:
            output = "测试超过 10 秒限制，执行已终止。"
            exit_code = 124
        duration_ms = round((time.perf_counter() - started) * 1000)
        result = {
            "passed": exit_code == 0,
            "command": ["python", "-m", "pytest", "-q"],
            "exit_code": exit_code,
            "duration_ms": duration_ms,
            "output": output,
        }
        return diff, result
