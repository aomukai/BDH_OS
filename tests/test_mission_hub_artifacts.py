from __future__ import annotations

from io import BytesIO, TextIOWrapper
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from mission_hub.artifacts import ArtifactFiles, sha256_file
from mission_hub import agent_cli, agent_remote
from mission_hub.config import load_config_bundle
from mission_hub.errors import ProtocolError, SafetyError
from mission_hub.handlers.commissioning import ArtifactRoundtripHandler, BoundedGPUProbeHandler
from mission_hub.jsonutil import content_hash
from mission_hub.service import MissionHubService
from mission_hub.schema import load_schema, validate
from mission_hub.store import MissionHubStore
from mission_hub.transport import SSHDispatcher


REPO = Path(__file__).resolve().parents[1]


def configured_bundle(tmp_path: Path):
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    for machine_id in ("mission-hub", "trainbox"):
        root = tmp_path / machine_id
        bundle.machines[machine_id]["state_root"] = str(root / "state")
        bundle.machines[machine_id]["artifact_roots"] = [str(root / "input")]
    return bundle


def test_content_addressed_ingest_receive_and_retransmission(tmp_path: Path) -> None:
    bundle = configured_bundle(tmp_path)
    source_root = Path(bundle.machines["mission-hub"]["artifact_roots"][0])
    source_root.mkdir(parents=True)
    source = source_root / "payload.bin"
    payload = b"bounded-artifact-payload\n"
    source.write_bytes(payload)

    path, digest, byte_size = ArtifactFiles(bundle, "mission-hub").ingest(source)

    assert path.read_bytes() == payload
    assert digest == hashlib.sha256(payload).hexdigest()
    assert byte_size == len(payload)
    receiver = ArtifactFiles(bundle, "trainbox")
    received = receiver.receive(BytesIO(payload), sha256=digest, byte_size=len(payload))
    assert received.read_bytes() == payload
    assert receiver.receive(BytesIO(payload), sha256=digest, byte_size=len(payload)) == received


def test_artifact_receive_rejects_truncation_and_oversize(tmp_path: Path) -> None:
    bundle = configured_bundle(tmp_path)
    receiver = ArtifactFiles(bundle, "trainbox")
    digest = hashlib.sha256(b"complete").hexdigest()
    with pytest.raises(SafetyError, match="size"):
        receiver.receive(BytesIO(b"short"), sha256=digest, byte_size=len(b"complete"))
    with pytest.raises(SafetyError, match="limit"):
        receiver.receive(
            BytesIO(), sha256=hashlib.sha256(b"").hexdigest(),
            byte_size=bundle.base["artifacts"]["max_transfer_bytes"] + 1,
        )


def test_agent_cli_artifact_put_binds_config_deployment_and_hash(tmp_path: Path, monkeypatch, capsys) -> None:
    bundle = configured_bundle(tmp_path)
    payload = b"restricted-agent-put"
    digest = hashlib.sha256(payload).hexdigest()
    artifact_id = f"art-{content_hash({'kind': 'commissioning_input', 'sha256': digest})[:16]}"
    manifest = tmp_path / "RELEASE-MANIFEST.json"
    manifest.write_text(json.dumps({"id": "dep-test", "environment": {}}), encoding="utf-8")
    monkeypatch.setattr(agent_cli, "load_config_bundle", lambda path: bundle)
    monkeypatch.setattr(agent_cli, "verify_release", lambda deployment, root: {"verified_files": 1})
    monkeypatch.setattr(
        "sys.argv",
        [
            "ninereeds-agent", "--config", "unused", "--machine-id", "trainbox",
            "--deployment-manifest", str(manifest), "artifact-put", artifact_id,
            "commissioning_input", digest, str(len(payload)), bundle.sha256, "dep-test",
        ],
    )
    monkeypatch.setattr("sys.stdin", TextIOWrapper(BytesIO(payload), encoding="utf-8"))

    assert agent_cli.main() == 0

    response = json.loads(capsys.readouterr().out)
    assert response["artifact_id"] == artifact_id
    assert Path(response["uri"]).read_bytes() == payload


