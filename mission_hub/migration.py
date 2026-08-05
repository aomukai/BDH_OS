"""Explicit, idempotent migration from preserved legacy evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import ConfigBundle
from .errors import EvidenceError, NotFoundError
from .evidence import EvidenceArchive
from .store import MissionHubStore


class LegacyMigrator:
    def __init__(self, store: MissionHubStore, bundle: ConfigBundle, archive: EvidenceArchive):
        self.store = store
        self.bundle = bundle
        self.archive = archive

    def migrate_current_campaign(self, *, actor: str) -> dict[str, Any]:
        policy = self.bundle.migration
        evidence = self.store.latest_evidence(policy["campaign_source_id"])
        manifest, _ = self.archive.load_capture(evidence["snapshot_sha256"])
        registry_entry = next((entry for entry in manifest["files"] if entry["path"] == "campaign_registry.json"), None)
        if registry_entry is None or not registry_entry.get("blob_uri"):
            raise EvidenceError("campaign registry was not copied into the evidence archive")
        registry_path = self.archive.root / registry_entry["blob_uri"]
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        campaigns = registry.get("campaigns", []) if isinstance(registry, dict) else []
        legacy = next(
            (item for item in campaigns if isinstance(item, dict) and item.get("number") == policy["active_legacy_campaign_number"]),
            None,
        )
        if legacy is None:
            raise NotFoundError(f"campaign {policy['active_legacy_campaign_number']} not found in preserved registry")
        campaign_id = str(legacy["campaign_id"])
        metadata = {
            "schema_version": "ninereeds_legacy_campaign_migration_v1",
            "legacy_campaign_number": legacy["number"],
            "legacy_status": legacy.get("status"),
            "legacy_created_at": legacy.get("created_at"),
            "legacy_updated_at": legacy.get("updated_at"),
            "legacy_artifact_root": legacy.get("artifact_root"),
            "evidence_source_id": evidence["id"],
            "evidence_snapshot_sha256": evidence["snapshot_sha256"],
            "resumption_allowed": policy["resumption_allowed"],
            "stale_legacy_plan_id": policy["stale_legacy_plan_id"],
            "freeze_reason": policy["freeze_reason"],
        }
        self.store.create_campaign(
            campaign_id=campaign_id,
            name=legacy.get("display_name") or campaign_id,
            objective=legacy.get("objective") or "",
            metadata=metadata,
            actor=actor,
            state=policy["import_state"],
        )
        decision_id = f"decision-legacy-freeze-{campaign_id}"
        self.store.record_decision(
            decision_id=decision_id,
            campaign_id=campaign_id,
            kind="legacy_freeze",
            payload={
                "state": policy["import_state"],
                "resumption_allowed": policy["resumption_allowed"],
                "reason": policy["freeze_reason"],
                "stale_legacy_plan_id": policy["stale_legacy_plan_id"],
            },
            evidence=[evidence["id"]],
            actor=actor,
        )
        # Freezing legacy automation is an already-authorized migration safety
        # action, not a proposal to resume or mutate the old campaign.
        self.store.transition_decision(decision_id, target="approved", actor=actor)
        self.store.transition_decision(decision_id, target="executed", actor=actor)
        return {"campaign_id": campaign_id, "state": policy["import_state"], "decision_id": decision_id, "evidence_id": evidence["id"]}
