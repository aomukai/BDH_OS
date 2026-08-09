from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")

from mission_hub.handlers.visual import VisualFeaturesFinalizeHandler


def _artifact(path: Path, artifact_id: str, kind: str, manifest: dict) -> dict:
    raw = path.read_bytes()
    return {
        "id": artifact_id, "kind": kind, "uri": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(), "byte_size": len(raw),
        "manifest": manifest,
    }


def test_feature_fan_in_preserves_pack_order_and_exact_coverage(tmp_path: Path) -> None:
    pack_path = tmp_path / "pack.json"
    pack_path.write_text("{}")
    pack = _artifact(pack_path, "pack", "visual_pack", {
        "status": "accepted", "items": [
            {"asset_sha256": "b" * 64}, {"asset_sha256": "a" * 64},
        ],
    })
    shards = []
    for index, digest in enumerate(("a" * 64, "b" * 64)):
        path = tmp_path / f"shard-{index}.npz"
        np.savez_compressed(
            path, asset_sha256=np.asarray([digest]),
            patch_0000=np.full((2, 3), index, dtype=np.float32),
            mask_0000=np.ones((2,), dtype=np.int64),
            shape_0000=np.asarray([1, 2], dtype=np.int64),
        )
        shards.append(_artifact(path, f"shard-{index}", "visual_features", {"asset_sha256": [digest]}))
    context = {
        "artifacts": [pack, *shards], "state_root": str(tmp_path / "state"),
        "artifact_roots": [str(tmp_path)], "run": {"id": "run-features"},
    }
    result = VisualFeaturesFinalizeHandler().execute(
        {"input_artifact_ids": ["pack", "shard-0", "shard-1"], "specification": {}, "limits": {}},
        context,
    )
    output = result["artifacts"][0]
    assert output["manifest"]["asset_sha256"] == ["b" * 64, "a" * 64]
    assert output["manifest"]["source_shard_artifact_ids"] == ["shard-1", "shard-0"]
    with np.load(output["uri"], allow_pickle=False) as combined:
        assert combined["asset_sha256"].tolist() == ["b" * 64, "a" * 64]
        assert combined["patch_0000"].tolist() == [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]
        assert combined["patch_0001"].tolist() == [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
