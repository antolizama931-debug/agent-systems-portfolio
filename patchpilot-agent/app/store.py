"""Small SQLite event store for replayable public demo runs."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from .models import AgentRun, RunStatus


class RunStore:
    def __init__(self, data_dir: Path, max_runs: int = 200):
        data_dir.mkdir(parents=True, exist_ok=True)
        self.path = data_dir / "patchpilot.db"
        self.max_runs = max_runs
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_runs_updated ON runs(updated_at DESC)")

    def save(self, run: AgentRun) -> AgentRun:
        with self._lock, self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs(run_id, session_id, status, updated_at, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status,
                    updated_at=excluded.updated_at,
                    payload=excluded.payload
                """,
                (
                    run.run_id,
                    run.session_id,
                    run.status.value,
                    run.updated_at.isoformat(),
                    run.model_dump_json(),
                ),
            )
            connection.execute(
                """
                DELETE FROM runs WHERE run_id IN (
                    SELECT run_id FROM runs ORDER BY updated_at DESC LIMIT -1 OFFSET ?
                )
                """,
                (self.max_runs,),
            )
        return run

    def get(self, run_id: str) -> AgentRun | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return AgentRun.model_validate(json.loads(row["payload"])) if row else None

    def list(self, session_id: str | None = None) -> list[AgentRun]:
        query = "SELECT payload FROM runs"
        params: tuple[str, ...] = ()
        if session_id:
            query += " WHERE session_id = ?"
            params = (session_id,)
        query += " ORDER BY updated_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [AgentRun.model_validate(json.loads(row["payload"])) for row in rows]

    def count(self, status: RunStatus | None = None) -> int:
        with self._connect() as connection:
            if status is None:
                row = connection.execute("SELECT COUNT(*) AS n FROM runs").fetchone()
            else:
                row = connection.execute("SELECT COUNT(*) AS n FROM runs WHERE status = ?", (status.value,)).fetchone()
        return int(row["n"])