def test_forced_command_accepts_only_exact_artifact_grammar(monkeypatch) -> None:
    monkeypatch.setenv("NINEREEDS_AGENT_CONFIG", "/config")
    monkeypatch.setenv("NINEREEDS_AGENT_MACHINE_ID", "trainbox")
    monkeypatch.setenv("NINEREEDS_AGENT_DEPLOYMENT_MANIFEST", "/manifest")
    called = []
    monkeypatch.setattr(agent_remote, "agent_main", lambda: called.append(list(__import__("sys").argv)) or 0)
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", "artifact-put art-a kind " + "a" * 64 + " 1 cfg dep")
    assert agent_remote.main() == 0
    assert called[0][-7] == "artifact-put"
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", "artifact-put art-a kind " + "a" * 64 + " 1 cfg dep extra")
    assert agent_remote.main() == 2


def test_store_rejects_artifact_location_traversal(tmp_path: Path) -> None:
    bundle = configured_bundle(tmp_path)
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    root = Path(bundle.machines["mission-hub"]["state_root"])
    with pytest.raises(SafetyError, match="outside"):
        store.register_artifact(
            bundle,
            kind="commissioning_input",
            sha256="a" * 64,
            byte_size=1,
            lifecycle="observed",
            manifest={},
            producing_run_id=None,
            machine_id="mission-hub",
            uri=str(root / ".." / "escape.bin"),
            actor="test",
        )


def test_service_ingest_registers_verified_canonical_bytes(tmp_path: Path) -> None:
    bundle = configured_bundle(tmp_path)
    source_root = Path(bundle.machines["mission-hub"]["artifact_roots"][0])
    source_root.mkdir(parents=True)
    source = source_root / "input.txt"
    source.write_text("commissioning\n", encoding="utf-8")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")

    artifact = MissionHubService(store, bundle).ingest_artifact(
        kind="commissioning_input",
        source_path=str(source),
        lifecycle="observed",
        manifest={"purpose": "test"},
        actor="test",
    )

    assert Path(artifact["uri"]).read_bytes() == source.read_bytes()
    assert artifact["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert store.integrity_report()["event_chain_ok"] is True


def test_service_records_materialized_and_retrieved_locations(tmp_path: Path, monkeypatch) -> None:
    bundle = configured_bundle(tmp_path)
    source_root = Path(bundle.machines["mission-hub"]["artifact_roots"][0])
    source_root.mkdir(parents=True)
    source = source_root / "input.txt"
    source.write_text("location-events\n", encoding="utf-8")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    deployment_id = store.register_deployment(
        {
            "machine_id": "trainbox", "role": "trainbox", "release_id": "release-test",
            "source_sha256": "1" * 64, "environment_sha256": "2" * 64,
            "config_snapshot_id": config_id,
        },
        actor="test",
        activate=True,
    )
    service = MissionHubService(store, bundle)
    artifact = service.ingest_artifact(
        kind="commissioning_input", source_path=str(source), lifecycle="observed",
        manifest={}, actor="test",
    )
    remote_uri = str(Path(bundle.machines["trainbox"]["state_root"]) / "artifacts" / "objects" / artifact["sha256"][:2] / artifact["sha256"])
    monkeypatch.setattr(
        "mission_hub.service.SSHDispatcher.put_artifact",
        lambda self, machine_id, deployment, item: remote_uri,
    )

    remote = service.materialize_artifact(artifact["id"], machine_id="trainbox", actor="test")

    assert remote["uri"] == remote_uri
    assert store.active_deployment("trainbox")["id"] == deployment_id
    monkeypatch.setattr(
        "mission_hub.service.SSHDispatcher.get_artifact",
        lambda self, machine_id, deployment, item: artifact["uri"],
    )
    retrieved = service.retrieve_artifact(artifact["id"], machine_id="trainbox", actor="test")
    assert retrieved["uri"] == artifact["uri"]
    event_types = [row["event_type"] for row in store.list_rows("events", limit=100)]
    assert "artifact.materialized" in event_types
    assert "artifact.retrieved" in event_types


def test_restricted_transport_streams_put_and_get(tmp_path: Path) -> None:
    bundle = configured_bundle(tmp_path)
    source_root = Path(bundle.machines["mission-hub"]["artifact_roots"][0])
    source_root.mkdir(parents=True)
    source = source_root / "input.bin"
    payload = b"transport-roundtrip"
    source.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    artifact_id = f"art-{content_hash({'kind': 'commissioning_input', 'sha256': digest})[:16]}"
    artifact = {
        "id": artifact_id,
        "kind": "commissioning_input",
        "sha256": digest,
        "byte_size": len(payload),
        "uri": str(source),
    }
    deployment = {"id": "dep-test"}
    remote_uri = str(Path(bundle.machines["trainbox"]["state_root"]) / "artifacts" / "objects" / digest[:2] / digest)

    def put_runner(command, **kwargs):
        assert kwargs["stdin"].read() == payload
        response = {
            "ok": True, "artifact_id": artifact_id, "kind": "commissioning_input",
            "sha256": digest, "byte_size": len(payload), "uri": remote_uri,
            "config_sha256": bundle.sha256, "deployment_id": "dep-test",
        }
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(response).encode(), stderr=b"")

    assert SSHDispatcher(bundle, runner=put_runner).put_artifact("trainbox", deployment, artifact) == remote_uri

    remote_artifact = {**artifact, "uri": remote_uri}

    def get_runner(command, **kwargs):
        kwargs["stdout"].write(payload)
        return subprocess.CompletedProcess(command, 0, stdout=None, stderr=b"")

    local_uri = SSHDispatcher(bundle, runner=get_runner).get_artifact("trainbox", deployment, remote_artifact)
    assert Path(local_uri).read_bytes() == payload


