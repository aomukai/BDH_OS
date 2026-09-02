"""Grep-friendly, provenance-preserving memory for one autonomous research campaign."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
import uuid

from .config import ConfigBundle, machine_id_for_role
from .jsonutil import canonical_json, content_hash


JOURNAL_SCHEMA_VERSION = "ninereeds_research_campaign_journal_v1"
ENRICHMENT_SCHEMA_VERSION = "ninereeds_research_journal_enrichment_v1"
TERMINAL_EXPERIMENT_STATES = {"succeeded", "failed", "blocked", "cancelled"}
_TOKEN = re.compile(r"[a-z0-9][a-z0-9._:-]{2,}")
_STOPWORDS = {
    "about", "after", "again", "against", "also", "and", "because", "before",
    "being", "between", "could", "does", "during", "every", "false", "for", "from",
    "have", "into", "kind", "none", "not", "null", "only", "other", "should", "than",
    "that", "the", "their", "then", "there", "these", "they", "this", "through", "true",
    "under", "using", "when", "where", "which", "while", "with", "would",
}


def _json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    parsed = json.loads(value)
    return parsed if isinstance(parsed, dict) else {}


def _single_line(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _result_summary(specification: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    """Retain diagnostic facts while excluding bulky snapshots and binary-adjacent detail."""
    kind = specification.get("kind")
    if not result:
        return {}
    if kind == "code_change":
        tests = []
        for item in result.get("tests", []):
            if isinstance(item, dict):
                tests.append({
                    key: item.get(key)
                    for key in ("scope", "passed", "exit_code", "sha256")
                    if key in item
                })
        deployment = result.get("deployment") if isinstance(result.get("deployment"), dict) else {}
        return {
            key: value for key, value in {
                "candidate_git_head": result.get("candidate_git_head"),
                "change_kind": result.get("change_kind"),
                "changed_files": result.get("changed_files"),
                "sol_changed_files": result.get("sol_changed_files"),
                "tests": tests,
                "deployment_id": deployment.get("id"),
                "release_id": deployment.get("release_id"),
            }.items() if value not in (None, [], {})
        }
    if kind == "dataset_acquisition":
        return {
            key: result[key]
            for key in (
                "artifact_id", "dataset_id", "dataset_name", "sha256", "byte_size",
                "record_count", "source_url", "license",
            )
            if key in result
        }

    progress = result.get("progress") if isinstance(result.get("progress"), dict) else {}
    latest = result.get("latest_snapshot") if isinstance(result.get("latest_snapshot"), dict) else {}
    if not progress and isinstance(latest.get("progress"), dict):
        progress = latest["progress"]
    development = (
        progress.get("development_telemetry")
        if isinstance(progress.get("development_telemetry"), dict)
        else {}
    )
    preflight = progress.get("organ_preflight") if isinstance(progress.get("organ_preflight"), dict) else {}
    summary = {
        "organism_status": result.get("organism_status"),
        "events_consumed": progress.get("events_consumed"),
        "text_events_consumed": progress.get("text_events_consumed"),
        "visual_events_consumed": progress.get("visual_events_consumed"),
        "sessions_completed": progress.get("sessions_completed"),
        "active_uid_count": progress.get("active_uid_count"),
        "next_uid": progress.get("next_uid"),
        "last_loss": progress.get("last_loss"),
        "development_telemetry": development,
        "organ_preflight_status": preflight.get("status"),
        "service": result.get("service"),
        "failure": result.get("failure"),
    }
    return {key: value for key, value in summary.items() if value not in (None, [], {})}


def _experiment_fingerprint(specification: dict[str, Any]) -> str:
    kind = specification.get("kind")
    if kind == "organism_experiment":
        identity = {
            key: specification.get(key)
            for key in (
                "kind", "dataset_id", "epochs", "max_records_per_epoch", "order_policy",
                "order_seed", "intervention_type", "max_sessions", "max_events_per_session",
                "controls",
            )
        }
    elif kind == "code_change":
        identity = {
            key: specification.get(key)
            for key in ("kind", "objective", "scopes", "acceptance_criteria")
        }
    elif kind == "dataset_acquisition":
        identity = {"kind": kind, "acquisition": specification.get("acquisition")}
    else:
        identity = specification
    return content_hash(identity)


def _keywords(*values: Any) -> list[str]:
    text = " ".join(_single_line(value).lower() for value in values if value not in (None, "", [], {}))
    terms = set()
    for raw_term in _TOKEN.findall(text):
        term = raw_term.rstrip("._:-")
        if len(term) < 3 or term in _STOPWORDS:
            continue
        # Content hashes remain available in their dedicated fields but make a
        # poor human lookup vocabulary. Exclude both bare and labelled digests.
        digest = term.rsplit(":", 1)[-1]
        if len(digest) >= 32 and all(character in "0123456789abcdef" for character in digest):
            continue
        terms.add(term)
    return sorted(terms)[:96]


class ResearchCampaignJournal:
    """Build a complete compact ledger from authoritative Mission Hub rows."""

    def __init__(self, store: Any, bundle: ConfigBundle):
        self.store = store
        self.bundle = bundle
        self.hub_machine = machine_id_for_role(bundle, "mission_hub")
        self.root = Path(bundle.machines[self.hub_machine]["state_root"]).resolve() / "research-journals"

    def render(self, lab_id: str) -> dict[str, Any]:
        lab, experiments, activations = self._rows(lab_id)
        enrichments = self._enrichments(lab["campaign_id"])
        activation_by_id = {row["id"]: row for row in activations}
        experiment_activation_ids: set[str] = set()
        lines = [
            "<!-- generated by Mission Hub; Luna enrichments are explicitly labeled -->",
            f"# Campaign {lab['campaign_number']} searchable experiment journal",
            "",
            f"JOURNAL_SCHEMA: {JOURNAL_SCHEMA_VERSION}",
            f"CAMPAIGN_ID: {lab['campaign_id']}",
            f"LAB_ID: {lab['id']}",
            f"GOAL: {lab['goal']}",
            "LOOKUP: rg -n -i 'keyword|parameter|dataset|experiment-id' campaign-journal.md",
            "NOTE: Repetition is allowed when intentional; label it replication, recovery, or rerun.",
            "",
        ]
        for experiment in experiments:
            specification = _json(experiment["specification_json"])
            result = _json(experiment["result_json"])
            summary = _result_summary(specification, result)
            suffix = experiment["id"].rsplit("-", 1)[-1]
            activation_id = f"research-activation-{lab['campaign_number']}-{suffix}"
            activation = activation_by_id.get(activation_id)
            if activation is not None:
                experiment_activation_ids.add(activation_id)
            decision = _json(activation["decision_json"]) if activation else {}
            action = decision.get("action") if isinstance(decision.get("action"), dict) else {}
            enrichment = enrichments.get(experiment["id"], {})
            acquisition = (
                specification.get("acquisition")
                if isinstance(specification.get("acquisition"), dict)
                else {}
            )
            deterministic_keywords = _keywords(
                experiment["id"], experiment["title"], experiment["hypothesis"],
                specification, summary, action.get("kind"), decision.get("message"),
                decision.get("rationale"),
            )
            luna_keywords = enrichment.get("keywords", []) if isinstance(enrichment.get("keywords"), list) else []
            combined_keywords = sorted(set(deterministic_keywords) | {str(item) for item in luna_keywords})
            fingerprint = _experiment_fingerprint(specification)
            result_sha = hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest() if result else None
            artifacts = self._experiment_artifacts(experiment["launch_job_id"])
            lines.extend([
                f"## {experiment['id']} — {experiment['title']}",
                "",
                f"EXPERIMENT_ID: {experiment['id']}",
                f"SEQUENCE: {experiment['sequence']}",
                f"STATUS: {experiment['state']}",
                f"ACTION: {action.get('kind') or specification.get('kind') or 'unknown'}",
                f"INTERVENTION: {specification.get('intervention_type') or specification.get('kind') or 'unknown'}",
                f"CONTROL: {specification.get('control_experiment_id') or 'none'}",
                f"DATASET: {specification.get('dataset_id') or acquisition.get('dataset_name') or 'none'}",
                f"REPEAT_FINGERPRINT: {fingerprint}",
                f"KEYWORDS: {' '.join(combined_keywords)}",
                f"HYPOTHESIS: {experiment['hypothesis']}",
                f"SPECIFICATION: {_single_line(specification)}",
                f"RESULT: {_single_line(summary)}",
                f"RESULT_SHA256: {result_sha or 'none'}",
                f"SOL_MESSAGE: {decision.get('message') or 'none'}",
                f"SOL_RATIONALE: {decision.get('rationale') or 'none'}",
                f"LUNA_SUMMARY: {enrichment.get('summary') or 'pending'}",
                f"PROVENANCE: activation={activation_id} launch_job={experiment['launch_job_id']} "
                f"launch_run={experiment['launch_run_id'] or 'none'} status_job={experiment['last_status_job_id'] or 'none'}",
                f"ARTIFACTS: {_single_line(artifacts)}",
                "",
            ])

        decision_only = [
            row for row in activations
            if row["id"] not in experiment_activation_ids and row["decision_json"] is not None
        ]
        if decision_only:
            lines.extend(["# Decisions without a new experiment", ""])
            for activation in decision_only:
                decision = _json(activation["decision_json"])
                action = decision.get("action") if isinstance(decision.get("action"), dict) else {}
                lines.extend([
                    f"## {activation['id']}",
                    f"STATUS: {activation['status']}",
                    f"ACTION: {action.get('kind') or 'unknown'}",
                    f"KEYWORDS: {' '.join(_keywords(action, decision.get('message'), decision.get('rationale')))}",
                    f"SOL_MESSAGE: {decision.get('message') or 'none'}",
                    f"SOL_RATIONALE: {decision.get('rationale') or 'none'}",
                    "",
                ])

        data = ("\n".join(lines).rstrip() + "\n").encode("utf-8")
        path = self.root / str(lab["campaign_id"]) / "campaign-journal.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        self._atomic_write(path, data)
        return {
            "schema_version": JOURNAL_SCHEMA_VERSION,
            "uri": str(path),
            "sha256": hashlib.sha256(data).hexdigest(),
            "byte_size": len(data),
            "experiment_count": len(experiments),
        }

    def queue_one_luna_enrichment(self, lab_id: str, *, actor: str) -> dict[str, Any] | None:
        lab, experiments, _ = self._rows(lab_id)
        existing = self._enrichment_record_hashes(lab["campaign_id"])
        with self.store._connect() as db:
            jobs = {
                row["idempotency_key"]: row["status"]
                for row in db.execute(
                    "SELECT idempotency_key,status FROM jobs WHERE job_type='research.journal_update'"
                ).fetchall()
            }
        for experiment in reversed(experiments):
            if experiment["state"] not in TERMINAL_EXPERIMENT_STATES:
                continue
            record = self._librarian_record(lab, experiment)
            record_sha = content_hash(record)
            if existing.get(experiment["id"]) == record_sha:
                continue
            # Include the config identity so an ineligible job left by a
            # superseded deployment cannot suppress the same enrichment after
            # a corrected configuration is activated.
            idempotency_key = (
                f"research-journal:{experiment['id']}:{record_sha}:"
                f"{self.bundle.sha256[:12]}"
            )
            if idempotency_key in jobs:
                continue
            return self.store.create_job(
                self.bundle,
                job_type="research.journal_update",
                input_payload={
                    "lab_id": lab["id"],
                    "campaign_id": lab["campaign_id"],
                    "campaign_number": int(lab["campaign_number"]),
                    "experiment_id": experiment["id"],
                    "record_sha256": record_sha,
                    "record": record,
                },
                idempotency_key=idempotency_key,
                created_by=actor,
                campaign_id=lab["campaign_id"],
                requested_machine_id=self.hub_machine,
                approved=True,
            )
        return None

    def _rows(self, lab_id: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        with self.store._connect() as db:
            lab_row = db.execute("SELECT * FROM research_labs WHERE id=?", (lab_id,)).fetchone()
            if lab_row is None:
                raise ValueError(f"unknown research lab {lab_id}")
            experiments = [dict(row) for row in db.execute(
                "SELECT * FROM research_experiments WHERE lab_id=? ORDER BY sequence,id", (lab_id,),
            ).fetchall()]
            activations = [dict(row) for row in db.execute(
                "SELECT * FROM research_activations WHERE lab_id=? ORDER BY sequence,id", (lab_id,),
            ).fetchall()]
        return dict(lab_row), experiments, activations

    def _experiment_artifacts(self, job_id: str) -> list[dict[str, Any]]:
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT a.id,a.kind,a.sha256 FROM artifacts a
                   JOIN runs r ON r.id=a.producing_run_id WHERE r.job_id=? ORDER BY a.kind,a.id""",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _enrichments(self, campaign_id: str) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT a.manifest_json,l.uri,a.created_at FROM artifacts a
                   JOIN artifact_locations l ON l.artifact_id=a.id
                   WHERE a.kind='research_journal_enrichment' AND a.lifecycle!='deleted'
                     AND l.machine_id=? AND l.available=1
                   ORDER BY a.created_at""",
                (self.hub_machine,),
            ).fetchall()
        for row in rows:
            manifest = _json(row["manifest_json"])
            if manifest.get("campaign_id") != campaign_id:
                continue
            path = Path(row["uri"])
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and value.get("schema_version") == ENRICHMENT_SCHEMA_VERSION:
                result[str(manifest.get("experiment_id"))] = value
        return result

    def _enrichment_record_hashes(self, campaign_id: str) -> dict[str, str]:
        return {
            experiment_id: str(value.get("record_sha256"))
            for experiment_id, value in self._enrichments(campaign_id).items()
            if value.get("record_sha256")
        }

    def _librarian_record(self, lab: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
        specification = _json(experiment["specification_json"])
        result = _json(experiment["result_json"])
        return {
            "campaign_id": lab["campaign_id"],
            "campaign_goal": lab["goal"],
            "experiment_id": experiment["id"],
            "sequence": int(experiment["sequence"]),
            "title": experiment["title"],
            "hypothesis": experiment["hypothesis"],
            "state": experiment["state"],
            "specification": specification,
            "result_summary": _result_summary(specification, result),
            "result_sha256": (
                hashlib.sha256(canonical_json(result).encode("utf-8")).hexdigest()
                if result else None
            ),
            "repeat_fingerprint": _experiment_fingerprint(specification),
        }

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
