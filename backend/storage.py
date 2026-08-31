"""SQLite persistence for scan results."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "truthlens.db"
_lock = threading.Lock()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    scan_id TEXT PRIMARY KEY,
    case_number TEXT NOT NULL,
    filename TEXT NOT NULL,
    created_at TEXT NOT NULL,
    n_rows INTEGER,
    n_cols INTEGER,
    integrity_total INTEGER,
    integrity_verdict TEXT,
    n_findings INTEGER,
    result_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scans_created ON scans(created_at DESC);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _lock:
        conn = _connect()
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()


def save_scan(result: dict) -> None:
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO scans VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    result["scan_id"], result["case_number"], result["filename"],
                    result["created_at"], result["n_rows"], result["n_cols"],
                    result["integrity"]["total"], result["integrity"]["verdict"],
                    len(result["findings"]), json.dumps(result, ensure_ascii=False),
                ),
            )
            conn.commit()
        finally:
            conn.close()


def get_scan(scan_id: str) -> dict | None:
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT result_json FROM scans WHERE scan_id = ?", (scan_id,)
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return None
    return json.loads(row[0])


def list_scans(limit: int = 50) -> list[dict]:
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT scan_id, case_number, filename, created_at, n_rows, n_cols,"
                " integrity_total, integrity_verdict, n_findings FROM scans"
                " ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            conn.close()
    cols = ["scan_id", "case_number", "filename", "created_at", "n_rows",
            "n_cols", "integrity_total", "integrity_verdict", "n_findings"]
    return [dict(zip(cols, r)) for r in rows]
