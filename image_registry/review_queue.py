from __future__ import annotations

import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any


QUEUE_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_queue (
    queue_name TEXT NOT NULL,
    asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending', 'leased', 'completed', 'failed')),
    current_attempt_id INTEGER,
    completed_at TEXT,
    result_json TEXT,
    PRIMARY KEY(queue_name, asset_id),
    UNIQUE(queue_name, ordinal)
);
CREATE TABLE IF NOT EXISTS review_worker (
    queue_name TEXT NOT NULL,
    worker_id TEXT NOT NULL,
    backend TEXT NOT NULL,
    model TEXT NOT NULL,
    max_claims INTEGER NOT NULL CHECK(max_claims BETWEEN 1 AND 100),
    registered_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    PRIMARY KEY(queue_name, worker_id)
);
CREATE TABLE IF NOT EXISTS review_attempt (
    id INTEGER PRIMARY KEY,
    queue_name TEXT NOT NULL,
    asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    attempt_number INTEGER NOT NULL,
    worker_id TEXT NOT NULL,
    claim_token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK(status IN ('leased', 'completed', 'failed', 'expired')),
    claimed_at TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    finished_at TEXT,
    response_json TEXT,
    error_json TEXT,
    UNIQUE(queue_name, asset_id, attempt_number)
);
CREATE INDEX IF NOT EXISTS idx_review_queue_status
    ON review_queue(queue_name, status, ordinal);
CREATE INDEX IF NOT EXISTS idx_review_attempt_worker
    ON review_attempt(queue_name, worker_id, status);
