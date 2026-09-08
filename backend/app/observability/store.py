"""SQLite schema + connection helper.

SQLite, not Postgres, because this is a one-person portfolio service running
on a single free-tier instance — a whole separate managed database for a
few hundred rows a day would be infrastructure the traffic doesn't justify.
If this ever runs with more than one replica, this is the first thing to
swap for something shared, exactly like the rate limiter in ask/routes.py.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS traces (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    question TEXT NOT NULL,
    verdict TEXT NOT NULL,
    reason TEXT,
    score REAL,
    spans_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_traces_started_at ON traces(started_at);

CREATE TABLE IF NOT EXISTS agent_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    agent TEXT NOT NULL,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_events_received_at ON agent_events(received_at);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    received_at TEXT NOT NULL,
    trace_id TEXT,
    question TEXT NOT NULL,
    answer_text TEXT NOT NULL DEFAULT '',
    reason TEXT NOT NULL DEFAULT '',
    contact_email TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_reports_received_at ON reports(received_at);

CREATE TABLE IF NOT EXISTS eval_runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    duration_ms REAL NOT NULL,
    suite_counts_json TEXT NOT NULL,
    attack_success_rate REAL NOT NULL,
    false_refusal_rate REAL NOT NULL,
    recall_at_k REAL NOT NULL,
    no_answer_accuracy REAL NOT NULL,
    citation_correctness REAL NOT NULL,
    answer_relevancy REAL,
    role_adherence REAL,
    knowledge_retention REAL,
    conversation_completeness REAL,
    passed INTEGER NOT NULL,
    git_sha TEXT,
    cases_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eval_runs_started_at ON eval_runs(started_at);
"""

# New eval_runs columns added after the table's first release. `CREATE TABLE
# IF NOT EXISTS` above only helps a brand-new database — an already-deployed
# Render instance has the old table shape, so it needs an explicit ALTER for
# each one, guarded because SQLite has no `ADD COLUMN IF NOT EXISTS`.
_NEW_EVAL_RUN_COLUMNS = {
    "answer_relevancy": "REAL",
    "role_adherence": "REAL",
    "knowledge_retention": "REAL",
    "conversation_completeness": "REAL",
}

_lock = threading.Lock()


