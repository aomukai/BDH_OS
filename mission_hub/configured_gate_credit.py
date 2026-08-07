"""Reconcile the bounded, paired Campaign 34 gate-credit experiment."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .campaign_contract import validate_campaign_contract
from .config import ConfigBundle
from .errors import NotFoundError, SafetyError
from .lesson_policy import policy_sha256
from .service import MissionHubService
from .store import MissionHubStore


SCHEMA_VERSION = "ninereeds_gate_credit_campaign_v1"


class ConfiguredGateCreditCampaign:
    def __init__(
        self, store: MissionHubStore, bundle: ConfigBundle, *, repo_root: Path,
        specification_path: Path,
    ) -> None:
        self.store = store
        self.bundle = bundle
        self.repo_root = repo_root.resolve()
        self.path = specification_path.resolve()
        self.value = json.loads(self.path.read_text(encoding="utf-8"))
        self.service = MissionHubService(store, bundle)
        self._validate()

    def _validate(self) -> None:
        if self.value.get("schema_version") != SCHEMA_VERSION:
            raise SafetyError("unsupported gate-credit campaign specification")
        campaign = self.value.get("campaign", {})
        contract = validate_campaign_contract(
            campaign.get("contract"), self.bundle.campaign_modes,
        )
        if campaign.get("state") != "active" or contract["mode"] != "evolutionary":
            raise SafetyError("gate-credit Phase 1 requires an active paired evolutionary contract")
        branches = set(contract["branches"])
        diagnostics = self.value.get("branch_diagnostics", {})
        if set(diagnostics) != branches or len(branches) != 2:
            raise SafetyError("gate-credit Phase 1 requires exactly two configured branches")
        enabled = sorted(bool(value.get("enabled")) for value in diagnostics.values())
        if enabled != [False, True]:
            raise SafetyError("gate-credit Phase 1 requires one control and one observed branch")
        for value in diagnostics.values():
            if set(value) != {"enabled", "log_every_n_steps", "max_sampled_steps"}:
                raise SafetyError("gate-credit branch has an unknown diagnostic control")
        authorization = self.value.get("authorization", {})
        if authorization != {
            "exact_workflow_reviewed": True,
            "allow_weight_updates": True,
            "allow_checkpoint_promotion": False,
            "allow_automatic_branch_ranking": False,
            "phase2_or_local_rule_authorized": False,
        }:
            raise SafetyError("gate-credit authorization exceeds observational Phase 1")
        lesson = self.value.get("ordered_lesson", {})
        if (
            lesson.get("order_policy") != "declared_only"
            or lesson.get("shuffle_allowed") is not False
            or not isinstance(lesson.get("ordered_concepts"), list)
            or not lesson["ordered_concepts"]
        ):
            raise SafetyError("gate-credit lesson violates immutable order")

    def reconcile(
        self, *, actor: str, authorize_branches: list[str] | None = None,
    ) -> dict[str, Any]:
        parent = self._parent()
        corpus_path = self._path(self.value["ordered_lesson"]["path"])
        rows = [json.loads(line) for line in corpus_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        lesson = self.value["ordered_lesson"]
        if len(rows) != lesson["row_count"]:
            raise SafetyError("gate-credit lesson row count changed")
        observed = [
            {"concept": row["concept"], "depends_on": row["depends_on"]}
            for row in rows if "concept" in row or "depends_on" in row
        ]
        if observed != lesson["ordered_concepts"]:
            raise SafetyError("gate-credit lesson concept order changed")
        corpus = self.service.ingest_artifact(
            kind="corpus", source_path=str(corpus_path), lifecycle="candidate",
            manifest={
                "schema_version": "ninereeds_ordered_training_corpus_v1",
                "campaign_id": self.value["campaign"]["id"],
                "row_count": len(rows), "ordered_concepts": observed,
                "order_policy": "declared_only", "shuffle_allowed": False,
                "dependency_order_required": True,
                "identity_policy_sha256": policy_sha256(self.bundle.identity_policy),
                "experiment_scope": "gate_credit_phase1_paired_smoke",
            }, actor=actor,
        )
        suite_path = self._path(self.value["evaluation_suite_path"])
        suite_value = json.loads(suite_path.read_text(encoding="utf-8"))
        suite = self.service.ingest_artifact(
            kind="evaluation_suite", source_path=str(suite_path), lifecycle="candidate",
            manifest={
                "schema_version": "ninereeds_cortex_eval_suite_artifact_v1",
                "suite_id": suite_value["suite_id"],
                "case_count": len(suite_value["cases"]),
                "evaluation_basis": ["behavioral_chat", "mri_activation"],
                "loss_role": "telemetry_only",
            }, actor=actor,
        )
        campaign = self.value["campaign"]
        self.store.create_campaign(
            campaign_id=campaign["id"], name=campaign["name"],
            objective=campaign["objective"], state=campaign["state"], actor=actor,
            metadata={
                "campaign_contract": campaign["contract"],
                "starting_checkpoint_artifact_id": parent["id"],
                "parent_selection": self.value["parent"]["selection"],
                "configured_campaign_path": str(self.path.relative_to(self.repo_root)),
                "phase_scope": "observational_gate_credit_only",
                "phase2_or_local_rule_authorized": False,
            },
        )
        workflows = []
        for branch in authorize_branches or []:
            if branch not in self.value["branch_diagnostics"]:
                raise SafetyError(f"unknown gate-credit branch: {branch}")
            parameters = dict(self.value["paired_parameters"])
            parameters["gate_credit_diagnostics"] = self.value["branch_diagnostics"][branch]
            workflows.append(self.store.create_cortex_workflow(
                self.bundle, {
                    "campaign_id": campaign["id"], "branch_id": branch,
                    "starting_checkpoint_artifact_id": parent["id"],
                    "evaluation_suite_artifact_id": suite["id"],
                    "architecture": "lfm2_5_encoder_230m_frozen__ninereeds_1_2b__lfm2_5_230m_frozen",
                    "identity_scope": "excluded",
                    "sessions": [{
                        "id": f"campaign34-{branch}-smoke-01",
                        "corpus_artifact_id": corpus["id"],
                        "ordered_concepts": lesson["ordered_concepts"],
                        "parameters": parameters,
                    }],
                    "evaluation_parameters": self.value["evaluation_parameters"],
                    "authorization": {
                        key: self.value["authorization"][key]
                        for key in (
                            "exact_workflow_reviewed", "allow_weight_updates",
                            "allow_checkpoint_promotion", "allow_automatic_branch_ranking",
                        )
                    },
                }, actor=actor,
            ))
        return {
            "campaign_id": campaign["id"], "parent_artifact_id": parent["id"],
            "corpus_artifact_id": corpus["id"], "evaluation_suite_artifact_id": suite["id"],
            "workflows": workflows,
        }

    def _parent(self) -> dict[str, Any]:
        expected = self.value["parent"]
        with self.store._connect() as db:
            row = db.execute(
                "SELECT * FROM artifacts WHERE id=? AND sha256=? AND kind='checkpoint' AND lifecycle!='deleted'",
                (expected["artifact_id"], expected["sha256"]),
            ).fetchone()
        if row is None:
            raise NotFoundError("configured gate-credit parent checkpoint is unavailable")
        return dict(row)

    def _path(self, relative: str) -> Path:
        path = (self.repo_root / relative).resolve()
        try:
            path.relative_to(self.repo_root)
        except ValueError as exc:
            raise SafetyError("configured gate-credit path escapes the repository") from exc
        if not path.is_file():
            raise NotFoundError(str(path))
        return path
