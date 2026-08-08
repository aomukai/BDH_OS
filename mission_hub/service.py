"""Application service joining configuration, store, protocol, and agent results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ConfigBundle
from .artifacts import ArtifactFiles
from .handlers.contracts import _object_file
from .lesson_policy import policy_sha256, require_lesson_material
from .errors import ConflictError, MissionHubError, ProtocolError, RemoteJobError, RunCancelled, SafetyError
from .jsonutil import content_hash
from .protocol import build_job_envelope
from .store import MissionHubStore
from .transport import SSHDispatcher
from .agent import TrainboxAgent
from .runtime_settings import settings_payload


class MissionHubService:
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle):
        self.store = store
        self.bundle = bundle

    def lease_envelope(self, *, machine_id: str, deployment_id: str, actor: str) -> dict[str, Any] | None:
        leased = self.store.lease_next(
            self.bundle,
            machine_id=machine_id,
            deployment_id=deployment_id,
            actor=actor,
        )
        if leased is None:
            return None
        job, token = leased
        definition = self.bundle.jobs[job["job_type"]]
        artifacts = self.store.resolve_artifacts(
            definition,
            json.loads(job["input_json"]),
            machine_id=machine_id,
        )
        runtime_payload = settings_payload(self.bundle)
        return build_job_envelope(self.bundle, job, token, artifacts, {
            "id": job.get("runtime_settings_id"),
            "sha256": content_hash(runtime_payload),
            "payload": runtime_payload,
        })

    def accept_result(self, envelope: dict[str, Any], result: dict[str, Any], *, actor: str) -> None:
        required = {
            "schema_version", "protocol_version", "job_id", "run_id", "attempt",
            "deployment_id", "finished_at", "output", "output_sha256", "envelope_hash",
        }
        if set(result) != required or result["schema_version"] != "ninereeds_result_envelope_v1":
            raise ProtocolError("invalid result envelope fields")
        supplied = result["envelope_hash"]
        body = {key: value for key, value in result.items() if key != "envelope_hash"}
        if supplied != content_hash(body) or result["output_sha256"] != content_hash(result["output"]):
            raise ProtocolError("result envelope hash mismatch")
        if result["job_id"] != envelope["job"]["id"] or result["run_id"] != envelope["run"]["id"]:
            raise ProtocolError("result does not belong to leased job/run")
        if result["deployment_id"] != envelope["deployment"]["id"]:
            raise ProtocolError("result deployment mismatch")
        self.store.finish_run(
            self.bundle,
            result["run_id"],
            envelope["lease"]["token"],
            status="succeeded",
            output=result["output"],
            failure=None,
            actor=actor,
        )
        if envelope["job"]["type"] == "system.healthcheck":
            self.store.record_machine_observation(
                envelope["deployment"]["machine_id"],
                result["output"],
                actor=actor,
            )

    def execute_envelope(self, machine_id: str, envelope: dict[str, Any]) -> dict[str, Any]:
        machine = self.bundle.machines[machine_id]
        if machine["transport"] == "restricted_ssh":
            return SSHDispatcher(self.bundle).execute(
                machine_id, envelope,
                heartbeat=lambda: self.store.heartbeat_run(
                    envelope["run"]["id"], envelope["lease"]["token"],
                    actor=f"agent:{machine_id}",
                    lease_seconds=self.bundle.base["scheduler"]["lease_seconds"],
                ),
                cancelled=lambda: self.store.run_cancelled(envelope["run"]["id"]),
            )
        if machine["transport"] != "local":
            raise ProtocolError(f"machine {machine_id} has unsupported transport")
        row = self.store.active_deployment(machine_id)
        manifest = json.loads(row["manifest_json"])
        deployment = {
            "id": row["id"], "release_id": row["release_id"],
            "source_sha256": row["source_sha256"],
            "environment_sha256": row["environment_sha256"],
            "environment": manifest.get("environment", {}),
            "release_root": str(Path(__file__).resolve().parent.parent),
        }
        try:
            return TrainboxAgent(
                self.bundle, machine_id=machine_id, deployment=deployment,
            ).execute(envelope)
        except RemoteJobError:
            raise
        except SafetyError as exc:
            raise RemoteJobError(str(exc), failure_class="safety_policy", code="safety_policy_refused") from exc
        except OSError as exc:
            raise RemoteJobError(str(exc), failure_class="operational_transient", code="resource_temporarily_unavailable") from exc
        except (MissionHubError, ValueError) as exc:
            raise RemoteJobError(str(exc), failure_class="deterministic_specification", code="job_spec_invalid") from exc
        except Exception as exc:
            raise RemoteJobError(
                f"{type(exc).__name__}: {exc}", failure_class="deterministic_specification",
                code="unexpected_internal_error",
            ) from exc

    def execute_and_record(self, machine_id: str, envelope: dict[str, Any], *, actor: str) -> str:
        """Execute one started run and always close its authoritative lifecycle."""
        try:
            result = self.execute_envelope(machine_id, envelope)
            if self.store.run_cancelled(envelope["run"]["id"]):
                return "cancelled"
            self.accept_result(envelope, result, actor=actor)
            return "succeeded"
        except RunCancelled:
            return "cancelled"
        except RemoteJobError as exc:
            self.record_failure(
                envelope, failure_class=exc.failure_class, code=exc.code,
                message=str(exc), actor=actor,
            )
            return "failed"
        except MissionHubError as exc:
            self.record_transport_failure(envelope, message=str(exc), actor=actor)
            return "failed"
        except Exception as exc:
            self.record_failure(
                envelope, failure_class="deterministic_specification",
                code="unexpected_internal_error", message=f"{type(exc).__name__}: {exc}",
                actor=actor,
            )
            return "failed"

    def record_transport_failure(self, envelope: dict[str, Any], *, message: str, actor: str) -> None:
        self.record_failure(
            envelope, failure_class="operational_transient", code="transport_unavailable",
            message=message, actor=actor,
        )

    def record_failure(
        self,
        envelope: dict[str, Any],
        *,
        failure_class: str,
        code: str,
        message: str,
        actor: str,
    ) -> None:
        self.store.finish_run(
            self.bundle,
            envelope["run"]["id"],
            envelope["lease"]["token"],
            status="failed",
            output=None,
            failure={
                "class": failure_class,
                "code": code,
                "message": message,
            },
            actor=actor,
        )

    def ingest_artifact(
        self,
        *,
        kind: str,
        source_path: str,
        lifecycle: str,
        manifest: dict[str, Any],
        actor: str,
    ) -> dict[str, Any]:
        self._require_active_config()
        if lifecycle not in {"observed", "candidate"}:
            raise SafetyError("artifact ingest lifecycle must be observed or candidate")
        destination, digest, byte_size = ArtifactFiles(self.bundle, "mission-hub").ingest(source_path)
        if kind == "commissioning_input" and byte_size > self.bundle.base["commissioning"]["max_artifact_input_bytes"]:
            raise SafetyError("commissioning artifact exceeds its configured input limit")
        artifact_id = self.store.register_artifact(
            self.bundle,
            kind=kind,
            sha256=digest,
            byte_size=byte_size,
            lifecycle=lifecycle,
            manifest=manifest,
            producing_run_id=None,
            machine_id="mission-hub",
            uri=str(destination),
            actor=actor,
        )
        return self.store.artifact_at(artifact_id, machine_id="mission-hub")

    def materialize_artifact(self, artifact_id: str, *, machine_id: str, actor: str) -> dict[str, Any]:
        self._require_active_config()
        artifact = self.store.artifact_at(artifact_id, machine_id="mission-hub")
        deployment = self.store.active_deployment(machine_id)
        uri = SSHDispatcher(self.bundle).put_artifact(machine_id, deployment, artifact)
        self.store.record_artifact_location(
            self.bundle, artifact_id, machine_id=machine_id, uri=uri,
            event_type="artifact.materialized", actor=actor,
        )
        return self.store.artifact_at(artifact_id, machine_id=machine_id)

    def certify_training_order(
        self,
        *,
        job_type: str,
        input_payload: dict[str, Any],
        campaign_id: str,
        actor: str,
    ) -> dict[str, Any]:
        """Emit the immutable certificate required before a training job exists."""
        self._require_active_config()
        if job_type not in {"model.train", "model.visual_train", "model.multimodal_train"}:
            raise SafetyError("dependency-order certification only applies to training jobs")
        definition = self.bundle.jobs[job_type]
        from .schema import load_schema, validate
        schema = load_schema(self.bundle.root.parent.parent, definition["input_schema"])
        errors = validate(input_payload, schema)
        if errors:
            raise ValueError("invalid prospective training input: " + "; ".join(errors))
        placeholder_id = "art-0000000000000000"
        if job_type == "model.train":
            prospective = dict(input_payload)
            prospective["order_validation_artifact_id"] = placeholder_id
        else:
            prospective = dict(input_payload)
            ids = list(prospective["input_artifact_ids"])
            if len(ids) != 4:
                raise SafetyError("visual or multimodal training certification requires one validation placeholder")
            ids[-1] = placeholder_id
            prospective["input_artifact_ids"] = ids
        plan = self.store.preview_training_session_plan(
            self.bundle, job_type=job_type, input_payload=prospective,
            campaign_id=campaign_id,
        )
        session = prospective["training_session"]
        material_evidence = self._validate_training_subject(
            plan, prospective, job_type=job_type,
        )
        dependency_evidence = {
            "campaign_id": campaign_id,
            "campaign_contract_sha256": session["campaign_contract_sha256"],
            "training_mode": session["training_mode"],
            "development_stage": self._campaign_contract(campaign_id)["development_stage"],
            "branch_id": session["branch_id"],
            "parent_knowledge_sha256": plan["parent_knowledge_sha256"],
            "ordered_concepts": plan["ordered_concepts"],
            "material_evidence": material_evidence,
        }
        manifest = {
            "schema_version": "ninereeds_dependency_order_validation_v1",
            "validation_scope": "dependency_order", "status": "passed",
            "subject_artifact_id": plan["subject_artifact_id"],
            "subject_sha256": plan["subject_sha256"],
            "parent_artifact_id": plan["parent_checkpoint_artifact_id"],
            "parent_sha256": plan["parent_checkpoint_sha256"],
            "order_policy": "declared_only", "shuffle_allowed": False,
            "dependency_order_required": True,
            "dependency_evidence_sha256": content_hash(dependency_evidence),
            "session_plan_sha256": plan["plan_sha256"],
            "parent_knowledge_sha256": plan["parent_knowledge_sha256"],
            "lesson_policy_status": "passed",
            "lesson_policy_id": self.bundle.identity_policy["id"],
            "lesson_policy_version": self.bundle.identity_policy["version"],
            "lesson_policy_sha256": policy_sha256(self.bundle.identity_policy),
            "identity_scope": session["identity_scope"],
            "campaign_contract_sha256": session["campaign_contract_sha256"],
            "training_mode": session["training_mode"],
            "development_stage": dependency_evidence["development_stage"],
            "branch_id": session["branch_id"],
            "material_evidence": material_evidence,
        }
        path, digest, size = _object_file(
            self.bundle.machines["mission-hub"]["state_root"],
            (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )
        artifact_id = self.store.register_artifact(
            self.bundle, kind="validation_report", sha256=digest, byte_size=size,
            lifecycle="candidate", manifest=manifest, producing_run_id=None,
            machine_id="mission-hub", uri=str(path), actor=actor,
        )
        return {"artifact_id": artifact_id, "manifest": manifest, "uri": str(path)}

    def _validate_training_subject(
        self, plan: dict[str, Any], prospective: dict[str, Any], *, job_type: str,
    ) -> dict[str, Any]:
        if job_type != "model.train":
            subject = self.store.artifact_at(plan["subject_artifact_id"], machine_id="mission-hub")
            experience = json.loads(Path(subject["uri"]).read_text(encoding="utf-8"))
            accepted = {
                event["asset_sha256"] for event in experience.get("events", [])
                if event.get("type") == "observe_image" and isinstance(event.get("asset_sha256"), str)
            }
            events = prospective["specification"]["events"]
            if prospective["specification"]["mode"] == "visual" and any(event.get("type") != "visual" for event in events):
                raise SafetyError("visual-only training contains a non-visual event")
            if any(event.get("type") == "visual" and event.get("asset_sha256") not in accepted for event in events):
                raise SafetyError("multimodal training names an image outside its accepted experience")
            concept_order = []
            seen = set()
            last_ordinal = -1
            text_rows = []
            for index, event in enumerate(events):
                ordinal = event.get("ordinal")
                concept = event.get("concept")
                if not isinstance(ordinal, int) or ordinal < last_ordinal or not isinstance(concept, str) or not concept.strip():
                    raise SafetyError(f"multimodal event order is invalid at position {index}")
                last_ordinal = ordinal
                key = concept.casefold()
                if key not in seen:
                    concept_order.append(concept); seen.add(key)
                if event.get("type") == "text":
                    text_rows.append({"prompt": event.get("prompt"), "completion": event.get("completion")})
            declared = [item["concept"] for item in prospective["training_session"]["ordered_concepts"]]
            if concept_order != declared:
                raise SafetyError("multimodal event concept order differs from the declared dependency list")
            if text_rows:
                require_lesson_material(text_rows, self.bundle.identity_policy)
            return {
                "format": "ordered_multimodal_events", "validated_by": "visual_training_contract",
                "event_count": len(events), "accepted_image_count": len(accepted),
                "specification_sha256": content_hash(prospective["specification"]),
            }
        subject = self.store.artifact_at(
            plan["subject_artifact_id"], machine_id="mission-hub",
        )
        rows: list[dict[str, Any]] = []
        material_concepts: list[dict[str, Any]] = []
        with Path(subject["uri"]).open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise SafetyError(f"training corpus line {line_no} is not JSON") from exc
                if not isinstance(row, dict) or not isinstance(row.get("prompt"), str) or not isinstance(row.get("completion"), str):
                    raise SafetyError(f"training corpus line {line_no} lacks prompt/completion text")
                if not row["prompt"].strip() or not row["completion"].strip():
                    raise SafetyError(f"training corpus line {line_no} contains empty teaching text")
                if len(row["completion"].encode("utf-8")) > self.bundle.training["max_completion_utf8_bytes"]:
                    raise SafetyError(f"training corpus line {line_no} exceeds the completion byte bound")
                if "concept" in row or "depends_on" in row:
                    if (
                        not isinstance(row.get("concept"), str)
                        or not row["concept"].strip()
                        or not isinstance(row.get("depends_on"), list)
                        or not all(isinstance(value, str) and value.strip() for value in row["depends_on"])
                    ):
                        raise SafetyError(f"training corpus line {line_no} has invalid concept-order metadata")
                    material_concepts.append({
                        "concept": row["concept"], "depends_on": row["depends_on"],
                        "line": line_no,
                    })
                rows.append(row)
        if not rows or len(rows) > self.bundle.training["max_examples_per_session"]:
            raise SafetyError("training corpus example count is outside configured bounds")
        if len(rows) != prospective["parameters"]["max_examples"]:
            raise SafetyError("training max_examples must equal the certified corpus row count")
        declared = prospective["training_session"]["ordered_concepts"]
        observed = [
            {"concept": item["concept"], "depends_on": item["depends_on"]}
            for item in material_concepts
        ]
        if observed != declared:
            raise SafetyError(
                "training corpus concept sequence does not exactly match the declared dependency-order list"
            )
        require_lesson_material(rows, self.bundle.identity_policy)
        return {
            "format": "prompt_completion_jsonl", "example_order": "declared",
            "row_count": len(rows), "subject_sha256": subject["sha256"],
            "concept_row_count": len(material_concepts),
            "concept_sequence_sha256": content_hash(material_concepts),
            "identity_and_lesson_policy": "passed",
        }

    def _campaign_contract(self, campaign_id: str) -> dict[str, Any]:
        with self.store._connect() as db:
            row = db.execute("SELECT metadata_json FROM campaigns WHERE id=?", (campaign_id,)).fetchone()
        if row is None:
            raise SafetyError(f"campaign does not exist: {campaign_id}")
        metadata = json.loads(row[0])
        contract = metadata.get("campaign_contract")
        if not isinstance(contract, dict):
            raise SafetyError("campaign lacks a training-purpose contract")
        return contract

    def retrieve_artifact(self, artifact_id: str, *, machine_id: str, actor: str) -> dict[str, Any]:
        self._require_active_config()
        artifact = self.store.artifact_at(artifact_id, machine_id=machine_id)
        deployment = self.store.active_deployment(machine_id)
        uri = SSHDispatcher(self.bundle).get_artifact(machine_id, deployment, artifact)
        self.store.record_artifact_location(
            self.bundle, artifact_id, machine_id="mission-hub", uri=uri,
            event_type="artifact.retrieved", actor=actor,
        )
        return self.store.artifact_at(artifact_id, machine_id="mission-hub")

    def _require_active_config(self) -> None:
        active = self.store.active_config()
        if active["sha256"] != self.bundle.sha256:
            raise ConflictError("loaded configuration is not the active configuration")
