from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ATTEMPT_OUTCOMES = {"pending", "succeeded", "failed", "blocked", "mixed", "inconclusive"}
EFFECTIVENESS = {"unknown", "working", "not_working", "mixed"}
LESSON_STATUSES = {"candidate", "active", "retired"}
SCHEMA_VERSION = "ninereeds_experience_digest_v2"
ANOMALY_STREAK_THRESHOLD = 2
SEARCH_STOP_WORDS = {
    "a",
    "an",
    "and",
    "for",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _json_list(values: Iterable[str], field: str) -> str:
    items = list(values)
    if not all(isinstance(item, str) and item.strip() for item in items):
        raise ValueError(f"{field} must contain non-empty strings")
    return json.dumps(items, ensure_ascii=False, separators=(",", ":"))


def _json_object(value: dict[str, Any], field: str) -> str:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _normalized_text(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in _normalized_text(value).split()
        if token not in SEARCH_STOP_WORDS
    }


def _method_key(steps: list[str]) -> str:
    encoded = json.dumps(
        steps, ensure_ascii=False, separators=(",", ":"), sort_keys=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ExperienceLedger:
    """Small operational-memory store; observations remain separate from promoted rules."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    problem TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    method_steps_json TEXT NOT NULL,
                    outcome TEXT NOT NULL CHECK (
                        outcome IN (
                            'pending', 'succeeded', 'failed', 'blocked',
                            'mixed', 'inconclusive'
                        )
                    ),
                    effectiveness TEXT NOT NULL CHECK (
                        effectiveness IN (
                            'unknown', 'working', 'not_working', 'mixed'
                        )
                    ),
                    evidence_refs_json TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    source_plan_id TEXT UNIQUE
                );

                CREATE INDEX IF NOT EXISTS attempts_recent
                    ON attempts(updated_at DESC);
                CREATE INDEX IF NOT EXISTS attempts_outcome
                    ON attempts(outcome, updated_at DESC);

                CREATE TABLE IF NOT EXISTS lessons (
                    lesson_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    title TEXT NOT NULL,
                    scope TEXT NOT NULL,
                    conditions_json TEXT NOT NULL,
                    recommendation_json TEXT NOT NULL,
                    avoid_json TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK (
                        confidence >= 0.0 AND confidence <= 1.0
                    ),
                    status TEXT NOT NULL CHECK (
                        status IN ('candidate', 'active', 'retired')
                    ),
                    evidence_attempt_ids_json TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS lessons_strategy
                    ON lessons(status, confidence DESC, updated_at DESC);
                """
            )
            self._migrate_v2(connection)
            connection.execute("PRAGMA user_version = 2")

    def _migrate_v2(self, connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS problems (
                problem_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                canonical_key TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                aliases_json TEXT NOT NULL,
                tags_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS methods (
                method_id TEXT PRIMARY KEY,
                problem_id TEXT NOT NULL REFERENCES problems(problem_id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                method_key TEXT NOT NULL,
                label TEXT NOT NULL,
                steps_json TEXT NOT NULL,
                UNIQUE(problem_id, method_key)
            );

            CREATE INDEX IF NOT EXISTS methods_by_problem
                ON methods(problem_id, updated_at DESC);

            CREATE TABLE IF NOT EXISTS outcome_anomalies (
                anomaly_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                attempt_id TEXT NOT NULL UNIQUE REFERENCES attempts(attempt_id),
                problem_id TEXT NOT NULL REFERENCES problems(problem_id),
                method_id TEXT NOT NULL REFERENCES methods(method_id),
                kind TEXT NOT NULL CHECK (
                    kind IN ('success_after_failure_streak', 'failure_after_success_streak')
                ),
                prior_streak INTEGER NOT NULL,
                prior_working INTEGER NOT NULL,
                prior_not_working INTEGER NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('open', 'acknowledged'))
            );

            CREATE INDEX IF NOT EXISTS anomalies_open
                ON outcome_anomalies(status, updated_at DESC);
            """
        )
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(attempts)").fetchall()
        }
        if "problem_id" not in columns:
            connection.execute(
                "ALTER TABLE attempts ADD COLUMN problem_id TEXT REFERENCES problems(problem_id)"
            )
        if "method_id" not in columns:
            connection.execute(
                "ALTER TABLE attempts ADD COLUMN method_id TEXT REFERENCES methods(method_id)"
            )
        rows = connection.execute(
            """
            SELECT attempt_id, problem, method_steps_json, tags_json
            FROM attempts
            WHERE problem_id IS NULL OR method_id IS NULL
            ORDER BY created_at, rowid
            """
        ).fetchall()
        for row in rows:
            steps = json.loads(str(row["method_steps_json"]))
            tags = json.loads(str(row["tags_json"]))
            problem_id = self._resolve_problem(
                connection, str(row["problem"]), tags, allow_similar=True
            )
            method_id = self._resolve_method(connection, problem_id, steps)
            connection.execute(
                """
                UPDATE attempts SET problem_id = ?, method_id = ?
                WHERE attempt_id = ?
                """,
                (problem_id, method_id, row["attempt_id"]),
            )
        for row in connection.execute(
            """
            SELECT attempt_id FROM attempts
            WHERE effectiveness IN ('working', 'not_working')
            ORDER BY created_at, rowid
            """
        ).fetchall():
            self._refresh_anomaly(connection, str(row["attempt_id"]))

    def record_attempt(
        self,
        *,
        problem: str,
        method_steps: Iterable[str],
        outcome: str = "pending",
        effectiveness: str = "unknown",
        context: dict[str, Any] | None = None,
        evidence_refs: Iterable[str] = (),
        notes: str = "",
        tags: Iterable[str] = (),
        source_plan_id: str | None = None,
        attempt_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(problem, str) or not problem.strip():
            raise ValueError("problem must be a non-empty string")
        if outcome not in ATTEMPT_OUTCOMES:
            raise ValueError(f"invalid outcome: {outcome}")
        if effectiveness not in EFFECTIVENESS:
            raise ValueError(f"invalid effectiveness: {effectiveness}")
        if not isinstance(notes, str):
            raise ValueError("notes must be a string")
        identifier = attempt_id or f"attempt-{uuid.uuid4().hex}"
        now = utc_now()
        steps = list(method_steps)
        tag_list = list(tags)
        steps_json = _json_list(steps, "method_steps")
        tags_json = _json_list(tag_list, "tags")
        with self._connect() as connection:
            if source_plan_id is not None:
                existing = connection.execute(
                    "SELECT attempt_id FROM attempts WHERE source_plan_id = ?",
                    (source_plan_id,),
                ).fetchone()
                if existing is not None:
                    return self.attempt(str(existing["attempt_id"]))
            problem_id = self._resolve_problem(
                connection, problem.strip(), tag_list, allow_similar=True
            )
            method_id = self._resolve_method(connection, problem_id, steps)
            connection.execute(
                """
                INSERT INTO attempts (
                    attempt_id, created_at, updated_at, problem, context_json,
                    method_steps_json, outcome, effectiveness, evidence_refs_json,
                    notes, tags_json, source_plan_id, problem_id, method_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    now,
                    now,
                    problem.strip(),
                    _json_object(context or {}, "context"),
                    steps_json,
                    outcome,
                    effectiveness,
                    _json_list(evidence_refs, "evidence_refs"),
                    notes.strip(),
                    tags_json,
                    source_plan_id,
                    problem_id,
                    method_id,
                ),
            )
            self._refresh_anomaly(connection, identifier)
        return self.attempt(identifier)

    def update_attempt(
        self,
        attempt_id: str,
        *,
        outcome: str,
        effectiveness: str | None = None,
        evidence_refs: Iterable[str] | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        if outcome not in ATTEMPT_OUTCOMES:
            raise ValueError(f"invalid outcome: {outcome}")
        current = self.attempt(attempt_id)
        effective = current["effectiveness"] if effectiveness is None else effectiveness
        if effective not in EFFECTIVENESS:
            raise ValueError(f"invalid effectiveness: {effective}")
        refs = current["evidence_refs"] if evidence_refs is None else list(evidence_refs)
        next_notes = current["notes"] if notes is None else notes
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE attempts
                SET updated_at = ?, outcome = ?, effectiveness = ?,
                    evidence_refs_json = ?, notes = ?
                WHERE attempt_id = ?
                """,
                (
                    utc_now(),
                    outcome,
                    effective,
                    _json_list(refs, "evidence_refs"),
                    next_notes,
                    attempt_id,
                ),
            )
            self._refresh_anomaly(connection, attempt_id)
        return self.attempt(attempt_id)

    def _resolve_problem(
        self,
        connection: sqlite3.Connection,
        title: str,
        tags: list[str],
        *,
        allow_similar: bool,
    ) -> str:
        canonical = _normalized_text(title)
        if not canonical:
            raise ValueError("problem must contain searchable characters")
        exact = connection.execute(
            "SELECT * FROM problems WHERE canonical_key = ?", (canonical,)
        ).fetchone()
        if exact is not None:
            self._merge_problem_metadata(connection, exact, title, tags)
            return str(exact["problem_id"])

        best: sqlite3.Row | None = None
        best_score = 0.0
        title_tokens = _tokens(title)
        if allow_similar and len(title_tokens) >= 3:
            for row in connection.execute("SELECT * FROM problems").fetchall():
                score = self._problem_score(
                    title,
                    tags,
                    str(row["title"]),
                    json.loads(str(row["aliases_json"])),
                    json.loads(str(row["tags_json"])),
                )
                if score > best_score:
                    best = row
                    best_score = score
        if best is not None and best_score >= 0.82:
            self._merge_problem_metadata(connection, best, title, tags)
            return str(best["problem_id"])

        identifier = f"problem-{uuid.uuid4().hex}"
        now = utc_now()
        connection.execute(
            """
            INSERT INTO problems (
                problem_id, created_at, updated_at, canonical_key,
                title, aliases_json, tags_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier,
                now,
                now,
                canonical,
                title.strip(),
                "[]",
                _json_list(tags, "tags"),
            ),
        )
        return identifier

    @staticmethod
    def _merge_problem_metadata(
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        title: str,
        tags: list[str],
    ) -> None:
        aliases = json.loads(str(row["aliases_json"]))
        known_tags = json.loads(str(row["tags_json"]))
        if title != row["title"] and title not in aliases:
            aliases.append(title)
        for tag in tags:
            if tag not in known_tags:
                known_tags.append(tag)
        connection.execute(
            """
            UPDATE problems SET updated_at = ?, aliases_json = ?, tags_json = ?
            WHERE problem_id = ?
            """,
            (
                utc_now(),
                _json_list(aliases, "aliases"),
                _json_list(known_tags, "tags"),
                row["problem_id"],
            ),
        )

    @staticmethod
    def _resolve_method(
        connection: sqlite3.Connection,
        problem_id: str,
        steps: list[str],
    ) -> str:
        steps_json = _json_list(steps, "method_steps")
        key = _method_key(steps)
        existing = connection.execute(
            """
            SELECT method_id FROM methods
            WHERE problem_id = ? AND method_key = ?
            """,
            (problem_id, key),
        ).fetchone()
        if existing is not None:
            connection.execute(
                "UPDATE methods SET updated_at = ? WHERE method_id = ?",
                (utc_now(), existing["method_id"]),
            )
            return str(existing["method_id"])
        identifier = f"method-{uuid.uuid4().hex}"
        now = utc_now()
        label = " → ".join(steps)
        connection.execute(
            """
            INSERT INTO methods (
                method_id, problem_id, created_at, updated_at,
                method_key, label, steps_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                identifier,
                problem_id,
                now,
                now,
                key,
                label[:1000],
                steps_json,
            ),
        )
        return identifier

    def attempt(self, attempt_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM attempts WHERE attempt_id = ?", (attempt_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown attempt: {attempt_id}")
        return self._attempt_dict(row)

    @staticmethod
    def _problem_score(
        query: str,
        query_tags: Iterable[str],
        title: str,
        aliases: Iterable[str],
        problem_tags: Iterable[str],
    ) -> float:
        query_tokens = _tokens(query)
        candidates = [_tokens(title), *(_tokens(alias) for alias in aliases)]
        text_score = 0.0
        for candidate in candidates:
            if not query_tokens or not candidate:
                continue
            intersection = len(query_tokens & candidate)
            union = len(query_tokens | candidate)
            jaccard = intersection / union
            containment = intersection / min(len(query_tokens), len(candidate))
            text_score = max(text_score, 0.55 * jaccard + 0.45 * containment)
        query_tag_set = {tag.casefold() for tag in query_tags}
        stored_tag_set = {tag.casefold() for tag in problem_tags}
        tag_score = (
            len(query_tag_set & stored_tag_set) / len(query_tag_set | stored_tag_set)
            if query_tag_set and stored_tag_set
            else 0.0
        )
        return min(1.0, text_score * 0.85 + tag_score * 0.15)

    def search_problems(
        self,
        query: str,
        *,
        tags: Iterable[str] = (),
        limit: int = 5,
        minimum_score: float = 0.12,
    ) -> list[dict[str, Any]]:
        tag_list = list(tags)
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM problems ORDER BY updated_at DESC"
            ).fetchall()
            matches: list[tuple[float, sqlite3.Row]] = []
            for row in rows:
                score = self._problem_score(
                    query,
                    tag_list,
                    str(row["title"]),
                    json.loads(str(row["aliases_json"])),
                    json.loads(str(row["tags_json"])),
                )
                if score >= minimum_score:
                    matches.append((score, row))
            matches.sort(key=lambda item: (item[0], item[1]["updated_at"]), reverse=True)
            return [
                self._problem_summary(connection, row, score)
                for score, row in matches[:limit]
            ]

    def _problem_summary(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        score: float,
    ) -> dict[str, Any]:
        methods = []
        for method in connection.execute(
            """
            SELECT
                m.*,
                COUNT(a.attempt_id) AS total_attempts,
                SUM(CASE WHEN a.outcome = 'succeeded' THEN 1 ELSE 0 END)
                    AS succeeded_count,
                SUM(CASE WHEN a.outcome = 'failed' THEN 1 ELSE 0 END)
                    AS failed_count,
                SUM(CASE WHEN a.outcome = 'blocked' THEN 1 ELSE 0 END)
                    AS blocked_count,
                SUM(CASE WHEN a.outcome = 'pending' THEN 1 ELSE 0 END)
                    AS pending_count,
                SUM(CASE WHEN a.effectiveness = 'working' THEN 1 ELSE 0 END)
                    AS working_count,
                SUM(CASE WHEN a.effectiveness = 'not_working' THEN 1 ELSE 0 END)
                    AS not_working_count,
                SUM(CASE WHEN a.effectiveness = 'mixed' THEN 1 ELSE 0 END)
                    AS mixed_count,
                SUM(CASE WHEN a.effectiveness = 'unknown' THEN 1 ELSE 0 END)
                    AS unknown_count,
                MAX(a.updated_at) AS last_attempt_at
            FROM methods m
            LEFT JOIN attempts a ON a.method_id = m.method_id
            WHERE m.problem_id = ?
            GROUP BY m.method_id
            ORDER BY working_count DESC, not_working_count ASC,
                     total_attempts DESC, m.updated_at DESC
            """,
            (row["problem_id"],),
        ).fetchall():
            assessed = int(method["working_count"] or 0) + int(
                method["not_working_count"] or 0
            ) + int(method["mixed_count"] or 0)
            methods.append(
                {
                    "method_id": method["method_id"],
                    "label": method["label"],
                    "steps": json.loads(str(method["steps_json"])),
                    "execution_counts": {
                        "succeeded": int(method["succeeded_count"] or 0),
                        "failed": int(method["failed_count"] or 0),
                        "blocked": int(method["blocked_count"] or 0),
                        "pending": int(method["pending_count"] or 0),
                        "total": int(method["total_attempts"] or 0),
                    },
                    "counts": {
                        "working": int(method["working_count"] or 0),
                        "not_working": int(method["not_working_count"] or 0),
                        "mixed": int(method["mixed_count"] or 0),
                        "unknown": int(method["unknown_count"] or 0),
                        "total": int(method["total_attempts"] or 0),
                    },
                    "observed_success_rate": (
                        round(int(method["working_count"] or 0) / assessed, 3)
                        if assessed
                        else None
                    ),
                    "last_attempt_at": method["last_attempt_at"],
                }
            )
        anomalies = [
            self._anomaly_dict(anomaly)
            for anomaly in connection.execute(
                """
                SELECT * FROM outcome_anomalies
                WHERE problem_id = ? AND status = 'open'
                ORDER BY updated_at DESC
                """,
                (row["problem_id"],),
            ).fetchall()
        ]
        return {
            "problem_id": row["problem_id"],
            "title": row["title"],
            "aliases": json.loads(str(row["aliases_json"])),
            "tags": json.loads(str(row["tags_json"])),
            "match_score": round(score, 3),
            "methods": methods,
            "open_anomalies": anomalies,
        }

    def _refresh_anomaly(
        self, connection: sqlite3.Connection, attempt_id: str
    ) -> None:
        current = connection.execute(
            """
            SELECT rowid, attempt_id, problem_id, method_id, effectiveness
            FROM attempts WHERE attempt_id = ?
            """,
            (attempt_id,),
        ).fetchone()
        if (
            current is None
            or current["problem_id"] is None
            or current["method_id"] is None
            or current["effectiveness"] not in {"working", "not_working"}
        ):
            connection.execute(
                "DELETE FROM outcome_anomalies WHERE attempt_id = ?", (attempt_id,)
            )
            return
        prior = connection.execute(
            """
            SELECT effectiveness FROM attempts
            WHERE problem_id = ? AND method_id = ? AND rowid < ?
              AND effectiveness IN ('working', 'not_working')
            ORDER BY rowid DESC
            """,
            (current["problem_id"], current["method_id"], current["rowid"]),
        ).fetchall()
        opposite = (
            "not_working" if current["effectiveness"] == "working" else "working"
        )
        streak = 0
        for row in prior:
            if row["effectiveness"] != opposite:
                break
            streak += 1
        if streak < ANOMALY_STREAK_THRESHOLD:
            connection.execute(
                "DELETE FROM outcome_anomalies WHERE attempt_id = ?", (attempt_id,)
            )
            return
        prior_working = sum(row["effectiveness"] == "working" for row in prior)
        prior_not_working = sum(
            row["effectiveness"] == "not_working" for row in prior
        )
        kind = (
            "success_after_failure_streak"
            if current["effectiveness"] == "working"
            else "failure_after_success_streak"
        )
        now = utc_now()
        connection.execute(
            """
            INSERT INTO outcome_anomalies (
                anomaly_id, created_at, updated_at, attempt_id, problem_id,
                method_id, kind, prior_streak, prior_working,
                prior_not_working, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
            ON CONFLICT(attempt_id) DO UPDATE SET
                updated_at = excluded.updated_at,
                kind = excluded.kind,
                prior_streak = excluded.prior_streak,
                prior_working = excluded.prior_working,
                prior_not_working = excluded.prior_not_working,
                status = 'open'
            """,
            (
                f"anomaly-{uuid.uuid4().hex}",
                now,
                now,
                attempt_id,
                current["problem_id"],
                current["method_id"],
                kind,
                streak,
                prior_working,
                prior_not_working,
            ),
        )

    def acknowledge_anomaly(self, anomaly_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            changed = connection.execute(
                """
                UPDATE outcome_anomalies
                SET status = 'acknowledged', updated_at = ?
                WHERE anomaly_id = ?
                """,
                (utc_now(), anomaly_id),
            ).rowcount
            if changed == 0:
                raise KeyError(f"unknown anomaly: {anomaly_id}")
            row = connection.execute(
                "SELECT * FROM outcome_anomalies WHERE anomaly_id = ?",
                (anomaly_id,),
            ).fetchone()
        assert row is not None
        return self._anomaly_dict(row)

    @staticmethod
    def _anomaly_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "anomaly_id": row["anomaly_id"],
            "attempt_id": row["attempt_id"],
            "problem_id": row["problem_id"],
            "method_id": row["method_id"],
            "kind": row["kind"],
            "prior_streak": row["prior_streak"],
            "prior_working": row["prior_working"],
            "prior_not_working": row["prior_not_working"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def add_lesson(
        self,
        *,
        title: str,
        scope: str,
        conditions: Iterable[str],
        recommendation: Iterable[str],
        avoid: Iterable[str] = (),
        confidence: float,
        status: str = "candidate",
        evidence_attempt_ids: Iterable[str] = (),
        lesson_id: str | None = None,
    ) -> dict[str, Any]:
        if not title.strip() or not scope.strip():
            raise ValueError("title and scope must be non-empty")
        if status not in LESSON_STATUSES:
            raise ValueError(f"invalid lesson status: {status}")
        if isinstance(confidence, bool) or not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        evidence_ids = list(evidence_attempt_ids)
        for identifier in evidence_ids:
            self.attempt(identifier)
        identifier = lesson_id or f"lesson-{uuid.uuid4().hex}"
        now = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO lessons (
                    lesson_id, created_at, updated_at, title, scope,
                    conditions_json, recommendation_json, avoid_json,
                    confidence, status, evidence_attempt_ids_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    identifier,
                    now,
                    now,
                    title.strip(),
                    scope.strip(),
                    _json_list(conditions, "conditions"),
                    _json_list(recommendation, "recommendation"),
                    _json_list(avoid, "avoid"),
                    float(confidence),
                    status,
                    _json_list(evidence_ids, "evidence_attempt_ids"),
                ),
            )
        return self.lesson(identifier)

    def lesson(self, lesson_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM lessons WHERE lesson_id = ?", (lesson_id,)
            ).fetchone()
        if row is None:
            raise KeyError(f"unknown lesson: {lesson_id}")
        return self._lesson_dict(row)

    def promote_lesson(
        self,
        lesson_id: str,
        *,
        confidence: float,
        evidence_attempt_ids: Iterable[str] = (),
    ) -> dict[str, Any]:
        if isinstance(confidence, bool) or not 0.0 <= float(confidence) <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        current = self.lesson(lesson_id)
        evidence_ids = list(current["evidence_attempt_ids"])
        for identifier in evidence_attempt_ids:
            self.attempt(identifier)
            if identifier not in evidence_ids:
                evidence_ids.append(identifier)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE lessons
                SET updated_at = ?, confidence = ?, status = 'active',
                    evidence_attempt_ids_json = ?
                WHERE lesson_id = ?
                """,
                (
                    utc_now(),
                    float(confidence),
                    _json_list(evidence_ids, "evidence_attempt_ids"),
                    lesson_id,
                ),
            )
        return self.lesson(lesson_id)

    def reconcile_control_reports(self, control_ledger: Any) -> int:
        """Resolve pending execution outcomes; never infer that success means effective."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT attempt_id, source_plan_id, evidence_refs_json
                FROM attempts
                WHERE outcome = 'pending' AND source_plan_id IS NOT NULL
                """
            ).fetchall()
        changed = 0
        for row in rows:
            plan_id = str(row["source_plan_id"])
            report = control_ledger.report(plan_id)
            effectiveness: str | None = None
            if report is None:
                receipt = control_ledger.receipt(plan_id)
                if receipt is None or receipt.get("status") not in {"blocked", "dead_letter"}:
                    continue
                outcome = "blocked" if receipt["status"] == "blocked" else "failed"
            else:
                outcome = {
                    "succeeded": "succeeded",
                    "failed": "failed",
                    "blocked": "blocked",
                }[report["status"]]
                result = report.get("result", {})
                explicit = result.get("effectiveness")
                if explicit in EFFECTIVENESS:
                    effectiveness = explicit
                elif isinstance(result.get("working"), bool):
                    effectiveness = (
                        "working" if result["working"] else "not_working"
                    )
            refs = json.loads(str(row["evidence_refs_json"]))
            reference = f"control:reports/{plan_id}.json"
            if reference not in refs:
                refs.append(reference)
            self.update_attempt(
                str(row["attempt_id"]),
                outcome=outcome,
                effectiveness=effectiveness,
                evidence_refs=refs,
            )
            changed += 1
        changed += self._reconcile_cortex_evaluations(control_ledger)
        return changed

    def _reconcile_cortex_evaluations(self, control_ledger: Any) -> int:
        """Attach a descendant evaluation to its originating strategic method.

        A certificate is one contextual observation, not a discovered learning law.
        Loss reduction is deliberately absent from this assessment. A non-finite loss may
        contribute to a rejection only as evidence of numerical invalidity.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT attempt_id, source_plan_id, outcome, evidence_refs_json, notes
                FROM attempts
                WHERE effectiveness = 'unknown' AND source_plan_id IS NOT NULL
                """
            ).fetchall()
        if not rows:
            return 0

        plans: dict[str, dict[str, Any]] = {}
        for path in control_ledger.plans_dir.glob("*.json"):
            plan = control_ledger.plan(path.stem)
            if plan is not None:
                plans[str(plan["plan_id"])] = plan
        children: dict[str, list[dict[str, Any]]] = {}
        for plan in plans.values():
            parent_id = plan.get("parent_plan_id")
            if isinstance(parent_id, str):
                children.setdefault(parent_id, []).append(plan)

        changed = 0
        for row in rows:
            source_plan_id = str(row["source_plan_id"])
            frontier = list(children.get(source_plan_id, ()))
            seen: set[str] = set()
            evaluation_plan: dict[str, Any] | None = None
            while frontier:
                candidate = frontier.pop(0)
                candidate_id = str(candidate["plan_id"])
                if candidate_id in seen:
                    continue
                seen.add(candidate_id)
                # A later strategic boundary starts a new method observation. Do not let
                # its eventual evaluation leak backward into an earlier failed attempt.
                if candidate.get("kind") == "strategic_decision":
                    continue
                if candidate.get("kind") == "cortex_evaluation":
                    evaluation_plan = candidate
                    break
                frontier.extend(children.get(candidate_id, ()))
            if evaluation_plan is None:
                continue
            evaluation_id = str(evaluation_plan["plan_id"])
            report = control_ledger.report(evaluation_id)
            if report is None or report.get("status") != "succeeded":
                continue
            result = report.get("result")
            if not isinstance(result, dict):
                continue
            certificate = result.get("certificate")
            if not isinstance(certificate, dict):
                evaluation = result.get("evaluation")
                certificate = (
                    evaluation.get("certificate")
                    if isinstance(evaluation, dict)
                    else None
                )
            if not isinstance(certificate, dict):
                continue
            status = certificate.get("status")
            effectiveness = {
                "admitted": "working",
                "rejected": "not_working",
                "developmental_progress": "mixed",
            }.get(status)
            if effectiveness is None:
                continue
            failure_modes = [
                str(item)
                for item in certificate.get("failure_modes", ())
                if isinstance(item, str)
            ]
            assessment = (
                "Cortex evaluation observation: "
                f"status={status}; effectiveness={effectiveness}; "
                f"failure_modes={json.dumps(failure_modes, separators=(',', ':'))}. "
                "This applies only to the recorded context and method. Finite or decreasing "
                "loss was not treated as evidence that the method worked."
            )
            notes = str(row["notes"])
            if assessment not in notes:
                notes = f"{notes}\n\n{assessment}".strip()
            refs = json.loads(str(row["evidence_refs_json"]))
            reference = f"control:reports/{evaluation_id}.json"
            if reference not in refs:
                refs.append(reference)
            self.update_attempt(
                str(row["attempt_id"]),
                outcome=str(row["outcome"]),
                effectiveness=effectiveness,
                evidence_refs=refs,
                notes=notes,
            )
            changed += 1
        return changed

    def digest(
        self,
        *,
        query: str | None = None,
        tags: Iterable[str] = (),
        max_lessons: int = 20,
        max_attempts: int = 12,
        max_problems: int = 3,
        max_chars: int = 16_000,
    ) -> dict[str, Any]:
        problem_matches = (
            self.search_problems(query, tags=tags, limit=max_problems)
            if query and query.strip()
            else []
        )
        with self._connect() as connection:
            lesson_rows = connection.execute(
                """
                SELECT * FROM lessons
                WHERE status IN ('active', 'candidate')
                ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END,
                         confidence DESC, updated_at DESC
                LIMIT ?
                """,
                (max_lessons,),
            ).fetchall()
            problem_ids = [match["problem_id"] for match in problem_matches]
            if problem_ids:
                placeholders = ",".join("?" for _ in problem_ids)
                attempt_rows = connection.execute(
                    f"""
                    SELECT * FROM attempts
                    WHERE problem_id IN ({placeholders})
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (*problem_ids, max_attempts),
                ).fetchall()
            elif query is None or not query.strip():
                attempt_rows = connection.execute(
                    """
                    SELECT * FROM attempts
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (max_attempts,),
                ).fetchall()
            else:
                attempt_rows = []
            totals = {
                "attempts": int(
                    connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
                ),
                "lessons": int(
                    connection.execute("SELECT COUNT(*) FROM lessons").fetchone()[0]
                ),
                "problems": int(
                    connection.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
                ),
                "methods": int(
                    connection.execute("SELECT COUNT(*) FROM methods").fetchone()[0]
                ),
                "open_anomalies": int(
                    connection.execute(
                        """
                        SELECT COUNT(*) FROM outcome_anomalies
                        WHERE status = 'open'
                        """
                    ).fetchone()[0]
                ),
            }
        lessons = [self._lesson_dict(row) for row in lesson_rows]
        attempts = [self._attempt_dict(row) for row in attempt_rows]
        digest = {
            "schema_version": SCHEMA_VERSION,
            "interpretation": (
                "Attempts are observations. Execution success is not proof of effectiveness. "
                "Execution counters describe operational feasibility; effectiveness counters "
                "describe assessed learning outcomes. Finite or decreasing loss is not positive "
                "effectiveness evidence for this Hebbian byte-level learner; non-finite loss is "
                "only a numerical-health failure. Active lessons are reusable guidance; candidate "
                "lessons remain hypotheses. All rules are provisional and scoped. Open anomalies "
                "merit a bounded experiment before assuming the old rule still holds."
            ),
            "query": query,
            "totals": totals,
            "problem_matches": problem_matches,
            "lessons": lessons,
            "recent_attempts": attempts,
            "omitted": {
                "lessons": max(0, totals["lessons"] - len(lessons)),
                "attempts": max(0, totals["attempts"] - len(attempts)),
                "problem_matches": 0,
            },
        }
        while (
            len(json.dumps(digest, ensure_ascii=False, separators=(",", ":"))) > max_chars
            and attempts
        ):
            attempts.pop()
            digest["omitted"]["attempts"] += 1
        while (
            len(json.dumps(digest, ensure_ascii=False, separators=(",", ":"))) > max_chars
            and lessons
        ):
            lessons.pop()
            digest["omitted"]["lessons"] += 1
        while (
            len(json.dumps(digest, ensure_ascii=False, separators=(",", ":"))) > max_chars
            and problem_matches
        ):
            problem_matches.pop()
            digest["omitted"]["problem_matches"] += 1
        return digest

    @staticmethod
    def _attempt_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "attempt_id": row["attempt_id"],
            "problem_id": row["problem_id"],
            "method_id": row["method_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "problem": row["problem"],
            "context": json.loads(row["context_json"]),
            "method_steps": json.loads(row["method_steps_json"]),
            "outcome": row["outcome"],
            "effectiveness": row["effectiveness"],
            "evidence_refs": json.loads(row["evidence_refs_json"]),
            "notes": row["notes"],
            "tags": json.loads(row["tags_json"]),
            "source_plan_id": row["source_plan_id"],
        }

    @staticmethod
    def _lesson_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "lesson_id": row["lesson_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "title": row["title"],
            "scope": row["scope"],
            "conditions": json.loads(row["conditions_json"]),
            "recommendation": json.loads(row["recommendation_json"]),
            "avoid": json.loads(row["avoid_json"]),
            "confidence": row["confidence"],
            "status": row["status"],
            "evidence_attempt_ids": json.loads(row["evidence_attempt_ids_json"]),
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Ninereeds operational memory.")
    parser.add_argument(
        "--control-root",
        type=Path,
        default=Path("/home/aomukai/.local/state/ninereeds-orchestrator-control"),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    record = commands.add_parser("record", help="Record one attempted method.")
    record.add_argument("--problem", required=True)
    record.add_argument("--step", action="append", required=True)
    record.add_argument("--outcome", choices=sorted(ATTEMPT_OUTCOMES), default="pending")
    record.add_argument("--effectiveness", choices=sorted(EFFECTIVENESS), default="unknown")
    record.add_argument("--evidence", action="append", default=[])
    record.add_argument("--tag", action="append", default=[])
    record.add_argument("--notes", default="")

    assess = commands.add_parser("assess", help="Update an attempted method.")
    assess.add_argument("attempt_id")
    assess.add_argument("--outcome", choices=sorted(ATTEMPT_OUTCOMES), required=True)
    assess.add_argument("--effectiveness", choices=sorted(EFFECTIVENESS))
    assess.add_argument("--evidence", action="append")
    assess.add_argument("--notes")

    rule = commands.add_parser("rule", help="Add a candidate or active lesson.")
    rule.add_argument("--title", required=True)
    rule.add_argument("--scope", required=True)
    rule.add_argument("--condition", action="append", required=True)
    rule.add_argument("--recommend", action="append", required=True)
    rule.add_argument("--avoid", action="append", default=[])
    rule.add_argument("--confidence", type=float, required=True)
    rule.add_argument("--status", choices=sorted(LESSON_STATUSES), default="candidate")
    rule.add_argument("--evidence-attempt", action="append", default=[])

    promote = commands.add_parser("promote", help="Promote a candidate lesson to active.")
    promote.add_argument("lesson_id")
    promote.add_argument("--confidence", type=float, required=True)
    promote.add_argument("--evidence-attempt", action="append", default=[])

    search = commands.add_parser("search", help="Find matching problems and method stats.")
    search.add_argument("query")
    search.add_argument("--tag", action="append", default=[])

    acknowledge = commands.add_parser(
        "acknowledge", help="Acknowledge an investigated outcome reversal."
    )
    acknowledge.add_argument("anomaly_id")

    digest = commands.add_parser("digest", help="Print the orchestrator-visible digest.")
    digest.add_argument("--query")
    digest.add_argument("--tag", action="append", default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    ledger = ExperienceLedger(args.control_root / "experience.sqlite3")
    if args.command == "record":
        result = ledger.record_attempt(
            problem=args.problem,
            method_steps=args.step,
            outcome=args.outcome,
            effectiveness=args.effectiveness,
            evidence_refs=args.evidence,
            notes=args.notes,
            tags=args.tag,
        )
    elif args.command == "assess":
        result = ledger.update_attempt(
            args.attempt_id,
            outcome=args.outcome,
            effectiveness=args.effectiveness,
            evidence_refs=args.evidence,
            notes=args.notes,
        )
    elif args.command == "rule":
        result = ledger.add_lesson(
            title=args.title,
            scope=args.scope,
            conditions=args.condition,
            recommendation=args.recommend,
            avoid=args.avoid,
            confidence=args.confidence,
            status=args.status,
            evidence_attempt_ids=args.evidence_attempt,
        )
    elif args.command == "promote":
        result = ledger.promote_lesson(
            args.lesson_id,
            confidence=args.confidence,
            evidence_attempt_ids=args.evidence_attempt,
        )
    elif args.command == "search":
        result = ledger.search_problems(args.query, tags=args.tag)
    elif args.command == "acknowledge":
        result = ledger.acknowledge_anomaly(args.anomaly_id)
    else:
        result = ledger.digest(query=args.query, tags=args.tag)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
