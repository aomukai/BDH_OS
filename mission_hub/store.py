"""SQLite-backed single source of truth for Ninereeds operations."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from typing import Any, Iterator
import unicodedata
import uuid

from .config import ConfigBundle
from .campaign_contract import (
    campaign_contract_sha256,
    expected_evaluation_context,
    validate_campaign_contract,
)
from .errors import ConflictError, NotFoundError, SafetyError, TransitionError
from .jsonutil import canonical_json, content_hash
from .lesson_policy import IDENTITY_SCOPES, policy_sha256, require_lesson_material, validate_lesson_specification
from .schema import load_schema, validate
from .training_order import require_dependency_order


SCHEMA_VERSION = 12
TERMINAL_JOB_STATES = {"succeeded", "failed", "blocked", "cancelled"}
TERMINAL_RUN_STATES = {"succeeded", "failed", "blocked", "cancelled", "expired"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def strategic_available_at(completed_at: str, cooldown_seconds: int) -> str:
    """Anchor a strategic wake to a durable terminal timestamp."""
    completed = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    return (completed + timedelta(seconds=cooldown_seconds)).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _future(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _past(seconds: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat(timespec="microseconds").replace("+00:00", "Z")


class MissionHubStore:
    """Authoritative transactional store.

    Trainbox agents never open this database. They operate through lease/result
    envelopes issued by a Mission Hub process.
    """

    def __init__(self, path: Path | str, *, busy_timeout_ms: int = 5000):
        self.path = Path(path)
        self.busy_timeout_ms = busy_timeout_ms

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pipeline_control (
                    id TEXT PRIMARY KEY CHECK(id='pipeline'),
                    desired_state TEXT NOT NULL CHECK(desired_state IN ('running','paused')),
                    applied_state TEXT NOT NULL CHECK(applied_state IN ('running','paused')),
                    requested_by TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS config_snapshots (
                    id TEXT PRIMARY KEY,
                    sha256 TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL CHECK(state IN ('draft','active','superseded')),
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    activated_at TEXT,
                    actor TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_config
                    ON config_snapshots(state) WHERE state='active';
                CREATE TABLE IF NOT EXISTS machines (
                    id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    hostname TEXT NOT NULL,
                    config_snapshot_id TEXT NOT NULL REFERENCES config_snapshots(id),
                    config_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL,
                    maintenance_mode INTEGER NOT NULL,
                    last_seen_at TEXT,
                    last_observation_json TEXT
                );
                CREATE TABLE IF NOT EXISTS job_definitions (
                    config_snapshot_id TEXT NOT NULL REFERENCES config_snapshots(id),
                    job_type TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    definition_json TEXT NOT NULL,
                    PRIMARY KEY(config_snapshot_id, job_type, version)
                );
                CREATE TABLE IF NOT EXISTS deployments (
                    id TEXT PRIMARY KEY,
                    machine_id TEXT NOT NULL REFERENCES machines(id),
                    role TEXT NOT NULL,
                    release_id TEXT NOT NULL,
                    source_sha256 TEXT NOT NULL,
                    environment_sha256 TEXT NOT NULL,
                    config_snapshot_id TEXT NOT NULL REFERENCES config_snapshots(id),
                    status TEXT NOT NULL CHECK(status IN ('candidate','active','retired','rejected')),
                    manifest_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    activated_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_deployment_per_machine
                    ON deployments(machine_id) WHERE status='active';
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('draft','paused','active','closed','superseded','legacy_stopped')),
                    config_snapshot_id TEXT NOT NULL REFERENCES config_snapshots(id),
                    objective TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT REFERENCES campaigns(id),
                    kind TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('proposed','approved','rejected','executed','superseded')),
                    payload_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    idempotency_key TEXT NOT NULL UNIQUE,
                    job_type TEXT NOT NULL,
                    job_version INTEGER NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('draft','awaiting_approval','queued','leased','running','succeeded','failed','blocked','cancelled')),
                    config_snapshot_id TEXT NOT NULL REFERENCES config_snapshots(id),
                    campaign_id TEXT REFERENCES campaigns(id),
                    requested_machine_id TEXT REFERENCES machines(id),
                    input_json TEXT NOT NULL,
                    input_sha256 TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    approval_policy TEXT NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    cancel_reason TEXT,
                    available_at TEXT
                );
                CREATE INDEX IF NOT EXISTS queued_jobs ON jobs(status, priority DESC, created_at);
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES jobs(id),
                    attempt INTEGER NOT NULL,
                    machine_id TEXT NOT NULL REFERENCES machines(id),
                    deployment_id TEXT NOT NULL REFERENCES deployments(id),
                    status TEXT NOT NULL CHECK(status IN ('leased','running','succeeded','failed','blocked','cancelled','expired')),
                    lease_token_sha256 TEXT NOT NULL,
                    lease_expires_at TEXT NOT NULL,
                    started_at TEXT,
                    heartbeat_at TEXT,
                    finished_at TEXT,
                    output_json TEXT,
                    output_sha256 TEXT,
                    failure_class TEXT,
                    failure_code TEXT,
                    failure_json TEXT,
                    UNIQUE(job_id, attempt)
                );
                CREATE INDEX IF NOT EXISTS live_runs ON runs(status, lease_expires_at);
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    producing_run_id TEXT REFERENCES runs(id),
                    sha256 TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    lifecycle TEXT NOT NULL CHECK(lifecycle IN ('observed','candidate','protected','published','rejected','deleted','legacy')),
                    manifest_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(kind, sha256)
                );
                CREATE TABLE IF NOT EXISTS artifact_locations (
                    artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                    machine_id TEXT NOT NULL REFERENCES machines(id),
                    uri TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    available INTEGER NOT NULL,
                    PRIMARY KEY(artifact_id, machine_id, uri)
                );
                CREATE TABLE IF NOT EXISTS artifact_protections (
                    id TEXT PRIMARY KEY,
                    artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                    protection_key TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    source TEXT NOT NULL CHECK(source IN ('automatic','operator')),
                    state TEXT NOT NULL CHECK(state IN ('active','released')),
                    metadata_json TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    released_by TEXT,
                    released_at TEXT,
                    UNIQUE(artifact_id,protection_key)
                );
                CREATE INDEX IF NOT EXISTS active_artifact_protections
                    ON artifact_protections(artifact_id,state);
                CREATE TABLE IF NOT EXISTS path_protections (
                    id TEXT PRIMARY KEY,
                    machine_id TEXT NOT NULL REFERENCES machines(id),
                    path TEXT NOT NULL,
                    protection_key TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    source TEXT NOT NULL CHECK(source IN ('automatic','operator')),
                    state TEXT NOT NULL CHECK(state IN ('active','released')),
                    metadata_json TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    released_by TEXT,
                    released_at TEXT,
                    UNIQUE(machine_id,path,protection_key)
                );
                CREATE INDEX IF NOT EXISTS active_path_protections
                    ON path_protections(machine_id,state);
                CREATE TABLE IF NOT EXISTS retention_deletions (
                    id TEXT PRIMARY KEY,
                    plan_sha256 TEXT NOT NULL,
                    artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                    machine_id TEXT NOT NULL REFERENCES machines(id),
                    uri TEXT NOT NULL,
                    expected_sha256 TEXT NOT NULL,
                    byte_size INTEGER NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('authorized','deleted','failed')),
                    authorized_by TEXT NOT NULL,
                    authorized_at TEXT NOT NULL,
                    finished_at TEXT,
                    failure TEXT,
                    UNIQUE(plan_sha256,artifact_id,machine_id,uri)
                );
                CREATE INDEX IF NOT EXISTS pending_retention_deletions
                    ON retention_deletions(artifact_id,state);
                CREATE TABLE IF NOT EXISTS evidence_sources (
                    id TEXT PRIMARY KEY,
                    machine_id TEXT,
                    source_kind TEXT NOT NULL,
                    source_uri TEXT NOT NULL,
                    snapshot_sha256 TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    imported_at TEXT,
                    UNIQUE(machine_id, source_kind, source_uri, snapshot_sha256)
                );
                CREATE TABLE IF NOT EXISTS legacy_records (
                    evidence_source_id TEXT NOT NULL REFERENCES evidence_sources(id),
                    record_kind TEXT NOT NULL,
                    legacy_id TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    imported_at TEXT NOT NULL,
                    PRIMARY KEY(evidence_source_id, record_kind, legacy_id, sha256)
                );
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_sha256 TEXT NOT NULL,
                    sha256 TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS entity_events ON events(entity_type, entity_id, sequence);
                CREATE TABLE IF NOT EXISTS schedule_firings (
                    schedule_id TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    job_id TEXT REFERENCES jobs(id),
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(schedule_id, slot)
                );
                CREATE TABLE IF NOT EXISTS lab_users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lab_sessions (
                    token_sha256 TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES lab_users(id) ON DELETE CASCADE,
                    csrf_token TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS lab_session_expiry ON lab_sessions(expires_at);
                CREATE TABLE IF NOT EXISTS message_threads (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('open','archived')),
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS thread_messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES message_threads(id) ON DELETE CASCADE,
                    sender TEXT NOT NULL CHECK(sender IN ('operator','mission_hub','sol','codex')),
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    read_at TEXT
                );
                CREATE INDEX IF NOT EXISTS thread_message_order ON thread_messages(thread_id, created_at);
                CREATE INDEX IF NOT EXISTS unread_thread_messages ON thread_messages(read_at) WHERE read_at IS NULL;
                CREATE TABLE IF NOT EXISTS chat_threads (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    checkpoint_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                    checkpoint_sha256 TEXT NOT NULL,
                    prompt_format_id TEXT NOT NULL,
                    prompt_format_version INTEGER NOT NULL,
                    generation_json TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('open','archived')),
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('operator','ninereeds','system')),
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS chat_message_order ON chat_messages(thread_id, created_at);
                CREATE TABLE IF NOT EXISTS chat_invocations (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
                    request_message_id TEXT NOT NULL REFERENCES chat_messages(id),
                    response_message_id TEXT REFERENCES chat_messages(id),
                    checkpoint_artifact_id TEXT NOT NULL,
                    checkpoint_sha256 TEXT NOT NULL,
                    prompt_format_id TEXT NOT NULL,
                    prompt_format_version INTEGER NOT NULL,
                    generation_json TEXT NOT NULL,
                    context_message_ids_json TEXT NOT NULL,
                    rendered_prompt TEXT,
                    rendered_prompt_sha256 TEXT,
                    status TEXT NOT NULL CHECK(status IN ('blocked','queued','running','succeeded','failed','cancelled')),
                    failure_json TEXT,
                    job_id TEXT REFERENCES jobs(id),
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT
                );
                CREATE TABLE IF NOT EXISTS lab_config_drafts (
                    id TEXT PRIMARY KEY,
                    base_config_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('draft','superseded','activated')),
                    payload_json TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS lab_config_draft_state ON lab_config_drafts(state, updated_at);
                CREATE TABLE IF NOT EXISTS budget_reservations (
                    job_id TEXT PRIMARY KEY REFERENCES jobs(id),
                    route_id TEXT NOT NULL,
                    reserved_usd REAL NOT NULL CHECK(reserved_usd>=0),
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS budget_reservation_created ON budget_reservations(created_at);
                CREATE TABLE IF NOT EXISTS visual_workflows (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
                    status TEXT NOT NULL CHECK(status IN ('active','shadow_complete','succeeded','failed','cancelled')),
                    specification_json TEXT NOT NULL,
                    config_snapshot_id TEXT NOT NULL REFERENCES config_snapshots(id),
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS visual_workflow_jobs (
                    workflow_id TEXT NOT NULL REFERENCES visual_workflows(id),
                    stage_key TEXT NOT NULL,
                    job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(workflow_id, stage_key)
                );
                CREATE TABLE IF NOT EXISTS cortex_workflows (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
                    status TEXT NOT NULL CHECK(status IN ('active','succeeded','blocked','failed','cancelled')),
                    specification_json TEXT NOT NULL,
                    config_snapshot_id TEXT NOT NULL REFERENCES config_snapshots(id),
                    reauthorized_config_snapshot_id TEXT REFERENCES config_snapshots(id),
                    authorized_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS cortex_workflow_jobs (
                    workflow_id TEXT NOT NULL REFERENCES cortex_workflows(id),
                    stage_key TEXT NOT NULL,
                    job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(workflow_id, stage_key)
                );
                CREATE TABLE IF NOT EXISTS knowledge_records (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT NOT NULL UNIQUE,
                    concept_key TEXT NOT NULL,
                    concept_label TEXT NOT NULL,
                    campaign_id TEXT REFERENCES campaigns(id),
                    session_id TEXT NOT NULL,
                    job_id TEXT REFERENCES jobs(id),
                    run_id TEXT REFERENCES runs(id),
                    checkpoint_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                    parent_checkpoint_artifact_id TEXT REFERENCES artifacts(id),
                    evidence_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    previous_sha256 TEXT NOT NULL,
                    sha256 TEXT NOT NULL UNIQUE
                );
                CREATE INDEX IF NOT EXISTS knowledge_by_concept ON knowledge_records(concept_key,sequence);
                CREATE INDEX IF NOT EXISTS knowledge_by_campaign ON knowledge_records(campaign_id,sequence);
                CREATE TABLE IF NOT EXISTS checkpoint_knowledge (
                    checkpoint_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                    concept_key TEXT NOT NULL,
                    source_record_id TEXT NOT NULL REFERENCES knowledge_records(id),
                    PRIMARY KEY(checkpoint_artifact_id,concept_key)
                );
                CREATE TABLE IF NOT EXISTS campaign_knowledge_start (
                    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
                    concept_key TEXT NOT NULL,
                    source_record_id TEXT NOT NULL REFERENCES knowledge_records(id),
                    PRIMARY KEY(campaign_id,concept_key)
                );
                CREATE TABLE IF NOT EXISTS training_session_plans (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT NOT NULL REFERENCES campaigns(id),
                    session_id TEXT NOT NULL,
                    job_id TEXT NOT NULL UNIQUE REFERENCES jobs(id),
                    parent_checkpoint_artifact_id TEXT REFERENCES artifacts(id),
                    subject_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                    validation_artifact_id TEXT NOT NULL REFERENCES artifacts(id),
                    ordered_concepts_json TEXT NOT NULL,
                    parent_knowledge_sha256 TEXT NOT NULL,
                    plan_sha256 TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL CHECK(status IN ('admitted','completed','cancelled')),
                    created_at TEXT NOT NULL,
                    completed_at TEXT,
                    output_checkpoint_artifact_id TEXT REFERENCES artifacts(id),
                    UNIQUE(campaign_id,session_id)
                );
                """
            )
            current = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            if current is None:
                db.execute("INSERT INTO metadata(key,value) VALUES('schema_version',?)", (str(SCHEMA_VERSION),))
            else:
                version = int(current[0])
                if version == 1:
                    columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)").fetchall()}
                    if "available_at" not in columns:
                        db.execute("ALTER TABLE jobs ADD COLUMN available_at TEXT")
                    version = 2
                if version == 2:
                    # Version-three tables are created idempotently above. The
                    # migration marker advances only after that script commits.
                    version = 3
                if version == 3:
                    # Version-four budget tables are created idempotently above.
                    version = 4
                if version == 4:
                    # Version-five visual workflow tables are created idempotently above.
                    version = 5
                if version == 5:
                    # Version-six pipeline control is created idempotently above.
                    version = 6
                if version == 6:
                    # Version-seven append-only knowledge tables are created above.
                    version = 7
                if version == 7:
                    # Version-eight atomic training-session admission is created above.
                    version = 8
                if version == 8:
                    # Version-nine durable Cortex workflow tables are created above.
                    version = 9
                if version == 9:
                    columns = {row[1] for row in db.execute("PRAGMA table_info(cortex_workflows)").fetchall()}
                    if "reauthorized_config_snapshot_id" not in columns:
                        db.execute(
                            "ALTER TABLE cortex_workflows ADD COLUMN reauthorized_config_snapshot_id TEXT REFERENCES config_snapshots(id)"
                        )
                    version = 10
                if version == 10:
                    columns = {row[1] for row in db.execute("PRAGMA table_info(visual_workflows)").fetchall()}
                    if "campaign_id" not in columns:
                        db.execute("ALTER TABLE visual_workflows ADD COLUMN campaign_id TEXT REFERENCES campaigns(id)")
                    version = 11
                if version == 11:
                    # Version-twelve retention-protection tables are created above.
                    version = 12
                if version != SCHEMA_VERSION:
                    raise RuntimeError(f"database schema {current[0]} is not supported by code schema {SCHEMA_VERSION}")
                db.execute("UPDATE metadata SET value=? WHERE key='schema_version'", (str(version),))
            now = utc_now()
            db.execute(
                """INSERT OR IGNORE INTO pipeline_control
                   (id,desired_state,applied_state,requested_by,requested_at,applied_at)
                   VALUES('pipeline','paused','paused','mission-hub:initial-safe-state',?,?)""",
                (now, now),
            )

    def pipeline_control(self) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM pipeline_control WHERE id='pipeline'").fetchone()
            live_runs = int(db.execute("SELECT COUNT(*) FROM runs WHERE status IN ('leased','running')").fetchone()[0])
        if row is None:
            raise RuntimeError("pipeline control is not initialized")
        result = dict(row)
        result["live_runs"] = live_runs
        if result["desired_state"] == "paused":
            result["effective_state"] = "pausing" if live_runs else "paused"
        else:
            result["effective_state"] = "starting" if result["applied_state"] != "running" else "running"
        return result

    def request_pipeline_state(self, desired_state: str, *, actor: str) -> dict[str, Any]:
        if desired_state not in {"running", "paused"}:
            raise ValueError("pipeline state must be running or paused")
        now = utc_now()
        with self.transaction() as db:
            current = db.execute("SELECT desired_state FROM pipeline_control WHERE id='pipeline'").fetchone()
            if current is None:
                raise RuntimeError("pipeline control is not initialized")
            if current[0] != desired_state:
                db.execute(
                    "UPDATE pipeline_control SET desired_state=?,requested_by=?,requested_at=? WHERE id='pipeline'",
                    (desired_state, actor, now),
                )
                self._event(db, "pipeline", "pipeline", f"pipeline.{desired_state}_requested", actor, {
                    "semantics": "finish_active_work_then_apply" if desired_state == "paused" else "start_at_next_daemon_boundary",
                })
        return self.pipeline_control()

    def apply_pipeline_state(self, *, actor: str) -> dict[str, Any]:
        """Acknowledge the desired state at a daemon safe boundary."""
        now = utc_now()
        with self.transaction() as db:
            row = db.execute("SELECT desired_state,applied_state FROM pipeline_control WHERE id='pipeline'").fetchone()
            if row is None:
                raise RuntimeError("pipeline control is not initialized")
            desired, applied = row
            live_runs = int(db.execute("SELECT COUNT(*) FROM runs WHERE status IN ('leased','running')").fetchone()[0])
            target = applied if desired == "paused" and live_runs else desired
            if target != applied:
                db.execute("UPDATE pipeline_control SET applied_state=?,applied_at=? WHERE id='pipeline'", (target, now))
                self._event(db, "pipeline", "pipeline", f"pipeline.{target}", actor, {"live_runs": live_runs})
        return self.pipeline_control()

    @contextmanager
    def transaction(self, *, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            try:
                yield db
            except BaseException:
                db.rollback()
                raise
            else:
                db.commit()

    def activate_config(self, bundle: ConfigBundle, *, actor: str) -> str:
        snapshot = bundle.snapshot()
        snapshot_id = f"cfg-{bundle.sha256[:16]}"
        now = utc_now()
        with self.transaction() as db:
            existing = db.execute("SELECT id,state FROM config_snapshots WHERE sha256=?", (bundle.sha256,)).fetchone()
            if existing is not None and existing[1] == "active":
                return str(existing[0])
            if existing is None:
                db.execute(
                    "INSERT INTO config_snapshots(id,sha256,state,payload_json,created_at,actor) VALUES(?,?,?,?,?,?)",
                    (snapshot_id, bundle.sha256, "draft", canonical_json(snapshot), now, actor),
                )
            else:
                snapshot_id = str(existing[0])
            db.execute("UPDATE config_snapshots SET state='superseded' WHERE state='active'")
            db.execute(
                "UPDATE config_snapshots SET state='active',activated_at=?,actor=? WHERE id=?",
                (now, actor, snapshot_id),
            )
            for machine in bundle.machines.values():
                db.execute(
                    """INSERT INTO machines(id,role,hostname,config_snapshot_id,config_json,enabled,maintenance_mode)
                       VALUES(?,?,?,?,?,?,?)
                       ON CONFLICT(id) DO UPDATE SET role=excluded.role,hostname=excluded.hostname,
                         config_snapshot_id=excluded.config_snapshot_id,config_json=excluded.config_json,
                         enabled=excluded.enabled,maintenance_mode=excluded.maintenance_mode""",
                    (
                        machine["id"], machine["role"], machine["hostname"], snapshot_id,
                        canonical_json(machine), int(machine["enabled"]), int(machine["maintenance_mode"]),
                    ),
                )
            for job in bundle.jobs.values():
                db.execute(
                    "INSERT OR REPLACE INTO job_definitions(config_snapshot_id,job_type,version,definition_json) VALUES(?,?,?,?)",
                    (snapshot_id, job["id"], job["version"], canonical_json(job)),
                )
            self._event(db, "config_snapshot", snapshot_id, "config.activated", actor, {"sha256": bundle.sha256})
        return snapshot_id

    def active_config(self) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT id,sha256,payload_json,activated_at FROM config_snapshots WHERE state='active'").fetchone()
        if row is None:
            raise NotFoundError("no active configuration snapshot")
        return {"id": row[0], "sha256": row[1], "payload": json.loads(row[2]), "activated_at": row[3]}

    def active_deployment(self, machine_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM deployments WHERE machine_id=? AND status='active'",
                (machine_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(f"no active deployment for machine {machine_id}")
        return dict(row)

    def latest_evidence(self, source_id: str) -> dict[str, Any]:
        with self._connect() as db:
            rows = db.execute("SELECT * FROM evidence_sources ORDER BY captured_at DESC").fetchall()
        for row in rows:
            result = dict(row)
            manifest = json.loads(result["manifest_json"])
            if manifest.get("source_id") == source_id:
                result["manifest"] = manifest
                return result
        raise NotFoundError(f"no preserved evidence for source {source_id}")

    def register_deployment(self, manifest: dict[str, Any], *, actor: str, activate: bool = False) -> str:
        required = {"machine_id", "role", "release_id", "source_sha256", "environment_sha256", "config_snapshot_id"}
        missing = sorted(required - set(manifest))
        if missing:
            raise ValueError(f"deployment manifest missing: {', '.join(missing)}")
        deployment_identity = {
            key: manifest[key]
            for key in ("machine_id", "role", "release_id", "source_sha256", "environment_sha256", "config_snapshot_id")
        }
        deployment_id = f"dep-{content_hash(deployment_identity)[:16]}"
        now = utc_now()
        with self.transaction() as db:
            machine = db.execute("SELECT role FROM machines WHERE id=?", (manifest["machine_id"],)).fetchone()
            if machine is None:
                raise NotFoundError(f"machine not configured: {manifest['machine_id']}")
            if machine[0] != manifest["role"]:
                raise ConflictError("deployment role does not match configured machine role")
            db.execute(
                """INSERT OR IGNORE INTO deployments
                   (id,machine_id,role,release_id,source_sha256,environment_sha256,config_snapshot_id,status,manifest_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    deployment_id, manifest["machine_id"], manifest["role"], manifest["release_id"],
                    manifest["source_sha256"], manifest["environment_sha256"], manifest["config_snapshot_id"],
                    "candidate", canonical_json(manifest), now,
                ),
            )
            if activate:
                db.execute("UPDATE deployments SET status='retired' WHERE machine_id=? AND status='active'", (manifest["machine_id"],))
                db.execute("UPDATE deployments SET status='active',activated_at=? WHERE id=?", (now, deployment_id))
            self._event(db, "deployment", deployment_id, "deployment.registered", actor, {"active": activate, **manifest})
        return deployment_id

    def reject_deployment(self, deployment_id: str, *, reason: str, actor: str) -> None:
        with self.transaction() as db:
            row = db.execute("SELECT status FROM deployments WHERE id=?", (deployment_id,)).fetchone()
            if row is None:
                raise NotFoundError(deployment_id)
            if row[0] == "active":
                raise SafetyError("an active deployment must be retired through replacement, not rejected")
            db.execute("UPDATE deployments SET status='rejected' WHERE id=?", (deployment_id,))
            self._event(db, "deployment", deployment_id, "deployment.rejected", actor, {"reason": reason})

    def create_job(
        self,
        bundle: ConfigBundle,
        *,
        job_type: str,
        input_payload: dict[str, Any],
        idempotency_key: str,
        created_by: str,
        campaign_id: str | None = None,
        requested_machine_id: str | None = None,
        approved: bool = False,
        available_at: str | None = None,
    ) -> dict[str, Any]:
        definition = bundle.jobs.get(job_type)
        if definition is None:
            raise NotFoundError(f"unknown job type: {job_type}")
        if not definition["enabled"]:
            raise SafetyError(f"job type is disabled: {job_type}")
        if definition["requires_live_execution"] and not bundle.base["safety"]["live_execution"]:
            raise SafetyError("live execution is disabled by active safety configuration")
        route = bundle.routes[definition["provider_route"]]
        if not route["enabled"]:
            raise SafetyError(f"provider route is disabled: {definition['provider_route']}")
        remote_models = [
            bundle.models[model_id]
            for model_id in route["ordered_model_ids"]
            if not bundle.models[model_id]["local"]
        ]
        if remote_models and not bundle.budget["external_calls_enabled"]:
            raise SafetyError("external provider calls are disabled by budget policy")
        metered_models = [
            model for model in remote_models
            if bundle.providers[model["provider"]]["kind"] == "openai_compatible"
        ]
        reserved_usd = route["max_cost_usd"] if metered_models else 0.0
        repo_root = bundle.root.parent.parent
        schema = load_schema(repo_root, definition["input_schema"])
        errors = validate(input_payload, schema)
        if errors:
            raise ValueError("invalid job input: " + "; ".join(errors))
        if job_type == "executor.generate":
            validate_lesson_specification(input_payload["specification"], bundle.identity_policy)
        artifact_ids = self._artifact_ids(definition, input_payload)
        config = self.active_config()
        if config["sha256"] != bundle.sha256:
            raise ConflictError("loaded configuration is not the active configuration")
        job_id = f"job-{uuid.uuid4()}"
        now = utc_now()
        approval_policy = definition["approval"]
        approval_threshold = bundle.budget["per_run_approval_above"]
        budget_approval = bool(approval_threshold > 0 and reserved_usd > approval_threshold)
        status = "queued" if (approval_policy == "none" and not budget_approval) or approved else "awaiting_approval"
        input_json = canonical_json(input_payload)
        with self.transaction() as db:
            for artifact_id in artifact_ids:
                if db.execute("SELECT 1 FROM artifacts WHERE id=? AND lifecycle!='deleted'", (artifact_id,)).fetchone() is None:
                    raise NotFoundError(f"input artifact does not exist: {artifact_id}")
            existing = db.execute("SELECT * FROM jobs WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if existing is not None:
                result = dict(existing)
                if result["job_type"] != job_type or result["input_sha256"] != content_hash(input_payload):
                    raise ConflictError("idempotency key was already used for different work")
                return result
            if campaign_id is not None and db.execute("SELECT 1 FROM campaigns WHERE id=?", (campaign_id,)).fetchone() is None:
                raise NotFoundError(f"campaign does not exist: {campaign_id}")
            if job_type == "executor.generate":
                if campaign_id is None:
                    raise SafetyError("lesson generation requires an explicit campaign")
                campaign_row = db.execute(
                    "SELECT state,metadata_json FROM campaigns WHERE id=?", (campaign_id,),
                ).fetchone()
                if campaign_row["state"] != "active":
                    raise SafetyError("lesson generation requires an active campaign")
                campaign_metadata = json.loads(campaign_row["metadata_json"])
                contract = validate_campaign_contract(
                    campaign_metadata.get("campaign_contract"), bundle.campaign_modes,
                )
                specification = input_payload["specification"]
                if any((
                    specification["campaign_contract_sha256"] != campaign_contract_sha256(contract),
                    specification["training_mode"] != contract["mode"],
                    specification["development_stage"] != contract["development_stage"],
                    specification["campaign_purpose"] != contract["purpose"],
                )):
                    raise SafetyError(
                        "lesson specification does not exactly match its immutable campaign purpose and developmental stage"
                    )
            if job_type == "model.evaluate":
                if campaign_id is None:
                    raise SafetyError("evaluation requires an explicit campaign")
                campaign_row = db.execute(
                    "SELECT state,metadata_json FROM campaigns WHERE id=?", (campaign_id,),
                ).fetchone()
                if campaign_row["state"] != "active":
                    raise SafetyError("evaluation requires an active campaign")
                campaign_metadata = json.loads(campaign_row["metadata_json"])
                contract = validate_campaign_contract(
                    campaign_metadata.get("campaign_contract"), bundle.campaign_modes,
                )
                supplied_context = input_payload["evaluation_context"]
                historical = campaign_metadata.get("completed_branch_evidence", {})
                if not isinstance(historical, dict):
                    raise SafetyError("campaign completed-branch evidence must be a mapping")
                completed_branches: set[str] = set(historical)
                for completed_row in db.execute(
                    "SELECT input_json FROM jobs WHERE campaign_id=? AND job_type='model.evaluate' AND status='succeeded'",
                    (campaign_id,),
                ).fetchall():
                    completed_context = json.loads(completed_row[0]).get("evaluation_context", {})
                    if (
                        completed_context.get("campaign_contract_sha256") == campaign_contract_sha256(contract)
                        and completed_context.get("branch_complete") is True
                    ):
                        completed_branch = completed_context.get("branch_id")
                        if isinstance(completed_branch, str):
                            completed_branches.add(completed_branch)
                phase = supplied_context["phase"]
                branch_id = supplied_context["branch_id"]
                branch_complete = self._candidate_completes_cortex_branch(
                    db, input_payload["candidate_artifact_id"], branch_id,
                ) if contract["mode"] == "evolutionary" else True
                if contract["mode"] == "evolutionary":
                    actual_complete = set(contract["branches"]) <= (
                        completed_branches | ({branch_id} if branch_complete else set())
                    )
                elif contract["mode"] == "merge":
                    if phase == "merge_specialist":
                        actual_complete = set(contract["merge_sources"]) <= (completed_branches | {branch_id})
                    else:
                        actual_complete = set(contract["merge_sources"]) <= completed_branches
                else:
                    actual_complete = True
                expected_context = expected_evaluation_context(
                    contract,
                    bundle.campaign_modes,
                    phase=phase,
                    branch_id=branch_id,
                    all_required_branches_complete=actual_complete,
                    branch_complete=branch_complete,
                )
                if supplied_context != expected_context:
                    raise SafetyError(
                        "evaluation context does not exactly match the immutable campaign contract"
                    )
            training_plan = None
            if job_type in {"model.train", "model.visual_train"}:
                training_plan = self._training_session_plan(
                    db, bundle, job_type=job_type, input_payload=input_payload,
                    campaign_id=campaign_id, require_certificate=True,
                )
            if reserved_usd:
                now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
                weekly_since = (now_dt - timedelta(days=7)).isoformat(timespec="microseconds").replace("+00:00", "Z")
                monthly_since = (now_dt - timedelta(days=30)).isoformat(timespec="microseconds").replace("+00:00", "Z")
                weekly_used = float(db.execute("SELECT COALESCE(SUM(reserved_usd),0) FROM budget_reservations WHERE created_at>=?", (weekly_since,)).fetchone()[0])
                monthly_used = float(db.execute("SELECT COALESCE(SUM(reserved_usd),0) FROM budget_reservations WHERE created_at>=?", (monthly_since,)).fetchone()[0])
                weekly_limit = bundle.budget["weekly_limit"]
                monthly_limit = bundle.budget["monthly_limit"]
                weekly_exceeded = weekly_limit > 0 and weekly_used + reserved_usd > weekly_limit * bundle.budget["hard_stop_fraction"] - bundle.budget["emergency_reserve"]
                monthly_exceeded = monthly_limit > 0 and monthly_used + reserved_usd > monthly_limit * bundle.budget["hard_stop_fraction"] - bundle.budget["emergency_reserve"]
                if weekly_exceeded or monthly_exceeded:
                    raise SafetyError("metered provider budget hard stop would be exceeded")
            if available_at is not None:
                try:
                    datetime.fromisoformat(available_at.replace("Z", "+00:00"))
                except (TypeError, ValueError) as exc:
                    raise ValueError("available_at must be an ISO-8601 timestamp") from exc
            if available_at is None and job_type == "campaign.decide" and campaign_id is not None:
                terminal = db.execute(
                    """SELECT MAX(r.finished_at) FROM runs r JOIN jobs j ON j.id=r.job_id
                       WHERE j.campaign_id=? AND r.status IN ('succeeded','failed','blocked','cancelled','expired')
                         AND r.finished_at IS NOT NULL""",
                    (campaign_id,),
                ).fetchone()[0]
                if terminal is not None:
                    available_at = strategic_available_at(
                        terminal, bundle.orchestration["strategic_boundary_cooldown_seconds"],
                    )
            db.execute(
                """INSERT INTO jobs
                   (id,idempotency_key,job_type,job_version,status,config_snapshot_id,campaign_id,
                    requested_machine_id,input_json,input_sha256,priority,approval_policy,approved_by,
                    approved_at,created_by,created_at,updated_at,available_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    job_id, idempotency_key, job_type, definition["version"], status, config["id"], campaign_id,
                    requested_machine_id, input_json, content_hash(input_payload), definition["priority"],
                    approval_policy, created_by if approved else None, now if approved else None, created_by, now, now,
                    available_at,
                ),
            )
            if reserved_usd:
                db.execute(
                    "INSERT INTO budget_reservations(job_id,route_id,reserved_usd,created_at) VALUES(?,?,?,?)",
                    (job_id, route["id"], reserved_usd, now),
                )
            if training_plan is not None:
                db.execute(
                    """INSERT INTO training_session_plans
                       (id,campaign_id,session_id,job_id,parent_checkpoint_artifact_id,
                        subject_artifact_id,validation_artifact_id,ordered_concepts_json,
                        parent_knowledge_sha256,plan_sha256,status,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        f"session-plan-{training_plan['plan_sha256'][:16]}", campaign_id,
                        training_plan["session_id"], job_id,
                        training_plan["parent_checkpoint_artifact_id"],
                        training_plan["subject_artifact_id"],
                        training_plan["validation_artifact_id"],
                        canonical_json(training_plan["ordered_concepts"]),
                        training_plan["parent_knowledge_sha256"],
                        training_plan["plan_sha256"], "admitted", now,
                    ),
                )
                self._event(
                    db, "training_session", training_plan["session_id"],
                    "training_session.admitted", created_by,
                    {"job_id": job_id, "plan_sha256": training_plan["plan_sha256"]},
                )
            self._event(db, "job", job_id, "job.created", created_by, {"job_type": job_type, "status": status, "available_at": available_at})
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row)

    def create_visual_workflow(self, bundle: ConfigBundle, specification: dict[str, Any], *, actor: str) -> dict[str, Any]:
        schema = load_schema(bundle.root.parent.parent, "schemas/mission_hub/workflows/visual-workflow.schema.json")
        errors = validate(specification, schema)
        if errors:
            raise ValueError("invalid visual workflow: " + "; ".join(errors))
        chain = (
            "visual.plan", "visual.generate", "visual.inspect", "visual.caption", "visual.decide",
            "visual.review", "visual.pack_finalize", "visual.encode", "visual.experience_compile",
        )
        if not bundle.base["safety"]["live_execution"] or any(not bundle.jobs[job_type]["enabled"] for job_type in chain):
            raise SafetyError("the complete visual workflow and live execution must be commissioned before a workflow can be created")
        for job_type in chain:
            definition = bundle.jobs[job_type]
            route = bundle.routes[definition["provider_route"]]
            if not route["enabled"]:
                raise SafetyError(f"visual workflow route is disabled: {route['id']}")
            for model_id in route["ordered_model_ids"]:
                model = bundle.models[model_id]
                if not model["enabled"] or not bundle.providers[model["provider"]]["enabled"]:
                    raise SafetyError(f"visual workflow model or provider is disabled: {model_id}")
        active = self.active_config()
        if active["sha256"] != bundle.sha256:
            raise ConflictError("loaded configuration is not the active configuration")
        workflow_id = f"visual-{uuid.uuid4()}"
        campaign_id = specification["campaign_id"]
        now = utc_now()
        with self.transaction() as db:
            campaign = db.execute("SELECT state FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
            if campaign is None:
                raise NotFoundError(campaign_id)
            if campaign["state"] != "active":
                raise SafetyError("visual workflow requires an active campaign")
            db.execute(
                "INSERT INTO visual_workflows(id,campaign_id,status,specification_json,config_snapshot_id,created_by,created_at,updated_at) VALUES(?,?,'active',?,?,?,?,?)",
                (workflow_id, campaign_id, canonical_json(specification), active["id"], actor, now, now),
            )
            self._event(db, "visual_workflow", workflow_id, "visual_workflow.created", actor, {"campaign_id": campaign_id})
        return self.visual_workflow(workflow_id)

    def visual_workflow(self, workflow_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM visual_workflows WHERE id=?", (workflow_id,)).fetchone()
            if row is None:
                raise NotFoundError(workflow_id)
            jobs = db.execute(
                "SELECT w.stage_key,j.* FROM visual_workflow_jobs w JOIN jobs j ON j.id=w.job_id WHERE w.workflow_id=? ORDER BY w.created_at,w.stage_key",
                (workflow_id,),
            ).fetchall()
        result = dict(row)
        result["specification"] = json.loads(result.pop("specification_json"))
        result["jobs"] = [dict(item) for item in jobs]
        return result

    def active_visual_workflows(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT id FROM visual_workflows WHERE status='active' ORDER BY created_at").fetchall()
        return [self.visual_workflow(row[0]) for row in rows]

    def link_visual_workflow_job(self, workflow_id: str, stage_key: str, job_id: str, *, actor: str) -> None:
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO visual_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES(?,?,?,?)",
                (workflow_id, stage_key, job_id, now),
            )
            self._event(db, "visual_workflow", workflow_id, "visual_workflow.stage_created", actor, {"stage_key": stage_key, "job_id": job_id})

    def workflow_job_artifacts(self, job_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], str | None]:
        with self._connect() as db:
            job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if job is None:
                raise NotFoundError(job_id)
            run = db.execute("SELECT * FROM runs WHERE job_id=? AND status='succeeded' ORDER BY attempt DESC LIMIT 1", (job_id,)).fetchone()
            artifacts = [] if run is None else db.execute("SELECT * FROM artifacts WHERE producing_run_id=? ORDER BY kind,id", (run["id"],)).fetchall()
        return dict(job), [dict(item) | {"manifest": json.loads(item["manifest_json"])} for item in artifacts], None if run is None else run["finished_at"]

    def finish_visual_workflow(self, workflow_id: str, status: str, *, actor: str, reason: str = "") -> None:
        if status not in {"shadow_complete", "succeeded", "failed", "cancelled"}:
            raise ValueError("invalid visual workflow terminal status")
        now = utc_now()
        with self.transaction() as db:
            db.execute("UPDATE visual_workflows SET status=?,updated_at=? WHERE id=? AND status='active'", (status, now, workflow_id))
            self._event(db, "visual_workflow", workflow_id, f"visual_workflow.{status}", actor, {"reason": reason})

    def create_cortex_workflow(self, bundle: ConfigBundle, specification: dict[str, Any], *, actor: str) -> dict[str, Any]:
        schema = load_schema(bundle.root.parent.parent, "schemas/mission_hub/workflows/cortex-workflow.schema.json")
        errors = validate(specification, schema)
        if errors:
            raise ValueError("invalid Cortex workflow: " + "; ".join(errors))
        if not bundle.base["safety"]["live_execution"]:
            raise SafetyError("live execution must be commissioned before a Cortex workflow can be authorized")
        if any(not bundle.jobs[job_type]["enabled"] for job_type in ("model.train", "model.evaluate")):
            raise SafetyError("Cortex training and evaluation jobs must both be commissioned")
        active = self.active_config()
        if active["sha256"] != bundle.sha256:
            raise ConflictError("loaded configuration is not the active configuration")
        with self._connect() as db:
            campaign = db.execute("SELECT state,metadata_json FROM campaigns WHERE id=?", (specification["campaign_id"],)).fetchone()
            if campaign is None:
                raise NotFoundError(specification["campaign_id"])
            metadata = json.loads(campaign["metadata_json"])
            contract = validate_campaign_contract(metadata.get("campaign_contract"), bundle.campaign_modes)
            if campaign["state"] not in {"active", "paused"}:
                raise SafetyError("Cortex workflow campaign must be active or paused")
            if specification["branch_id"] not in contract["branches"]:
                raise SafetyError("Cortex workflow branch is not declared by its campaign contract")
            if specification["starting_checkpoint_artifact_id"] != metadata.get("starting_checkpoint_artifact_id"):
                raise SafetyError("Cortex workflow must start from the campaign's exact baseline artifact")
            for artifact_id, kind in (
                (specification["starting_checkpoint_artifact_id"], "checkpoint"),
                (specification["evaluation_suite_artifact_id"], "evaluation_suite"),
            ):
                artifact = db.execute("SELECT kind FROM artifacts WHERE id=? AND lifecycle!='deleted'", (artifact_id,)).fetchone()
                if artifact is None or artifact[0] != kind:
                    raise SafetyError(f"Cortex workflow requires a registered {kind} artifact")
        specification_json = canonical_json(specification)
        with self._connect() as db:
            prior = db.execute(
                "SELECT id,status,specification_json FROM cortex_workflows WHERE campaign_id=? ORDER BY created_at",
                (specification["campaign_id"],),
            ).fetchall()
        branch_rows = [
            row for row in prior
            if json.loads(row["specification_json"]).get("branch_id") == specification["branch_id"]
        ]
        exact_rows = [row for row in branch_rows if row["specification_json"] == specification_json]
        active_exact = [row for row in exact_rows if row["status"] == "active"]
        if active_exact:
            return self.cortex_workflow(active_exact[-1]["id"])
        if any(row["status"] == "active" for row in branch_rows):
            raise ConflictError(
                "an active Cortex workflow already owns this campaign branch with different bytes"
            )
        if exact_rows:
            return self.cortex_workflow(exact_rows[-1]["id"])
        if branch_rows:
            raise SafetyError(
                "a completed/terminal campaign branch cannot be silently re-authorized with a different workflow"
            )
        workflow_id = f"cortex-{uuid.uuid4()}"
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                "INSERT INTO cortex_workflows(id,campaign_id,status,specification_json,config_snapshot_id,authorized_by,created_at,updated_at) VALUES(?,?,'active',?,?,?,?,?)",
                (workflow_id, specification["campaign_id"], specification_json, active["id"], actor, now, now),
            )
            self._event(db, "cortex_workflow", workflow_id, "cortex_workflow.authorized", actor, {
                "branch_id": specification["branch_id"], "session_count": len(specification["sessions"]),
                "authorization_scope": "exact_immutable_workflow",
            })
        return self.cortex_workflow(workflow_id)

    def restart_failed_cortex_workflow(
        self, bundle: ConfigBundle, workflow_id: str, *, reason: str, actor: str,
    ) -> dict[str, Any]:
        """Authorize an exact clean repeat after an evidenced implementation fault.

        The failed workflow, runs, candidate bytes, and incidents remain
        untouched.  A new workflow receives the identical specification and
        starts from the same parent; no stage job is reused or silently reset.
        """
        reason = reason.strip()
        if not reason or len(reason.encode("utf-8")) > 4096:
            raise ValueError("Cortex restart requires a bounded operator reason")
        active = self.active_config()
        if active["sha256"] != bundle.sha256:
            raise ConflictError("loaded configuration is not active")
        now = utc_now()
        with self.transaction() as db:
            workflow = db.execute(
                "SELECT * FROM cortex_workflows WHERE id=?", (workflow_id,),
            ).fetchone()
            if workflow is None:
                raise NotFoundError(workflow_id)
            if workflow["status"] != "failed":
                raise TransitionError(f"Cortex workflow {workflow_id} is {workflow['status']}, not failed")
            control = db.execute(
                "SELECT desired_state FROM pipeline_control WHERE id='pipeline'",
            ).fetchone()
            if control is None or control[0] != "paused":
                raise SafetyError("Cortex restart requires the pipeline to be paused")
            if db.execute(
                "SELECT COUNT(*) FROM runs WHERE status IN ('leased','running')",
            ).fetchone()[0]:
                raise SafetyError("Cortex restart requires a globally quiet run boundary")
            failed = db.execute(
                """SELECT w.stage_key,j.id AS job_id,r.id AS run_id,r.machine_id,
                          r.deployment_id,r.failure_class,r.failure_code,r.failure_json
                   FROM cortex_workflow_jobs w
                   JOIN jobs j ON j.id=w.job_id AND j.status='failed'
                   JOIN runs r ON r.job_id=j.id
                   WHERE w.workflow_id=? AND r.attempt=(
                       SELECT MAX(r2.attempt) FROM runs r2 WHERE r2.job_id=j.id
                   )""",
                (workflow_id,),
            ).fetchall()
            if len(failed) != 1:
                raise SafetyError("Cortex restart requires exactly one failed stage and terminal run")
            failure = failed[0]
            failure_body = json.loads(failure["failure_json"] or "{}")
            commissioned_contract_bug = (
                failure["failure_code"] == "unexpected_internal_error"
                and str(failure_body.get("message", "")).startswith(
                    "Cortex training report does not match the commissioned session contract"
                )
            )
            if not commissioned_contract_bug:
                raise SafetyError("Cortex clean restart is limited to the evidenced training-report contract fault")
            if failure["stage_key"] != "s00:train":
                raise SafetyError("Cortex clean restart currently requires a first-stage training contract fault")
            failed_job = db.execute(
                "SELECT * FROM jobs WHERE id=?", (failure["job_id"],),
            ).fetchone()
            plan = db.execute(
                "SELECT * FROM training_session_plans WHERE job_id=? AND status='admitted'",
                (failure["job_id"],),
            ).fetchone()
            if failed_job is None or failed_job["job_type"] != "model.train" or plan is None:
                raise SafetyError("failed Cortex training has no exact admitted session plan to rebind")
            replacement = db.execute(
                "SELECT id FROM deployments WHERE machine_id=? AND status='active'",
                (failure["machine_id"],),
            ).fetchone()
            if replacement is None or replacement["id"] == failure["deployment_id"]:
                raise SafetyError("Cortex restart requires a replacement active deployment")
            specification = json.loads(workflow["specification_json"])
            branch_id = specification["branch_id"]
            for row in db.execute(
                "SELECT id,specification_json FROM cortex_workflows WHERE campaign_id=? AND status='active'",
                (workflow["campaign_id"],),
            ).fetchall():
                if json.loads(row["specification_json"]).get("branch_id") == branch_id:
                    raise ConflictError(f"active Cortex workflow already owns branch: {row['id']}")
            restarted_id = f"cortex-{uuid.uuid4()}"
            db.execute(
                """INSERT INTO cortex_workflows
                   (id,campaign_id,status,specification_json,config_snapshot_id,
                    authorized_by,created_at,updated_at)
                   VALUES(?,?,'active',?,?,?,?,?)""",
                (
                    restarted_id, workflow["campaign_id"], workflow["specification_json"],
                    active["id"], actor, now, now,
                ),
            )
            replacement_job_id = f"job-{uuid.uuid4()}"
            db.execute(
                """INSERT INTO jobs
                   (id,idempotency_key,job_type,job_version,status,config_snapshot_id,campaign_id,
                    requested_machine_id,input_json,input_sha256,priority,approval_policy,approved_by,
                    approved_at,created_by,created_at,updated_at,available_at)
                   VALUES(?,?,?,?, 'queued',?,?,?,?,?,?,?,?,?,?,?,?,NULL)""",
                (
                    replacement_job_id, f"cortex-workflow:{restarted_id}:s00:train",
                    failed_job["job_type"], failed_job["job_version"], active["id"],
                    failed_job["campaign_id"], failed_job["requested_machine_id"],
                    failed_job["input_json"], failed_job["input_sha256"], failed_job["priority"],
                    failed_job["approval_policy"], actor, now, actor, now, now,
                ),
            )
            db.execute(
                "UPDATE training_session_plans SET job_id=? WHERE id=?",
                (replacement_job_id, plan["id"]),
            )
            db.execute(
                "INSERT INTO cortex_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES(?,?,?,?)",
                (restarted_id, "s00:train", replacement_job_id, now),
            )
            evidence = {
                "restart_of": workflow_id,
                "failed_stage": failure["stage_key"],
                "failed_job_id": failure["job_id"],
                "failed_run_id": failure["run_id"],
                "replacement_job_id": replacement_job_id,
                "failed_deployment_id": failure["deployment_id"],
                "replacement_deployment_id": replacement["id"],
                "failure_class": failure["failure_class"],
                "failure_code": failure["failure_code"],
                "specification_sha256": content_hash(specification),
                "reason": reason,
            }
            self._event(db, "cortex_workflow", workflow_id, "cortex_workflow.clean_restart_authorized", actor, {
                **evidence, "restarted_workflow_id": restarted_id,
            })
            self._event(db, "cortex_workflow", restarted_id, "cortex_workflow.authorized", actor, evidence)
            self._event(db, "training_session", plan["session_id"], "training_session.rebound_after_failed_workflow", actor, {
                "plan_sha256": plan["plan_sha256"],
                "failed_job_id": failure["job_id"],
                "replacement_job_id": replacement_job_id,
                "failed_workflow_id": workflow_id,
                "replacement_workflow_id": restarted_id,
            })
            self._event(db, "job", replacement_job_id, "job.created", actor, {
                "job_type": failed_job["job_type"], "status": "queued",
                "clean_restart_of_job_id": failure["job_id"],
            })
        return self.cortex_workflow(restarted_id)

    def cortex_workflow(self, workflow_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM cortex_workflows WHERE id=?", (workflow_id,)).fetchone()
            if row is None:
                raise NotFoundError(workflow_id)
            jobs = db.execute(
                "SELECT w.stage_key,j.* FROM cortex_workflow_jobs w JOIN jobs j ON j.id=w.job_id WHERE w.workflow_id=? ORDER BY w.created_at,w.stage_key",
                (workflow_id,),
            ).fetchall()
        result = dict(row)
        result["specification"] = json.loads(result.pop("specification_json"))
        result["jobs"] = [dict(item) for item in jobs]
        return result

    def active_cortex_workflows(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT id FROM cortex_workflows WHERE status='active' ORDER BY created_at").fetchall()
        return [self.cortex_workflow(row[0]) for row in rows]

    @staticmethod
    def _candidate_completes_cortex_branch(
        db: sqlite3.Connection, candidate_artifact_id: str, branch_id: str,
    ) -> bool:
        """Prove branch completion from durable workflow lineage.

        Evaluation input is untrusted here: only a checkpoint emitted by the
        final training stage of the same authorized Cortex workflow can finish
        an evolutionary branch, and every preceding evaluation must already
        have succeeded.  Manually submitted/intermediate evaluations therefore
        fail closed instead of advancing experiment-wide comparison state.
        """
        row = db.execute(
            """
            SELECT w.stage_key,c.id AS workflow_id,c.specification_json
            FROM artifacts a
            JOIN runs r ON r.id=a.producing_run_id AND r.status='succeeded'
            JOIN cortex_workflow_jobs w ON w.job_id=r.job_id
            JOIN cortex_workflows c ON c.id=w.workflow_id AND c.status='active'
            WHERE a.id=? AND a.kind='checkpoint'
            """,
            (candidate_artifact_id,),
        ).fetchone()
        if row is None:
            return False
        match = re.fullmatch(r"s(\d+):train", row["stage_key"])
        if match is None:
            return False
        specification = json.loads(row["specification_json"])
        session_index = int(match.group(1))
        sessions = specification.get("sessions")
        if (
            specification.get("branch_id") != branch_id
            or not isinstance(sessions, list)
            or session_index != len(sessions) - 1
        ):
            return False
        workflow_id = row["workflow_id"]
        for index in range(session_index):
            completed = db.execute(
                """
                SELECT 1
                FROM cortex_workflow_jobs w
                JOIN jobs j ON j.id=w.job_id
                WHERE w.workflow_id=? AND w.stage_key=? AND j.status='succeeded'
                """,
                (workflow_id, f"s{index:02d}:evaluate"),
            ).fetchone()
            if completed is None:
                return False
        return True

    def link_cortex_workflow_job(self, workflow_id: str, stage_key: str, job_id: str, *, actor: str) -> None:
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                "INSERT OR IGNORE INTO cortex_workflow_jobs(workflow_id,stage_key,job_id,created_at) VALUES(?,?,?,?)",
                (workflow_id, stage_key, job_id, now),
            )
            self._event(db, "cortex_workflow", workflow_id, "cortex_workflow.stage_created", actor, {
                "stage_key": stage_key, "job_id": job_id,
            })

    def finish_cortex_workflow(
        self, workflow_id: str, status: str, *, actor: str, reason: str = "",
        pause_pipeline: bool = False,
    ) -> None:
        if status not in {"succeeded", "blocked", "failed", "cancelled"}:
            raise ValueError("invalid Cortex workflow terminal status")
        now = utc_now()
        with self.transaction() as db:
            updated = db.execute(
                "UPDATE cortex_workflows SET status=?,updated_at=? WHERE id=? AND status='active'",
                (status, now, workflow_id),
            ).rowcount
            self._event(db, "cortex_workflow", workflow_id, f"cortex_workflow.{status}", actor, {"reason": reason})
            if updated and pause_pipeline:
                control = db.execute(
                    "SELECT desired_state FROM pipeline_control WHERE id='pipeline'",
                ).fetchone()
                if control is not None and control[0] != "paused":
                    db.execute(
                        "UPDATE pipeline_control SET desired_state='paused',requested_by=?,requested_at=? WHERE id='pipeline'",
                        (actor, now),
                    )
                    self._event(db, "pipeline", "pipeline", "pipeline.paused_requested", actor, {
                        "semantics": "authorized_workflow_complete_wait_for_operator",
                        "workflow_id": workflow_id,
                    })

    def retry_failed_cortex_stage(
        self, bundle: ConfigBundle, workflow_id: str, *, reason: str, actor: str,
    ) -> dict[str, Any]:
        """Explicitly requeue one evidence-reviewed infrastructure failure.

        The same job, training-session admission, corpus, parent, order
        certificate, and workflow bytes are retained. Nothing is regenerated,
        and deterministic model/specification failures cannot use this path.
        """
        reason = reason.strip()
        if not reason or len(reason.encode("utf-8")) > 4096:
            raise ValueError("Cortex retry requires a bounded operator reason")
        active = self.active_config()
        if active["sha256"] != bundle.sha256:
            raise ConflictError("loaded configuration is not active")
        now = utc_now()
        with self.transaction() as db:
            workflow = db.execute(
                "SELECT * FROM cortex_workflows WHERE id=?", (workflow_id,),
            ).fetchone()
            if workflow is None:
                raise NotFoundError(workflow_id)
            if workflow["status"] != "failed":
                raise TransitionError(f"Cortex workflow {workflow_id} is {workflow['status']}, not failed")
            failed = db.execute(
                """SELECT w.stage_key,j.* FROM cortex_workflow_jobs w
                   JOIN jobs j ON j.id=w.job_id
                   WHERE w.workflow_id=? AND j.status='failed' ORDER BY w.created_at,w.stage_key""",
                (workflow_id,),
            ).fetchall()
            if len(failed) != 1:
                raise SafetyError("Cortex recovery requires exactly one failed workflow stage")
            job = failed[0]
            run = db.execute(
                "SELECT * FROM runs WHERE job_id=? ORDER BY attempt DESC LIMIT 1", (job["id"],),
            ).fetchone()
            if run is None or run["status"] != "failed":
                raise SafetyError("failed Cortex stage has no terminal failed run evidence")
            failure = json.loads(run["failure_json"] or "{}")
            historical_transport_bug = (
                failure.get("code") == "unexpected_internal_error"
                and str(failure.get("message", "")).startswith("TimeoutExpired: Command '['ssh'")
            )
            if run["failure_class"] != "operational_transient" and not historical_transport_bug:
                raise SafetyError("only an evidenced infrastructure failure can be retried in place")
            definition = bundle.jobs[job["job_type"]]
            if run["attempt"] >= definition["max_attempts"]:
                raise SafetyError("Cortex stage has exhausted its configured operator attempts")
            live = db.execute(
                "SELECT COUNT(*) FROM runs WHERE status IN ('leased','running')",
            ).fetchone()[0]
            if live:
                raise SafetyError("Cortex recovery requires a globally quiet run boundary")
            db.execute(
                "UPDATE jobs SET status='queued',available_at=NULL,updated_at=? WHERE id=?",
                (now, job["id"]),
            )
            db.execute(
                """UPDATE cortex_workflows
                   SET status='active',reauthorized_config_snapshot_id=?,updated_at=? WHERE id=?""",
                (active["id"], now, workflow_id),
            )
            evidence = {
                "stage_key": job["stage_key"], "job_id": job["id"],
                "failed_run_id": run["id"], "failed_attempt": run["attempt"],
                "failure_class": run["failure_class"], "failure_code": run["failure_code"],
                "historical_transport_classification_corrected": historical_transport_bug,
                "reason": reason,
            }
            self._event(db, "job", job["id"], "job.operator_retry_authorized", actor, evidence)
            self._event(db, "cortex_workflow", workflow_id, "cortex_workflow.reauthorized", actor, evidence)
        return self.cortex_workflow(workflow_id)

    def approve_job(self, job_id: str, *, actor: str) -> None:
        now = utc_now()
        with self.transaction() as db:
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise NotFoundError(job_id)
            if row[0] != "awaiting_approval":
                raise TransitionError(f"job {job_id} is {row[0]}, not awaiting approval")
            db.execute(
                "UPDATE jobs SET status='queued',approved_by=?,approved_at=?,updated_at=? WHERE id=?",
                (actor, now, now, job_id),
            )
            self._event(db, "job", job_id, "job.approved", actor, {})

    def lease_next(
        self,
        bundle: ConfigBundle,
        *,
        machine_id: str,
        deployment_id: str,
        actor: str,
    ) -> tuple[dict[str, Any], str] | None:
        now = utc_now()
        machine = bundle.machines.get(machine_id)
        if machine is None or not machine["enabled"] or machine["maintenance_mode"]:
            raise SafetyError(f"machine {machine_id} is disabled or in maintenance mode")
        config = self.active_config()
        if config["sha256"] != bundle.sha256:
            raise ConflictError("agent requested a lease with a non-active configuration")
        with self.transaction() as db:
            control = db.execute("SELECT desired_state FROM pipeline_control WHERE id='pipeline'").fetchone()
            if control is None:
                return None
            pipeline_running = control[0] == "running"
            deployment = db.execute(
                "SELECT * FROM deployments WHERE id=? AND machine_id=? AND status='active'",
                (deployment_id, machine_id),
            ).fetchone()
            if deployment is None:
                raise SafetyError("machine has no matching active deployment")
            if bundle.base["safety"]["require_config_match"] and deployment["config_snapshot_id"] != config["id"]:
                raise SafetyError("deployment configuration does not match active configuration")
            live_count = db.execute(
                "SELECT COUNT(*) FROM runs WHERE machine_id=? AND status IN ('leased','running')",
                (machine_id,),
            ).fetchone()[0]
            if live_count >= machine["max_concurrent_jobs"]:
                return None
            too_old = _past(bundle.base["scheduler"]["max_queue_age_seconds"])
            stale = db.execute(
                "SELECT id FROM jobs WHERE status='queued' AND created_at<? AND (requested_machine_id IS NULL OR requested_machine_id=?)",
                (too_old, machine_id),
            ).fetchall()
            for stale_job in stale:
                db.execute("UPDATE jobs SET status='blocked',updated_at=? WHERE id=?", (now, stale_job["id"]))
                self._event(db, "job", stale_job["id"], "job.queue_age_exceeded", actor, {})
            allowed = set(machine["allowed_job_types"])
            candidates = db.execute(
                "SELECT * FROM jobs WHERE status='queued' AND (available_at IS NULL OR available_at<=?) AND (requested_machine_id IS NULL OR requested_machine_id=?) ORDER BY priority DESC,created_at,id",
                (now, machine_id),
            ).fetchall()
            job = None
            definition = None
            for candidate in candidates:
                if not pipeline_running and candidate["job_type"] != "model.chat":
                    continue
                if candidate["job_type"] not in allowed:
                    continue
                candidate_definition = bundle.jobs.get(candidate["job_type"])
                if candidate_definition is None or not candidate_definition["enabled"]:
                    continue
                if candidate_definition["executor_role"] != machine["role"]:
                    continue
                if not set(candidate_definition["required_capabilities"]).issubset(set(machine["capabilities"])):
                    continue
                if candidate["job_type"] in {"model.train", "model.visual_train"}:
                    admitted = db.execute(
                        "SELECT 1 FROM training_session_plans WHERE job_id=? AND status='admitted'",
                        (candidate["id"],),
                    ).fetchone()
                    if admitted is None:
                        db.execute("UPDATE jobs SET status='blocked',updated_at=? WHERE id=?", (now, candidate["id"]))
                        self._event(
                            db, "job", candidate["id"], "job.training_session_admission_missing", actor, {},
                        )
                        continue
                artifact_ids = self._artifact_ids(candidate_definition, json.loads(candidate["input_json"]))
                if any(
                    db.execute(
                        "SELECT 1 FROM artifact_locations WHERE artifact_id=? AND machine_id=? AND available=1 LIMIT 1",
                        (artifact_id, machine_id),
                    ).fetchone() is None
                    for artifact_id in artifact_ids
                ):
                    continue
                job = candidate
                definition = candidate_definition
                break
            if job is None or definition is None:
                return None
            attempt_row = db.execute("SELECT COALESCE(MAX(attempt),0)+1 FROM runs WHERE job_id=?", (job["id"],)).fetchone()
            attempt = int(attempt_row[0])
            if attempt > definition["max_attempts"]:
                db.execute("UPDATE jobs SET status='failed',updated_at=? WHERE id=?", (now, job["id"]))
                self._event(db, "job", job["id"], "job.attempts_exhausted", actor, {"attempt": attempt})
                return None
            token = secrets.token_urlsafe(32)
            run_id = f"run-{uuid.uuid4()}"
            expires = _future(bundle.base["scheduler"]["lease_seconds"])
            db.execute(
                """INSERT INTO runs(id,job_id,attempt,machine_id,deployment_id,status,lease_token_sha256,lease_expires_at,heartbeat_at)
                   VALUES(?,?,?,?,?,'leased',?,?,?)""",
                (run_id, job["id"], attempt, machine_id, deployment_id, hashlib.sha256(token.encode()).hexdigest(), expires, now),
            )
            db.execute("UPDATE jobs SET status='leased',updated_at=? WHERE id=?", (now, job["id"]))
            self._event(db, "run", run_id, "run.leased", actor, {"job_id": job["id"], "attempt": attempt, "expires_at": expires})
            result = dict(job)
            result["run_id"] = run_id
            result["attempt"] = attempt
            result["lease_expires_at"] = expires
            result["deployment"] = dict(deployment)
            return result, token

    def start_run(self, run_id: str, token: str, *, actor: str) -> None:
        self._transition_run(run_id, token, expected="leased", target="running", actor=actor, event="run.started")

    def heartbeat_run(self, run_id: str, token: str, *, actor: str, lease_seconds: int) -> str:
        now = utc_now()
        expires = _future(lease_seconds)
        with self.transaction() as db:
            row = self._authorized_run(db, run_id, token)
            if row["status"] not in {"leased", "running"}:
                raise TransitionError(f"run {run_id} is {row['status']}")
            db.execute("UPDATE runs SET heartbeat_at=?,lease_expires_at=? WHERE id=?", (now, expires, run_id))
            self._event(db, "run", run_id, "run.heartbeat", actor, {"lease_expires_at": expires})
        return expires

    def finish_run(
        self,
        bundle: ConfigBundle,
        run_id: str,
        token: str,
        *,
        status: str,
        output: dict[str, Any] | None,
        failure: dict[str, Any] | None,
        actor: str,
    ) -> None:
        if status not in {"succeeded", "failed", "blocked", "cancelled"}:
            raise ValueError(f"invalid terminal run status: {status}")
        now = utc_now()
        failure_recorder = None
        failure_log_path = None
        if status == "failed":
            with self._connect() as inspection:
                inspected_run = self._authorized_run(inspection, run_id, token)
                inspected_job = inspection.execute(
                    "SELECT * FROM jobs WHERE id=?", (inspected_run["job_id"],)
                ).fetchone()
            # Write the operational incident before committing the terminal
            # transition. If durable logging itself fails, the run remains live
            # and therefore fails closed instead of disappearing without a log.
            from .failures import CriticalFailureRecorder
            failure_recorder = CriticalFailureRecorder(bundle)
            failure_log_path = failure_recorder.record(
                job=dict(inspected_job), run=dict(inspected_run), failure=failure or {},
                actor=actor, phase="run_failure", invoke_emergency=False,
            )
        knowledge_campaign_id: str | None = None
        with self.transaction() as db:
            run = self._authorized_run(db, run_id, token)
            if run["status"] not in {"leased", "running"}:
                raise TransitionError(f"run {run_id} is already {run['status']}")
            job = db.execute("SELECT * FROM jobs WHERE id=?", (run["job_id"],)).fetchone()
            definition = bundle.jobs[job["job_type"]]
            if status == "succeeded":
                schema = load_schema(bundle.root.parent.parent, definition["output_schema"])
                errors = validate(output, schema)
                if errors:
                    raise ValueError("invalid job output: " + "; ".join(errors))
                self._register_output_artifacts(
                    db,
                    bundle,
                    definition,
                    output.get("artifacts", []),
                    run_id=run_id,
                    machine_id=run["machine_id"],
                    actor=actor,
                    now=now,
                )
                if job["job_type"] in {"model.train", "model.visual_train"}:
                    plan = db.execute(
                        "SELECT * FROM training_session_plans WHERE job_id=? AND status='admitted'",
                        (job["id"],),
                    ).fetchone()
                    if plan is None:
                        raise SafetyError("successful training run has no admitted immutable session list")
                    checkpoints = db.execute(
                        "SELECT id FROM artifacts WHERE producing_run_id=? AND kind='checkpoint'",
                        (run_id,),
                    ).fetchall()
                    if len(checkpoints) != 1:
                        raise SafetyError("successful training must produce exactly one checkpoint for its knowledge closure")
                    checkpoint_id = checkpoints[0][0]
                    ordered = json.loads(plan["ordered_concepts_json"])
                    self._append_checkpoint_knowledge_db(
                        db, checkpoint_artifact_id=checkpoint_id,
                        parent_checkpoint_artifact_id=plan["parent_checkpoint_artifact_id"],
                        campaign_id=plan["campaign_id"], session_id=plan["session_id"],
                        concepts=[item["concept_label"] for item in ordered],
                        evidence=[plan["subject_artifact_id"], plan["validation_artifact_id"], plan["plan_sha256"]],
                        actor=actor, job_id=job["id"], run_id=run_id, now=now,
                    )
                    db.execute(
                        """UPDATE training_session_plans
                           SET status='completed',completed_at=?,output_checkpoint_artifact_id=? WHERE id=?""",
                        (now, checkpoint_id, plan["id"]),
                    )
                    self._event(
                        db, "training_session", plan["session_id"], "training_session.completed", actor,
                        {"job_id": job["id"], "run_id": run_id, "checkpoint_artifact_id": checkpoint_id},
                    )
                    knowledge_campaign_id = plan["campaign_id"]
            elif status == "failed":
                if failure is None or failure.get("code") not in bundle.failure_codes:
                    raise ValueError("failed run requires a configured failure code")
                configured_failure = bundle.failure_codes[failure["code"]]
                if failure.get("class") != configured_failure["failure_class"]:
                    raise ValueError("failure class does not match configured failure code")
            failure_class = None if failure is None else failure.get("class")
            failure_code = None if failure is None else failure.get("code")
            db.execute(
                """UPDATE runs SET status=?,finished_at=?,heartbeat_at=?,output_json=?,output_sha256=?,
                   failure_class=?,failure_code=?,failure_json=? WHERE id=?""",
                (
                    status, now, now, canonical_json(output) if output is not None else None,
                    content_hash(output) if output is not None else None, failure_class, failure_code,
                    canonical_json(failure) if failure is not None else None, run_id,
                ),
            )
            self._event(db, "run", run_id, f"run.{status}", actor, {"failure_class": failure_class, "failure_code": failure_code})
            next_status = status
            available_at = None
            if status == "failed":
                definition = bundle.jobs[job["job_type"]]
                policy = bundle.retry_policies[definition["retry_policy"]]
                configured_failure = bundle.failure_codes[failure_code]
                retryable = (
                    configured_failure["retryable"]
                    and failure_class in policy["retryable_failure_classes"]
                    and run["attempt"] < min(definition["max_attempts"], policy["max_execution_attempts"])
                )
                if retryable:
                    next_status = "queued"
                    backoff_index = min(run["attempt"] - 1, len(policy["backoff_seconds"]) - 1)
                    backoff = policy["backoff_seconds"][backoff_index] if policy["backoff_seconds"] else 0
                    available_at = _future(backoff)
                    self._event(db, "job", run["job_id"], "job.retry_scheduled", actor, {"after_seconds": backoff, "failure_code": failure_code})
            db.execute("UPDATE jobs SET status=?,available_at=?,updated_at=? WHERE id=?", (next_status, available_at, now, run["job_id"]))
        if knowledge_campaign_id is not None:
            self.sync_knowledge_views(campaign_id=knowledge_campaign_id)
        # Never hold the authoritative SQLite transaction open while an
        # external emergency adviser runs (the configured bound is minutes).
        if failure_recorder is not None:
            failure_recorder.escalate(failure_log_path)
            self._record_lab_incident_notice(failure_log_path)

    def cancel_job(self, job_id: str, *, reason: str, actor: str) -> None:
        now = utc_now()
        with self.transaction() as db:
            job = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if job is None:
                raise NotFoundError(job_id)
            if job[0] in TERMINAL_JOB_STATES:
                raise TransitionError(f"job {job_id} is already {job[0]}")
            db.execute("UPDATE jobs SET status='cancelled',cancel_reason=?,updated_at=? WHERE id=?", (reason, now, job_id))
            db.execute(
                "UPDATE training_session_plans SET status='cancelled' WHERE job_id=? AND status='admitted'",
                (job_id,),
            )
            db.execute(
                "UPDATE runs SET status='cancelled',finished_at=? WHERE job_id=? AND status IN ('leased','running')",
                (now, job_id),
            )
            self._event(db, "job", job_id, "job.cancelled", actor, {"reason": reason})

    def expire_leases(self, bundle: ConfigBundle | None = None, *, actor: str) -> int:
        now = utc_now()
        incidents: list[tuple[dict[str, Any], dict[str, Any]]] = []
        with self.transaction() as db:
            rows = db.execute("SELECT * FROM runs WHERE status IN ('leased','running') AND lease_expires_at<?", (now,)).fetchall()
            for row in rows:
                job = db.execute("SELECT * FROM jobs WHERE id=?", (row["job_id"],)).fetchone()
                incidents.append((dict(job), dict(row)))
                db.execute("UPDATE runs SET status='expired',finished_at=? WHERE id=?", (now, row["id"]))
                db.execute("UPDATE jobs SET status='queued',updated_at=? WHERE id=? AND status IN ('leased','running')", (now, row["job_id"]))
                self._event(db, "run", row["id"], "run.expired", actor, {"job_id": row["job_id"]})
        if bundle is not None:
            from .failures import CriticalFailureRecorder
            recorder = CriticalFailureRecorder(bundle)
            for job, run in incidents:
                path = recorder.record(
                    job=job, run=run,
                    failure={"class": "operational_transient", "code": "lease_expired", "message": "run lease expired before completion"},
                    actor=actor, phase="lease_expiry",
                )
                self._record_lab_incident_notice(path)
        return len(rows)

    def _record_lab_incident_notice(self, path: Path | None) -> None:
        """Mirror a critical incident into the operational inbox.

        The rolling incident file remains the required evidence. Notification
        is deliberately best-effort so a presentation failure cannot reopen or
        corrupt an already committed run transition.
        """
        if path is None:
            return
        try:
            incident = json.loads(path.read_text(encoding="utf-8"))
            failure = incident.get("failure", {})
            job = incident.get("job", {})
            run = incident.get("run", {})
            lines = [
                f"Critical job {job.get('type', 'unknown')} failed.",
                f"Job: {job.get('id', 'unknown')}",
                f"Run: {run.get('id', 'unknown')}",
                f"Failure: {failure.get('code', 'unknown')} ({failure.get('class', 'unknown')})",
                str(failure.get("message", "")),
            ]
            emergency = incident.get("emergency", {})
            advisory = emergency.get("advisory") if isinstance(emergency, dict) else None
            if isinstance(advisory, dict):
                lines.extend(["", "Sol assessment:", str(advisory.get("assessment", ""))])
                actions = advisory.get("operator_actions", [])
                if actions:
                    lines.extend(["", "Recommended operator actions:", *(f"- {item}" for item in actions)])
            from .lab import LabStore
            LabStore(self).system_notice(
                f"Critical failure · {job.get('type', 'unknown')}",
                "\n".join(lines),
                sender="sol" if advisory else "mission_hub",
                actor="mission-hub:critical-failure",
            )
        except Exception:
            return

    def register_artifact(
        self,
        bundle: ConfigBundle,
        *,
        kind: str,
        sha256: str,
        byte_size: int,
        lifecycle: str,
        manifest: dict[str, Any],
        producing_run_id: str | None,
        machine_id: str,
        uri: str,
        actor: str,
    ) -> str:
        if kind not in bundle.artifact_types:
            raise ValueError(f"unknown artifact type: {kind}")
        if lifecycle == "deleted":
            raise SafetyError("artifact deletion requires a separate approved decision")
        if bundle.artifact_types[kind]["content_hash_required"] and (len(sha256) != 64 or any(character not in "0123456789abcdef" for character in sha256)):
            raise ValueError("artifact requires a lowercase SHA-256 content hash")
        machine = bundle.machines.get(machine_id)
        if machine is None:
            raise NotFoundError(f"artifact machine is not configured: {machine_id}")
        normalized_uri = Path(os.path.normpath(uri)).resolve(strict=False)
        allowed_roots = [Path(machine["state_root"]).resolve(strict=False), *(Path(value).resolve(strict=False) for value in machine["artifact_roots"])]
        if not normalized_uri.is_absolute() or not any(normalized_uri == root or root in normalized_uri.parents for root in allowed_roots):
            raise SafetyError(f"artifact URI is outside configured machine roots: {uri}")
        self._require_identity_policy_artifact(bundle, kind=kind, path=normalized_uri, manifest=manifest)
        artifact_id = f"art-{content_hash({'kind': kind, 'sha256': sha256})[:16]}"
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                """INSERT OR IGNORE INTO artifacts(id,kind,producing_run_id,sha256,byte_size,lifecycle,manifest_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (artifact_id, kind, producing_run_id, sha256, byte_size, lifecycle, canonical_json(manifest), now),
            )
            db.execute(
                """INSERT INTO artifact_locations(artifact_id,machine_id,uri,observed_at,available)
                   VALUES(?,?,?,?,1) ON CONFLICT(artifact_id,machine_id,uri)
                   DO UPDATE SET observed_at=excluded.observed_at,available=1""",
                (artifact_id, machine_id, str(normalized_uri), now),
            )
            self._event(db, "artifact", artifact_id, "artifact.registered", actor, {"kind": kind, "sha256": sha256, "uri": str(normalized_uri)})
        return artifact_id

    def resolve_artifacts(self, definition: dict[str, Any], input_payload: dict[str, Any], *, machine_id: str) -> list[dict[str, Any]]:
        artifact_ids = self._artifact_ids(definition, input_payload)
        result: list[dict[str, Any]] = []
        with self._connect() as db:
            for artifact_id in artifact_ids:
                row = db.execute("SELECT * FROM artifacts WHERE id=? AND lifecycle!='deleted'", (artifact_id,)).fetchone()
                if row is None:
                    raise NotFoundError(f"input artifact does not exist: {artifact_id}")
                locations = db.execute(
                    "SELECT uri,observed_at FROM artifact_locations WHERE artifact_id=? AND machine_id=? AND available=1 ORDER BY observed_at DESC",
                    (artifact_id, machine_id),
                ).fetchall()
                if not locations:
                    raise SafetyError(f"artifact {artifact_id} is not available on machine {machine_id}")
                result.append(
                    {
                        "id": row["id"], "kind": row["kind"], "sha256": row["sha256"],
                        "byte_size": row["byte_size"], "lifecycle": row["lifecycle"],
                        "manifest": json.loads(row["manifest_json"]), "uri": locations[0]["uri"],
                    }
                )
        return result

    def artifact_at(self, artifact_id: str, *, machine_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM artifacts WHERE id=? AND lifecycle!='deleted'", (artifact_id,)).fetchone()
            if row is None:
                raise NotFoundError(f"input artifact does not exist: {artifact_id}")
            location = db.execute(
                "SELECT uri,observed_at FROM artifact_locations WHERE artifact_id=? AND machine_id=? AND available=1 ORDER BY observed_at DESC LIMIT 1",
                (artifact_id, machine_id),
            ).fetchone()
        if location is None:
            raise NotFoundError(f"artifact {artifact_id} has no available location on {machine_id}")
        return {
            "id": row["id"], "kind": row["kind"], "sha256": row["sha256"],
            "byte_size": row["byte_size"], "lifecycle": row["lifecycle"],
            "manifest": json.loads(row["manifest_json"]), "uri": location["uri"],
        }

    def record_artifact_location(
        self,
        bundle: ConfigBundle,
        artifact_id: str,
        *,
        machine_id: str,
        uri: str,
        event_type: str,
        actor: str,
    ) -> None:
        machine = bundle.machines.get(machine_id)
        if machine is None:
            raise NotFoundError(f"artifact machine is not configured: {machine_id}")
        normalized_uri = Path(os.path.normpath(uri)).resolve(strict=False)
        allowed_roots = [Path(machine["state_root"]).resolve(strict=False), *(Path(value).resolve(strict=False) for value in machine["artifact_roots"])]
        if not normalized_uri.is_absolute() or not any(normalized_uri == root or root in normalized_uri.parents for root in allowed_roots):
            raise SafetyError(f"artifact URI is outside configured machine roots: {uri}")
        if event_type not in {"artifact.materialized", "artifact.retrieved"}:
            raise ValueError("unsupported artifact location event")
        now = utc_now()
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM artifacts WHERE id=? AND lifecycle!='deleted'", (artifact_id,)).fetchone() is None:
                raise NotFoundError(f"input artifact does not exist: {artifact_id}")
            db.execute(
                """INSERT INTO artifact_locations(artifact_id,machine_id,uri,observed_at,available)
                   VALUES(?,?,?,?,1) ON CONFLICT(artifact_id,machine_id,uri)
                   DO UPDATE SET observed_at=excluded.observed_at,available=1""",
                (artifact_id, machine_id, str(normalized_uri), now),
            )
            self._event(db, "artifact", artifact_id, event_type, actor, {"machine_id": machine_id, "uri": str(normalized_uri)})

    def protect_artifact(
        self, artifact_id: str, *, protection_key: str, reason: str,
        actor: str, source: str = "operator", metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create or reactivate one auditable reason an artifact must remain available."""
        if source not in {"automatic", "operator"}:
            raise ValueError("artifact protection source must be automatic or operator")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,159}", protection_key):
            raise ValueError("invalid artifact protection key")
        if not reason.strip():
            raise ValueError("artifact protection requires a reason")
        now = utc_now()
        protection_id = f"protect-{content_hash({'artifact_id': artifact_id, 'key': protection_key})[:16]}"
        with self.transaction() as db:
            artifact = db.execute("SELECT lifecycle FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
            if artifact is None or artifact["lifecycle"] == "deleted":
                raise NotFoundError(f"protectable artifact does not exist: {artifact_id}")
            if db.execute(
                "SELECT 1 FROM retention_deletions WHERE artifact_id=? AND state='authorized'", (artifact_id,)
            ).fetchone():
                raise SafetyError("artifact has an authorized deletion already in progress")
            existing = db.execute(
                "SELECT state,reason,metadata_json FROM artifact_protections WHERE artifact_id=? AND protection_key=?",
                (artifact_id, protection_key),
            ).fetchone()
            encoded = canonical_json(metadata or {})
            if existing is None:
                db.execute(
                    """INSERT INTO artifact_protections
                       (id,artifact_id,protection_key,reason,source,state,metadata_json,created_by,created_at)
                       VALUES(?,?,?,?,?,'active',?,?,?)""",
                    (protection_id, artifact_id, protection_key, reason.strip(), source, encoded, actor, now),
                )
            elif existing["state"] != "active" or existing["reason"] != reason.strip() or existing["metadata_json"] != encoded:
                db.execute(
                    """UPDATE artifact_protections SET reason=?,source=?,state='active',metadata_json=?,
                       created_by=?,created_at=?,released_by=NULL,released_at=NULL WHERE id=?""",
                    (reason.strip(), source, encoded, actor, now, protection_id),
                )
            else:
                return dict(db.execute("SELECT * FROM artifact_protections WHERE id=?", (protection_id,)).fetchone())
            if artifact["lifecycle"] in {"candidate", "observed", "legacy", "rejected"}:
                db.execute("UPDATE artifacts SET lifecycle='protected' WHERE id=?", (artifact_id,))
            self._event(db, "artifact", artifact_id, "artifact.protected", actor, {
                "protection_id": protection_id, "protection_key": protection_key,
                "reason": reason.strip(), "source": source,
            })
            return dict(db.execute("SELECT * FROM artifact_protections WHERE id=?", (protection_id,)).fetchone())

    def release_artifact_protection(self, protection_id: str, *, actor: str) -> dict[str, Any]:
        """Release an operator pin; automatic dependency pins cannot be manually bypassed."""
        now = utc_now()
        with self.transaction() as db:
            row = db.execute("SELECT * FROM artifact_protections WHERE id=?", (protection_id,)).fetchone()
            if row is None:
                raise NotFoundError(protection_id)
            if row["source"] != "operator":
                raise SafetyError("automatic dependency protection cannot be released manually")
            if row["state"] == "active":
                db.execute(
                    "UPDATE artifact_protections SET state='released',released_by=?,released_at=? WHERE id=?",
                    (actor, now, protection_id),
                )
                remaining = db.execute(
                    "SELECT COUNT(*) FROM artifact_protections WHERE artifact_id=? AND state='active'",
                    (row["artifact_id"],),
                ).fetchone()[0]
                if not remaining:
                    db.execute(
                        "UPDATE artifacts SET lifecycle='candidate' WHERE id=? AND lifecycle='protected'",
                        (row["artifact_id"],),
                    )
                self._event(db, "artifact", row["artifact_id"], "artifact.protection_released", actor, {
                    "protection_id": protection_id,
                })
            return dict(db.execute("SELECT * FROM artifact_protections WHERE id=?", (protection_id,)).fetchone())

    def protect_path(
        self, machine_id: str, path: str, *, protection_key: str, reason: str,
        actor: str, source: str = "automatic", metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Pin a configured model directory which is not itself an artifact."""
        if source not in {"automatic", "operator"}:
            raise ValueError("path protection source must be automatic or operator")
        normalized = str(Path(os.path.normpath(path)).resolve(strict=False))
        now = utc_now()
        protection_id = f"pathpin-{content_hash({'machine_id': machine_id, 'path': normalized, 'key': protection_key})[:16]}"
        encoded = canonical_json(metadata or {})
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM machines WHERE id=?", (machine_id,)).fetchone() is None:
                raise NotFoundError(machine_id)
            existing = db.execute(
                "SELECT * FROM path_protections WHERE machine_id=? AND path=? AND protection_key=?",
                (machine_id, normalized, protection_key),
            ).fetchone()
            if existing is None:
                db.execute(
                    """INSERT INTO path_protections
                       (id,machine_id,path,protection_key,reason,source,state,metadata_json,created_by,created_at)
                       VALUES(?,?,?,?,?,?,'active',?,?,?)""",
                    (protection_id, machine_id, normalized, protection_key, reason.strip(), source, encoded, actor, now),
                )
                self._event(db, "path_protection", protection_id, "path.protected", actor, {
                    "machine_id": machine_id, "path": normalized, "protection_key": protection_key,
                })
            elif existing["state"] != "active" or existing["reason"] != reason.strip() or existing["metadata_json"] != encoded:
                db.execute(
                    """UPDATE path_protections SET reason=?,source=?,state='active',metadata_json=?,
                       created_by=?,created_at=?,released_by=NULL,released_at=NULL WHERE id=?""",
                    (reason.strip(), source, encoded, actor, now, protection_id),
                )
            return dict(db.execute("SELECT * FROM path_protections WHERE id=?", (protection_id,)).fetchone())

    @staticmethod
    def _artifact_ids_in(value: Any) -> set[str]:
        found: set[str] = set()
        if isinstance(value, str) and re.fullmatch(r"art-[0-9a-f]{16}", value):
            found.add(value)
        elif isinstance(value, dict):
            for item in value.values():
                found.update(MissionHubStore._artifact_ids_in(item))
        elif isinstance(value, list):
            for item in value:
                found.update(MissionHubStore._artifact_ids_in(item))
        return found

    def reconcile_retention_protections(self, bundle: ConfigBundle, *, actor: str) -> dict[str, Any]:
        """Derive non-optional pins from lineage, live work, chats, and deployed model declarations."""
        desired: dict[tuple[str, str], tuple[str, dict[str, Any]]] = {}
        with self._connect() as db:
            checkpoints = {
                row["id"]: dict(row) for row in db.execute(
                    "SELECT id,manifest_json FROM artifacts WHERE kind='checkpoint' AND lifecycle!='deleted'"
                )
            }
            plans = [dict(row) for row in db.execute("SELECT * FROM training_session_plans ORDER BY created_at")]
            outputs_by_campaign: dict[str, set[str]] = {}
            for plan in plans:
                if plan["output_checkpoint_artifact_id"]:
                    outputs_by_campaign.setdefault(plan["campaign_id"], set()).add(plan["output_checkpoint_artifact_id"])
            for plan in plans:
                parent = plan["parent_checkpoint_artifact_id"]
                if parent and parent not in outputs_by_campaign.get(plan["campaign_id"], set()):
                    desired[(parent, f"campaign-baseline:{plan['campaign_id']}")] = (
                        "Starting checkpoint required to reproduce a campaign lineage.",
                        {"campaign_id": plan["campaign_id"]},
                    )
            terminals: dict[tuple[str, str], tuple[str, str]] = {}
            for artifact_id, checkpoint in checkpoints.items():
                manifest = json.loads(checkpoint["manifest_json"])
                branch = manifest.get("branch_id")
                row = db.execute(
                    """SELECT j.campaign_id,a.created_at FROM artifacts a JOIN runs r ON r.id=a.producing_run_id
                       JOIN jobs j ON j.id=r.job_id WHERE a.id=?""",
                    (artifact_id,),
                ).fetchone()
                if row and row["campaign_id"] and branch:
                    key = (row["campaign_id"], str(branch))
                    if key not in terminals or row["created_at"] > terminals[key][1]:
                        terminals[key] = (artifact_id, row["created_at"])
            for (campaign_id, branch_id), (artifact_id, _created) in terminals.items():
                desired[(artifact_id, f"branch-terminal:{campaign_id}:{branch_id}")] = (
                    "Terminal checkpoint retained for a completed experimental branch.",
                    {"campaign_id": campaign_id, "branch_id": branch_id},
                )
            for row in db.execute(
                "SELECT id,manifest_json FROM artifacts WHERE kind='evaluation_report' AND lifecycle!='deleted'"
            ):
                manifest = json.loads(row["manifest_json"])
                candidate = manifest.get("candidate_artifact_id")
                if manifest.get("branch_complete") is True and candidate in checkpoints:
                    desired[(candidate, f"terminal-evaluation:{row['id']}")] = (
                        "Checkpoint has preserved terminal behavioral-chat and MRI evidence.",
                        {"evaluation_artifact_id": row["id"], "branch_id": manifest.get("branch_id")},
                    )
            for row in db.execute("SELECT checkpoint_artifact_id,id FROM chat_threads"):
                desired[(row["checkpoint_artifact_id"], f"chat:{row['id']}")] = (
                    "Exact checkpoint bound to a preserved Ninereeds conversation.", {"chat_id": row["id"]},
                )
            for row in db.execute(
                """SELECT j.id,j.input_json FROM jobs j
                   WHERE j.status IN ('draft','awaiting_approval','queued','leased','running')"""
            ):
                for artifact_id in self._artifact_ids_in(json.loads(row["input_json"])):
                    if artifact_id in checkpoints:
                        desired[(artifact_id, f"live-job:{row['id']}")] = (
                            "Checkpoint is referenced by live or authorized work.", {"job_id": row["id"]},
                        )
        for (artifact_id, key), (reason, metadata) in sorted(desired.items()):
            self.protect_artifact(
                artifact_id, protection_key=key, reason=reason,
                actor=actor, source="automatic", metadata=metadata,
            )
        desired_pairs = set(desired)
        with self.transaction() as db:
            stale = db.execute(
                "SELECT id,artifact_id,protection_key FROM artifact_protections WHERE source='automatic' AND state='active'"
            ).fetchall()
            for row in stale:
                if (row["artifact_id"], row["protection_key"]) in desired_pairs:
                    continue
                db.execute(
                    "UPDATE artifact_protections SET state='released',released_by=?,released_at=? WHERE id=?",
                    (actor, utc_now(), row["id"]),
                )
                remaining = db.execute(
                    "SELECT COUNT(*) FROM artifact_protections WHERE artifact_id=? AND state='active'",
                    (row["artifact_id"],),
                ).fetchone()[0]
                if not remaining:
                    db.execute(
                        "UPDATE artifacts SET lifecycle='candidate' WHERE id=? AND lifecycle='protected'",
                        (row["artifact_id"],),
                    )
                self._event(db, "artifact", row["artifact_id"], "artifact.protection_released", actor, {
                    "protection_id": row["id"], "reason": "automatic protection no longer applies",
                })
        path_count = 0
        declared = {}
        for role in bundle.deployment_roles.values():
            if role["role"] != "trainbox":
                continue
            for model in role["required_model_paths"]:
                declared[model["id"]] = model
        for model_id, model in sorted(declared.items()):
            self.protect_path(
                "trainbox", model["path"], protection_key=f"deployed-model:{model_id}",
                reason="Pinned model snapshot required by the commissioned trainbox release.",
                actor=actor, source="automatic", metadata={"model_id": model_id, "revision": model["revision"]},
            )
            path_count += 1
        desired_path_keys = {
            ("trainbox", str(Path(model["path"]).resolve(strict=False)), f"deployed-model:{model_id}")
            for model_id, model in declared.items()
        }
        with self.transaction() as db:
            stale_paths = db.execute(
                "SELECT id,machine_id,path,protection_key FROM path_protections WHERE source='automatic' AND state='active'"
            ).fetchall()
            for row in stale_paths:
                if (row["machine_id"], row["path"], row["protection_key"]) in desired_path_keys:
                    continue
                db.execute(
                    "UPDATE path_protections SET state='released',released_by=?,released_at=? WHERE id=?",
                    (actor, utc_now(), row["id"]),
                )
                self._event(db, "path_protection", row["id"], "path.protection_released", actor, {
                    "reason": "configured model path is no longer required",
                })
        return {"artifact_protections": len(desired), "path_protections": path_count}

    def retention_inventory(self, *, machine_id: str = "trainbox") -> dict[str, Any]:
        """Return an exact, hash-bound cleanup preview; never touches filesystem bytes."""
        with self._connect() as db:
            rows = db.execute(
                """SELECT a.id,a.kind,a.sha256,a.byte_size,a.lifecycle,l.uri,l.observed_at,
                   EXISTS(SELECT 1 FROM artifact_protections p WHERE p.artifact_id=a.id AND p.state='active') protected
                   FROM artifacts a JOIN artifact_locations l ON l.artifact_id=a.id
                   WHERE a.kind='checkpoint' AND a.lifecycle!='deleted' AND l.machine_id=? AND l.available=1
                   ORDER BY a.created_at,a.id,l.uri""",
                (machine_id,),
            ).fetchall()
            protections = [
                dict(row) for row in db.execute(
                    "SELECT * FROM artifact_protections WHERE state='active' ORDER BY artifact_id,protection_key"
                )
            ]
            path_protections = [
                dict(row) for row in db.execute(
                    "SELECT * FROM path_protections WHERE state='active' AND machine_id=? ORDER BY path,protection_key",
                    (machine_id,),
                )
            ]
        items = [dict(row) for row in rows]
        eligible = [
            {key: item[key] for key in ("id", "kind", "sha256", "byte_size", "uri", "observed_at")}
            for item in items if not item["protected"]
        ]
        body = {
            "schema_version": "ninereeds_retention_plan_v1", "machine_id": machine_id,
            "eligible": eligible,
            "protected": [item for item in items if item["protected"]],
            "artifact_protections": protections, "path_protections": path_protections,
            "eligible_bytes": sum(item["byte_size"] for item in eligible),
        }
        body["plan_sha256"] = content_hash(body)
        return body

    def record_retention_deletion(
        self, *, artifact_id: str, machine_id: str, uri: str,
        expected_sha256: str, plan_sha256: str, actor: str,
    ) -> None:
        """Record a verified physical deletion without erasing its immutable ledger row."""
        now = utc_now()
        with self.transaction() as db:
            artifact = db.execute("SELECT sha256 FROM artifacts WHERE id=?", (artifact_id,)).fetchone()
            if artifact is None or artifact["sha256"] != expected_sha256:
                raise ConflictError("retention deletion artifact identity changed")
            if db.execute(
                "SELECT 1 FROM artifact_protections WHERE artifact_id=? AND state='active'", (artifact_id,)
            ).fetchone():
                raise SafetyError("protected artifact cannot be deleted")
            intent = db.execute(
                """SELECT id,state FROM retention_deletions
                   WHERE plan_sha256=? AND artifact_id=? AND machine_id=? AND uri=?""",
                (plan_sha256, artifact_id, machine_id, uri),
            ).fetchone()
            if intent is None or intent["state"] != "authorized":
                raise SafetyError("artifact deletion has no active exact-plan authorization")
            location = db.execute(
                "SELECT available FROM artifact_locations WHERE artifact_id=? AND machine_id=? AND uri=?",
                (artifact_id, machine_id, uri),
            ).fetchone()
            if location is None or not location["available"]:
                raise ConflictError("retention deletion location is no longer available")
            db.execute(
                "UPDATE artifact_locations SET available=0,observed_at=? WHERE artifact_id=? AND machine_id=? AND uri=?",
                (now, artifact_id, machine_id, uri),
            )
            remaining = db.execute(
                "SELECT COUNT(*) FROM artifact_locations WHERE artifact_id=? AND available=1", (artifact_id,)
            ).fetchone()[0]
            if not remaining:
                db.execute("UPDATE artifacts SET lifecycle='deleted' WHERE id=?", (artifact_id,))
            db.execute(
                "UPDATE retention_deletions SET state='deleted',finished_at=? WHERE id=?",
                (now, intent["id"]),
            )
            self._event(db, "artifact", artifact_id, "artifact.location_deleted", actor, {
                "machine_id": machine_id, "uri": uri, "plan_sha256": plan_sha256,
                "metadata_preserved": True, "remaining_locations": remaining,
            })

    def authorize_retention_plan(self, plan: dict[str, Any], *, actor: str) -> list[dict[str, Any]]:
        """Atomically lock every deletion in one unchanged, hash-bound preview."""
        if content_hash({key: value for key, value in plan.items() if key != "plan_sha256"}) != plan.get("plan_sha256"):
            raise ConflictError("retention plan content hash is invalid")
        current = self.retention_inventory(machine_id=plan.get("machine_id", ""))
        if current["plan_sha256"] != plan["plan_sha256"]:
            raise ConflictError("retention plan is stale")
        now = utc_now()
        created: list[dict[str, Any]] = []
        with self.transaction() as db:
            for item in plan["eligible"]:
                if db.execute(
                    "SELECT 1 FROM artifact_protections WHERE artifact_id=? AND state='active'", (item["id"],)
                ).fetchone():
                    raise SafetyError(f"retention target became protected: {item['id']}")
                location = db.execute(
                    """SELECT 1 FROM artifact_locations WHERE artifact_id=? AND machine_id=? AND uri=? AND available=1""",
                    (item["id"], plan["machine_id"], item["uri"]),
                ).fetchone()
                if location is None:
                    raise ConflictError(f"retention target location changed: {item['id']}")
                deletion_id = f"retire-{content_hash({'plan': plan['plan_sha256'], 'artifact': item['id'], 'uri': item['uri']})[:16]}"
                db.execute(
                    """INSERT OR IGNORE INTO retention_deletions
                       (id,plan_sha256,artifact_id,machine_id,uri,expected_sha256,byte_size,state,authorized_by,authorized_at)
                       VALUES(?,?,?,?,?,?,?,'authorized',?,?)""",
                    (deletion_id, plan["plan_sha256"], item["id"], plan["machine_id"], item["uri"],
                     item["sha256"], item["byte_size"], actor, now),
                )
                created.append(dict(db.execute("SELECT * FROM retention_deletions WHERE id=?", (deletion_id,)).fetchone()))
            self._event(db, "retention_plan", plan["plan_sha256"], "retention.authorized", actor, {
                "machine_id": plan["machine_id"], "items": len(created),
                "bytes": sum(item["byte_size"] for item in plan["eligible"]),
            })
        return created

    def fail_retention_deletion(self, deletion_id: str, *, failure: str, actor: str) -> None:
        now = utc_now()
        with self.transaction() as db:
            row = db.execute("SELECT * FROM retention_deletions WHERE id=?", (deletion_id,)).fetchone()
            if row is None:
                raise NotFoundError(deletion_id)
            if row["state"] == "authorized":
                db.execute(
                    "UPDATE retention_deletions SET state='failed',finished_at=?,failure=? WHERE id=?",
                    (now, failure[:1000], deletion_id),
                )
                self._event(db, "retention_plan", row["plan_sha256"], "retention.deletion_failed", actor, {
                    "artifact_id": row["artifact_id"], "failure": failure[:1000],
                })

    def preserve_evidence(
        self,
        manifest: dict[str, Any],
        records: list[dict[str, Any]],
        *,
        actor: str,
    ) -> str:
        required = {"source_id", "machine_id", "source_kind", "source_uri", "snapshot_sha256", "captured_at", "files"}
        missing = sorted(required - set(manifest))
        if missing:
            raise ValueError(f"evidence manifest missing: {', '.join(missing)}")
        evidence_id = f"evidence-{manifest['snapshot_sha256'][:16]}"
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                """INSERT OR IGNORE INTO evidence_sources
                   (id,machine_id,source_kind,source_uri,snapshot_sha256,manifest_json,captured_at,imported_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (
                    evidence_id, manifest["machine_id"], manifest["source_kind"], manifest["source_uri"],
                    manifest["snapshot_sha256"], canonical_json(manifest), manifest["captured_at"], now,
                ),
            )
            for record in records:
                db.execute(
                    """INSERT OR IGNORE INTO legacy_records
                       (evidence_source_id,record_kind,legacy_id,sha256,payload_json,source_path,imported_at)
                       VALUES(?,?,?,?,?,?,?)""",
                    (
                        evidence_id, record["record_kind"], record["legacy_id"], record["sha256"],
                        canonical_json(record["payload"]), record["source_path"], now,
                    ),
                )
            self._event(
                db,
                "evidence_source",
                evidence_id,
                "evidence.preserved",
                actor,
                {"source_id": manifest["source_id"], "snapshot_sha256": manifest["snapshot_sha256"], "file_count": len(manifest["files"]), "record_count": len(records)},
            )
        return evidence_id

    def create_campaign(self, *, campaign_id: str, name: str, objective: str, metadata: dict[str, Any], actor: str, state: str = "draft") -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,126}[a-z0-9]", campaign_id):
            raise ValueError("campaign ID must be a filesystem-safe lowercase identifier")
        config = self.active_config()
        historical_branch_evidence = metadata.get("completed_branch_evidence", {})
        if state != "legacy_stopped":
            modes = config["payload"]["resolved"]["campaign_modes"]
            contract = validate_campaign_contract(metadata.get("campaign_contract"), modes)
            if not isinstance(historical_branch_evidence, dict) or any(
                branch not in contract["branches"]
                or not isinstance(artifact_ids, list)
                or not artifact_ids
                or not all(isinstance(value, str) for value in artifact_ids)
                for branch, artifact_ids in historical_branch_evidence.items()
            ):
                raise SafetyError("historical branch evidence is not bound to declared campaign branches")
        now = utc_now()
        with self.transaction() as db:
            existing = db.execute("SELECT name,state,objective,metadata_json FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
            if existing is not None:
                expected = (name, state, objective, canonical_json(metadata))
                if tuple(existing) != expected:
                    raise ConflictError(f"campaign {campaign_id} already exists with different evidence")
                return
            db.execute(
                "INSERT INTO campaigns(id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (campaign_id, name, state, config["id"], objective, canonical_json(metadata), now, now),
            )
            for branch_id, artifact_ids in historical_branch_evidence.items():
                for artifact_id in artifact_ids:
                    artifact = db.execute(
                        "SELECT kind FROM artifacts WHERE id=? AND lifecycle!='deleted'", (artifact_id,),
                    ).fetchone()
                    if artifact is None or artifact[0] != "evaluation_report":
                        raise SafetyError(
                            f"historical branch {branch_id} lacks a registered evaluation report: {artifact_id}"
                        )
            starting_checkpoint = metadata.get("starting_checkpoint_artifact_id")
            if starting_checkpoint is not None:
                row = db.execute(
                    "SELECT kind FROM artifacts WHERE id=? AND lifecycle!='deleted'",
                    (starting_checkpoint,),
                ).fetchone()
                if row is None or row[0] != "checkpoint":
                    raise SafetyError("campaign starting checkpoint is not a registered checkpoint artifact")
                db.execute(
                    """INSERT INTO campaign_knowledge_start(campaign_id,concept_key,source_record_id)
                       SELECT ?,concept_key,source_record_id FROM checkpoint_knowledge
                       WHERE checkpoint_artifact_id=?""",
                    (campaign_id, starting_checkpoint),
                )
            self._event(db, "campaign", campaign_id, "campaign.created", actor, {"state": state})
        self.sync_knowledge_views(campaign_id=campaign_id)

    def close_campaign(
        self, campaign_id: str, *, review_artifact_id: str, actor: str,
    ) -> dict[str, Any]:
        """Close a campaign only after its declared evidence is complete.

        Closure is an operator decision bound to one immutable review.  It does
        not rank, publish, promote, or select a checkpoint.
        """

        now = utc_now()
        with self.transaction() as db:
            campaign = db.execute(
                "SELECT * FROM campaigns WHERE id=?", (campaign_id,),
            ).fetchone()
            if campaign is None:
                raise NotFoundError(campaign_id)
            if campaign["state"] == "closed":
                metadata = json.loads(campaign["metadata_json"])
                if metadata.get("final_review_artifact_id") != review_artifact_id:
                    raise ConflictError("campaign is already closed with a different review")
                return dict(campaign) | {"metadata": metadata}
            if campaign["state"] not in {"active", "paused"}:
                raise TransitionError(
                    f"campaign {campaign_id} is {campaign['state']}, not active or paused"
                )

            review = db.execute(
                "SELECT * FROM artifacts WHERE id=? AND kind='campaign_review' AND lifecycle!='deleted'",
                (review_artifact_id,),
            ).fetchone()
            if review is None:
                raise SafetyError("campaign closure requires an immutable campaign_review artifact")
            review_manifest = json.loads(review["manifest_json"])
            if any((
                review_manifest.get("campaign_id") != campaign_id,
                review_manifest.get("evaluation_basis") != ["behavioral_chat", "mri_activation"],
                review_manifest.get("loss_role") != "telemetry_only",
                review_manifest.get("automatic_winner_selected") is not False,
            )):
                raise SafetyError("campaign review does not match the non-ranking closure contract")
            learning = review_manifest.get("architecture_knowledge")
            if not isinstance(learning, dict) or set(learning) != {
                "canonical_path", "ledger_sha256", "disposition", "entry_ids", "reason",
            }:
                raise SafetyError("campaign closure requires an explicit architecture-knowledge disposition")
            if learning["canonical_path"] != "docs/ninereeds_architecture_knowledge.md":
                raise SafetyError("campaign review names the wrong architecture-knowledge ledger")
            if not isinstance(learning["ledger_sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", learning["ledger_sha256"]):
                raise SafetyError("campaign review has an invalid architecture-knowledge ledger hash")
            entry_ids = learning["entry_ids"]
            if not isinstance(entry_ids, list) or len(entry_ids) != len(set(entry_ids)) or any(
                not isinstance(entry_id, str) or not re.fullmatch(r"NRK-[0-9]{4}", entry_id)
                for entry_id in entry_ids
            ):
                raise SafetyError("campaign review has invalid architecture-knowledge entry IDs")
            reason = learning["reason"]
            if not isinstance(reason, str) or len(reason.strip()) < 20:
                raise SafetyError("campaign review requires a substantive architecture-knowledge reason")
            if learning["disposition"] == "updated":
                if not entry_ids:
                    raise SafetyError("an updated architecture ledger must name its new entries")
            elif learning["disposition"] == "no_new_findings":
                if entry_ids:
                    raise SafetyError("no-new-findings disposition cannot name new entries")
            else:
                raise SafetyError("campaign review has an invalid architecture-knowledge disposition")

            metadata = json.loads(campaign["metadata_json"])
            contract = validate_campaign_contract(
                metadata.get("campaign_contract"),
                self.active_config()["payload"]["resolved"]["campaign_modes"],
            )
            completed: dict[str, list[str]] = {
                branch: list(artifact_ids)
                for branch, artifact_ids in metadata.get("completed_branch_evidence", {}).items()
            }
            terminal_rows = db.execute(
                """SELECT j.input_json,a.id
                   FROM jobs j
                   JOIN runs r ON r.job_id=j.id AND r.status='succeeded'
                   JOIN artifacts a ON a.producing_run_id=r.id AND a.kind='evaluation_report'
                   WHERE j.campaign_id=? AND j.job_type='model.evaluate' AND j.status='succeeded'""",
                (campaign_id,),
            ).fetchall()
            expected_hash = campaign_contract_sha256(contract)
            for row in terminal_rows:
                context = json.loads(row["input_json"]).get("evaluation_context", {})
                branch = context.get("branch_id")
                if (
                    isinstance(branch, str)
                    and context.get("campaign_contract_sha256") == expected_hash
                    and context.get("branch_complete") is True
                ):
                    completed.setdefault(branch, []).append(row["id"])

            required = (
                set(contract["branches"])
                if contract["mode"] == "evolutionary"
                else set(contract["merge_sources"])
                if contract["mode"] == "merge"
                else set()
            )
            missing = sorted(required - set(completed))
            if missing:
                raise SafetyError(
                    "campaign closure is missing terminal chat-and-MRI evidence for: "
                    + ", ".join(missing)
                )
            if db.execute(
                "SELECT 1 FROM cortex_workflows WHERE campaign_id=? AND status='active' LIMIT 1",
                (campaign_id,),
            ).fetchone() is not None:
                raise SafetyError("campaign closure requires every Cortex workflow to be terminal")
            if db.execute(
                """SELECT 1 FROM jobs WHERE campaign_id=?
                   AND status IN ('queued','awaiting_approval','leased','running') LIMIT 1""",
                (campaign_id,),
            ).fetchone() is not None:
                raise SafetyError("campaign closure requires every campaign job to be terminal")
            control = db.execute(
                "SELECT desired_state,applied_state FROM pipeline_control WHERE id='pipeline'",
            ).fetchone()
            if control is None or tuple(control) != ("paused", "paused"):
                raise SafetyError("campaign closure requires the pipeline to be safely paused")

            completed = {key: sorted(set(values)) for key, values in sorted(completed.items())}
            metadata["completed_branch_evidence"] = completed
            metadata["final_review_artifact_id"] = review_artifact_id
            metadata["architecture_knowledge"] = learning
            metadata["closed_at"] = now
            metadata["closure_policy"] = {
                "evaluation_basis": ["behavioral_chat", "mri_activation"],
                "loss_role": "telemetry_only",
                "automatic_winner_selected": False,
            }
            db.execute(
                "UPDATE campaigns SET state='closed',metadata_json=?,updated_at=? WHERE id=?",
                (canonical_json(metadata), now, campaign_id),
            )
            self._event(db, "campaign", campaign_id, "campaign.closed", actor, {
                "review_artifact_id": review_artifact_id,
                "architecture_knowledge": learning,
                "completed_branch_evidence": completed,
                "automatic_winner_selected": False,
            })
            result = dict(campaign)
            result.update({"state": "closed", "updated_at": now, "metadata": metadata})
            return result

    @staticmethod
    def normalize_concept(value: str) -> tuple[str, str]:
        if not isinstance(value, str):
            raise ValueError("knowledge concepts must be text")
        label = " ".join(unicodedata.normalize("NFKC", value).split())
        if not label or len(label.encode("utf-8")) > 512:
            raise ValueError("knowledge concept must contain 1-512 UTF-8 bytes")
        return label.casefold(), label

    def preview_training_session_plan(
        self,
        bundle: ConfigBundle,
        *,
        job_type: str,
        input_payload: dict[str, Any],
        campaign_id: str,
    ) -> dict[str, Any]:
        """Validate dependencies and return the hashes a certificate must bind."""

        if job_type not in {"model.train", "model.visual_train"}:
            raise ValueError("training-session plans only apply to training jobs")
        with self._connect() as db:
            return self._training_session_plan(
                db, bundle, job_type=job_type, input_payload=input_payload,
                campaign_id=campaign_id, require_certificate=False,
            )

    def _training_session_plan(
        self,
        db: sqlite3.Connection,
        bundle: ConfigBundle,
        *,
        job_type: str,
        input_payload: dict[str, Any],
        campaign_id: str | None,
        require_certificate: bool,
    ) -> dict[str, Any]:
        if campaign_id is None:
            raise SafetyError("training requires an explicit campaign")
        campaign = db.execute(
            "SELECT state,metadata_json FROM campaigns WHERE id=?", (campaign_id,),
        ).fetchone()
        if campaign is None:
            raise NotFoundError(f"campaign does not exist: {campaign_id}")
        if campaign["state"] != "active":
            raise SafetyError("training requires an active campaign")

        artifact_ids = self._artifact_ids(bundle.jobs[job_type], input_payload)
        rows = db.execute(
            f"SELECT * FROM artifacts WHERE id IN ({','.join('?' for _ in artifact_ids)}) AND lifecycle!='deleted'",
            artifact_ids,
        ).fetchall()
        artifacts = {
            row["id"]: dict(row) | {"manifest": json.loads(row["manifest_json"])}
            for row in rows
        }
        missing_artifact_ids = sorted(set(artifact_ids) - set(artifacts))
        allowed_missing = 0 if require_certificate else 1
        if len(missing_artifact_ids) != allowed_missing:
            raise SafetyError("training-session plan references an unavailable artifact")

        if job_type == "model.train":
            subject = artifacts[input_payload["corpus_artifact_id"]]
            parent_id = input_payload["parent_artifact_id"]
            parent = None if parent_id is None else artifacts[parent_id]
            validation_id = input_payload["order_validation_artifact_id"]
            validation_artifact = artifacts.get(validation_id, {"id": validation_id})
        else:
            by_kind: dict[str, list[dict[str, Any]]] = {}
            for artifact in artifacts.values():
                by_kind.setdefault(artifact["kind"], []).append(artifact)
            required_kinds = ("checkpoint", "visual_experience") if not require_certificate else ("checkpoint", "visual_experience", "validation_report")
            if any(len(by_kind.get(kind, [])) != 1 for kind in required_kinds):
                raise SafetyError("visual training admission cannot resolve its parent, sequence, and order certificate")
            parent = by_kind["checkpoint"][0]
            parent_id = parent["id"]
            subject = by_kind["visual_experience"][0]
            validation_artifact = by_kind["validation_report"][0] if require_certificate else {"id": missing_artifact_ids[0]}

        if subject["kind"] not in {"corpus", "visual_experience"}:
            raise SafetyError("training subject must be an ordered corpus or visual experience")
        if parent is not None and parent["kind"] != "checkpoint":
            raise SafetyError("training parent must be a checkpoint")
        metadata = json.loads(campaign["metadata_json"])
        campaign_contract = validate_campaign_contract(
            metadata.get("campaign_contract"), bundle.campaign_modes,
        )
        session = input_payload["training_session"]
        branch_id = session["branch_id"]
        starting_parent = metadata.get("starting_checkpoint_artifact_id")
        if parent_id != starting_parent:
            inherited = db.execute(
                """SELECT 1
                   FROM training_session_plans p
                   JOIN jobs j ON j.id=p.job_id
                   WHERE p.campaign_id=? AND p.status='completed'
                     AND p.output_checkpoint_artifact_id IS ?
                     AND json_extract(j.input_json,'$.training_session.branch_id') IS ?""",
                (campaign_id, parent_id, branch_id),
            ).fetchone()
            if inherited is None:
                raise SafetyError("training parent is outside the exact campaign branch lineage")

        mode = campaign_contract["mode"]
        if session["campaign_contract_sha256"] != campaign_contract_sha256(campaign_contract):
            raise SafetyError("training session used a different campaign-purpose contract")
        if session["training_mode"] != mode:
            raise SafetyError("training session mode does not match its campaign-purpose contract")
        if mode == "evolutionary" and branch_id not in campaign_contract["branches"]:
            raise SafetyError("evolutionary training requires a declared campaign branch")
        if mode == "merge" and branch_id not in campaign_contract["merge_sources"]:
            raise SafetyError("merge specialist training requires a declared merge source")
        if mode not in {"evolutionary", "merge"} and branch_id is not None:
            raise SafetyError(f"campaign mode {mode} does not accept a training branch ID")
        prior_session = db.execute(
            "SELECT job_id FROM training_session_plans WHERE campaign_id=? AND session_id=?",
            (campaign_id, session["id"]),
        ).fetchone()
        if prior_session is not None:
            raise ConflictError(
                f"training session {campaign_id}/{session['id']} is already bound to job {prior_session['job_id']}"
            )
        ordered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index, item in enumerate(session["ordered_concepts"]):
            concept_key, concept_label = self.normalize_concept(item["concept"])
            if concept_key in seen:
                raise SafetyError(f"training concept is duplicated at position {index}: {concept_label}")
            dependencies: list[dict[str, str]] = []
            dependency_keys: set[str] = set()
            for dependency in item["depends_on"]:
                key, label = self.normalize_concept(dependency)
                if key == concept_key:
                    raise SafetyError(f"training concept cannot depend on itself: {concept_label}")
                if key not in dependency_keys:
                    dependencies.append({"concept_key": key, "concept_label": label})
                    dependency_keys.add(key)
            ordered.append({
                "position": index,
                "concept_key": concept_key,
                "concept_label": concept_label,
                "depends_on": dependencies,
            })
            seen.add(concept_key)

        parent_rows = db.execute(
            """SELECT r.concept_key,r.id AS source_record_id,r.sha256
               FROM checkpoint_knowledge k JOIN knowledge_records r ON r.id=k.source_record_id
               WHERE k.checkpoint_artifact_id IS ? ORDER BY r.concept_key""",
            (parent_id,),
        ).fetchall() if parent_id is not None else []
        parent_evidence = [dict(row) for row in parent_rows]
        available = {row["concept_key"] for row in parent_rows}
        for item in ordered:
            missing = [dep["concept_label"] for dep in item["depends_on"] if dep["concept_key"] not in available]
            if missing:
                raise SafetyError(
                    f"dependency-order violation at position {item['position']} for {item['concept_label']}: "
                    f"missing {', '.join(missing)}"
                )
            available.add(item["concept_key"])

        parent_knowledge_sha256 = content_hash(parent_evidence)
        plan_body = {
            "schema_version": "ninereeds_training_session_plan_v1",
            "campaign_id": campaign_id,
            "campaign_contract_sha256": campaign_contract_sha256(campaign_contract),
            "training_mode": mode,
            "branch_id": branch_id,
            "session_id": session["id"],
            "identity_scope": session["identity_scope"],
            "parent_checkpoint_artifact_id": parent_id,
            "parent_checkpoint_sha256": None if parent is None else parent["sha256"],
            "subject_artifact_id": subject["id"],
            "subject_sha256": subject["sha256"],
            "parent_knowledge_sha256": parent_knowledge_sha256,
            "ordered_concepts": ordered,
        }
        plan = plan_body | {
            "plan_sha256": content_hash(plan_body),
            "validation_artifact_id": validation_artifact["id"],
        }
        if require_certificate:
            require_dependency_order(
                subject, validation_artifact, bundle.training, parent=parent,
                identity_policy=bundle.identity_policy,
                identity_scope=session["identity_scope"],
            )
            certificate = validation_artifact["manifest"]
            if certificate.get("session_plan_sha256") != plan["plan_sha256"]:
                raise SafetyError("dependency-order certificate does not bind the admitted training-session list")
            if certificate.get("parent_knowledge_sha256") != parent_knowledge_sha256:
                raise SafetyError("dependency-order certificate was built from a different parent knowledge snapshot")
            if certificate.get("lesson_policy_sha256") != policy_sha256(bundle.identity_policy):
                raise SafetyError("dependency-order certificate used a different identity and lesson policy")
        return plan

    def append_checkpoint_knowledge(
        self,
        *,
        checkpoint_artifact_id: str,
        parent_checkpoint_artifact_id: str | None,
        campaign_id: str,
        session_id: str,
        concepts: list[str],
        evidence: list[str],
        actor: str,
        job_id: str | None = None,
        run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Append teaching events and materialize one checkpoint's inherited closure."""
        with self.transaction() as db:
            created = self._append_checkpoint_knowledge_db(
                db, checkpoint_artifact_id=checkpoint_artifact_id,
                parent_checkpoint_artifact_id=parent_checkpoint_artifact_id,
                campaign_id=campaign_id, session_id=session_id, concepts=concepts,
                evidence=evidence, actor=actor, job_id=job_id, run_id=run_id,
                now=utc_now(),
            )
        self.sync_knowledge_views(campaign_id=campaign_id)
        return created

    def _append_checkpoint_knowledge_db(
        self,
        db: sqlite3.Connection,
        *,
        checkpoint_artifact_id: str,
        parent_checkpoint_artifact_id: str | None,
        campaign_id: str,
        session_id: str,
        concepts: list[str],
        evidence: list[str],
        actor: str,
        job_id: str | None,
        run_id: str | None,
        now: str,
    ) -> list[dict[str, Any]]:
        if not isinstance(session_id, str) or not session_id.strip() or len(session_id.encode("utf-8")) > 512:
            raise ValueError("knowledge session ID must contain 1-512 UTF-8 bytes")
        normalized: list[tuple[str, str]] = []
        seen: set[str] = set()
        for concept in concepts:
            item = self.normalize_concept(concept)
            if item[0] not in seen:
                normalized.append(item)
                seen.add(item[0])
        if not normalized:
            raise ValueError("training must declare at least one taught concept")
        if not all(isinstance(item, str) and item for item in evidence):
            raise ValueError("knowledge evidence IDs must be non-empty strings")
        existing_session = db.execute(
            """SELECT * FROM knowledge_records
               WHERE checkpoint_artifact_id=? AND session_id=? ORDER BY sequence""",
            (checkpoint_artifact_id, session_id.strip()),
        ).fetchall()
        if existing_session:
            expected_keys = [item[0] for item in normalized]
            exact = (
                [row["concept_key"] for row in existing_session] == expected_keys
                and all(row["parent_checkpoint_artifact_id"] == parent_checkpoint_artifact_id for row in existing_session)
                and all(json.loads(row["evidence_json"]) == sorted(set(evidence)) for row in existing_session)
                and all(row["campaign_id"] == campaign_id for row in existing_session)
            )
            if not exact:
                raise ConflictError(
                    f"knowledge session {checkpoint_artifact_id}/{session_id.strip()} already has different evidence"
                )
            return [self._knowledge_row(row) for row in existing_session]
        checkpoint = db.execute(
            "SELECT kind FROM artifacts WHERE id=? AND lifecycle!='deleted'", (checkpoint_artifact_id,),
        ).fetchone()
        if checkpoint is None or checkpoint[0] != "checkpoint":
            raise SafetyError("knowledge target is not a registered checkpoint")
        if db.execute("SELECT 1 FROM campaigns WHERE id=?", (campaign_id,)).fetchone() is None:
            raise NotFoundError(f"campaign does not exist: {campaign_id}")
        if parent_checkpoint_artifact_id is not None:
            parent = db.execute(
                "SELECT kind FROM artifacts WHERE id=? AND lifecycle!='deleted'", (parent_checkpoint_artifact_id,),
            ).fetchone()
            if parent is None or parent[0] != "checkpoint":
                raise SafetyError("knowledge parent is not a registered checkpoint")
            db.execute(
                """INSERT OR IGNORE INTO checkpoint_knowledge(checkpoint_artifact_id,concept_key,source_record_id)
                   SELECT ?,concept_key,source_record_id FROM checkpoint_knowledge
                   WHERE checkpoint_artifact_id=?""",
                (checkpoint_artifact_id, parent_checkpoint_artifact_id),
            )
        created: list[dict[str, Any]] = []
        for concept_key, concept_label in normalized:
            previous_row = db.execute("SELECT sha256 FROM knowledge_records ORDER BY sequence DESC LIMIT 1").fetchone()
            previous = previous_row[0] if previous_row else "0" * 64
            record_id = f"knowledge-{uuid.uuid4()}"
            body = {
                "id": record_id, "concept_key": concept_key, "concept_label": concept_label,
                "campaign_id": campaign_id, "session_id": session_id.strip(), "job_id": job_id,
                "run_id": run_id, "checkpoint_artifact_id": checkpoint_artifact_id,
                "parent_checkpoint_artifact_id": parent_checkpoint_artifact_id,
                "evidence": sorted(set(evidence)), "recorded_at": now, "previous_sha256": previous,
            }
            digest = content_hash(body)
            db.execute(
                """INSERT INTO knowledge_records
                   (id,concept_key,concept_label,campaign_id,session_id,job_id,run_id,
                    checkpoint_artifact_id,parent_checkpoint_artifact_id,evidence_json,
                    recorded_at,previous_sha256,sha256) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    record_id, concept_key, concept_label, campaign_id, session_id.strip(), job_id, run_id,
                    checkpoint_artifact_id, parent_checkpoint_artifact_id, canonical_json(body["evidence"]),
                    now, previous, digest,
                ),
            )
            db.execute(
                """INSERT INTO checkpoint_knowledge(checkpoint_artifact_id,concept_key,source_record_id)
                   VALUES(?,?,?) ON CONFLICT(checkpoint_artifact_id,concept_key)
                   DO UPDATE SET source_record_id=excluded.source_record_id""",
                (checkpoint_artifact_id, concept_key, record_id),
            )
            sequence = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
            created.append({"sequence": sequence, **body, "sha256": digest})
            self._event(
                db, "knowledge", record_id, "knowledge.taught", actor,
                {"concept_key": concept_key, "campaign_id": campaign_id, "checkpoint_artifact_id": checkpoint_artifact_id},
            )
        return created

    def checkpoint_knowledge(self, checkpoint_artifact_id: str) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                """SELECT r.* FROM checkpoint_knowledge k JOIN knowledge_records r ON r.id=k.source_record_id
                   WHERE k.checkpoint_artifact_id=? ORDER BY r.concept_key""",
                (checkpoint_artifact_id,),
            ).fetchall()
        return [self._knowledge_row(row) for row in rows]

    def campaign_knowledge(self, campaign_id: str) -> dict[str, list[dict[str, Any]]]:
        with self._connect() as db:
            known = db.execute(
                """SELECT r.* FROM campaign_knowledge_start s JOIN knowledge_records r ON r.id=s.source_record_id
                   WHERE s.campaign_id=? ORDER BY r.concept_key""",
                (campaign_id,),
            ).fetchall()
            trained = db.execute(
                "SELECT * FROM knowledge_records WHERE campaign_id=? ORDER BY sequence",
                (campaign_id,),
            ).fetchall()
        return {
            "known_at_start": [self._knowledge_row(row) for row in known],
            "trained_during_campaign": [self._knowledge_row(row) for row in trained],
        }

    @staticmethod
    def _knowledge_row(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["evidence"] = json.loads(value.pop("evidence_json"))
        return value

    def sync_knowledge_views(self, *, campaign_id: str | None = None) -> None:
        """Catch grep-friendly append-only views up to committed SQLite records."""

        root = self.path.parent / "knowledge"
        root.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            global_rows = [
                self._knowledge_row(row)
                for row in db.execute("SELECT * FROM knowledge_records ORDER BY sequence").fetchall()
            ]
            campaign_ids = (
                [campaign_id]
                if campaign_id is not None
                else [row[0] for row in db.execute("SELECT id FROM campaigns ORDER BY id").fetchall()]
            )
        self._append_only_jsonl(root / "ledger.jsonl", global_rows)
        readme = root / "README.txt"
        if not readme.exists():
            readme.write_text(
                "Append-only Ninereeds teaching ledger.\n"
                "Search all teaching history: rg -i 'dog' ledger.jsonl campaigns/\n"
                "Campaign known-at-start snapshots never change; trained-during files only append.\n",
                encoding="utf-8",
            )
        for selected in campaign_ids:
            if selected is None:
                continue
            view = self.campaign_knowledge(selected)
            directory = root / "campaigns" / selected
            directory.mkdir(parents=True, exist_ok=True)
            self._append_only_jsonl(directory / "known-at-start.jsonl", view["known_at_start"])
            self._append_only_jsonl(directory / "trained-during.jsonl", view["trained_during_campaign"])

    @staticmethod
    def _append_only_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        expected = [(canonical_json(row) + "\n").encode("utf-8") for row in rows]
        existing = path.read_bytes().splitlines(keepends=True) if path.exists() else []
        if len(existing) > len(expected) or any(left != right for left, right in zip(existing, expected)):
            raise ConflictError(f"append-only knowledge view diverged from Mission Hub: {path}")
        if len(existing) == len(expected):
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
        try:
            with os.fdopen(descriptor, "ab", closefd=False) as handle:
                for line in expected[len(existing):]:
                    handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(descriptor)

    def record_decision(self, *, decision_id: str, campaign_id: str | None, kind: str, payload: dict[str, Any], evidence: list[str], actor: str) -> None:
        now = utc_now()
        with self.transaction() as db:
            existing = db.execute("SELECT campaign_id,kind,payload_json,evidence_json FROM decisions WHERE id=?", (decision_id,)).fetchone()
            if existing is not None:
                expected = (campaign_id, kind, canonical_json(payload), canonical_json(evidence))
                if tuple(existing) != expected:
                    raise ConflictError(f"decision {decision_id} already exists with different evidence")
                return
            db.execute(
                "INSERT INTO decisions(id,campaign_id,kind,state,payload_json,evidence_json,actor,created_at) VALUES(?,?,?,'proposed',?,?,?,?)",
                (decision_id, campaign_id, kind, canonical_json(payload), canonical_json(evidence), actor, now),
            )
            self._event(db, "decision", decision_id, "decision.proposed", actor, {"kind": kind, "evidence": evidence})

    def transition_decision(self, decision_id: str, *, target: str, actor: str) -> None:
        transitions = {
            "proposed": {"approved", "rejected", "superseded"},
            "approved": {"executed", "superseded"},
        }
        now = utc_now()
        with self.transaction() as db:
            row = db.execute("SELECT state FROM decisions WHERE id=?", (decision_id,)).fetchone()
            if row is None:
                raise NotFoundError(decision_id)
            current = row[0]
            if current == target:
                return
            if current == "executed" and target == "approved":
                return
            if target not in transitions.get(current, set()):
                raise TransitionError(f"decision {decision_id} cannot transition from {current} to {target}")
            db.execute("UPDATE decisions SET state=?,decided_at=? WHERE id=?", (target, now, decision_id))
            self._event(db, "decision", decision_id, f"decision.{target}", actor, {})

    def list_rows(self, table: str, *, limit: int = 100) -> list[dict[str, Any]]:
        allowed = {
            "config_snapshots", "machines", "deployments", "campaigns", "decisions", "jobs", "runs",
            "artifacts", "evidence_sources", "events", "knowledge_records", "training_session_plans",
            "cortex_workflows", "cortex_workflow_jobs", "visual_workflows", "visual_workflow_jobs",
        }
        if table not in allowed:
            raise ValueError(f"table is not queryable: {table}")
        with self._connect() as db:
            rows = db.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def next_queued_job(self) -> dict[str, Any] | None:
        """Return the oldest due-or-soonest scheduled queued job."""
        with self._connect() as db:
            row = db.execute(
                """SELECT * FROM jobs
                   WHERE status='queued'
                   ORDER BY COALESCE(available_at, '') ASC, priority DESC, created_at ASC
                   LIMIT 1""",
            ).fetchone()
        return dict(row) if row is not None else None

    def record_schedule_firing(self, *, schedule_id: str, slot: str, job_id: str) -> bool:
        now = utc_now()
        with self.transaction() as db:
            existing = db.execute(
                "SELECT job_id FROM schedule_firings WHERE schedule_id=? AND slot=?",
                (schedule_id, slot),
            ).fetchone()
            if existing is not None:
                if existing[0] != job_id:
                    raise ConflictError(f"schedule slot {schedule_id}/{slot} already names another job")
                return False
            db.execute(
                "INSERT INTO schedule_firings(schedule_id,slot,job_id,created_at) VALUES(?,?,?,?)",
                (schedule_id, slot, job_id, now),
            )
        return True

    def record_machine_observation(self, machine_id: str, observation: dict[str, Any], *, actor: str) -> None:
        now = utc_now()
        with self.transaction() as db:
            if db.execute("SELECT 1 FROM machines WHERE id=?", (machine_id,)).fetchone() is None:
                raise NotFoundError(machine_id)
            db.execute(
                "UPDATE machines SET last_seen_at=?,last_observation_json=? WHERE id=?",
                (now, canonical_json(observation), machine_id),
            )
            self._event(db, "machine", machine_id, "machine.observed", actor, {"status": observation.get("status"), "hostname": observation.get("hostname")})

    def integrity_report(self) -> dict[str, Any]:
        with self._connect() as db:
            integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
            foreign = [tuple(row) for row in db.execute("PRAGMA foreign_key_check").fetchall()]
            events = db.execute("SELECT * FROM events ORDER BY sequence").fetchall()
        previous = "0" * 64
        chain_ok = True
        for row in events:
            body = {
                "id": row["id"], "entity_type": row["entity_type"], "entity_id": row["entity_id"],
                "event_type": row["event_type"], "actor": row["actor"], "occurred_at": row["occurred_at"],
                "payload_json": row["payload_json"], "previous_sha256": previous,
            }
            if row["previous_sha256"] != previous or row["sha256"] != content_hash(body):
                chain_ok = False
                break
            previous = row["sha256"]
        return {"sqlite_integrity": integrity, "foreign_key_errors": foreign, "event_chain_ok": chain_ok, "event_count": len(events)}

    def _transition_run(self, run_id: str, token: str, *, expected: str, target: str, actor: str, event: str) -> None:
        now = utc_now()
        with self.transaction() as db:
            run = self._authorized_run(db, run_id, token)
            if run["status"] != expected:
                raise TransitionError(f"run {run_id} is {run['status']}, expected {expected}")
            db.execute("UPDATE runs SET status=?,started_at=?,heartbeat_at=? WHERE id=?", (target, now, now, run_id))
            db.execute("UPDATE jobs SET status=?,updated_at=? WHERE id=?", (target, now, run["job_id"]))
            self._event(db, "run", run_id, event, actor, {})

    def _authorized_run(self, db: sqlite3.Connection, run_id: str, token: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise NotFoundError(run_id)
        supplied = hashlib.sha256(token.encode()).hexdigest()
        if not secrets.compare_digest(row["lease_token_sha256"], supplied):
            raise SafetyError("invalid lease token")
        return row

    def _register_output_artifacts(
        self,
        db: sqlite3.Connection,
        bundle: ConfigBundle,
        definition: dict[str, Any],
        artifacts: list[dict[str, Any]],
        *,
        run_id: str,
        machine_id: str,
        actor: str,
        now: str,
    ) -> None:
        machine = bundle.machines[machine_id]
        allowed_roots = [Path(machine["state_root"]).resolve(strict=False), *(Path(value).resolve(strict=False) for value in machine["artifact_roots"])]
        required_fields = {"kind", "sha256", "byte_size", "uri", "lifecycle", "manifest"}
        produced_kinds = [artifact.get("kind") for artifact in artifacts if isinstance(artifact, dict)]
        for required_kind in definition["required_artifact_types"]:
            if produced_kinds.count(required_kind) != 1:
                raise ValueError(f"job output must contain exactly one {required_kind} artifact")
        for artifact in artifacts:
            if not isinstance(artifact, dict) or set(artifact) != required_fields:
                raise ValueError("output artifact declaration has invalid fields")
            kind = artifact["kind"]
            if kind not in definition["artifact_types"] or kind not in bundle.artifact_types:
                raise SafetyError(f"job is not allowed to produce artifact type: {kind}")
            digest = artifact["sha256"]
            if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
                raise ValueError("output artifact has invalid SHA-256")
            if not isinstance(artifact["byte_size"], int) or isinstance(artifact["byte_size"], bool) or artifact["byte_size"] < 0:
                raise ValueError("output artifact has invalid byte size")
            path = Path(os.path.normpath(artifact["uri"])).resolve(strict=False)
            if not path.is_absolute() or not any(path == root or root in path.parents for root in allowed_roots):
                raise SafetyError(f"output artifact URI is outside configured machine roots: {path}")
            if artifact["lifecycle"] not in {"observed", "candidate"}:
                raise SafetyError("job output may only register observed or candidate artifacts")
            self._require_identity_policy_artifact(bundle, kind=kind, path=path, manifest=artifact["manifest"])
            artifact_id = f"art-{content_hash({'kind': kind, 'sha256': digest})[:16]}"
            db.execute(
                """INSERT OR IGNORE INTO artifacts(id,kind,producing_run_id,sha256,byte_size,lifecycle,manifest_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (artifact_id, kind, run_id, digest, artifact["byte_size"], artifact["lifecycle"], canonical_json(artifact["manifest"]), now),
            )
            db.execute(
                """INSERT INTO artifact_locations(artifact_id,machine_id,uri,observed_at,available)
                   VALUES(?,?,?,?,1) ON CONFLICT(artifact_id,machine_id,uri)
                   DO UPDATE SET observed_at=excluded.observed_at,available=1""",
                (artifact_id, machine_id, str(path), now),
            )
            self._event(db, "artifact", artifact_id, "artifact.produced", actor, {"run_id": run_id, "kind": kind, "sha256": digest, "uri": str(path)})

    @staticmethod
    def _require_identity_policy_artifact(
        bundle: ConfigBundle, *, kind: str, path: Path, manifest: dict[str, Any],
    ) -> None:
        if kind != "generated_material":
            return
        policy = bundle.identity_policy
        identity_scope = manifest.get("identity_scope")
        if identity_scope not in IDENTITY_SCOPES or any((
            manifest.get("lesson_policy_status") != "passed",
            manifest.get("lesson_policy_id") != policy["id"],
            manifest.get("lesson_policy_version") != policy["version"],
            manifest.get("lesson_policy_sha256") != policy_sha256(policy),
        )):
            raise SafetyError("generated lesson artifact did not pass the exact active identity policy")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise SafetyError("generated lesson artifact must be UTF-8 for identity-policy inspection") from exc
        try:
            material = json.loads(text)
        except json.JSONDecodeError:
            material = text
        require_lesson_material(material, policy)

    @staticmethod
    def _artifact_ids(definition: dict[str, Any], input_payload: dict[str, Any]) -> list[str]:
        result: list[str] = []
        for field in definition["artifact_input_fields"]:
            value = input_payload.get(field)
            if value is None:
                continue
            values = value if isinstance(value, list) else [value]
            if not all(isinstance(item, str) and item for item in values):
                raise ValueError(f"artifact input field {field} must contain artifact IDs")
            result.extend(values)
        return sorted(set(result))

    def _event(self, db: sqlite3.Connection, entity_type: str, entity_id: str, event_type: str, actor: str, payload: dict[str, Any]) -> str:
        previous_row = db.execute("SELECT sha256 FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
        previous = previous_row[0] if previous_row else "0" * 64
        event_id = f"evt-{uuid.uuid4()}"
        occurred = utc_now()
        body = {
            "id": event_id, "entity_type": entity_type, "entity_id": entity_id,
            "event_type": event_type, "actor": actor, "occurred_at": occurred,
            "payload_json": canonical_json(payload), "previous_sha256": previous,
        }
        digest = content_hash(body)
        db.execute(
            "INSERT INTO events(id,entity_type,entity_id,event_type,actor,occurred_at,payload_json,previous_sha256,sha256) VALUES(?,?,?,?,?,?,?,?,?)",
            (event_id, entity_type, entity_id, event_type, actor, occurred, body["payload_json"], previous, digest),
        )
        return event_id

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=self.busy_timeout_ms / 1000, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(f"PRAGMA busy_timeout={int(self.busy_timeout_ms)}")
        return db
