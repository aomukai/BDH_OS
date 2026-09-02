"""Durable twenty-minute Sol conductor for sequential research campaigns."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import re
from typing import Any
import uuid

from .campaign_contract import validate_campaign_contract
from .config import ConfigBundle, machine_id_for_role
from .errors import ConflictError, MissionHubError, NotFoundError, SafetyError
from .jsonutil import canonical_json
from .lab import LabStore
from .store import MissionHubStore, TERMINAL_JOB_STATES, utc_now


HEARTBEAT_SECONDS = 20 * 60
ACTIVE_JOB_STATES = {"draft", "awaiting_approval", "queued", "leased", "running"}


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (result[:48].rstrip("-") or "research")


def research_campaign_metadata(goal: str) -> dict[str, Any]:
    """Return the immutable knowledge-first contract shared by lab campaigns."""
    return {
        "schema_version": "ninereeds_research_lab_campaign_v1",
        "campaign_contract": {
            "schema_version": "ninereeds_campaign_contract_v1",
            "mode": "experimental",
            "development_stage": "autonomous Mycelium laboratory",
            "purpose": goal,
            "success_criteria": [
                "The campaign resolves or materially narrows its declared research question with reproducible evidence.",
                "Every intervention is bound to an exact configuration, source release, dataset identity, and durable result.",
                "Negative, null, regression, and recovery results are retained as knowledge rather than hidden as failed improvement.",
            ],
            "failure_criteria": [
                "The campaign performs work merely to appear active or treats loss as an automatic rank, promotion, or rollback signal.",
                "A wake interrupts, duplicates, or silently replaces an experiment that authoritative state says is still running.",
                "An idle unfinished campaign skips its next decision without either advancing the research or concluding it.",
            ],
            "expected_regressions": [
                "Traditional repeated exposure may regress behavior or fail to produce capabilities.",
                "Mycelium growth, routing, energy, and packing defaults may be badly calibrated before useful regimes are identified.",
                "A well-controlled falsification or null result may be the most valuable outcome of a campaign.",
            ],
            "branches": [],
            "merge_sources": [],
            "target_capabilities": [
                "knowledge of BDH learning dynamics",
                "knowledge of Mycelium growth and routing dynamics",
                "knowledge of multimodal text and visual bootstrap behavior",
            ],
            "bootstrap_milestones": [],
            "hypothesis": goal,
            "observations_sought": [
                "Learning, regression, and recovery across controlled exposure order and duration.",
                "Cell birth, routing, energy, activation, packing, and structural behavior under controlled parameter changes.",
                "Differences between text ingress through frozen LFM, visual ingress through frozen SigLIP2, and shared latent-state learning.",
            ],
        },
        "authority": {
            "conductor": "Sol",
            "mission_hub_is_control_plane": True,
            "trainbox_is_executor": True,
            "may_launch_bounded_experiments_without_per-experiment_permission": True,
            "may_acquire_research_data": True,
            "may_edit_experimental_model_code": True,
            "improvement_is_not_required": True,
            "loss_is_telemetry_only": True,
        },
        "heartbeat_seconds": HEARTBEAT_SECONDS,
    }


def commission_research_lab(
    store: MissionHubStore,
    bundle: ConfigBundle,
    *,
    campaign_number: int,
    title: str,
    goal: str,
    actor: str,
    supersede_campaign_id: str | None = None,
) -> dict[str, Any]:
    """Atomically commission one ordinary numbered campaign and its Lab thread."""
    if campaign_number <= 0 or not title.strip() or not goal.strip():
        raise ValueError("research campaign number, title, and goal are required")
    active = store.active_config()
    if active["sha256"] != bundle.sha256:
        raise ConflictError("loaded configuration is not the active configuration")
    metadata = research_campaign_metadata(goal.strip())
    validate_campaign_contract(
        metadata["campaign_contract"], active["payload"]["resolved"]["campaign_modes"],
    )
    campaign_id = f"campaign-{campaign_number}-{_slug(title)}-v1"
    lab_id = f"research-lab-{campaign_number}"
    thread_id = f"thread-{uuid.uuid5(uuid.NAMESPACE_URL, 'ninereeds:research-lab:' + str(campaign_number))}"
    now = utc_now()
    todo = {
        "focus": goal.strip(),
        "current_hypothesis": "Establish a reproducible complete-organ baseline before varying one mechanism at a time.",
        "next_questions": [
            "What does the unmodified complete-organ bootstrap do over a bounded exposure?",
            "Which measurements distinguish learning, regression, recovery, routing change, and cell birth?",
            "Which single Mycelium control should the next campaign isolate?",
        ],
        "constraints": [
            "Knowledge is the objective; improvement is optional.",
            "Loss is telemetry only.",
            "Do not interrupt or duplicate an authoritatively running experiment.",
            "When idle, advance or conclude; never sleep through an unfinished campaign.",
        ],
    }
    subject = f"Campaign {campaign_number} — {title.strip()}"
    opening = (
        f"I am opening Campaign {campaign_number}.\n\n"
        f"Research goal: {goal.strip()}\n\n"
        "I will wake every 20 minutes. A running experiment will be observed and left alone; "
        "an idle unfinished campaign will advance or conclude. I am optimizing for knowledge, "
        "not activity or automatic improvement. I will announce each decision here and then execute it."
    )
    with store.transaction() as db:
        existing_lab = db.execute(
            "SELECT id FROM research_labs WHERE state='active'"
        ).fetchone()
        if existing_lab is not None:
            raise ConflictError(f"research lab already active: {existing_lab[0]}")
        if db.execute(
            "SELECT 1 FROM research_labs WHERE campaign_number=?", (campaign_number,),
        ).fetchone() is not None:
            raise ConflictError(f"Campaign {campaign_number} already has a research lab")
        if supersede_campaign_id is not None:
            previous = db.execute(
                "SELECT state FROM campaigns WHERE id=?", (supersede_campaign_id,),
            ).fetchone()
            if previous is None:
                raise NotFoundError(supersede_campaign_id)
            live = db.execute(
                "SELECT COUNT(*) FROM jobs WHERE campaign_id=? AND status IN ('leased','running')",
                (supersede_campaign_id,),
            ).fetchone()[0]
            if live:
                raise SafetyError("cannot supersede a campaign while one of its jobs is running")
            if previous["state"] in {"draft", "paused", "active"}:
                db.execute(
                    "UPDATE campaigns SET state='superseded',updated_at=? WHERE id=?",
                    (now, supersede_campaign_id),
                )
                store._event(
                    db, "campaign", supersede_campaign_id,
                    "campaign.superseded_by_numbered_research_lab", actor,
                    {"successor_campaign_id": campaign_id, "campaign_number": campaign_number},
                )
        if db.execute("SELECT 1 FROM campaigns WHERE id=?", (campaign_id,)).fetchone():
            raise ConflictError(f"campaign already exists: {campaign_id}")
        db.execute(
            """INSERT INTO campaigns
               (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
               VALUES(?,?,'active',?,?,?,?,?)""",
            (campaign_id, subject, active["id"], goal.strip(), canonical_json(metadata), now, now),
        )
        db.execute(
            """INSERT INTO message_threads
               (id,subject,state,created_by,created_at,updated_at)
               VALUES(?,?,'open',?,?,?)""",
            (thread_id, subject, actor, now, now),
        )
        db.execute(
            """INSERT INTO thread_messages
               (id,thread_id,sender,body,created_at)
               VALUES(?,?,'sol',?,?)""",
            (f"message-{uuid.uuid4()}", thread_id, opening, now),
        )
        db.execute(
            """INSERT INTO research_labs
               (id,campaign_id,campaign_number,thread_id,state,goal,heartbeat_seconds,
                todo_json,next_activation_at,created_at,updated_at)
               VALUES(?,?,?,?,'active',?,?,?,?,?,?)""",
            (
                lab_id, campaign_id, campaign_number, thread_id, goal.strip(),
                HEARTBEAT_SECONDS, canonical_json(todo), now, now, now,
            ),
        )
        store._event(db, "campaign", campaign_id, "campaign.created", actor, {"state": "active"})
        store._event(db, "research_lab", lab_id, "research_lab.commissioned", actor, {
            "campaign_id": campaign_id, "campaign_number": campaign_number,
            "thread_id": thread_id, "heartbeat_seconds": HEARTBEAT_SECONDS,
        })
    return {"id": lab_id, "campaign_id": campaign_id, "thread_id": thread_id}


class ResearchLabCoordinator:
    """Advance at most one durable state transition per active lab per tick."""

    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store = store
        self.bundle = bundle
        self.hub_machine = machine_id_for_role(bundle, "mission_hub")
        self.trainbox_machine = machine_id_for_role(bundle, "trainbox")

    def tick(self, *, actor: str) -> list[dict[str, Any]]:
        changes: list[dict[str, Any]] = []
        for lab in self._active_labs():
            try:
                change = self._advance(lab, actor=actor)
                if change:
                    changes.append({"lab_id": lab["id"], **change})
            except SafetyError as exc:
                self._record_coordinator_failure(lab, exc, actor=actor)
                changes.append({"lab_id": lab["id"], "status": "failed"})
            except MissionHubError:
                continue
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                self._record_coordinator_failure(lab, exc, actor=actor)
                changes.append({"lab_id": lab["id"], "status": "failed"})
        return changes

    def _active_labs(self) -> list[dict[str, Any]]:
        with self.store._connect() as db:
            rows = db.execute(
                "SELECT * FROM research_labs WHERE state='active' ORDER BY campaign_number"
            ).fetchall()
        return [self._lab(row) for row in rows]

    @staticmethod
    def _lab(row: Any) -> dict[str, Any]:
        result = dict(row)
        result["todo"] = json.loads(result.pop("todo_json"))
        return result

    def _advance(self, lab: dict[str, Any], *, actor: str) -> dict[str, Any] | None:
        activation = self._pending_activation(lab["id"])
        if activation is not None:
            return self._advance_activation(lab, activation, actor=actor)
        if lab["next_activation_at"] > utc_now():
            return None
        activation = self._begin_activation(lab, actor=actor)
        return self._prepare_observation(lab, activation, actor=actor)

    def _pending_activation(self, lab_id: str) -> dict[str, Any] | None:
        with self.store._connect() as db:
            row = db.execute(
                """SELECT * FROM research_activations
                   WHERE lab_id=? AND status NOT IN ('complete','failed')
                   ORDER BY sequence LIMIT 1""", (lab_id,),
            ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["observation"] = json.loads(result.pop("observation_json"))
        decision_json = result.pop("decision_json")
        result["decision"] = json.loads(decision_json) if decision_json is not None else None
        return result

    def _begin_activation(self, lab: dict[str, Any], *, actor: str) -> dict[str, Any]:
        sequence = int(lab["activation_count"]) + 1
        activation_id = f"research-activation-{lab['campaign_number']}-{sequence}"
        now = utc_now()
        with self.store.transaction() as db:
            row = db.execute(
                "SELECT activation_count,next_activation_at,state FROM research_labs WHERE id=?",
                (lab["id"],),
            ).fetchone()
            if row is None or row["state"] != "active":
                raise SafetyError("research lab is no longer active")
            if int(row["activation_count"]) + 1 != sequence:
                raise ConflictError("another conductor already began this activation")
            db.execute(
                """INSERT INTO research_activations
                   (id,lab_id,sequence,status,observation_json,created_at,updated_at)
                   VALUES(?,?,?,'observing',?,?,?)""",
                (activation_id, lab["id"], sequence, canonical_json({"state": "preparing"}), now, now),
            )
            db.execute(
                "UPDATE research_labs SET activation_count=?,updated_at=? WHERE id=?",
                (sequence, now, lab["id"]),
            )
            self.store._event(db, "research_activation", activation_id, "research.woke", actor, {
                "sequence": sequence, "heartbeat_seconds": int(lab["heartbeat_seconds"]),
            })
        return {
            "id": activation_id, "lab_id": lab["id"], "sequence": sequence,
            "status": "observing", "observation": {"state": "preparing"},
            "status_job_id": None, "decision_job_id": None, "decision": None,
        }

    def _prepare_observation(
        self, lab: dict[str, Any], activation: dict[str, Any], *, actor: str,
    ) -> dict[str, Any]:
        experiment = self._current_experiment(lab)
        if experiment is None:
            observation = self._observation(lab, None, operating_state="idle")
            self._set_observation(activation["id"], observation, status="deciding")
            return self._queue_decision(lab, activation["id"], observation, actor=actor)
        launch = self._job(experiment["launch_job_id"])
        if launch["status"] in ACTIVE_JOB_STATES:
            observation = self._observation(
                lab, experiment, operating_state="running",
                detail={"phase": "launch_job", "job_status": launch["status"]},
            )
            self._set_experiment_state(experiment["id"], "launching")
            self._set_observation(activation["id"], observation, status="deciding")
            return self._queue_decision(lab, activation["id"], observation, actor=actor)
        if launch["status"] != "succeeded":
            self._finish_experiment(experiment["id"], "failed", {"launch_job_status": launch["status"]})
            observation = self._observation(
                lab, experiment, operating_state="idle",
                detail={"phase": "launch_job", "job_status": launch["status"], "result": "failed"},
            )
            self._set_observation(activation["id"], observation, status="deciding")
            return self._queue_decision(lab, activation["id"], observation, actor=actor)
        launch_run_id = launch.get("run_id")
        if not launch_run_id:
            observation = self._observation(
                lab, experiment, operating_state="indeterminate",
                detail={"reason": "successful launch job has no successful run identity"},
            )
            self._set_observation(activation["id"], observation, status="deciding")
            return self._queue_decision(lab, activation["id"], observation, actor=actor)
        self._set_launch_run(experiment["id"], launch_run_id)
        if experiment["specification"].get("kind") in {"code_change", "dataset_acquisition"}:
            result = launch.get("output", {}).get("metrics", {})
            self._finish_experiment(experiment["id"], "succeeded", result)
            observation = self._observation(
                lab, experiment, operating_state="idle",
                detail={
                    "phase": experiment["specification"]["kind"],
                    "result": "succeeded", **result,
                },
            )
            self._set_observation(activation["id"], observation, status="deciding")
            return self._queue_decision(lab, activation["id"], observation, actor=actor)
        job = self.store.create_job(
            self.bundle,
            job_type="model.organism_status",
            input_payload={
                "launch_run_id": launch_run_id,
                "campaign_id": lab["campaign_id"],
                "experiment_id": experiment["id"],
            },
            idempotency_key=f"{activation['id']}:status",
            created_by=actor,
            campaign_id=lab["campaign_id"],
            requested_machine_id=self.trainbox_machine,
            approved=True,
        )
        now = utc_now()
        with self.store.transaction() as db:
            db.execute(
                "UPDATE research_activations SET status_job_id=?,updated_at=? WHERE id=?",
                (job["id"], now, activation["id"]),
            )
            db.execute(
                "UPDATE research_experiments SET last_status_job_id=?,updated_at=? WHERE id=?",
                (job["id"], now, experiment["id"]),
            )
        return {"status": "observing", "job_id": job["id"]}

    def _advance_activation(
        self, lab: dict[str, Any], activation: dict[str, Any], *, actor: str,
    ) -> dict[str, Any] | None:
        if activation["status"] == "observing":
            if activation["status_job_id"] is None:
                return self._prepare_observation(lab, activation, actor=actor)
            status_job = self._job(activation["status_job_id"])
            if status_job["status"] in ACTIVE_JOB_STATES:
                return None
            experiment = self._current_experiment(lab)
            if status_job["status"] != "succeeded" or status_job.get("output") is None:
                observation = self._observation(
                    lab, experiment, operating_state="indeterminate",
                    detail={"status_job_status": status_job["status"]},
                )
            else:
                metrics = status_job["output"].get("metrics", {})
                organism_status = metrics.get("organism_status", "unknown")
                if organism_status == "training":
                    operating_state = "running"
                    if experiment:
                        self._set_experiment_state(experiment["id"], "running")
                elif organism_status == "complete":
                    operating_state = "idle"
                    if experiment:
                        self._finish_experiment(experiment["id"], "succeeded", metrics)
                elif organism_status == "failed":
                    operating_state = "idle"
                    if experiment:
                        self._finish_experiment(experiment["id"], "failed", metrics)
                else:
                    operating_state = "indeterminate"
                observation = self._observation(
                    lab, experiment, operating_state=operating_state, detail=metrics,
                )
            self._set_observation(activation["id"], observation, status="deciding")
            return self._queue_decision(lab, activation["id"], observation, actor=actor)
        if activation["status"] == "deciding":
            if activation["decision_job_id"] is None:
                return self._queue_decision(lab, activation["id"], activation["observation"], actor=actor)
            decision_job = self._job(activation["decision_job_id"])
            if decision_job["status"] in ACTIVE_JOB_STATES:
                return None
            if decision_job["status"] != "succeeded" or decision_job.get("output") is None:
                self._fail_activation(
                    lab, activation["id"],
                    f"Sol's decision job ended {decision_job['status']}; I will retry at the next 20-minute wake.",
                    actor=actor,
                )
                return {"status": "failed", "job_status": decision_job["status"]}
            decision = decision_job["output"]
            now = utc_now()
            with self.store.transaction() as db:
                db.execute(
                    """UPDATE research_activations
                       SET status='applying',decision_json=?,updated_at=? WHERE id=?""",
                    (canonical_json(decision), now, activation["id"]),
                )
            return self._apply_decision(lab, activation["id"], activation["observation"], decision, actor=actor)
        if activation["status"] == "applying":
            if activation["decision"] is None:
                raise SafetyError("research activation lost its durable decision")
            return self._apply_decision(
                lab, activation["id"], activation["observation"], activation["decision"], actor=actor,
            )
        return None

    def _queue_decision(
        self, lab: dict[str, Any], activation_id: str,
        observation: dict[str, Any], *, actor: str,
    ) -> dict[str, Any]:
        allowed = {
            "running": ["wait"],
            "idle": [
                "ask_for_advice", "acquire_dataset", "launch_experiment",
                "modify_code", "conclude_campaign",
            ],
            "indeterminate": ["inspect_state"],
        }[observation["operating_state"]]
        payload = {
            "lab_id": lab["id"],
            "campaign_id": lab["campaign_id"],
            "campaign_number": int(lab["campaign_number"]),
            "activation_id": activation_id,
            "goal": lab["goal"],
            "todo": lab["todo"],
            "observation": observation,
            "recent_reports": self._recent_reports(lab["thread_id"]),
            "available_datasets": self._available_datasets(),
            "allowed_actions": allowed,
        }
        job = self.store.create_job(
            self.bundle,
            job_type="research.decide",
            input_payload=payload,
            idempotency_key=f"{activation_id}:decision",
            created_by=actor,
            campaign_id=lab["campaign_id"],
            requested_machine_id=self.hub_machine,
            approved=True,
        )
        with self.store.transaction() as db:
            db.execute(
                """UPDATE research_activations
                   SET status='deciding',decision_job_id=?,updated_at=? WHERE id=?""",
                (job["id"], utc_now(), activation_id),
            )
        return {"status": "deciding", "job_id": job["id"], "allowed_actions": allowed}

    def _apply_decision(
        self, lab: dict[str, Any], activation_id: str, observation: dict[str, Any],
        decision: dict[str, Any], *, actor: str,
    ) -> dict[str, Any]:
        action = decision["action"]
        kind = action["kind"]
        operating = observation["operating_state"]
        allowed = {
            "running": {"wait"},
            "idle": {"acquire_dataset", "launch_experiment", "modify_code", "conclude_campaign"},
            "indeterminate": {"inspect_state"},
        }[operating]
        if kind not in allowed:
            raise SafetyError(
                f"Sol selected {kind} while authoritative operating state was {operating}"
            )
        todo = decision["updated_todo"]
        if kind in {"wait", "inspect_state"}:
            self._complete_activation(
                lab, activation_id, todo, decision["message"], actor=actor,
            )
            return {"status": "complete", "action": kind}
        if kind == "acquire_dataset":
            acquisition = action["dataset_acquisition"]
            experiment_id = f"experiment-{lab['campaign_number']}-{activation_id.rsplit('-', 1)[-1]}"
            specification = {
                "kind": "dataset_acquisition",
                "title": f"Acquire {acquisition['dataset_name']}",
                "hypothesis": decision["rationale"],
                "acquisition": acquisition,
            }
            job = self.store.create_job(
                self.bundle,
                job_type="research.dataset_acquire",
                input_payload={
                    "dataset_name": acquisition["dataset_name"],
                    "source_url": acquisition["source_url"],
                    "source_page_url": acquisition["source_page_url"],
                    "license": acquisition["license"],
                    "expected_sha256": acquisition["expected_sha256"],
                    "max_download_bytes": acquisition["max_download_bytes"],
                    "dataset_format": acquisition["dataset_format"],
                    "archive_format": acquisition["archive_format"],
                    "records_member": acquisition["records_member"],
                    "modality": acquisition["modality"],
                    "objective": acquisition["objective"],
                    "text_field": acquisition["text_field"],
                    "prompt_field": acquisition["prompt_field"],
                    "completion_field": acquisition["completion_field"],
                    "image_field": acquisition["image_field"],
                    "caption_field": acquisition["caption_field"],
                },
                idempotency_key=f"{activation_id}:dataset-acquisition",
                created_by=actor, campaign_id=lab["campaign_id"],
                requested_machine_id=self.trainbox_machine, approved=True,
            )
            self._record_experiment_and_close_activation(
                lab, activation_id, experiment_id, specification, job["id"], todo,
                decision["message"], actor=actor,
                event_type="research.dataset_acquisition_queued",
                event_payload={"job_id": job["id"], "source_url": acquisition["source_url"]},
            )
            return {
                "status": "complete", "action": kind,
                "experiment_id": experiment_id, "job_id": job["id"],
            }
        if kind == "modify_code":
            experiment_id = f"experiment-{lab['campaign_number']}-{activation_id.rsplit('-', 1)[-1]}"
            active_deployment = self.store.active_deployment(self.trainbox_machine)
            active_manifest = json.loads(active_deployment["manifest_json"])
            source = active_manifest.get("source") or {}
            git_head = source.get("git_head")
            if not isinstance(git_head, str) or not re.fullmatch(r"[0-9a-f]{40}", git_head):
                raise SafetyError("active Trainbox deployment lacks an exact Git source commit")
            specification = {
                "kind": "code_change",
                "title": action["code_change_title"],
                "hypothesis": action["code_change_hypothesis"],
                "objective": action["code_change_objective"],
                "acceptance_criteria": action["code_change_acceptance_criteria"],
                "scopes": action["code_change_scopes"],
                "base_deployment_id": active_deployment["id"],
                "base_git_head": git_head,
            }
            job = self.store.create_job(
                self.bundle,
                job_type="research.code_change",
                input_payload={
                    "lab_id": lab["id"], "campaign_id": lab["campaign_id"],
                    "campaign_number": int(lab["campaign_number"]),
                    "change_id": experiment_id,
                    "title": action["code_change_title"],
                    "hypothesis": action["code_change_hypothesis"],
                    "objective": action["code_change_objective"],
                    "acceptance_criteria": action["code_change_acceptance_criteria"],
                    "scopes": action["code_change_scopes"],
                    "expected_trainbox_deployment_id": active_deployment["id"],
                    "expected_source_git_head": git_head,
                },
                idempotency_key=f"{activation_id}:code-change",
                created_by=actor, campaign_id=lab["campaign_id"],
                requested_machine_id=self.hub_machine, approved=True,
            )
            now = utc_now()
            with self.store.transaction() as db:
                existing = db.execute(
                    "SELECT id FROM research_experiments WHERE id=?", (experiment_id,),
                ).fetchone()
                if existing is None:
                    sequence = db.execute(
                        "SELECT COUNT(*)+1 FROM research_experiments WHERE lab_id=?", (lab["id"],),
                    ).fetchone()[0]
                    db.execute(
                        """INSERT INTO research_experiments
                           (id,lab_id,sequence,title,hypothesis,state,specification_json,
                            launch_job_id,created_at,updated_at)
                           VALUES(?,?,?,?,?,'launch_queued',?,?,?,?)""",
                        (
                            experiment_id, lab["id"], sequence,
                            action["code_change_title"], action["code_change_hypothesis"],
                            canonical_json(specification), job["id"], now, now,
                        ),
                    )
                db.execute(
                    """UPDATE research_labs
                       SET current_experiment_id=?,todo_json=?,next_activation_at=?,updated_at=?
                       WHERE id=?""",
                    (
                        experiment_id, canonical_json(todo),
                        self._activation_due(activation_id, int(lab["heartbeat_seconds"])),
                        now, lab["id"],
                    ),
                )
                self._close_activation_row(db, activation_id, now)
                self.store._event(
                    db, "research_experiment", experiment_id,
                    "research.code_change_queued", actor,
                    {"job_id": job["id"], "scopes": action["code_change_scopes"]},
                )
            self._post(lab["thread_id"], decision["message"], actor=actor)
            return {
                "status": "complete", "action": kind,
                "experiment_id": experiment_id, "job_id": job["id"],
            }
        if kind == "launch_experiment":
            experiment_id = f"experiment-{lab['campaign_number']}-{activation_id.rsplit('-', 1)[-1]}"
            dataset = self._dataset(action["dataset_id"])
            self._validate_control_experiment(
                lab["id"], action["intervention_type"], action["control_experiment_id"],
            )
            specification = {
                "kind": "organism_experiment",
                "title": action["experiment_title"],
                "hypothesis": action["hypothesis"],
                "dataset_id": action["dataset_id"],
                "dataset": dataset,
                "epochs": action["epochs"],
                "max_records_per_epoch": action["max_records_per_epoch"],
                "order_policy": action["order_policy"],
                "order_seed": action["order_seed"],
                "intervention_type": action["intervention_type"],
                "control_experiment_id": action["control_experiment_id"],
                "max_sessions": action["max_sessions"],
                "max_events_per_session": action["max_events_per_session"],
                "controls": action["controls"],
            }
            job = self.store.create_job(
                self.bundle,
                job_type="model.organism_bootstrap",
                input_payload={
                    "mode": "launch", "resume": False,
                    "campaign_id": lab["campaign_id"],
                    "experiment_id": experiment_id,
                    "dataset_artifact_id": (
                        None if dataset["kind"] == "builtin_bootstrap" else dataset["id"]
                    ),
                    "epochs": action["epochs"],
                    "max_records_per_epoch": action["max_records_per_epoch"],
                    "order_policy": action["order_policy"],
                    "order_seed": action["order_seed"],
                    "max_sessions": action["max_sessions"],
                    "max_events_per_session": action["max_events_per_session"],
                    "controls": action["controls"],
                    "device_indices": [0, 1], "dtype": "bfloat16",
                },
                idempotency_key=f"{activation_id}:launch",
                created_by=actor,
                campaign_id=lab["campaign_id"],
                requested_machine_id=self.trainbox_machine,
                approved=True,
            )
            now = utc_now()
            with self.store.transaction() as db:
                existing = db.execute(
                    "SELECT id FROM research_experiments WHERE id=?", (experiment_id,),
                ).fetchone()
                if existing is None:
                    sequence = db.execute(
                        "SELECT COUNT(*)+1 FROM research_experiments WHERE lab_id=?", (lab["id"],),
                    ).fetchone()[0]
                    db.execute(
                        """INSERT INTO research_experiments
                           (id,lab_id,sequence,title,hypothesis,state,specification_json,
                            launch_job_id,created_at,updated_at)
                           VALUES(?,?,?,?,?,'launch_queued',?,?,?,?)""",
                        (
                            experiment_id, lab["id"], sequence,
                            action["experiment_title"], action["hypothesis"],
                            canonical_json(specification), job["id"], now, now,
                        ),
                    )
                db.execute(
                    """UPDATE research_labs
                       SET current_experiment_id=?,todo_json=?,next_activation_at=?,updated_at=?
                       WHERE id=?""",
                    (
                        experiment_id, canonical_json(todo),
                        self._activation_due(activation_id, int(lab["heartbeat_seconds"])),
                        now, lab["id"],
                    ),
                )
                self._close_activation_row(db, activation_id, now)
                self.store._event(db, "research_experiment", experiment_id, "research.experiment_launched", actor, {
                    "job_id": job["id"], "hypothesis": action["hypothesis"],
                })
            self._post(lab["thread_id"], decision["message"], actor=actor)
            return {"status": "complete", "action": kind, "experiment_id": experiment_id, "job_id": job["id"]}
        return self._conclude_and_rollover(lab, activation_id, todo, decision, actor=actor)

    def _record_experiment_and_close_activation(
        self, lab: dict[str, Any], activation_id: str, experiment_id: str,
        specification: dict[str, Any], job_id: str, todo: dict[str, Any],
        message: str, *, actor: str, event_type: str,
        event_payload: dict[str, Any],
    ) -> None:
        now = utc_now()
        with self.store.transaction() as db:
            if db.execute(
                "SELECT id FROM research_experiments WHERE id=?", (experiment_id,),
            ).fetchone() is None:
                sequence = db.execute(
                    "SELECT COUNT(*)+1 FROM research_experiments WHERE lab_id=?", (lab["id"],),
                ).fetchone()[0]
                db.execute(
                    """INSERT INTO research_experiments
                       (id,lab_id,sequence,title,hypothesis,state,specification_json,
                        launch_job_id,created_at,updated_at)
                       VALUES(?,?,?,?,?,'launch_queued',?,?,?,?)""",
                    (
                        experiment_id, lab["id"], sequence, specification["title"],
                        specification["hypothesis"], canonical_json(specification),
                        job_id, now, now,
                    ),
                )
            db.execute(
                """UPDATE research_labs
                   SET current_experiment_id=?,todo_json=?,next_activation_at=?,updated_at=?
                   WHERE id=?""",
                (
                    experiment_id, canonical_json(todo),
                    self._activation_due(activation_id, int(lab["heartbeat_seconds"])),
                    now, lab["id"],
                ),
            )
            self._close_activation_row(db, activation_id, now)
            self.store._event(
                db, "research_experiment", experiment_id, event_type, actor, event_payload,
            )
        self._post(lab["thread_id"], message, actor=actor)

    def _conclude_and_rollover(
        self, lab: dict[str, Any], activation_id: str, todo: dict[str, Any],
        decision: dict[str, Any], *, actor: str,
    ) -> dict[str, Any]:
        action = decision["action"]
        next_goal = action["next_campaign_goal"]
        next_title = action["next_campaign_title"]
        if not next_goal or not next_title:
            raise SafetyError("campaign conclusion must define the next campaign's goal and title")
        next_number = int(lab["campaign_number"]) + 1
        next_id = f"campaign-{next_number}-{_slug(next_title)}-v1"
        next_lab_id = f"research-lab-{next_number}"
        next_thread = f"thread-{uuid.uuid5(uuid.NAMESPACE_URL, 'ninereeds:research-lab:' + str(next_number))}"
        metadata = research_campaign_metadata(next_goal)
        active = self.store.active_config()
        validate_campaign_contract(
            metadata["campaign_contract"], active["payload"]["resolved"]["campaign_modes"],
        )
        now = utc_now()
        with self.store.transaction() as db:
            if db.execute("SELECT 1 FROM campaigns WHERE id=?", (next_id,)).fetchone():
                raise ConflictError(f"next research campaign already exists: {next_id}")
            db.execute(
                "UPDATE campaigns SET state='closed',updated_at=? WHERE id=?",
                (now, lab["campaign_id"]),
            )
            db.execute(
                "UPDATE research_labs SET state='concluded',todo_json=?,updated_at=?,concluded_at=? WHERE id=?",
                (canonical_json(todo), now, now, lab["id"]),
            )
            self._close_activation_row(db, activation_id, now)
            db.execute(
                """INSERT INTO campaigns
                   (id,name,state,config_snapshot_id,objective,metadata_json,created_at,updated_at)
                   VALUES(?,?,'active',?,?,?,?,?)""",
                (next_id, f"Campaign {next_number} — {next_title}", active["id"], next_goal, canonical_json(metadata), now, now),
            )
            db.execute(
                """INSERT INTO message_threads
                   (id,subject,state,created_by,created_at,updated_at)
                   VALUES(?,?,'open',?,?,?)""",
                (next_thread, f"Campaign {next_number} — {next_title}", actor, now, now),
            )
            opening = (
                f"I concluded Campaign {lab['campaign_number']} and opened Campaign {next_number}.\n\n"
                f"Research goal: {next_goal}\n\nThe 20-minute knowledge-first heartbeat continues."
            )
            db.execute(
                "INSERT INTO thread_messages(id,thread_id,sender,body,created_at) VALUES(?,?,'sol',?,?)",
                (f"message-{uuid.uuid4()}", next_thread, opening, now),
            )
            db.execute(
                """INSERT INTO research_labs
                   (id,campaign_id,campaign_number,thread_id,state,goal,heartbeat_seconds,
                    todo_json,next_activation_at,created_at,updated_at)
                   VALUES(?,?,?,?,'active',?,?,?,?,?,?)""",
                (
                    next_lab_id, next_id, next_number, next_thread, next_goal,
                    int(lab["heartbeat_seconds"]), canonical_json(todo), now, now, now,
                ),
            )
            self.store._event(db, "campaign", lab["campaign_id"], "campaign.research_concluded", actor, {
                "report": action["campaign_report"], "successor_campaign_id": next_id,
            })
            self.store._event(db, "research_lab", next_lab_id, "research_lab.commissioned", actor, {
                "campaign_id": next_id, "campaign_number": next_number,
                "thread_id": next_thread, "heartbeat_seconds": int(lab["heartbeat_seconds"]),
            })
        self._post(lab["thread_id"], decision["message"], actor=actor)
        return {"status": "complete", "action": "conclude_campaign", "next_campaign_id": next_id}

    def _complete_activation(
        self, lab: dict[str, Any], activation_id: str, todo: dict[str, Any],
        message: str, *, actor: str,
    ) -> None:
        now = utc_now()
        with self.store.transaction() as db:
            db.execute(
                """UPDATE research_labs
                   SET todo_json=?,next_activation_at=?,updated_at=? WHERE id=?""",
                (
                    canonical_json(todo),
                    self._activation_due(activation_id, int(lab["heartbeat_seconds"])),
                    now, lab["id"],
                ),
            )
            self._close_activation_row(db, activation_id, now)
        self._post(lab["thread_id"], message, actor=actor)

    @staticmethod
    def _close_activation_row(db: Any, activation_id: str, now: str) -> None:
        db.execute(
            "UPDATE research_activations SET status='complete',updated_at=?,finished_at=? WHERE id=?",
            (now, now, activation_id),
        )

    def _fail_activation(self, lab: dict[str, Any], activation_id: str, message: str, *, actor: str) -> None:
        now = utc_now()
        with self.store.transaction() as db:
            db.execute(
                "UPDATE research_activations SET status='failed',updated_at=?,finished_at=? WHERE id=?",
                (now, now, activation_id),
            )
            db.execute(
                "UPDATE research_labs SET next_activation_at=?,updated_at=? WHERE id=?",
                (
                    self._activation_due(activation_id, int(lab["heartbeat_seconds"])),
                    now, lab["id"],
                ),
            )
        self._post(lab["thread_id"], message, actor=actor, sender="mission_hub")

    def _record_coordinator_failure(self, lab: dict[str, Any], exc: Exception, *, actor: str) -> None:
        activation = self._pending_activation(lab["id"])
        if activation is not None:
            self._fail_activation(
                lab, activation["id"],
                f"The conductor hit a bounded state-contract error: {type(exc).__name__}: {exc}. I will retry on the next wake.",
                actor=actor,
            )

    def _set_observation(self, activation_id: str, value: dict[str, Any], *, status: str) -> None:
        with self.store.transaction() as db:
            db.execute(
                "UPDATE research_activations SET status=?,observation_json=?,updated_at=? WHERE id=?",
                (status, canonical_json(value), utc_now(), activation_id),
            )

    def _activation_due(self, activation_id: str, heartbeat_seconds: int) -> str:
        """Anchor cadence to wake time so provider latency cannot defeat caching."""
        with self.store._connect() as db:
            row = db.execute(
                "SELECT created_at FROM research_activations WHERE id=?", (activation_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(activation_id)
        created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        return (created + timedelta(seconds=heartbeat_seconds)).isoformat(
            timespec="microseconds",
        ).replace("+00:00", "Z")

    def _current_experiment(self, lab: dict[str, Any]) -> dict[str, Any] | None:
        experiment_id = lab.get("current_experiment_id")
        if not experiment_id:
            return None
        with self.store._connect() as db:
            row = db.execute(
                "SELECT * FROM research_experiments WHERE id=?", (experiment_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError(experiment_id)
        result = dict(row)
        result["specification"] = json.loads(result.pop("specification_json"))
        result_json = result.pop("result_json")
        result["result"] = json.loads(result_json) if result_json else None
        return result

    def _available_datasets(self) -> list[dict[str, Any]]:
        result = [{
            "id": "builtin:foundation-visual-3022-v1",
            "name": "foundation-visual-3022-v1",
            "kind": "builtin_bootstrap",
            "modality": "multimodal",
            "format": "frozen 3,022 word / 30,220 image concept blocks",
            "byte_size": None,
            "sha256": "e1d760e264717d05676076429a2e13e46cd05da6d8376169feaad579121ac2fb",
            "constraints": "One declared-order epoch; bound with complete sessions and ten-image concept blocks.",
        }]
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT a.id,a.kind,a.sha256,a.byte_size,a.manifest_json
                   FROM artifacts a
                   WHERE a.kind IN ('research_dataset','corpus') AND a.lifecycle!='deleted'
                     AND EXISTS(
                       SELECT 1 FROM artifact_locations l
                       WHERE l.artifact_id=a.id AND l.machine_id=? AND l.available=1
                     )
                   ORDER BY a.created_at,a.id""",
                (self.trainbox_machine,),
            ).fetchall()
        for row in rows:
            manifest = json.loads(row["manifest_json"])
            if row["kind"] == "corpus":
                if manifest.get("schema_version") != "ninereeds_corpus_artifact_v1":
                    continue
                adapter = {"modality": "text", "archive": "none", "format": "jsonl"}
            else:
                adapter = manifest.get("adapter", {})
            result.append({
                "id": row["id"],
                "name": manifest.get("dataset_name", row["id"]),
                "kind": row["kind"],
                "modality": adapter.get("modality", "text"),
                "format": f"{adapter.get('archive', 'none')}:{adapter.get('format', 'unknown')}",
                "byte_size": int(row["byte_size"]),
                "sha256": row["sha256"],
                "constraints": "Immutable registered bytes; bound by records per epoch, epochs, and deterministic order policy.",
            })
        return result

    def _dataset(self, dataset_id: str) -> dict[str, Any]:
        matches = [item for item in self._available_datasets() if item["id"] == dataset_id]
        if len(matches) != 1:
            raise SafetyError(f"selected research dataset is not available on Trainbox: {dataset_id}")
        return matches[0]

    def _validate_control_experiment(
        self, lab_id: str, intervention_type: str, control_experiment_id: str | None,
    ) -> None:
        if control_experiment_id is None:
            if intervention_type != "baseline":
                raise SafetyError("a non-baseline experiment requires an exact control lineage")
            return
        with self.store._connect() as db:
            row = db.execute(
                """SELECT state,specification_json FROM research_experiments
                   WHERE id=? AND lab_id=?""",
                (control_experiment_id, lab_id),
            ).fetchone()
        if row is None or row["state"] != "succeeded":
            raise SafetyError("control experiment is not a completed experiment in this campaign")
        if json.loads(row["specification_json"]).get("kind") != "organism_experiment":
            raise SafetyError("control lineage must name a completed organism experiment")

    def _job(self, job_id: str) -> dict[str, Any]:
        with self.store._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if row is None:
                raise NotFoundError(job_id)
            run = db.execute(
                "SELECT * FROM runs WHERE job_id=? ORDER BY attempt DESC LIMIT 1", (job_id,),
            ).fetchone()
        result = dict(row)
        if run is not None:
            result["run_id"] = run["id"] if run["status"] == "succeeded" else None
            result["run_status"] = run["status"]
            result["output"] = json.loads(run["output_json"]) if run["output_json"] else None
        else:
            result["run_id"] = None
            result["output"] = None
        return result

    def _set_experiment_state(self, experiment_id: str, state: str) -> None:
        with self.store.transaction() as db:
            db.execute(
                "UPDATE research_experiments SET state=?,updated_at=? WHERE id=?",
                (state, utc_now(), experiment_id),
            )

    def _set_launch_run(self, experiment_id: str, run_id: str) -> None:
        with self.store.transaction() as db:
            db.execute(
                "UPDATE research_experiments SET launch_run_id=?,updated_at=? WHERE id=?",
                (run_id, utc_now(), experiment_id),
            )

    def _finish_experiment(self, experiment_id: str, state: str, result: dict[str, Any]) -> None:
        now = utc_now()
        with self.store.transaction() as db:
            db.execute(
                """UPDATE research_experiments
                   SET state=?,result_json=?,updated_at=?,finished_at=? WHERE id=?""",
                (state, canonical_json(result), now, now, experiment_id),
            )
            row = db.execute("SELECT lab_id FROM research_experiments WHERE id=?", (experiment_id,)).fetchone()
            if row is not None:
                db.execute(
                    "UPDATE research_labs SET current_experiment_id=NULL,updated_at=? WHERE id=?",
                    (now, row["lab_id"]),
                )

    def _observation(
        self, lab: dict[str, Any], experiment: dict[str, Any] | None,
        *, operating_state: str, detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "observed_at": utc_now(),
            "operating_state": operating_state,
            "running_process_must_not_be_interrupted": operating_state == "running",
            "idle_campaign_must_advance_or_conclude": operating_state == "idle",
            "experiment": ({
                "id": experiment["id"], "sequence": experiment["sequence"],
                "title": experiment["title"], "hypothesis": experiment["hypothesis"],
                "state": experiment["state"], "specification": experiment["specification"],
            } if experiment else None),
            "detail": detail or {},
            "heartbeat_seconds": int(lab["heartbeat_seconds"]),
        }

    def _recent_reports(self, thread_id: str) -> list[dict[str, str]]:
        with self.store._connect() as db:
            rows = db.execute(
                """SELECT sender,body,created_at FROM thread_messages
                   WHERE thread_id=? AND sender IN ('sol','mission_hub')
                   ORDER BY created_at DESC,id DESC LIMIT 4""", (thread_id,),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def _post(self, thread_id: str, message: str, *, actor: str, sender: str = "sol") -> None:
        LabStore(self.store).add_thread_message(thread_id, message, sender=sender, actor=actor)
