"""Reconcile a reviewed, file-configured Cortex campaign into Mission Hub."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .campaign_contract import validate_campaign_contract
from .config import ConfigBundle
from .errors import NotFoundError, SafetyError
from .jsonutil import content_hash
from .lesson_policy import policy_sha256
from .service import MissionHubService
from .store import MissionHubStore


CONFIG_SCHEMA = "ninereeds_configured_cortex_campaign_v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


class ConfiguredCortexCampaign:
    """Content-reconcile one explicit campaign recipe; never starts the pipeline."""

    def __init__(
        self, store: MissionHubStore, bundle: ConfigBundle, *, repo_root: Path,
        specification_path: Path,
    ):
        self.store = store
        self.bundle = bundle
        self.repo_root = repo_root.resolve()
        self.path = specification_path.resolve()
        try:
            self.path.relative_to(self.repo_root / "config" / "mission_hub" / "campaigns")
        except ValueError as exc:
            raise SafetyError("configured campaign must live under config/mission_hub/campaigns") from exc
        self.value = json.loads(self.path.read_text(encoding="utf-8"))
        self._validate()
        self.service = MissionHubService(store, bundle)

    def _validate(self) -> None:
        value = self.value
        if value.get("schema_version") != CONFIG_SCHEMA:
            raise SafetyError("unsupported configured Cortex campaign")
        campaign = value.get("campaign")
        if not isinstance(campaign, dict) or campaign.get("state") != "active":
            raise SafetyError("configured Cortex campaign must declare an active campaign")
        validate_campaign_contract(campaign.get("contract"), self.bundle.campaign_modes)
        baseline = value.get("baseline", {})
        baseline_path = Path(str(baseline.get("trainbox_path", "")))
        if (
            not baseline_path.is_absolute()
            or not isinstance(baseline.get("sha256"), str)
            or len(baseline["sha256"]) != 64
            or not isinstance(baseline.get("byte_size"), int)
            or baseline["byte_size"] < 1
        ):
            raise SafetyError("configured campaign baseline identity is incomplete")
        branches = value.get("new_branches")
        if not isinstance(branches, dict) or set(branches) - set(campaign["contract"]["branches"]):
            raise SafetyError("configured material names an undeclared campaign branch")
        defaults = value.get("workflow_defaults", {})
        if defaults.get("identity_scope") not in {"excluded", "identity_and_integrity"}:
            raise SafetyError("configured workflow has no valid identity scope")
        authorization = defaults.get("authorization")
        if authorization != {
            "exact_workflow_reviewed": True,
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_automatic_branch_ranking": False,
        }:
            raise SafetyError("configured campaign authorization exceeds an exact non-promoting workflow")

    def register_local_artifacts(self, *, actor: str) -> dict[str, Any]:
        """Ingest exact suite, historical evidence, inventory, and branch bytes."""
        suite_path = self._path(self.value["evaluation_suite_path"])
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        if suite.get("schema_version") != "ninereeds_cortex_eval_suite_v1" or not suite.get("cases"):
            raise SafetyError("configured evaluation suite is invalid")
        suite_artifact = self.service.ingest_artifact(
            kind="evaluation_suite", source_path=str(suite_path), lifecycle="candidate",
            manifest={
                "schema_version": "ninereeds_cortex_eval_suite_artifact_v1",
                "suite_id": suite["suite_id"], "case_count": len(suite["cases"]),
                "evaluation_basis": ["behavioral_chat", "mri_activation"],
                "loss_role": "telemetry_only",
            }, actor=actor,
        )
        historical: dict[str, str] = {}
        for branch_id, relative in self.value["historical_branch_evidence"].items():
            path = self._path(relative)
            report = json.loads(path.read_text(encoding="utf-8"))
            self._require_historical_evaluation(report, branch_id)
            artifact = self.service.ingest_artifact(
                kind="evaluation_report", source_path=str(path), lifecycle="observed",
                manifest={
                    "schema_version": "ninereeds_historical_evaluation_evidence_v1",
                    "legacy_campaign_id": report["campaign_id"], "branch_id": branch_id,
                    "candidate_sha256": report["candidate"]["checkpoint_sha256"],
                    "evaluation_basis_verified": ["behavioral_chat", "mri_activation"],
                    "loss_role_in_successor": "telemetry_only",
                    "historical_limitations": "preserved legacy trajectory; not reclassified as a clean recommissioned run",
                }, actor=actor,
            )
            historical[branch_id] = artifact["id"]

        inventory_path = self._path(self.value["knowledge_seed"]["inventory_path"])
        inventory = self.service.ingest_artifact(
            kind="corpus_manifest", source_path=str(inventory_path), lifecycle="observed",
            manifest={
                "schema_version": "ninereeds_ranked_concept_inventory_evidence_v1",
                "known_rank_first": self.value["knowledge_seed"]["known_rank_first"],
                "known_rank_last": self.value["knowledge_seed"]["known_rank_last"],
            }, actor=actor,
        )

        corpora: dict[str, list[dict[str, Any]]] = {}
        for branch_id, branch in self.value["new_branches"].items():
            directory = self._path(branch["material_directory"])
            manifest_path = directory / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if any((
                manifest.get("schema_version") != "ninereeds_ordered_corpus_variant_v1",
                manifest.get("order_policy") != "declared_only",
                manifest.get("shuffle_allowed") is not False,
                manifest.get("dependency_order_required") is not True,
                manifest.get("identity_policy_sha256") != policy_sha256(self.bundle.identity_policy),
            )):
                raise SafetyError(f"branch corpus manifest violates active training law: {branch_id}")
            rows: list[dict[str, Any]] = []
            for index, block in enumerate(manifest["blocks"], 1):
                path = directory / block["block"]
                if _sha256(path) != block["variant_sha256"] or block["row_count"] != 500:
                    raise SafetyError(f"branch corpus bytes do not match manifest: {branch_id}/{block['block']}")
                artifact = self.service.ingest_artifact(
                    kind="corpus", source_path=str(path), lifecycle="candidate",
                    manifest={
                        "schema_version": "ninereeds_ordered_training_corpus_v1",
                        "campaign_id": self.value["campaign"]["id"], "branch_id": branch_id,
                        "variant": branch["variant"], "variant_id": manifest["variant_id"],
                        "block_index": index, "row_count": block["row_count"],
                        "ordered_concepts": block["ordered_concepts"],
                        "order_policy": "declared_only", "shuffle_allowed": False,
                        "dependency_order_required": True,
                        "identity_policy_sha256": manifest["identity_policy_sha256"],
                        "source_manifest_sha256": manifest["source_manifest_sha256"],
                    }, actor=actor,
                )
                rows.append({
                    "artifact_id": artifact["id"], "block_index": index,
                    "ordered_concepts": block["ordered_concepts"], "row_count": block["row_count"],
                })
            corpora[branch_id] = rows
        return {
            "evaluation_suite_artifact_id": suite_artifact["id"],
            "historical_branch_evidence": historical,
            "inventory_artifact_id": inventory["id"], "corpora": corpora,
        }

    def reconcile(
        self, *, actor: str, authorize_branches: list[str] | None = None,
    ) -> dict[str, Any]:
        """Bind artifacts, baseline knowledge, campaign, and selected workflows."""
        artifacts = self.register_local_artifacts(actor=actor)
        baseline = self._baseline_artifact()
        seed_id = self.value["knowledge_seed"]["reconciliation_campaign_id"]
        seed_contract = {
            "schema_version": "ninereeds_campaign_contract_v1", "mode": "advancement",
            "development_stage": "historical baseline knowledge reconciliation",
            "purpose": "Record the concept inventory evidenced as known before Campaign 33 without changing checkpoint bytes.",
            "success_criteria": ["Ranks 1 through 500 are attached to the exact certified baseline."],
            "failure_criteria": ["The inventory, checkpoint hash, or rank bounds do not match preserved evidence."],
            "expected_regressions": [], "branches": [], "merge_sources": [],
            "target_capabilities": ["grep-friendly baseline knowledge provenance"],
            "bootstrap_milestones": [], "hypothesis": "", "observations_sought": [],
        }
        self.store.create_campaign(
            campaign_id=seed_id, name="Campaign 33 baseline knowledge reconciliation",
            objective=seed_contract["purpose"], metadata={"campaign_contract": seed_contract},
            state="closed", actor=actor,
        )
        concepts = self._known_concepts()
        self.store.append_checkpoint_knowledge(
            checkpoint_artifact_id=baseline["id"], parent_checkpoint_artifact_id=None,
            campaign_id=seed_id, session_id="known-ranks-0001-0500",
            concepts=concepts,
            evidence=[artifacts["inventory_artifact_id"], f"sha256:{self.value['baseline']['sha256']}"],
            actor=actor,
        )
        configured_sha = _sha256(self.path)
        campaign = self.value["campaign"]
        metadata = {
            "schema_version": "ninereeds_configured_campaign_reconciliation_v1",
            "campaign_contract": campaign["contract"],
            "starting_checkpoint_artifact_id": baseline["id"],
            "completed_branch_evidence": {
                branch: [artifact_id]
                for branch, artifact_id in artifacts["historical_branch_evidence"].items()
            },
            "configured_campaign_path": str(self.path.relative_to(self.repo_root)),
            "configured_campaign_sha256": configured_sha,
            "baseline_knowledge_count": len(concepts),
            "historical_evidence_limitations": [
                "Branch 1 terminal weights are unavailable; its preserved chat/MRI report remains evidence.",
                "Branch 2 contains historically invalid intermediate repairs and is not treated as a clean counterpart to branches 3 and 4.",
            ],
        }
        self.store.create_campaign(
            campaign_id=campaign["id"], name=campaign["name"], objective=campaign["objective"],
            metadata=metadata, state=campaign["state"], actor=actor,
        )
        workflows = []
        for branch_id in authorize_branches or []:
            if branch_id not in artifacts["corpora"]:
                raise SafetyError(f"cannot authorize an unconfigured branch: {branch_id}")
            workflows.append(self.store.create_cortex_workflow(
                self.bundle,
                self.workflow_specification(branch_id, artifacts=artifacts, baseline_id=baseline["id"]),
                actor=actor,
            ))
        return {"campaign_id": campaign["id"], "baseline_artifact_id": baseline["id"], **artifacts, "workflows": workflows}

    def create_validation_jobs(self, branch_id: str, *, actor: str) -> list[dict[str, Any]]:
        """Place and queue exact read-only corpus validation for one branch."""
        artifacts = self.register_local_artifacts(actor=actor)
        if branch_id not in artifacts["corpora"]:
            raise SafetyError(f"cannot validate an unconfigured branch: {branch_id}")
        jobs = []
        for block in artifacts["corpora"][branch_id]:
            try:
                self.store.artifact_at(block["artifact_id"], machine_id="trainbox")
            except NotFoundError:
                self.service.materialize_artifact(
                    block["artifact_id"], machine_id="trainbox", actor=actor,
                )
            jobs.append(self.store.create_job(
                self.bundle, job_type="corpus.validate",
                input_payload={
                    "corpus_artifact_id": block["artifact_id"],
                    "expected_rows": block["row_count"],
                    "identity_scope": self.value["workflow_defaults"]["identity_scope"],
                    "ordered_concepts": block["ordered_concepts"],
                },
                idempotency_key=(
                    f"configured-campaign:{self.value['campaign']['id']}:{branch_id}:"
                    f"block-{block['block_index']:02d}:validate"
                ),
                created_by=actor, campaign_id=None,
                requested_machine_id="trainbox", approved=True,
            ))
        return jobs

    def workflow_specification(
        self, branch_id: str, *, artifacts: dict[str, Any], baseline_id: str,
    ) -> dict[str, Any]:
        defaults = self.value["workflow_defaults"]
        sessions = []
        for block in artifacts["corpora"][branch_id]:
            parameters = dict(defaults["training_parameters"])
            parameters["max_examples"] = block["row_count"]
            sessions.append({
                "id": f"{branch_id}-block-{block['block_index']:02d}",
                "corpus_artifact_id": block["artifact_id"],
                "ordered_concepts": block["ordered_concepts"], "parameters": parameters,
            })
        return {
            "campaign_id": self.value["campaign"]["id"], "branch_id": branch_id,
            "starting_checkpoint_artifact_id": baseline_id,
            "evaluation_suite_artifact_id": artifacts["evaluation_suite_artifact_id"],
            "architecture": self.value["architecture"],
            "identity_scope": defaults["identity_scope"], "sessions": sessions,
            "evaluation_parameters": defaults["evaluation_parameters"],
            "authorization": defaults["authorization"],
        }

    def _baseline_artifact(self) -> dict[str, Any]:
        with self.store._connect() as db:
            row = db.execute(
                "SELECT * FROM artifacts WHERE kind='checkpoint' AND sha256=? AND lifecycle!='deleted'",
                (self.value["baseline"]["sha256"],),
            ).fetchone()
        if row is None:
            raise NotFoundError("configured baseline has not completed byte certification")
        return dict(row)

    def _known_concepts(self) -> list[str]:
        seed = self.value["knowledge_seed"]
        lines = self._path(seed["inventory_path"]).read_text(encoding="utf-8").splitlines()
        selected = lines[seed["known_rank_first"] - 1:seed["known_rank_last"]]
        concepts = [json.loads(line)["concept_id"] for line in selected]
        if len(concepts) != seed["known_rank_last"] - seed["known_rank_first"] + 1 or len(set(concepts)) != len(concepts):
            raise SafetyError("baseline concept inventory rank slice is incomplete or duplicated")
        return concepts

    def _path(self, relative: str) -> Path:
        path = (self.repo_root / relative).resolve()
        try:
            path.relative_to(self.repo_root)
        except ValueError as exc:
            raise SafetyError("configured campaign path escapes the repository") from exc
        if not path.is_file() and not path.is_dir():
            raise NotFoundError(str(path))
        return path

    @staticmethod
    def _require_historical_evaluation(report: dict[str, Any], branch_id: str) -> None:
        try:
            candidate = report["candidate"]
            certificate = report["certificate"]
            cases = candidate["cases"]
            scan = candidate["scan"]
            exact_hash = candidate["checkpoint_sha256"] == certificate["candidate_sha256"]
            complete = bool(cases) and bool(scan["activation_health"]) and bool(scan["representation_health"])
        except (KeyError, TypeError) as exc:
            raise SafetyError(f"historical branch evidence lacks chat/MRI data: {branch_id}") from exc
        if not exact_hash or not complete:
            raise SafetyError(f"historical branch evidence is internally inconsistent: {branch_id}")
