from __future__ import annotations

import json
from pathlib import Path

from mission_hub.config import load_config_bundle
from mission_hub.readiness import readiness_report


REPO = Path(__file__).resolve().parents[1]


class CommissionedStore:
    def __init__(self, bundle):
        self.bundle = bundle

    def integrity_report(self):
        return {
            "sqlite_integrity": "ok",
            "foreign_key_errors": [],
            "event_chain_ok": True,
            "event_count": 1,
        }

    def active_config(self):
        return {"sha256": self.bundle.sha256}

    def list_rows(self, entity, *, limit):
        if entity == "evidence_sources":
            return [
                {"manifest_json": json.dumps({"source_id": source["id"], "hash_content": True})}
                for source in self.bundle.evidence_sources.values()
                if source["required"]
            ]
        if entity == "campaigns":
            return [{"id": "play-word-evolution-0501-2000-v1", "state": "legacy_stopped"}]
        if entity == "deployments":
            return [
                {"role": "mission_hub", "status": "active"},
                {"role": "trainbox", "status": "active"},
            ]
        if entity == "jobs":
            return [{"job_type": "system.healthcheck", "status": "succeeded"}]
        raise AssertionError(entity)


def test_commissioning_remains_ready_after_maintenance_is_restored(monkeypatch) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    assert bundle.machines["trainbox"]["maintenance_mode"] is True
    monkeypatch.setattr(
        "mission_hub.readiness.DeploymentBuilder.source_manifest",
        lambda self, role_id: {"git_clean": True},
    )

    report = readiness_report(CommissionedStore(bundle), bundle, repo_root=REPO)

    assert report["backend_ready"] is True
    assert report["commissioning_ready"] is True
    assert report["training_restart_ready"] is False
    maintenance = next(item for item in report["checks"] if item["id"] == "trainbox_out_of_maintenance")
    assert maintenance["gate"] == "training_restart"
    assert maintenance["passed"] is False