def test_restricted_transport_rejects_receipt_path_traversal(tmp_path: Path) -> None:
    bundle = configured_bundle(tmp_path)
    source_root = Path(bundle.machines["mission-hub"]["artifact_roots"][0])
    source_root.mkdir(parents=True)
    source = source_root / "input.bin"
    source.write_bytes(b"x")
    digest = hashlib.sha256(b"x").hexdigest()
    artifact_id = f"art-{content_hash({'kind': 'commissioning_input', 'sha256': digest})[:16]}"
    artifact = {"id": artifact_id, "kind": "commissioning_input", "sha256": digest, "byte_size": 1, "uri": str(source)}

    def runner(command, **kwargs):
        bad_uri = str(Path(bundle.machines["trainbox"]["state_root"]) / ".." / "escape")
        response = {
            "ok": True, "artifact_id": artifact_id, "kind": "commissioning_input",
            "sha256": digest, "byte_size": 1, "uri": bad_uri,
            "config_sha256": bundle.sha256, "deployment_id": "dep-test",
        }
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(response).encode(), stderr=b"")

    with pytest.raises(ProtocolError, match="outside"):
        SSHDispatcher(bundle, runner=runner).put_artifact("trainbox", {"id": "dep-test"}, artifact)


def test_artifact_roundtrip_handler_emits_hashed_receipt(tmp_path: Path) -> None:
    payload = b"handler-input"
    source = tmp_path / "artifacts" / "input.bin"
    source.parent.mkdir()
    source.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    context = {
        "state_root": str(tmp_path / "state"),
        "artifact_roots": [str(source.parent)],
        "run": {"id": "run-test"},
        "deployment": {"id": "dep-test"},
        "commissioning_limits": {"max_artifact_input_bytes": 1024},
        "artifacts": [{
            "id": "art-input", "kind": "commissioning_input", "sha256": digest,
            "byte_size": len(payload), "uri": str(source), "lifecycle": "observed", "manifest": {},
        }],
    }

    output = ArtifactRoundtripHandler().execute({"input_artifact_id": "art-input"}, context)

    assert output["status"] == "succeeded"
    assert output["metrics"] == {"input_bytes": len(payload), "input_sha256": digest}
    receipt = output["artifacts"][0]
    assert receipt["kind"] == "commissioning_receipt"
    assert sha256_file(Path(receipt["uri"])) == receipt["sha256"]
    schema = load_schema(REPO, "schemas/mission_hub/jobs/system.artifact_roundtrip.output.schema.json")
    assert validate(output, schema) == []


def test_gpu_probe_refuses_configured_bound_before_loading_cuda(tmp_path: Path) -> None:
    context = {
        "commissioning_limits": {
            "gpu_max_devices": 1,
            "gpu_max_matrix_size": 64,
            "gpu_max_iterations": 2,
            "gpu_max_duration_seconds": 5,
            "gpu_max_allocated_bytes": 1024 * 1024,
            "gpu_max_start_temperature_c": 80,
        }
    }
    with pytest.raises(SafetyError, match="matrix"):
        BoundedGPUProbeHandler().execute(
            {"device_indices": [0], "matrix_size": 65, "iterations": 1, "duration_limit_seconds": 1, "seed": 1},
            context,
        )
