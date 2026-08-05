from __future__ import annotations

from pathlib import Path
import tarfile

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.deployment import DeploymentBuilder
from mission_hub.release import verify_release
from mission_hub.errors import ProtocolError


REPO = Path(__file__).resolve().parents[1]


def test_role_manifests_enforce_machine_separation(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    builder = DeploymentBuilder(REPO, bundle)
    mission = builder.source_manifest("mission-hub-release")
    training = builder.source_manifest("trainbox-agent-release")
    mission_paths = {entry["path"] for entry in mission["files"]}
    training_paths = {entry["path"] for entry in training["files"]}
    assert "mission_hub/store.py" in mission_paths
    assert "mission_hub/api.py" in mission_paths
    assert "mission_hub/store.py" not in training_paths
    assert "mission_hub/evidence.py" not in training_paths
    assert "mission_hub/api.py" not in training_paths
    assert "mission_hub/daemon.py" not in training_paths
    assert "mission_hub/artifacts.py" in training_paths
    assert "mission_hub/handlers/commissioning.py" in training_paths
    assert "schemas/mission_hub/jobs/system.gpu_probe.input.schema.json" in training_paths
    assert "bdh.py" in training_paths
    assert "cortex/student.py" in training_paths
    assert "training/optim/__init__.py" in training_paths
    assert "training/pipeline/cortex/evaluation.py" in training_paths
    assert "training/pipeline/cortex/evolution.py" not in training_paths
    assert "training/pipeline/cortex/retention.py" not in training_paths
    assert "training/pipeline/cortex/evolution_goal.json" not in training_paths
    assert "training/pipeline/cortex/retention_policy.json" not in training_paths
    assert not any(path.startswith(("lab/", "training_data/", "archive/", "docs/")) for path in training_paths)

    deployment = builder.deployment_manifest(
        "trainbox-agent-release",
        machine_id="trainbox",
        config_snapshot_id="cfg-test",
        environment={
            "hostname": "ninereeds",
            "python_executable": "/home/aomukai/.venvs/ninereeds-cortex/bin/python",
            "python_site_paths": ["/home/aomukai/.unsloth/studio/unsloth_studio/lib/python3.13/site-packages"],
            "packages": {"torch": "test"},
        },
    )
    deployment["id"] = "dep-test"
    first = builder.build_archive(deployment, tmp_path / "first.tar.gz")
    second = builder.build_archive(deployment, tmp_path / "second.tar.gz")
    assert first["sha256"] == second["sha256"]
    with tarfile.open(first["path"], "r:gz") as archive:
        names = set(archive.getnames())
    assert "RELEASE-MANIFEST.json" in names
    assert "bdh.py" in names
    assert "mission_hub/agent_remote.py" in names
    assert "mission_hub/store.py" not in names
    extract = tmp_path / "extract"
    extract.mkdir()
    with tarfile.open(first["path"], "r:gz") as archive:
        archive.extractall(extract, filter="data")
    assert verify_release(deployment, extract)["verified_files"] == len(deployment["source"]["files"])
    (extract / "mission_hub" / "agent.py").write_text("tampered\n", encoding="utf-8")
    with pytest.raises(ProtocolError, match="verification failed"):
        verify_release(deployment, extract)