"""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(QUEUE_SCHEMA)


def create_queue(db: sqlite3.Connection, queue_name: str, selection: str) -> int:
    ensure_schema(db)
    rows = db.execute(
        """SELECT asset_id, ordinal FROM selection
           WHERE name=? ORDER BY ordinal""",
        (selection,),
    ).fetchall()
    if not rows:
        raise ValueError(f"selection is empty or missing: {selection}")
    invalid = db.execute(
        """SELECT COUNT(*) FROM selection s JOIN asset a ON a.id=s.asset_id
           WHERE s.name=? AND (a.local_path IS NULL OR a.sha256 IS NULL)""",
        (selection,),
    ).fetchone()[0]
    if invalid:
        raise ValueError(f"selection contains {invalid} image(s) without a local path/hash")
    existing = db.execute(
        "SELECT COUNT(*) FROM review_queue WHERE queue_name=?", (queue_name,)
    ).fetchone()[0]
    if existing:
        raise ValueError(f"queue already exists: {queue_name}")
    db.executemany(
        "INSERT INTO review_queue(queue_name, asset_id, ordinal) VALUES (?, ?, ?)",
        ((queue_name, row["asset_id"], row["ordinal"]) for row in rows),
    )
    db.commit()
    return len(rows)


def register_worker(
    db: sqlite3.Connection,
    queue_name: str,
    worker_id: str,
    backend: str,
    model: str,
    max_claims: int,
) -> None:
    ensure_schema(db)
    if not 1 <= max_claims <= 100:
        raise ValueError("max_claims must be between 1 and 100")
    now = timestamp(utc_now())
    db.execute(
        """INSERT INTO review_worker(
               queue_name, worker_id, backend, model, max_claims,
               registered_at, last_seen_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(queue_name, worker_id) DO UPDATE SET
               backend=excluded.backend, model=excluded.model,
               max_claims=excluded.max_claims, last_seen_at=excluded.last_seen_at""",
        (queue_name, worker_id, backend, model, max_claims, now, now),
    )
    db.commit()


def _expire_leases(db: sqlite3.Connection, queue_name: str, now: str) -> int:
    rows = db.execute(
        """SELECT id, asset_id FROM review_attempt
           WHERE queue_name=? AND status='leased' AND lease_expires_at<=?""",
        (queue_name, now),
    ).fetchall()
    for row in rows:
        db.execute(
            "UPDATE review_attempt SET status='expired', finished_at=? WHERE id=?",
            (now, row["id"]),
        )
        db.execute(
            """UPDATE review_queue SET status='pending', current_attempt_id=NULL
               WHERE queue_name=? AND asset_id=? AND current_attempt_id=?""",
            (queue_name, row["asset_id"], row["id"]),
        )
    return len(rows)


def claim_batch(
    db: sqlite3.Connection,
    queue_name: str,
    worker_id: str,
    requested: int | None = None,
    lease_seconds: int = 1800,
) -> list[dict[str, Any]]:
    ensure_schema(db)
    if lease_seconds < 30:
        raise ValueError("lease_seconds must be at least 30")
    db.execute("BEGIN IMMEDIATE")
    try:
        now_dt = utc_now()
        now = timestamp(now_dt)
        _expire_leases(db, queue_name, now)
        worker = db.execute(
            """SELECT * FROM review_worker
               WHERE queue_name=? AND worker_id=?""",
            (queue_name, worker_id),
        ).fetchone()
        if worker is None:
            raise ValueError(f"worker is not registered: {worker_id}")
        amount = worker["max_claims"] if requested is None else requested
        if not 1 <= amount <= worker["max_claims"]:
            raise ValueError(f"requested claims exceed worker limit {worker['max_claims']}")
        active = db.execute(
            """SELECT COUNT(*) FROM review_attempt
               WHERE queue_name=? AND worker_id=? AND status='leased'""",
            (queue_name, worker_id),
        ).fetchone()[0]
        if active:
            raise ValueError(
                f"worker {worker_id} must finish its {active} active claim(s) before claiming more"
            )
        rows = db.execute(
            """SELECT q.asset_id, q.ordinal, a.source_id, a.local_path, a.sha256
               FROM review_queue q JOIN asset a ON a.id=q.asset_id
               WHERE q.queue_name=? AND q.status='pending'
                 AND NOT EXISTS (
                   SELECT 1 FROM review_attempt previous
                   WHERE previous.queue_name=q.queue_name
                     AND previous.asset_id=q.asset_id
                     AND previous.worker_id=?
                     AND previous.status IN ('failed', 'expired')
                 )
               ORDER BY q.ordinal LIMIT ?""",
            (queue_name, worker_id, amount),
        ).fetchall()
        expires = timestamp(now_dt + timedelta(seconds=lease_seconds))
        claims: list[dict[str, Any]] = []
        for row in rows:
            attempt_number = db.execute(
                """SELECT COALESCE(MAX(attempt_number), 0) + 1 FROM review_attempt
                   WHERE queue_name=? AND asset_id=?""",
                (queue_name, row["asset_id"]),
            ).fetchone()[0]
            token = secrets.token_urlsafe(32)
            cursor = db.execute(
                """INSERT INTO review_attempt(
                       queue_name, asset_id, attempt_number, worker_id, claim_token,
                       status, claimed_at, lease_expires_at
                   ) VALUES (?, ?, ?, ?, ?, 'leased', ?, ?)""",
                (queue_name, row["asset_id"], attempt_number, worker_id, token, now, expires),
            )
            db.execute(
                """UPDATE review_queue SET status='leased', current_attempt_id=?
                   WHERE queue_name=? AND asset_id=? AND status='pending'""",
                (cursor.lastrowid, queue_name, row["asset_id"]),
            )
            claims.append({
                "queue_name": queue_name,
                "ordinal": row["ordinal"],
                "source_id": row["source_id"],
                "local_path": row["local_path"],
                "sha256": row["sha256"],
                "claim_token": token,
                "lease_expires_at": expires,
                "attempt_number": attempt_number,
                "worker_id": worker_id,
                "backend": worker["backend"],
                "model": worker["model"],
            })
        db.execute(
            """UPDATE review_worker SET last_seen_at=?
               WHERE queue_name=? AND worker_id=?""",
            (now, queue_name, worker_id),
        )
        db.commit()
        return claims
    except Exception:
        db.rollback()
        raise


def renew_claim(
    db: sqlite3.Connection, claim_token: str, worker_id: str, lease_seconds: int = 1800
) -> str:
    ensure_schema(db)
    now = timestamp(utc_now())
    expires = timestamp(utc_now() + timedelta(seconds=lease_seconds))
    cursor = db.execute(
        """UPDATE review_attempt SET lease_expires_at=?
           WHERE claim_token=? AND worker_id=? AND status='leased' AND lease_expires_at>?""",
        (expires, claim_token, worker_id, now),
    )
    if cursor.rowcount != 1:
        db.rollback()
        raise ValueError("claim is missing, expired, completed, or owned by another worker")
    db.commit()
    return expires


def complete_claim(
    db: sqlite3.Connection, claim_token: str, worker_id: str, response: dict[str, Any]
) -> None:
    _finish_claim(db, claim_token, worker_id, "completed", response, retry=False)


def fail_claim(
    db: sqlite3.Connection,
    claim_token: str,
    worker_id: str,
    error: dict[str, Any],
    retry: bool = True,
) -> None:
    _finish_claim(db, claim_token, worker_id, "failed", error, retry=retry)


def _finish_claim(
    db: sqlite3.Connection,
    claim_token: str,
    worker_id: str,
    outcome: str,
    payload: dict[str, Any],
    retry: bool,
) -> None:
    ensure_schema(db)
    db.execute("BEGIN IMMEDIATE")
    try:
        now = timestamp(utc_now())
        attempt = db.execute(
            """SELECT * FROM review_attempt
               WHERE claim_token=? AND worker_id=? AND status='leased'""",
            (claim_token, worker_id),
        ).fetchone()
        if attempt is None or attempt["lease_expires_at"] <= now:
            raise ValueError("claim is missing, expired, completed, or owned by another worker")
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        db.execute(
            f"""UPDATE review_attempt SET status=?, finished_at=?,
                    {'response_json' if outcome == 'completed' else 'error_json'}=?
                WHERE id=?""",
            (outcome, now, encoded, attempt["id"]),
        )
        item_status = "completed" if outcome == "completed" else ("pending" if retry else "failed")
        db.execute(
            """UPDATE review_queue SET status=?, current_attempt_id=NULL,
                   completed_at=?, result_json=?
               WHERE queue_name=? AND asset_id=? AND current_attempt_id=?""",
            (
                item_status,
                now if outcome == "completed" else None,
                encoded if outcome == "completed" else None,
                attempt["queue_name"], attempt["asset_id"], attempt["id"],
            ),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise


def queue_status(db: sqlite3.Connection, queue_name: str) -> dict[str, Any]:
    ensure_schema(db)
    db.execute("BEGIN IMMEDIATE")
    try:
        expired = _expire_leases(db, queue_name, timestamp(utc_now()))
        counts = {
            row["status"]: row["count"]
            for row in db.execute(
                """SELECT status, COUNT(*) AS count FROM review_queue
                   WHERE queue_name=? GROUP BY status""",
                (queue_name,),
            )
        }
        workers = [dict(row) for row in db.execute(
            """SELECT w.*,
                      (SELECT COUNT(*) FROM review_attempt a
                       WHERE a.queue_name=w.queue_name AND a.worker_id=w.worker_id
                         AND a.status='leased') AS active_claims
               FROM review_worker w WHERE queue_name=? ORDER BY worker_id""",
            (queue_name,),
        )]
        db.commit()
        return {"queue_name": queue_name, "counts": counts, "expired_now": expired, "workers": workers}
    except Exception:
        db.rollback()
        raise


def requeue_terminal_failures(
    db: sqlite3.Connection,
    queue_name: str,
    *,
    error_types: set[str],
) -> int:
    """Requeue exact terminal infrastructure failures without erasing evidence."""
    ensure_schema(db)
    if not error_types:
        raise ValueError("at least one terminal error type is required")
    db.execute("BEGIN IMMEDIATE")
    try:
        rows = db.execute(
            """SELECT q.asset_id, a.error_json
               FROM review_queue q
               JOIN review_attempt a ON a.id=(
                   SELECT MAX(previous.id) FROM review_attempt previous
                   WHERE previous.queue_name=q.queue_name
                     AND previous.asset_id=q.asset_id
               )
               WHERE q.queue_name=? AND q.status='failed'""",
            (queue_name,),
        ).fetchall()
        selected = []
        for row in rows:
            try:
                error_type = json.loads(row["error_json"] or "{}").get("type")
            except json.JSONDecodeError:
                error_type = None
            if error_type in error_types:
                selected.append(row["asset_id"])
        db.executemany(
            """UPDATE review_queue
               SET status='pending', current_attempt_id=NULL,
                   completed_at=NULL, result_json=NULL
               WHERE queue_name=? AND asset_id=? AND status='failed'""",
            ((queue_name, asset_id) for asset_id in selected),
        )
        db.commit()
        return len(selected)
    except Exception:
        db.rollback()
        raise


def export_filename_list(db: sqlite3.Connection, queue_name: str) -> list[dict[str, Any]]:
    ensure_schema(db)
    return [dict(row) for row in db.execute(
        """SELECT q.ordinal, a.source_id, a.local_path, a.sha256, q.status
           FROM review_queue q JOIN asset a ON a.id=q.asset_id
           WHERE q.queue_name=? ORDER BY q.ordinal""",
        (queue_name,),
    )]


def export_results(db: sqlite3.Connection, queue_name: str) -> list[dict[str, Any]]:
    ensure_schema(db)
    rows = db.execute(
        """SELECT q.ordinal, a.source_id, q.result_json
           FROM review_queue q JOIN asset a ON a.id=q.asset_id
           WHERE q.queue_name=? AND q.status='completed' ORDER BY q.ordinal""",
        (queue_name,),
    )
    results = []
    for row in rows:
        result = json.loads(row["result_json"])
        result.setdefault("ordinal", row["ordinal"])
        result.setdefault("source_id", row["source_id"])
        results.append(result)
    return results
