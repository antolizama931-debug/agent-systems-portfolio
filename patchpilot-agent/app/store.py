"""Small bounded in-memory store for public demo runs."""

from __future__ import annotations

from collections import OrderedDict

from .models import AgentRun, RunStatus


class RunStore:
    def __init__(self, max_runs: int = 200) -> None:
        self.max_runs = max_runs
        self._runs: OrderedDict[str, AgentRun] = OrderedDict()

    def save(self, run: AgentRun) -> AgentRun:
        self._runs[run.run_id] = run
        self._runs.move_to_end(run.run_id)
        while len(self._runs) > self.max_runs:
            self._runs.popitem(last=False)
        return run

    def get(self, run_id: str) -> AgentRun | None:
        return self._runs.get(run_id)

    def count(self, status: RunStatus | None = None) -> int:
        if status is None:
            return len(self._runs)
        return sum(run.status == status for run in self._runs.values())
