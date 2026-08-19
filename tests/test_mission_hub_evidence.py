from __future__ import annotations

import json
from pathlib import Path

from mission_hub.evidence import EvidenceArchive
from mission_hub.store import MissionHubStore
from mission_hub.config import load_config_bundle


REPO = Path(__file__).resolve().parents[1]


def test_evidence_is_content_addressed_verified_and_idempotent(tmp_path: Path) -> None:
    source_root = tmp_path / "legacy" / "plans"
    source_root.mkdir(parents=True)
    (source_root / "plan-1.json").write_text(json.dumps({"id": "plan-1", "kind": "cortex_block"}), encoding="utf-8")
    source = {
        "id": "test-source",
        "machine_id": "mission-hub",
        "source_kind": "legacy_control_ledger",
        "path": str(source_root.parent),
        "required": True,
        "hash_content": True,
        "copy_bytes": True,
        "import_json": True,
        "max_import_bytes": 1024,
        "include_suffixes": [".json"],
        "exclude_names": [],
    }
    archive = EvidenceArchive(tmp_path / "evidence")
    manifest, records = archive.capture(source)
    assert archive.verify(manifest) == []
    assert records[0]["legacy_id"] == "plan-1"
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    first = store.preserve_evidence(manifest, records, actor="test")
    second = store.preserve_evidence(manifest, records, actor="test")
    assert first == second
    assert len(store.list_rows("evidence_sources")) == 1
