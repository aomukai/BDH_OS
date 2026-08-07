"""Read-only campaign, evaluation, and provider-use projections for The Lab."""

from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
from typing import Any

from .errors import NotFoundError
from .store import MissionHubStore


class Observatory:
    """Build presentation-safe projections from immutable Mission Hub evidence."""

    def __init__(self, store: MissionHubStore):
        self.store = store

    @staticmethod
    def _json(value: str | None, default: Any) -> Any:
        if not value:
            return default
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default

    def summary(self) -> dict[str, Any]:
        with self.store._connect() as db:
            campaign_rows = db.execute(
                "SELECT * FROM campaigns ORDER BY created_at DESC"
            ).fetchall()
            workflow_rows = db.execute(
                "SELECT * FROM cortex_workflows ORDER BY created_at DESC"
            ).fetchall()
            job_rows = db.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC"
            ).fetchall()
            run_rows = db.execute(
                "SELECT * FROM runs ORDER BY COALESCE(started_at, lease_expires_at) DESC"
            ).fetchall()
            evaluation_rows = db.execute(
                """SELECT a.*,j.campaign_id,l.uri,l.machine_id
                   FROM artifacts a
                   LEFT JOIN runs r ON r.id=a.producing_run_id
                   LEFT JOIN jobs j ON j.id=r.job_id
                   LEFT JOIN artifact_locations l ON l.artifact_id=a.id
                     AND l.machine_id='mission-hub' AND l.available=1
                   WHERE a.kind='evaluation_report'
                   ORDER BY a.created_at DESC"""
            ).fetchall()
            knowledge_rows = db.execute(
                "SELECT * FROM knowledge_records ORDER BY sequence"
            ).fetchall()
            transcript_rows = db.execute(
                """SELECT a.id,a.manifest_json,l.uri,j.job_type,j.campaign_id,a.created_at
                   FROM artifacts a
                   JOIN artifact_locations l ON l.artifact_id=a.id
                     AND l.machine_id='mission-hub' AND l.available=1
                   LEFT JOIN runs r ON r.id=a.producing_run_id
                   LEFT JOIN jobs j ON j.id=r.job_id
                   WHERE a.kind='provider_transcript'
                   ORDER BY a.created_at DESC"""
            ).fetchall()

        campaigns = []
        for row in campaign_rows:
            item = dict(row)
            item["metadata"] = self._json(item.pop("metadata_json"), {})
            campaigns.append(item)
        active = next((row for row in campaigns if row["state"] == "active"), None)
        active_id = active["id"] if active else None

        workflows = []
        for row in workflow_rows:
            item = dict(row)
            spec = self._json(item.pop("specification_json"), {})
            item["branch_id"] = spec.get("branch_id")
            item["blocks_total"] = len(spec.get("sessions", []))
            item["development_stage"] = spec.get("evaluation_context", {}).get("development_stage")
            workflows.append(item)

        evaluations = []
        for row in evaluation_rows:
            item = dict(row)
            manifest = self._json(item.pop("manifest_json"), {})
            branch_id = manifest.get("branch_id")
            structured = False
            if item.get("uri"):
                try:
                    document = json.loads(Path(item["uri"]).read_text(encoding="utf-8"))
                    structured = self._is_structured_evaluation(document)
                except (OSError, json.JSONDecodeError):
                    structured = False
            evaluations.append({
                "id": item["id"],
                "campaign_id": item.get("campaign_id") or manifest.get("campaign_id") or manifest.get("legacy_campaign_id"),
                "branch_id": branch_id,
                "checkpoint_artifact_id": manifest.get("candidate_artifact_id"),
                "checkpoint_sha256": manifest.get("candidate_sha256"),
                "created_at": item["created_at"],
                "branch_complete": bool(manifest.get("branch_complete")),
                "structured": structured,
                "historical": str(manifest.get("schema_version", "")).startswith("ninereeds_historical"),
                "limitations": manifest.get("historical_limitations"),
                "views": ["mri", "atlas", "map"] if structured else [],
            })

        required_branches = []
        if active:
            required_branches = list(active["metadata"].get("campaign_contract", {}).get("branches", []))
        branch_rows = []
        for branch_id in required_branches:
            branch_workflows = [row for row in workflows if row["campaign_id"] == active_id and row["branch_id"] == branch_id]
            workflow = branch_workflows[0] if branch_workflows else None
            branch_evaluations = [row for row in evaluations if row["branch_id"] == branch_id]
            terminal = next((row for row in branch_evaluations if row["branch_complete"]), None)
            if terminal is None and workflow is None:
                terminal = next((row for row in branch_evaluations if row["historical"]), None)
            branch_rows.append({
                "branch_id": branch_id,
                "status": workflow["status"] if workflow else ("historical" if terminal else "not_started"),
                "blocks_total": workflow["blocks_total"] if workflow else None,
                "terminal_evaluation": terminal,
                "scan_status": (
                    "available" if terminal and terminal["structured"]
                    else "historical_summary" if terminal
                    else "waiting"
                ),
            })

        campaign_jobs = [dict(row) for row in job_rows if row["campaign_id"] == active_id]
        campaign_job_ids = {row["id"] for row in campaign_jobs}
        campaign_runs = [dict(row) for row in run_rows if row["job_id"] in campaign_job_ids]
        campaign_knowledge = [dict(row) for row in knowledge_rows if row["campaign_id"] == active_id]
        concept_keys = {row["concept_key"] for row in campaign_knowledge}
        baseline_count = int(active["metadata"].get("baseline_knowledge_count", 0)) if active else 0
        job_statuses = Counter(row["status"] for row in campaign_jobs)
        run_statuses = Counter(row["status"] for row in campaign_runs)

        route_stats = self._route_statistics(transcript_rows)
        timeline = self._timeline(active_id, workflows, campaign_jobs, campaign_runs, evaluations)
        complete_scans = sum(row["scan_status"] in {"available", "historical_summary"} for row in branch_rows)
        return {
            "active_campaign": active,
            "campaign_scan": {
                "required": len(required_branches),
                "complete": complete_scans,
                "ready": bool(required_branches) and complete_scans == len(required_branches),
                "policy": "The terminal chat-and-MRI evaluation of every declared branch forms the campaign-completion scan. Loss remains telemetry only.",
            },
            "branches": branch_rows,
            "evaluations": evaluations[:100],
            "statistics": {
                "baseline_known": baseline_count,
                "things_taught": len(concept_keys),
                "lesson_records": len(campaign_knowledge),
                "jobs": len(campaign_jobs),
                "job_statuses": dict(job_statuses),
                "attempts": len(campaign_runs),
                "retry_attempts": sum(max(0, int(row["attempt"]) - 1) for row in campaign_runs),
                "run_statuses": dict(run_statuses),
                "training_blocks": sum(row["job_type"] == "model.train" and row["status"] == "succeeded" for row in campaign_jobs),
                "evaluations_completed": sum(row["job_type"] == "model.evaluate" and row["status"] == "succeeded" for row in campaign_jobs),
            },
            "route_statistics": route_stats,
            "timeline": timeline[:160],
        }

    def evaluation(self, artifact_id: str) -> dict[str, Any]:
        with self.store._connect() as db:
            row = db.execute(
                """SELECT a.id,a.sha256,a.manifest_json,l.uri
                   FROM artifacts a JOIN artifact_locations l ON l.artifact_id=a.id
                   WHERE a.id=? AND a.kind='evaluation_report'
                     AND l.machine_id='mission-hub' AND l.available=1
                   ORDER BY l.observed_at DESC LIMIT 1""",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(artifact_id)
        try:
            document = json.loads(Path(row["uri"]).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise NotFoundError(f"evaluation content unavailable: {artifact_id}") from exc
        if not self._is_structured_evaluation(document):
            raise NotFoundError(f"interactive scan unavailable for historical summary: {artifact_id}")
        return {
            "artifact_id": artifact_id,
            "sha256": row["sha256"],
            "manifest": self._json(row["manifest_json"], {}),
            "evaluation": document,
        }

    @staticmethod
    def _is_structured_evaluation(document: Any) -> bool:
        return (
            isinstance(document, dict)
            and isinstance(document.get("candidate"), dict)
            and isinstance(document["candidate"].get("scan"), dict)
            and isinstance(document["candidate"].get("cases"), list)
        )

    @staticmethod
    def _timeline(
        campaign_id: str | None,
        workflows: list[dict[str, Any]],
        jobs: list[dict[str, Any]],
        runs: list[dict[str, Any]],
        evaluations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for workflow in workflows:
            if workflow["campaign_id"] != campaign_id:
                continue
            events.append({
                "at": workflow["created_at"], "kind": "branch", "status": workflow["status"],
                "title": workflow["branch_id"] or workflow["id"],
                "detail": f"{workflow['blocks_total']} declared blocks",
            })
        run_by_job = defaultdict(list)
        for run in runs:
            run_by_job[run["job_id"]].append(run)
        for job in jobs:
            if job["job_type"] not in {"model.train", "model.evaluate", "executor.generate", "campaign.decide"}:
                continue
            attempts = run_by_job.get(job["id"], [])
            events.append({
                "at": job.get("updated_at") or job["created_at"], "kind": "job", "status": job["status"],
                "title": job["job_type"],
                "detail": f"{len(attempts)} attempt{'s' if len(attempts) != 1 else ''} · {job['id']}",
            })
        for evaluation in evaluations:
            if evaluation["campaign_id"] not in {campaign_id, "play-word-evolution-0501-2000-v1"}:
                continue
            events.append({
                "at": evaluation["created_at"], "kind": "scan", "status": "succeeded",
                "title": "Terminal branch scan" if evaluation["branch_complete"] else "Chat + MRI evaluation",
                "detail": evaluation["branch_id"] or evaluation["id"],
            })
        return sorted(events, key=lambda row: row["at"] or "", reverse=True)

    @staticmethod
    def _route_statistics(rows: list[Any]) -> list[dict[str, Any]]:
        stats: dict[str, dict[str, Any]] = {}
        for raw in rows:
            row = dict(raw)
            try:
                document = json.loads(Path(row["uri"]).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            attempts = document.get("attempts") if isinstance(document, dict) else None
            if not isinstance(attempts, list) or not attempts:
                continue
            route_id = str(document.get("route_id") or row.get("job_type") or "unknown")
            item = stats.setdefault(route_id, {
                "route_id": route_id, "jobs": 0, "attempts": 0, "fallback_uses": 0,
                "fallback_successes": 0, "models": Counter(),
            })
            item["jobs"] += 1
            item["attempts"] += len(attempts)
            for index, attempt in enumerate(attempts):
                model = str(attempt.get("model_id") or "unknown")
                item["models"][model] += 1
                if index > 0:
                    item["fallback_uses"] += 1
                    if attempt.get("status") == "succeeded":
                        item["fallback_successes"] += 1
        result = []
        for item in stats.values():
            jobs = item["jobs"]
            fallback_rate = item["fallback_uses"] / jobs if jobs else 0.0
            result.append({
                **{key: value for key, value in item.items() if key != "models"},
                "fallback_rate": round(fallback_rate, 4),
                "models": [{"model_id": key, "attempts": value} for key, value in item["models"].most_common()],
                "attention": "review_primary" if jobs >= 3 and fallback_rate >= 0.5 else "normal",
            })
        return sorted(result, key=lambda row: (-row["fallback_rate"], row["route_id"]))
