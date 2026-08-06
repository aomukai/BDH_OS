"""SQLite-backed single source of truth for Ninereeds operations."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
from typing import Any, Iterator
import uuid

from .config import ConfigBundle
from .errors import ConflictError, NotFoundError, SafetyError, TransitionError
from .jsonutil import canonical_json, content_hash
from .schema import load_schema, validate


SCHEMA_VERSION = 5
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
                if version != SCHEMA_VERSION:
                    raise RuntimeError(f"database schema {current[0]} is not supported by code schema {SCHEMA_VERSION}")
                db.execute("UPDATE metadata SET value=? WHERE key='schema_version'", (str(version),))

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
        if metered_models and reserved_usd <= 0:
            raise SafetyError("metered provider route requires a positive per-job cost reservation")
        repo_root = bundle.root.parent.parent
        schema = load_schema(repo_root, definition["input_schema"])
        errors = validate(input_payload, schema)
        if errors:
            raise ValueError("invalid job input: " + "; ".join(errors))
        artifact_ids = self._artifact_ids(definition, input_payload)
        config = self.active_config()
        if config["sha256"] != bundle.sha256:
            raise ConflictError("loaded configuration is not the active configuration")
        job_id = f"job-{uuid.uuid4()}"
        now = utc_now()
        approval_policy = definition["approval"]
        budget_approval = bool(reserved_usd > bundle.budget["per_run_approval_above"])
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
            if reserved_usd:
                now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
                weekly_since = (now_dt - timedelta(days=7)).isoformat(timespec="microseconds").replace("+00:00", "Z")
                monthly_since = (now_dt - timedelta(days=30)).isoformat(timespec="microseconds").replace("+00:00", "Z")
                weekly_used = float(db.execute("SELECT COALESCE(SUM(reserved_usd),0) FROM budget_reservations WHERE created_at>=?", (weekly_since,)).fetchone()[0])
                monthly_used = float(db.execute("SELECT COALESCE(SUM(reserved_usd),0) FROM budget_reservations WHERE created_at>=?", (monthly_since,)).fetchone()[0])
                weekly_cap = bundle.budget["weekly_limit"] * bundle.budget["hard_stop_fraction"] - bundle.budget["emergency_reserve"]
                monthly_cap = bundle.budget["monthly_limit"] * bundle.budget["hard_stop_fraction"] - bundle.budget["emergency_reserve"]
                if weekly_used + reserved_usd > weekly_cap or monthly_used + reserved_usd > monthly_cap:
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
        now = utc_now()
        with self.transaction() as db:
            db.execute(
                "INSERT INTO visual_workflows(id,status,specification_json,config_snapshot_id,created_by,created_at,updated_at) VALUES(?,'active',?,?,?,?,?)",
                (workflow_id, canonical_json(specification), active["id"], actor, now, now),
            )
            self._event(db, "visual_workflow", workflow_id, "visual_workflow.created", actor, {})
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
                if candidate["job_type"] not in allowed:
                    continue
                candidate_definition = bundle.jobs.get(candidate["job_type"])
                if candidate_definition is None or not candidate_definition["enabled"]:
                    continue
                if candidate_definition["executor_role"] != machine["role"]:
                    continue
                if not set(candidate_definition["required_capabilities"]).issubset(set(machine["capabilities"])):
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
        config = self.active_config()
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
            self._event(db, "campaign", campaign_id, "campaign.created", actor, {"state": state})

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
        allowed = {"config_snapshots", "machines", "deployments", "campaigns", "decisions", "jobs", "runs", "artifacts", "evidence_sources", "events"}
        if table not in allowed:
            raise ValueError(f"table is not queryable: {table}")
        with self._connect() as db:
            rows = db.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

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