class Store:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(eval_runs)").fetchall()}
        for name, col_type in _NEW_EVAL_RUN_COLUMNS.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE eval_runs ADD COLUMN {name} {col_type}")

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            with _lock:
                yield conn
                conn.commit()
        finally:
            conn.close()

    # --- traces -------------------------------------------------------------

    def insert_trace(self, trace: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO traces (id, started_at, duration_ms, question, verdict, reason, score, spans_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    trace["id"], trace["started_at"], trace["duration_ms"], trace["question"],
                    trace["verdict"], trace.get("reason"), trace.get("score"),
                    json.dumps(trace["spans"]),
                ),
            )

    def list_traces(self, limit: int = 50, before: str | None = None) -> list[dict]:
        with self._connect() as conn:
            if before:
                rows = conn.execute(
                    "SELECT * FROM traces WHERE started_at < ? ORDER BY started_at DESC LIMIT ?",
                    (before, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM traces ORDER BY started_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [_trace_row(r) for r in rows]

    def get_trace(self, trace_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM traces WHERE id = ?", (trace_id,)).fetchone()
        return _trace_row(row) if row else None

    # --- agent events ----------------------------------------------------------

    def insert_agent_event(self, event: dict) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO agent_events (received_at, agent, kind, severity, message, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    event["received_at"], event["agent"], event["kind"], event["severity"],
                    event["message"], json.dumps(event["payload"]),
                ),
            )
            return cur.lastrowid

    def list_agent_events(self, limit: int = 100, before_id: int | None = None) -> list[dict]:
        with self._connect() as conn:
            if before_id is not None:
                rows = conn.execute(
                    "SELECT * FROM agent_events WHERE id < ? ORDER BY id DESC LIMIT ?",
                    (before_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agent_events ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [_agent_event_row(r) for r in rows]

    # --- visitor reports ("this answer was wrong / unhelpful") --------------------

    def insert_report(self, report: dict) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO reports (received_at, trace_id, question, answer_text, reason, contact_email) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    report["received_at"], report.get("trace_id"), report["question"],
                    report.get("answer_text", ""), report.get("reason", ""), report.get("contact_email", ""),
                ),
            )
            return cur.lastrowid

    def list_reports(self, limit: int = 50, before_id: int | None = None) -> list[dict]:
        with self._connect() as conn:
            if before_id is not None:
                rows = conn.execute(
                    "SELECT * FROM reports WHERE id < ? ORDER BY id DESC LIMIT ?",
                    (before_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reports ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
        return [_report_row(r) for r in rows]

    # --- eval runs ----------------------------------------------------------

    def insert_eval_run(self, run: dict) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO eval_runs "
                "(id, started_at, duration_ms, suite_counts_json, attack_success_rate, false_refusal_rate, "
                " recall_at_k, no_answer_accuracy, citation_correctness, answer_relevancy, role_adherence, "
                " knowledge_retention, conversation_completeness, passed, git_sha, cases_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run["id"], run["started_at"], run["duration_ms"], json.dumps(run["suite_counts"]),
                    run["attack_success_rate"], run["false_refusal_rate"], run["recall_at_k"],
                    run["no_answer_accuracy"], run["citation_correctness"],
                    run.get("answer_relevancy"), run.get("role_adherence"),
                    run.get("knowledge_retention"), run.get("conversation_completeness"),
                    int(run["passed"]), run.get("git_sha"), json.dumps(run["cases"]),
                ),
            )

    def list_eval_runs(self, limit: int = 50) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM eval_runs ORDER BY started_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_eval_run_row(r, with_cases=False) for r in rows]

    def get_eval_run(self, run_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,)).fetchone()
        return _eval_run_row(row, with_cases=True) if row else None


def _trace_row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"], "started_at": r["started_at"], "duration_ms": r["duration_ms"],
        "question": r["question"], "verdict": r["verdict"], "reason": r["reason"],
        "score": r["score"], "spans": json.loads(r["spans_json"]),
    }


def _agent_event_row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"], "received_at": r["received_at"], "agent": r["agent"], "kind": r["kind"],
        "severity": r["severity"], "message": r["message"], "payload": json.loads(r["payload_json"]),
    }


def _report_row(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"], "received_at": r["received_at"], "trace_id": r["trace_id"],
        "question": r["question"], "answer_text": r["answer_text"], "reason": r["reason"],
        "contact_email": r["contact_email"],
    }


def _eval_run_row(r: sqlite3.Row, with_cases: bool) -> dict:
    keys = r.keys()
    out = {
        "id": r["id"], "started_at": r["started_at"], "duration_ms": r["duration_ms"],
        "suite_counts": json.loads(r["suite_counts_json"]), "attack_success_rate": r["attack_success_rate"],
        "false_refusal_rate": r["false_refusal_rate"], "recall_at_k": r["recall_at_k"],
        "no_answer_accuracy": r["no_answer_accuracy"], "citation_correctness": r["citation_correctness"],
        # Absent on rows published before these columns existed — None reads
        # as "n/a" on the dashboard rather than a misleading 0%.
        "answer_relevancy": r["answer_relevancy"] if "answer_relevancy" in keys else None,
        "role_adherence": r["role_adherence"] if "role_adherence" in keys else None,
        "knowledge_retention": r["knowledge_retention"] if "knowledge_retention" in keys else None,
        "conversation_completeness": r["conversation_completeness"] if "conversation_completeness" in keys else None,
        "passed": bool(r["passed"]), "git_sha": r["git_sha"],
    }
    if with_cases:
        out["cases"] = json.loads(r["cases_json"])
    return out
